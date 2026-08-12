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

## Traffic injection (Stage 2)

**[STAGE2.md](STAGE2.md) is the authoritative Stage 2 decision doc** — representation
choice (option **a**: DNN-derived statistical table rows using `t_on/t_off/t_period`
phase windows), the constraint envelope, the expressiveness gap analysis, subject-model
recommendation, and the routing-choice warning (§8). Read it before touching the converter.

Supplementary findings not covered there:

### Fixed packet size — zero code changes

`-size N N` (e.g. `-size 16 16`) yields an exactly fixed packet size: `getRandomSize()`
-> `randInt(min,max)` returns `min` exactly when `min==max` (verified empirically, 1M
draws, zero deviation), and it passes both CLI validators
([`CmdLineParser.cpp`](CmdLineParser.cpp)). The size is **global** (one value per run),
not per-row, so per-flow volume differences must be encoded in `pir` (packet *count*),
not size — resolving the STAGE2.md §9 open item "decide whether the converter also fixes
packet size" in favour of *no simulator change needed*. What's lost is message
granularity only (a 64-flit message becomes four 16-flit packets), not total volume.

This is also the more hardware-realistic model: real NoCs use fixed flit width and
fixed/near-fixed packet formats per chip; variable-size *messages* are segmented into
fixed-size packets at the NI. Precedent: Krishnan et al. (ACM JETC 2021) encode DNN
layer->tile traffic as non-uniform per-pair injection rates with this same packet model.

### Multicast — explored, not planned

True router-level multicast is **absent from noxim3d** (unicast only: `TFlit` carries a
single `dst_id`; `route()` returns one output port; DP cost-to-go is per single dst).
Adding it would touch flit format, router datapath + reservation table, a fresh deadlock
argument (flit replication under wormhole + the OEB turn model), stats, and DP — weeks of
work with a correctness research question inside. **Garnet (gem5) also lacks router-level
multicast** — it breaks multicast into unicasts at the NI (per gem5 docs). Source-replication
(PE injects N unicasts, one per dst) is therefore the field-standard approximation and is
runnable today via table rows. Not switching simulators for this.

### Stage 6 comparison arm (planned): phase-indexed DP

A non-learning baseline the Stage 7 RL contribution must beat (or show breaks). Phase
timing is known from trace generation (`t_on`/`t_off` windows), so per-phase DP cost
fields can be precomputed (snapshot `cost_mem` per phase, or derive from the phase's
traffic matrix) and swapped in by a cycle-driven phase counter at each boundary — instead
of waiting ~`dp_cycle` for online DP to reconverge.

- **Fixes DP's temporal weakness:** stale cost field during phase transitions — the right
  field is loaded at cycle 1 of the burst. (Related: `-dpsettle 0` already improves
  freshness; see [FINDINGS.md](FINDINGS.md) settle study.)
- **Threat to the RL claim:** same "anticipate the burst" benefit, zero training, zero
  inference overhead, full determinism.
- **Where RL could still win:** unknown/aperiodic timing (dynamic batching, early-exit
  nets); open-loop (doesn't adapt if congestion deviates from the precomputed profile);
  per-phase field storage cost.

Selection logic unchanged from today's DP; only the cost-field source differs. Not
implemented — logged for Stage 6.

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
- Remote: `origin` → `https://github.com/nizarsd/noxim3d-dnn.git`.
