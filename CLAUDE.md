# Noxim3D — NoC for DNN

SystemC cycle-accurate Network-on-Chip simulator (fork of Noxim), extended to 3D and used
to study **how an in-memory-computing DNN accelerator should be packed, mapped and routed**.
The mesh is 6×6×3 = 108 tiles of 128×128 crossbars; layers are packed onto tiles, tiles are
placed on the mesh, and traffic is generated from the resulting flow graph.

Three coupled design axes, in decreasing order of measured effect:

1. **Packing** — `(c, r, s)`: crossbars per tile and how rows/columns are grouped. Sets the
   placement-invariant **port floor PF**, which dominates delay (~4.4× elasticity) and caps
   throughput (`k_max = 1/sustained`).
2. **Mapping** — which tile sits on which node. Matters only once peak link load clears PF;
   below that floor delay is flat.
3. **Routing/selection** — odd-even-balanced routing with **DP** (multi-hop congestion
   cost-to-go) versus **bufferlevel** (local heuristic). DP pays only above PF, and only in
   proportion to how much load is escapable.

Workloads are ResNet-50, VGG-16 and DeiT-S blocks, converted to statistical traffic tables
with phase windows. Later stages replace DP with a learned selection policy; the packing and
mapping results define the regime in which that contribution can matter.

Read [PD-PO-DESIGN-FLOW.md](docs/PD-PO-DESIGN-FLOW.md) before any packing or mapping work,
and [STAGE2.md](docs/STAGE2.md) before touching the traffic converter.

## Research focus (Stage 1)

Comparing two selection policies layered on odd-even balanced routing:
- **DP**: distributed selection unit using a multi-hop congestion cost-to-go field.
- **bufferlevel (BL)**: local heuristic based on immediate neighbour buffer occupancy.

DP's advantage appears at/above the congestion knee; below it, DP ≈ BL (sometimes
marginally worse). Key finding from the size series (Z=3): **peak DP benefit scales
with mesh diameter within a parity class, and X/Y parity governs past-knee behaviour**
— odd×odd meshes win through saturation, even×even meshes reverse just past the knee.

**See [FINDINGS.md](docs/FINDINGS.md) for the full DP-vs-BL results, method, and open items.**
(The older `stage1-log.txt` is superseded by FINDINGS.md.)

## Traffic injection (Stage 2)

**[STAGE2.md](docs/STAGE2.md) is the authoritative Stage 2 decision doc** — representation
choice (option **a**: DNN-derived statistical table rows using `t_on/t_off/t_period`
phase windows), the constraint envelope, the expressiveness gap analysis, subject-model
recommendation, and the routing-choice warning (§8). Read it before touching the converter.

Supplementary findings not covered there:

### Fixed packet size — zero code changes

`-size N N` (e.g. `-size 16 16`) yields an exactly fixed packet size: `getRandomSize()`
-> `randInt(min,max)` returns `min` exactly when `min==max` (verified empirically, 1M
draws, zero deviation), and it passes both CLI validators
([`CmdLineParser.cpp`](noxim3d_src/CmdLineParser.cpp)). The size is **global** (one value per run),
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
  freshness; see [FINDINGS.md](docs/FINDINGS.md) settle study.)
- **Threat to the RL claim:** same "anticipate the burst" benefit, zero training, zero
  inference overhead, full determinism.
- **Where RL could still win:** unknown/aperiodic timing (dynamic batching, early-exit
  nets); open-loop (doesn't adapt if congestion deviates from the precomputed profile);
  per-phase field storage cost.

Selection logic unchanged from today's DP; only the cost-field source differs. Not
implemented — logged for Stage 6.

## Packing & mapping (Stage 3+) — decisions

**[PD-PO-DESIGN-FLOW.md](docs/PD-PO-DESIGN-FLOW.md) is the authoritative flow doc** —
full derivation, evidence level per claim, and an explicit "not established" section.
Read it before touching the packing sweep or any mapping search. The decisions below
are load-bearing; several supersede earlier docs.

**Metric names** (use these, don't invent synonyms). Port and link capacity are both
1 flit/cycle = **4 GB/s** (flit = 4 B, clock 1 ns; `flit_rx`/`flit_tx` are separate
channels, so injection and ejection are independent).

| symbol | meaning | placement-dependent? |
|---|---|---|
| **PD** / **PO** | packing density `c` / orientation `(r,s)`, `r·s = c` | no |
| **PIL** / **PEL** | peak injection / ejection load | **no** |
| **PF** | port floor = `max(PIL, PEL)` — never their sum | **no** |
| **PL** | peak link load (inter-router, first hop included) | yes |
| **BIND** | `max(PL, PF)` — the delay predictor, r ≈ +0.86 | yes |
| **PLf** | forced link load (edges every admissible path uses) | yes |
| **CC** / **PV** / **PR** | comm cost / path variety / peak router load | yes |

- **Feasibility is `tiles ≤ 108` AND `sustained port rate ≤ 1`** — *not* `PF ≤ 1`.
  PF is a peak over an interval that is 13% of the period; 18 of 34 points exceed it
  but only 5 exceed sustained. Do not exclude a packing on PF.
- **Rank POs on PF, never on min total bytes.** Min-bytes selects the burstiest
  packings (burst ratio spans 1.7–9.9×). `docs/packing_crs_sweep.xlsx` still
  highlights min-bytes cells as GLOBAL MIN — wrong objective, not yet fixed.
- **Mapping objective:** `PL < PF` as a hard constraint (delay is flat below the
  floor, steep above), then min PL, with CC minimised throughout as energy overhead.
  **Do not optimise PV** (null) **or PLf** (83% collinear with PL). PLf is a
  diagnostic; its *ratio* `1 − PLf/PL` is the escapable fraction and predicts how
  much DP can recover.
- **`k` is tuned per (workload, `c`)**, shared across all POs at that `c`, so
  orientation is compared at equal load. All ratios are k-invariant; PV exactly so.
- **Delay takes the PEAK, temperature takes the TIME-AVERAGE.** Thermal time
  constants (0.1–10 ms) dwarf the 38.5 µs period. Using burst power for thermal
  reverses the ranking.
- **Thermal is out of scope as analysis** — it appears only as the *motivation* for
  spreading a placement (which is what puts the design in the regime where DP pays).
- **PL and PLf are offline models, never validated against the simulator.**
  `-detailed` reports per-(src,dst) pairs, not per-link. Say so when citing them.
- **Never compare an optimised point against arbitrary ones.** That error produced
  two wrong conclusions in one session. Optimise both arms, or compare within a
  single sampling regime.

## Correctness & performance

- **odd-even-balanced + DP legality** (`a698e05`): DP's turn legality
  ([`can_turnOddEvenBalanced`](noxim3d_src/DPNode.cpp) + `*_DPStrict` helpers) mirrors the
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

### DP clock runs at 4× the NoC clock (implemented — Design A)

`dp_pass = dp_dwell · num_dst` NoC cycles grows with mesh size (∝ nodes·diameter) — the
destination-multiplexing bottleneck. Running DP faster than the NoC cuts convergence by
that factor — a **constant factor** (doesn't change the nodes·diameter scaling; approaches
k for large diameter, less for tiny meshes where the `+3` margin dominates). Relevant to
later **RL stages**: faster reconfiguration = fresher cost fields (complements the
`settle=0` result).

**Design A is in the build.** Two coupled constants:

- `dp_clock` is `250 SC_PS` = 4× the NoC clock ([main.cpp:127](noxim3d_src/main.cpp))
- `DP_CLOCK_MULT 4` with `dp_dwell() = ceil(diameter / DP_CLOCK_MULT) + 3`
  ([NoximDefs.h:252](noxim3d_src/NoximDefs.h))

**Change both together or DP breaks**: the dwell formula assumes the dp clock propagates
`DP_CLOCK_MULT` cost-hops per NoC cycle (each dp edge = one hop via `dp_rx`). No
clock-domain crossing is involved — `dpProcess` and `routing_directionsUpdater` both key
their phase off `sc_time_stamp`, so all 4 dp ticks inside a NoC cycle share one stime and
the domains stay in lockstep for free. After any change, re-verify the publish margin
(`phase%dwell==dwell-2` must be post-convergence) and realign `CINTERVAL`/sweep timing to
the new `dp_cycle`.

**All DP results in FINDINGS.md and later reflect the 4× clock.** DP numbers are not
comparable across a change to `DP_CLOCK_MULT`.

- **Design B (tick-based counter, rejected):** re-base `dpProcess` on a `dp_clock`-tick
  counter instead of `sc_time_stamp`. Cleaner-sounding but *worse* — it breaks the free
  sim-time coordination and forces an explicit CDC handshake (DP exposes `dp_dir`+dst+valid,
  router latches on its own clock, DP must hold each config stable ≥1 NoC cycle). Avoid
  unless full decoupling is needed.

**See [PERFORMANCE.md](docs/PERFORMANCE.md) for profiling, fixes, and validation.**

## Build

```
# Edit noxim3d_src/Makefile.defs: set SYSTEMC to your systemc-2.3.3 install path
make
```

Sources and `.o` files live in `noxim3d_src/`; **binaries are written to the repo root**,
where the sweep scripts expect them. The root `Makefile` just delegates, so `make`,
`make clean` and `make -jN MODULE=noxim_variant` all still run from the root.
`.o` files and the binaries are gitignored — rebuild locally.

## Key source files

All under `noxim3d_src/`.

- [TRouter.cpp](noxim3d_src/TRouter.cpp) / [TRouter.h](noxim3d_src/TRouter.h) — router, routing algorithms, selection policies
- [DPNode.cpp](noxim3d_src/DPNode.cpp) / [DPNode.h](noxim3d_src/DPNode.h) — DP cost-to-go computation unit
- [TNoC.cpp](noxim3d_src/TNoC.cpp) / [TNoC.h](noxim3d_src/TNoC.h) — top-level NoC topology/wiring
- [TGlobalStats.cpp](noxim3d_src/TGlobalStats.cpp) — delay/throughput/energy stats collection
- [TPower.cpp](noxim3d_src/TPower.cpp) — power modeling
- [TProcessingElement.cpp](noxim3d_src/TProcessingElement.cpp) — traffic generation/injection per node
- `variants/TRouter_old_can_turn.cpp`, `variants/TRouterTCandNormal.cpp` — earlier routing
  variants kept for reference; **not in `SRCS`, not compiled**

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


## Working agreement (read before any action)

This repo is a research simulator. Results already published in FINDINGS.md depend
on its current behaviour. Unrequested changes are worse than no changes.

### Before acting

1. Run `git ls-files` and read every `.md` in the repo before advising on any stage.
   Chat attachments may be stale; **the repo is authoritative**.
2. Default posture is investigate-and-report. Do not edit unless the current turn
   explicitly asks for an edit.
3. Before any code change, state: the file, the function, the exact lines, and why.
   Then stop and wait for approval.

### Scope discipline

- One change per turn. Never bundle a fix with a refactor, a rename, or a cleanup.
- Do not touch anything not named in the request — no tidying, no reformatting,
  no "while I was in there" improvements, no dead-code removal.
- Do not add abstractions, config options, helper functions, or new files unless
  asked. Prefer the smallest diff that works over the most elegant one.
- Do not modify build scripts, sweep scripts, or `NoximDefs.h` constants without
  explicit instruction — the DP-aware timing derivation there is load-bearing.

### When the plan turns out to be wrong

- Stop and report. Do not adapt silently, do not substitute your own approach,
  do not "fix it while you're there."
- Report investigation findings **as findings**, not as justification for having
  already acted on them.

### Reporting

- Show the diff. State what you changed and what you deliberately left alone.
- If you were uncertain about anything and guessed, say so explicitly, and say
  what you guessed.
- Flag any behaviour change that could affect Stage 1 numbers in FINDINGS.md.

### Validation

- Any change to DP cost computation, routing legality, or selection must be
  checked against a Stage 1 synthetic-traffic run before being trusted on DNN
  traffic. Regression against the published `transpose1` numbers is the gate.
- Runs are deterministic per seed. If output is not bit-identical when it should
  be, that is a bug, not noise.