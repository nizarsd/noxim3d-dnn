# Noxim3D — NoC for DNN

SystemC-based cycle-accurate Network-on-Chip simulator (fork of Noxim), extended for 3D NoC
research comparing routing/selection policies under DNN-style traffic.

## Research focus (Stage 1)

Comparing two selection policies layered on odd-even balanced routing:
- **DP**: distributed selection unit using a multi-hop congestion cost-to-go field.
- **bufferlevel (BL)**: local heuristic based on immediate neighbour buffer occupancy.

DP's advantage appears at/above the congestion knee; below it, DP ≈ BL (sometimes
marginally worse). Key finding from the size series (Z=3): **peak DP benefit scales
with mesh diameter within a parity class, and X/Y parity governs past-knee behaviour**
— odd×odd meshes win through saturation, even×even meshes reverse just past the knee.

**See [FINDINGS.md](FINDINGS.md) for the full DP-vs-BL results, method, and open items.**
(The older `stage1-log.txt` is superseded by FINDINGS.md.)

## Traffic injection (Stage 2, in progress)

DNN trace generation (Stage 2 of the execution plan) surfaced a format mismatch: the
project proposal assumed a per-packet flit-level trace format, but the actual traffic
input mechanism ([`TGlobalTrafficTable`](TGlobalTrafficTable.cpp)) is a **statistical**
descriptor table — rows of `src dst pir por t_on t_off t_period` — consumed via
per-cycle Bernoulli draws in `TProcessingElement::txProcess` against a cumulative PIR,
not literal per-packet replay. Built-in `TRAFFIC_RANDOM` (uniform destination, global
PIR, whole-run only — not phase-switchable) is also available as a distribution
alongside `TRAFFIC_TABLE_BASED` ([`NoximDefs.h`](NoximDefs.h)).

### Two hard limits of the table mechanism (code-as-written)

1. **Packet size is never read from the table.** `canShot()` calls
   `packet.make(local_id, dst, now, getRandomSize())` — the profiled per-layer output
   volume cannot be expressed at any `pir`/window setting. The format has no size column.
2. **One destination per source per cycle.** `getCumulativePirPor()` picks a single dst
   by weighted random draw among rows active that cycle, so a source cannot fan out to
   two dsts simultaneously (e.g. a ResNet skip connection firing to both the next
   sequential tile and the merge tile).

Timing itself is *not* a blocker: a narrow window (`t_on=C-1, t_off=C+1, pir=1.0`) forces
near-deterministic single-shot firing at cycle C, with `t_period` = inference-pass length
for repeats.

### Three candidate approaches

- **(a) Statistical approximation** — DNN traffic as ordinary table rows. Lossy (no real
  size, no fan-out), but **zero simulator changes**.
- **(b-lite) Table + fixed packet size** — keep the whole table mechanism; change
  `canShot()` to read a new size column instead of `getRandomSize()` (~5 lines + parser
  field). Carries real per-layer size. Still approximate: `pir`×Bernoulli means *packet
  count* and *exact cycle* within the window remain random (total volume is an
  expectation, not exact), size is quantised to **flits** (profiled `comm_bytes` ÷ flit
  size, integer-rounded), and the one-dst-per-cycle limit still applies.
- **(b-full) Dependency-gated dataflow firing** — per-PE state machine: track required
  inputs, fire only once all have *actually arrived* in-sim, so congestion delays
  propagate downstream. The architecturally correct model for a layer DAG, and the only
  option where routing improvements show up in true end-to-end inference latency. Large
  `TProcessingElement` change.

### Model-by-model fit

| Model | Fit under (b-lite) | Notes |
|-------|--------------------|-------|
| VGG-16 | Full fit | Purely sequential, one src→one dst per layer; FC burst is just high `pir` over a window. No structural gap. |
| ResNet-50 | Mostly fits | Skip-connection fan-out served by weighted draw, not guaranteed simultaneous — OK for volume, imperfect for synchronised burst. |
| Transformer | Poor fit | Attention is all-to-all/collective in one window; b-lite scatters it as pairwise traffic. Needs `TRAFFIC_RANDOM` or ring/tree collective rows — a separate modelling path. |

**(b-full) fixes the CNN cases (ResNet, VGG) exactly, but does *not* dissolve the
transformer problem** — attention is a collective, not a DAG dependency, so it still needs
explicit all-to-all edges (O(N²) rows) or a collective primitive either way.

### Current lean (not yet committed)

**(b-lite) for CNNs now** — unblocks Stage 2/3 for ResNet-50 + VGG-16 at ~5 lines of
change, consistent with Stage 2's "get something running" goal. **Defer (b-full)** until
Stage 5/6 evidence shows arrival-coupled timing is actually needed to demonstrate the RL
agent's benefit. **Transformer handled separately** as a synthetic pattern regardless of
which option is chosen.

Not yet implemented — logged here before Stage 2 code is written.

## Correctness & performance

- **odd-even-balanced + DP legality** (`a698e05`): DP's turn legality
  ([`can_turnOddEvenBalanced`](DPNode.cpp) + `*_DPStrict` helpers) mirrors the
  router's `routingOddEvenBalanced` but source-independent (DP has no packet-source
  state); correct 3D vertical exclusivity; falls back to 2D odd-even when `Z==1`.
- **DP perf optimizations** (this session, behaviour-preserving / bit-identical):
  gated unused NoP output, and cached the topology-static DP turn-legality.
- **Parallel sweeps:** [`noximrun_buffer_sweep_parallel.bash`](noximrun_buffer_sweep_parallel.bash)
  (`JOBS` knob; deterministic → identical to sequential).
- **Limit:** `DPSIZE = 260` caps mesh size; > 260 nodes overflow DP arrays (raise & rebuild).
- **DP settle window** (`-dpsettle N`, runtime; default 0): settle = N·dp_pass. Finding —
  `settle=0` (continuous reconvergence, freshest field) is best-or-tied; more settle only
  degrades DP. Big win on small/fast meshes, marginal on large. See FINDINGS.md settle section.

### Idea (not implemented): faster DP clock to cut convergence time

`dp_pass = dp_dwell · num_dst` NoC cycles grows with mesh size (∝ nodes·diameter) — the
destination-multiplexing bottleneck. `dp_clock` is **already a separate clock**
([main.cpp](main.cpp), currently `1 SC_NS` = NoC clock), so DP can run faster than the NoC.
Running it k× (4–6×) cuts convergence ~k× — a **constant factor** (doesn't change the
nodes·diameter scaling; approaches k for large diameter, less for tiny meshes where the
`+3` margin dominates). Relevant to later **RL stages**: faster reconfiguration = fresher
cost fields (complements the `settle=0` result).

- **Design A (recommended, minimal, no clock-domain crossing):** a faster `dp_clock` already
  propagates k cost-hops per NoC cycle (each dp edge = one hop via `dp_rx`), so just shrink
  `dp_dwell()` to ~`ceil(diameter/k)+3`. `dpProcess` and `routing_directionsUpdater` stay
  unchanged — both key their phase off `sc_time_stamp`, so the two clock domains remain
  coordinated automatically. ~3 lines (dp_clock period in main.cpp + dwell formula in
  NoximDefs.h). Then re-verify the publish margin (`phase%dwell==dwell-2` must be
  post-convergence) and realign `CINTERVAL`/sweep timing to the new `dp_cycle`.
- **Design B (tick-based counter):** re-base `dpProcess` on a `dp_clock`-tick counter instead
  of `sc_time_stamp`. Cleaner-sounding but *worse* — it breaks the free sim-time coordination
  and forces an explicit CDC handshake (DP exposes `dp_dir`+dst+valid, router latches on its
  own clock, DP must hold each config stable ≥1 NoC cycle). Avoid unless full decoupling is needed.

**See [PERFORMANCE.md](PERFORMANCE.md) for profiling, fixes, and validation.**

## Traffic injection (Stage 2, in progress)

DNN trace generation (Stage 2 of the execution plan) surfaced a format mismatch: the
project proposal assumed a per-packet flit-level trace format, but the actual traffic
input mechanism ([`TGlobalTrafficTable`](TGlobalTrafficTable.cpp)) is a **statistical**
descriptor table — rows of `src dst pir por t_on t_off t_period` — consumed via
per-cycle Bernoulli draws in `TProcessingElement::txProcess` against a cumulative PIR,
not literal per-packet replay. Built-in `TRAFFIC_RANDOM` (uniform destination, global
PIR, whole-run only — not phase-switchable) is also available as a distribution
alongside `TRAFFIC_TABLE_BASED` ([`NoximDefs.h`](NoximDefs.h)).

### Two hard limits of the table mechanism (code-as-written)

1. **Packet size is never read from the table.** `canShot()` calls
   `packet.make(local_id, dst, now, getRandomSize())` — the table format has no size
   column and the value is always randomized.
2. **One destination per source per cycle.** `getCumulativePirPor()` picks a single dst
   by weighted random draw among rows active that cycle, so a source cannot fan out to
   two dsts simultaneously (e.g. a ResNet skip connection to both the next sequential
   tile and the merge tile).

Timing itself is *not* a blocker: a narrow window (`t_on=C-1, t_off=C+1, pir=1.0`) forces
near-deterministic single-shot firing at cycle C; `t_period` = inference-pass length repeats it.

### Three candidate approaches

- **(a) Statistical approximation** — DNN traffic as ordinary table rows. Lossy (no real
  size, no fan-out), **zero simulator changes**.
- **(b-lite) Table + fixed packet size** — *superseded, see "Fixed packet size" below.*
- **(b-full) Dependency-gated dataflow firing** — per-PE state machine: track required
  inputs, fire only once all have *actually arrived* in-sim, so congestion delays
  propagate downstream. Architecturally correct for a layer DAG, and the only option
  where routing improvements show up in true end-to-end inference latency. Large
  `TProcessingElement` change — deferred to Stage 5/6.

### Model-by-model fit

| Model | Fit under (a) + fixed size | Notes |
|-------|----------------------------|-------|
| VGG-16 | Full fit | Purely sequential, one src→one dst per layer; FC burst is just high `pir` over a window. |
| ResNet-50 | Mostly fits | Skip-connection fan-out served by weighted draw, not guaranteed simultaneous — OK for volume, imperfect for synchronised burst. |
| Transformer | Poor fit | Attention is all-to-all/collective in one window; scatters as pairwise traffic. Needs `TRAFFIC_RANDOM` or ring/tree collective rows — separate path. Deferred. |

### Fixed packet size — resolved, zero code changes

(b-lite) is unnecessary. `-size N N` (e.g. `-size 16 16`) already yields an exactly fixed
packet size: `getRandomSize()` → `randInt(min,max)` returns `min` exactly when `min==max`
(verified empirically, 1M draws, zero deviation), and `-size 16 16` passes both CLI
validators ([`CmdLineParser.cpp`](CmdLineParser.cpp)). The size is **global** (one value
per run), not per-row — per-layer volume differences are encoded entirely in `pir`
(packet *count*), not packet size. What's lost is message granularity only (a 64-flit
message becomes four 16-flit packets), not total volume.

This is also the more hardware-realistic model: real NoCs use fixed flit width and
fixed/near-fixed packet formats per chip; variable-size *messages* are segmented into
fixed-size packets at the NI. Precedent: Krishnan et al. (ACM JETC 2021) encode DNN
layer→tile traffic as non-uniform per-pair injection rates with this same packet model.
**Net: (b-lite) collapses into (a).** Stage 2 needs zero simulator changes for
ResNet-50/VGG-16.

### Mapping strategy

**Layer→tile** (each layer resident on its own tile), not token→tile or within-layer
splitting. Realistic for IMC/ReRAM accelerators (weights stay tile-resident), precedented
in-venue (Krishnan JETC 2021), and the only scheme this simulator runs today (see
multicast note). Within-layer splitting (spatial-tiling halo exchange, or channel-split
all-gather) is a legitimate future direction but requires multicast — out of Stage 2 scope.

### Multicast — explored, not planned

True router-level multicast is **absent from noxim3d** (unicast only: `TFlit` carries a
single `dst_id`; `route()` returns one output port; DP cost-to-go is per single dst).
Adding it would touch flit format, router datapath + reservation table, a fresh
deadlock argument (flit replication under wormhole + the OEB turn model), stats, and DP
— weeks of work with a correctness research question inside. **Garnet (gem5) also lacks
router-level multicast** — it breaks multicast into unicasts at the NI (confirmed in
gem5 docs). Source-replication (PE injects N unicasts, one per dst) is therefore the
field-standard approximation and is runnable today via table rows. Not switching
simulators for this.

### Stage 6 comparison arm (planned): phase-indexed DP

A non-learning baseline the Stage 7 RL contribution must beat (or show breaks). CNN phase
timing is fully known from trace generation (`t_on`/`t_off` windows), so per-phase DP cost
fields can be precomputed (snapshot `cost_mem` per phase, or derive from the phase's
traffic matrix) and swapped in by a cycle-driven phase counter at each boundary — instead
of waiting ~`DP_CYCLE` for online DP to reconverge.

- **Fixes DP's one temporal weakness:** stale cost field during phase transitions
  (e.g. entering an FC burst) — right field loaded at cycle 1 of the burst.
- **Threat to the RL claim:** same "anticipate the burst" benefit, zero training, zero
  inference overhead, full determinism.
- **Where RL could still win:** unknown/aperiodic timing (dynamic batching, early-exit
  nets); open-loop (doesn't adapt if congestion deviates from the precomputed profile);
  per-phase field storage cost.

Selection logic unchanged from today's DP; only the cost-field source differs. Not
implemented — logged for Stage 6.

## Build

```
# Edit Makefile.defs: set SYSTEMC to your systemc-2.3.3 install path
make
```

Produces the `noxim` binary. `.o` files and the binary are gitignored — rebuild locally.

## Key source files

- [TRouter.cpp](TRouter.cpp) / [TRouter.h](TRouter.h) — router, routing algorithms, selection policies
- [DPNode.cpp](DPNode.cpp) / [DPNode.h](DPNode.h) — DP cost-to-go computation unit
- [TNoC.cpp](TNoC.cpp) / [TNoC.h](TNoC.h) — top-level NoC topology/wiring
- [TGlobalStats.cpp](TGlobalStats.cpp) — delay/throughput/energy stats collection
- [TPower.cpp](TPower.cpp) — power modeling
- [TProcessingElement.cpp](TProcessingElement.cpp) — traffic generation/injection per node
- `TRouter_old_can_turn.cpp`, `TRouterTCandNormal.cpp` — earlier routing variants kept for reference

## Running experiments

- [noximrun.bash](noximrun.bash), [noximrun_buffer_sweep.bash](noximrun_buffer_sweep.bash) — main
  experiment sweep scripts (PIR sweep, buffer-size sweep)
- [noximrun_buffer_sweep_parallel.bash](noximrun_buffer_sweep_parallel.bash) — parallel sweep
  (set `JOBS`; env overrides `DIMX/DIMY/DIMZ`, `PIR_LIST`, `SEEDS`, `BUFFER_LIST`, `OUTDIR`)
- `traffics/` — synthetic traffic pattern definitions (transpose, ami25/49, mpeg, mms, tele, ...)
- Results land in `results_*/` directories (gitignored — regenerate rather than commit)
- **DP-aware timing** (auto-derived by the sweep scripts): `DP_CYCLE = 2·nodes·(diameter+3)`,
  `CINTERVAL = DP_CYCLE`, `WARMUP = 3·DP_CYCLE`, `SIM = 20·DP_CYCLE`. Workflow: coarse 1-seed
  knee-finder → 3-seed fine sweep at the knee. Knee PIR *drops* as the mesh grows.

## Git

- Repo-local identity is set (`user.name`/`user.email`), not global.
- `.gitignore` excludes build artifacts (`*.o`, `noxim` binary), `results_*/`, simulation dumps
  (`.ptrace`, `.steady`, `.init`, etc.), `.svn/`, and Windows Zone.Identifier files.
- Remote: `origin` → `https://github.com/nizarsd/noxim3d.git`.
