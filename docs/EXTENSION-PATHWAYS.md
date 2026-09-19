# Extension pathways — Paper 1 (working document)

**Status 2026-09-13.** Plan for the journal / CODES extension after the DATE 2027
decision. Investigation only: no simulator source changed, nothing run. Decoder-LLM
packing (the paper's future-work item) is assigned to Paper 2 and is not listed here.

**Terms used below.** *Oracle*: for each placement × load cell, the better of BL and DP
measured on the same seeds; the paper's switching bound. *Capture*: the fraction of the
BL→oracle delay reduction that always-DP achieves (99/98% above the floor, 81/76%
below, mean/p99). *Phase window*: a `t_on`/`t_off` interval of the traffic table's
period; congestion below the floor clusters at their boundaries.

## Plan

| # | task | new content? | effort | status |
|---|---|---|---|---|
| 1 | phase-gated oracle | yes | ~1 day | DONE 2026-09-16 — gap +0.2–0.5%: boundary switching buys nothing |
| 2 | runtime attribution of the below-floor loss | yes, with 1 | ~2 days | hot-link arm DONE 2026-09-16 — body-dominated (head 0–31%); relief links pending |
| 3 | sink-list hybrid (DP for top-volume sinks, BL fallback); k-truncation demoted to arm 2 | yes | ~1 day | BUILT + GATED 2026-09-16 (`-dptopn`, see TOPN-DP-INVESTIGATION.md) — N sweep pending |
| 4 | packing panel completeness (Pathway 5) | completeness | half day | NEEDS RUNS (~200) |
| 5 | full-width routing figure (Pathway 1) | presentation | hours | DONE 2026-09-16 |
| 6 | second mesh 7×7×3 (Pathway 2) | only if reviews ask | ≥1 week | CONDITIONAL |
| 7 | runtime BL/DP switching on a phase schedule | yes, if triggered | ~1 day | TRIGGER FAILED 2026-09-16 (task-1 gap small) — stays out |
| 8 | phase-length hypothesis: accurate-field fraction vs DP/BL gain | yes | ~1 day + ~100 runs | observational arm NULL 2026-09-16; stretch test pending |

Tasks 1–3 form one new section: two oracles (temporal null, spatial headroom), a
decomposition, and a tested mechanism (the sink-list hybrid).
Task 8 sits between 2 and 3 in conduct order: it turns task 2's mechanism into a
registered predictor and gives task 3 its prediction of where the control should pay.
Housekeeping first: tag and push the submission state, make `results_*` read-only,
archive them to the G drive, work on a branch.

---

## Task 1 — Phase-gated oracle

**Definition.** The *phase-gated oracle* picks the better of BL and DP per phase window
inside a run, instead of per run, and sums over windows. Its gap to the per-cell oracle
is the headroom a policy that switches at phase boundaries could have.

- Population: the 128 canonical below-floor cells (ResNet (8,1,8), ResNet (8,2,4),
  VGG (8,4,2); `res_bf`, `res_f1`, `res_f2` in
  `results_stage3/mapping_pilot/pool1000/hill/`), 3 seeds.
- Built on **mean delay**. p99 does not decompose across windows: per-window p99 may
  be shown as a panel, never summed.
- It is an **estimate**, not an achievable number and (per the result's Caveat 2) not
  a rigorous bound either: the two runs' queue states differ at every boundary, so a
  switched run would inherit different congestion than the pure runs did.
- Phase index: injection time modulo the table period (38536 for ResNet, 115606 for
  VGG), binned into the converter's layer windows.
- Instrumentation — CHECKED 2026-09-16, no simulator change needed: the env-gated
  `BARRIERTRACE` hook in `TStats::receivedFlit` (noxim3d_src/TStats.cpp:66-74,
  committed, bit-exact no-op unset) prints one line per delivered packet:
  `B,<dst>,<injection timestamp>,<arrival>`, warm-up excluded. Delay = arrival −
  timestamp; phase = timestamp mod t_period; `tools/barrier_group.py` already parses
  the format. Reruns still required — the stored below-floor results were run without
  the env var, so no traces exist: 128 cells × 2 policies × 3 seeds = 768 runs with
  `BARRIERTRACE=1`, stderr captured gzipped under a new `results_ext/` (the frozen
  `results_stage3/` is read-only). The same runs carry task 2's `DPTRACE` channel.

**Reads:** small gap → the residue is not fixable by switching at boundaries, which
sends the argument to a fresher field (task 3); large gap → phase-aware selection has a
real target (Paper 2's motivation, stated as a bound only).

**RESULT 2026-09-16 — the gap is SMALL.** 1,056 traced runs (canonical 128 cells +
DeiT-S ES 48, both policies, 3 seeds, zero failures; driver and traces in
`results_ext/trace_runs/`, per-cell numbers in `oracle_cells_<set>.csv`):

| set | cells | windows | phase-oracle over cell-oracle (mean delay) |
|---|---|---|---|
| ResNet (8,1,8) | 32 | 4 | +0.4% |
| ResNet (8,2,4) | 56 | 4 | +0.2% |
| VGG (8,4,2) | 40 | 4 | +0.5% |
| DeiT-S ES arm | 48 | 5 | +0.5% |

Per-window winners are mixed in most cells (75/73/33/83% of cells have both a B and a
D window), but the windows the per-cell loser wins carry little volume, so the bound
barely moves. By the registered reading: **the below-floor residue is not recoverable
by switching policies at phase boundaries**; the argument moves to a fresher field
(task 3). **Task 7's trigger fails on its first condition — task 7 stays out** (it
remains Paper 2 material at most). Caveat 1: computed on the global table windows;
an oracle on finer within-window segments would be a different (larger) number, but is
no longer 'phase-gated'. Caveat 2 (user's objection, 2026-09-16, upheld and tested):
the composition is an ESTIMATE, not a bound — in a switched run each window inherits
the previous window's queues from a different policy, so per-window means from two
pure runs do not compose exactly. Robustness check: recomputed on body-only packets
(injected ≥ 2,000 cycles after their window's start, past refresh + the longest drain
tail, so their delays are set by their own window's steady state and DO compose):
+0.4/+0.1/+0.4/+0.6% vs full-data +0.4/+0.2/+0.5/+0.5%, with 4–15% of packets
excluded. The small-gap conclusion does not rest on the coupled region.

## Task 2 — Runtime attribution of the below-floor loss (Pathway 4)

**Goal.** Decompose the below-floor loss (DP vs oracle) into drain tails at phase
boundaries versus reconvergence lag, by phase window and by link class (hot tier vs
relief links). **Attribute on mean delay or per-link blocking cycles only**; p99 stays a
headline.

What exists:

- `DPTRACE=<node>:<dir>` streams, per cycle, the downstream queue occupancy and the
  cumulative departures of **one** channel ([TRouter.cpp:324-337](../noxim3d_src/TRouter.cpp);
  counter at [TRouter.cpp:227](../noxim3d_src/TRouter.cpp)). One channel per run is a
  hard limit of the hook, so the 7-link validation
  (`trace_{bl,dp}_*.csv`, `trace_validation.csv`, `trace_targets.json` in `hill/`) was a
  choice of coverage, not a ceiling; full coverage of a placement is 648 runs per policy
  and load. Overhead is one stderr line per cycle, negligible.
- Drain tails of 0.8–1.5k cycles are already measured from those traces
  ([FINDINGS.md:560-562](FINDINGS.md)).
- Whether any existing script decomposes p99 by link or phase was **not verified**
  (the scan was not run); check `hill/*.py` before reusing anything.

Design: same 128 cells as task 1, DPTRACE on the top-PL link and one relief link per
placement, both policies, 3 seeds; attribute blocking cycles per window. Shares task 1's
runs where the per-window accumulator is added.

**RESULT 2026-09-16 — hot-link arm (relief links not yet traced).** Same 1,056 runs;
per-cell blocking (occupancy-cycles on the placement's hot link, pooled seeds) in
`results_ext/trace_runs/blocking_<set>.csv`; head = the first 1,500 cycles after each
window boundary (drain tail + refresh span), body = the rest:

| set | DP−BL head | DP−BL body | head share of the difference |
|---|---|---|---|
| ResNet (8,1,8) | −52k | −1,006k | 5% |
| ResNet (8,2,4) | +19k | +81k | 19% |
| VGG (8,4,2) | −2k | −1,305k | 0% |
| DeiT-S ES arm | +81k | +177k | 31% |

**The DP-vs-BL difference on the hot link is body-dominated everywhere** — where DP
wins it wins in-window, and where it loses (ResNet (8,2,4), DeiT-S ES) it loses mostly
in-window too. Together with task 1's small bound this REVISES the temporal
interpretation the paper's conclusion leans on ("transient congestion clustered at
phase boundaries"): the below-floor DP-BL difference is **in-window**, not
boundary-clustered. For task 3's registered three-outcome prediction this points, in
advance, at outcome three: intra-phase tracking (queue dynamics under constant injected
rates) is where the headroom lives. **Deep-knee nuance (esxd + its k 1.0/1.1 top-up, 80 cells):** the head share flips
to 73% — deep in DeiT-S's knee the hot-link difference DOES become
boundary-dominated, while the phase-gated oracle stays small (+1.2%). So the
body-dominated conclusion is a statement about the canonical (light-to-knee) rungs;
past the knee on the most transition-violent workload, boundary drain grows into the
dominant term without becoming switchable. Caveats: one traced link per placement
(the PL argmax); the 1,500-cycle head is a fixed convention; occupancy on the hot
link is a proxy, not the full mean-delay decomposition over links.

**The residue is destination-structured, not phase-structured (2026-09-16, user's
reframing).** The *destination-gated oracle* — computed exactly like task 1's
phase-gated oracle but splitting the policy choice over destinations instead of
windows (per cell, per destination, the better policy's mean delay, packet-weighted;
B-lines carry the destination) — against the same per-cell oracle:

| set | phase-gated | destination-gated |
|---|---|---|
| ResNet (8,1,8) | +0.4% | +1.8% |
| ResNet (8,2,4) | +0.2% | **+7.0%** |
| VGG (8,4,2) | +0.5% | +2.0% |
| DeiT-S ES arm | +0.5% | +4.7% |

The spatial split is 4–35× the temporal one and is largest exactly where always-DP
gains nothing (the injection-bound ResNet, DeiT-S) — the open question below the
floor is *for which traffic* to run DP, not *when*. Composition caveat, stronger
than task 1's: destinations interact simultaneously through shared links, so this is
a heuristic estimate, not a bound; the live hybrid (task 3) is its test.

**Supporting trace measurements (same runs):**
- *Queue-mass mechanism (registered below-floor generality prediction: PASSED).* Mean
  hot-link queue at the knee: ResNet (8,1,8) ejection-bound 2.4–2.6 flits → DP gain
  1.36; ResNet (8,2,4) injection-bound 0.05–0.08 → 1.00; VGG (8,4,2) 0.04–0.67 →
  1.06; DeiT-S 0.6–1.2 → 1.00 (DP halves its hot-link queue yet gains no delay: 108/108
  occupancy leaves nowhere to divert). Gain tracks in-network queue mass, not the
  binding label alone; on empty-network packings the occupancy signal is
  information-free at ANY refresh rate.
- *Coherence time of hot-link occupancy* (detrended ACF): 50–160 cycles (lag-0.5) at
  light/knee loads, stretching toward and past 648 near saturation. Today's 648-cycle
  refresh is matched to the saturated/above-floor regime and is 2–6× too slow at the
  knee — the capture asymmetry (99% above, 81% below) restated as a sampling-rate
  mismatch. A fixed refresh suited to the knee is ~100–150 cycles.
- *Cost metric pilot* (96 runs, `res_bf_dpwait.txt`): `-dpcost wait` ≈ occupancy
  through the knee, 9–12% worse at the deepest rung. Production choice (occupancy)
  validated on this set; full close-out needs the other three sets (~288 runs).

## Task 3 — Sink-list hybrid (redefined 2026-09-16; k-truncation demoted to arm 2)

**Why (updated).** Two trace measurements re-aimed this task. (a) The knee-load
coherence time of hot-link occupancy is 50–160 cycles, so a refresh must sit at or
below ~150 cycles to be inside the window — the k-truncated control (432, or 216 with
the margin trim) cannot get there, and a null at 432 would be uninterpretable.
(b) The destination-gated oracle (task 2 addendum) shows the residue is
destination-structured: +1.8 to +7.0% vs the per-cell oracle, largest where always-DP
ties. The mechanism shaped to both facts is the **sink-list hybrid**: per-destination
DP exactly as today (full-diameter field, real anchors, unchanged legality and
timing), but sweeping ONLY the top-volume destinations, with **BL selection as the
fallback** for unlisted destinations. Volume is concentrated where DP has queues to
steer: 80% of bytes reach 14–15 sinks on the ejection-bound sets (ResNet (8,1,8) 15,
DeiT-S 14; 90% in 24–25), so the rotation shortens from 108×6 = 648 to N×6 cycles:

| N (sinks) | period | vs 648 | volume covered (ResNet 8,1,8) |
|---|---|---|---|
| 15 | 90 | 7.2× | 80% |
| 24 | 144 | 4.5× | 90% |

*Coverage vs convergence:* every listed destination's field converges FULLY (its
6-cycle window is today's, whole-mesh, real anchor); coverage is only the byte
fraction whose destination has a field at all — the rest are BL-selected. Breadth
of DP service is cut, never field quality (the deliberate contrast with arm 2's
k-truncation, which keeps all destinations but cuts each field's reach).

**Sink structure (`results_ext/phase_score/` analysis 2026-09-16).** Below-floor
c=8 arms: ResNet (8,1,8) 80% of bytes at N=15 of 89 sinks (accumulators 8, 9 take
19.3% each); DeiT-S (16,1,16) 80% at N=14 of 64 (42, 43 at 17.4% each); the
injection-bound ResNet (8,2,4) and VGG (8,4,2) are flat (80% needs N≈40 of 91/104)
— but those are the sets where no refresh helps anyway. On each workload's GLOBAL
min-PF packing the concentration is uniformly strong (fewer tiles, heavier sinks):

| coverage | ResNet (16,2,8), 45 sinks | DeiT-S (16,1,16), 64 | VGG (32,8,4), 31 |
|---|---|---|---|
| 50% | N=6 (period 36 cyc) | N=6 (36) | N=7 (42) |
| 80% | N=17 (102) | N=14 (84) | N=13 (78) |
| 90% | N=23 (138) | N=25 (150) | N=22 (132) |
| 95% | N=27 (162) | N=45 (270) | N=26 (156) |

Top of each list: ResNet nodes 4, 5 at 19.2% each then a 3.6% bank (1, 30–37);
DeiT 42, 43 at 17.4% then a 4.3% bank (24–29); VGG eight equal accumulators at
7.9% (8–11, 20–23). Node ids are logical (the run tables carry them permuted, so
the implementation ranks from the run's own table). **Cross-layer point:** the
min-PF packing rule, chosen for the floor, also produces the concentrated sink
structure that makes the hybrid fast — at 80–90% coverage all three workloads sit
inside the measured 100–150-cycle coherence window. The flat, hybrid-unfriendly
tables are the near-full-mesh c=8 arms. Per-workload N rule: smallest N covering
~80% of bytes.

Both inside the coherence window with the dwell and publish/latch protocol untouched
(no margin trim needed — it becomes optional). The N axis: N = 0 = empty list =
pure BL via the fallback (a sanity arm that should statistically match
`-sel bufferlevel`); N = 108 = today's full rotation; the sweep traces the whole
policy-assignment axis. The FEATURE-OFF value is separate (flag absent / −1), which
keeps today's code path untouched for the bit-identical gate. This is a distinct policy: label
it as the hybrid, never as DP. Hardware story: the sink set is known at mapping time.

**Changes (for approval, not made):** `-dpsinks N` (absent/−1 = feature off, today's
pure-DP path untouched — the gate; N = 0 = all-BL fallback); at startup rank destinations by table volume (pir × window length), keep the
top N as `dst_list`; `dpProcess` and `routing_directionsUpdater` sweep
`dst_list[(phase/dwell) % N]` instead of all destinations; `selectionDP` returns
`selectionBufferLevel(directions)` when the packet's destination is not listed.
~30 lines; no timing constant, clock, or protocol change.

**Gates and runs.** `-dpsinks 0` bit-identical to today; Stage 1 `transpose1`
regression; then the 128 canonical + 48 ES cells × 3 seeds at N ∈ {8, 15, 24} plus the
above-floor guard (VGG (8,4,2) grid, 168 runs). Registered reading: the hybrid should
(i) recover a large part of the destination-gated oracle's headroom on the sets where
it is big, and (ii) hold or beat always-DP where always-DP already wins (fresher
fields for the sinks that matter). If it does neither, the spatial-oracle headroom was
a composition artifact.

**Arm 2 (demoted): k-truncated refresh control.** Mak's k-step look ahead reduced to
its cheapest form, **DP within k hops, static beyond** — kept as the pure
refresh-rate control for the reviewer question, with the caveat that its reachable
periods (432; 216 trimmed) sit above the knee coherence window.

**Mechanism.** Today one destination is held for a dwell of
`ceil(diameter/4) + 3` NoC cycles ([NoximDefs.h:252-256](../noxim3d_src/NoximDefs.h)),
so the sweep of 108 destinations takes 648 cycles. Set the dwell from k instead of the
diameter, and let nodes farther than k from the live destination publish NOT_VALID
(*region gating*), so the router never reads a row that did not converge. A packet whose
destination is beyond k then finds no DP match and takes the routing function's first
admissible port ([TRouter.cpp:595](../noxim3d_src/TRouter.cpp)); within k it is ranked
by a converged field. Deadlock freedom is the routing function's and is untouched.

**Changes (for approval, not made):**

1. `-dpk N` (0 = today): parse beside `-dpsettle` at
   [CmdLineParser.cpp:376](../noxim3d_src/CmdLineParser.cpp), default at
   [main.cpp:88](../noxim3d_src/main.cpp), field beside `dp_settle_mult` at
   [NoximDefs.h:213](../noxim3d_src/NoximDefs.h).
2. `dp_dwell()` at [NoximDefs.h:253](../noxim3d_src/NoximDefs.h): use
   `min(dp_k, dp_diameter())` when `dp_k > 0`. The only timing change; `DP_CLOCK_MULT`
   stays.
3. `dpProcess`, after the anchor branch ([DPNode.cpp:71](../noxim3d_src/DPNode.cpp)): if
   Manhattan distance to `dst_id` > k, write `BIG_VALUE` on `dp_tx`, `NOT_VALID` on
   `dp_dir`, return.

About 20 lines. Period = 108 × (ceil(k/4) + 3) = 432 at k = 4; trimming the +3 protocol
margin to +1 (optional, separate change) gives 216.

**Gates and runs.** `-dpk 0` must be bit-identical to today; then the Stage 1
`transpose1` regression; then the 128 below-floor cells × 3 seeds = 384 runs at k = 4,
plus an above-floor guard (VGG (8,4,2) `res_e3_vgg842_grid`, 56 knee cells × 3 seeds =
168) so the above-floor gain is shown not to be lost. Register the prediction before
running. `-cinterval` is tied to the 648-cycle pass today and must be chosen
deliberately. Numbers are not comparable to the paper's DP.

**Registered three-outcome prediction (2026-09-16, from the phase-transition
analysis in `results_ext/phase_score/`).** The post-boundary error span is
refresh + drain tail; the control cuts only the refresh part (648 → ~200 at k = 4),
while the drain tail (0.8–1.5k cycles, queue physics) is untouched. The workload-level
finding to test against: boundary *turnover* (summed rate of flows stopping + starting,
normalised by the mean rate) ranks ResNet < VGG < DeiT-S, and that inter-phase ranking
matches the DP-gain ordering in all four columns (mean/p99 × below/above), while the
intra-phase ranking (steady-stretch length) does not. Under the control:

- turnover–gain relation **weakens** → the inter-phase deficit was refresh-limited:
  DP's fault, fixable by a faster field;
- it **persists** → drain-limited: no field speed fixes it; the case shifts to
  anticipation (task 7's schedule, or Paper 2's policy);
- within-window gain **rises** → intra-phase tracking (queue fluctuations under
  constant injected rates, averaged away by the 648-cycle field) is real headroom.

Task 2's decomposition splits each boundary's cost into drain vs refresh beforehand;
the drain share is the part this control cannot move.

**Full KSLA, if the control moves capture.** Two additions make it Mak's published
form: expose the per-destination min cost to the router (the commented `dp_dir_cost`
port at [DPNode.h:18](../noxim3d_src/DPNode.h) is the hook) and, for a destination beyond
k, rank by the row of the *stand-in*, the cheapest boundary node k hops away that lies
on a minimal path to the destination, recomputed at every hop (Algorithm 2 of the
paper). ~60–90 lines. Beyond that, a tagged event-driven relay (link values carry the
destination id, entries re-sent only when they change) reaches ~77 cycles at k = 4 for a
central node, but it is a link-protocol change; see the 2026-09-13 session notes if
that stage is reached.

### 3.1 What the prompt got wrong (record)

- "DP cycle 162" is the `-cinterval` sampling window of the EWMA study (arms B/C,
  [FINDINGS.md:468-480](FINDINGS.md)), not a DP period; with 108 destinations and a
  minimum dwell of 4 the period cannot fall below 432 by the clock multiplier alone.
- There is no torn read. The router latches DP's ranking on the NoC clock
  ([TRouter.h:128-130](../noxim3d_src/TRouter.h)) one cycle after DP publishes
  ([DPNode.cpp:116-127](../noxim3d_src/DPNode.cpp), [TRouter.cpp:377-385](../noxim3d_src/TRouter.cpp));
  the six-entry row write is atomic within the method. No `dir_tbl[2]` fix is needed.
- The 648-cycle period is a property of the serialised implementation; Mak's
  convergence analysis (Table 2) counts iterations equal to the diameter and does not
  state a destination schedule. The paper sentence should say "destination-serialised".

Mak, Cheung, Luk, Lam, CODES+ISSS 2009: `G:\Research\NoC_for_DNN\Resources\DP_MAK_2009.pdf`.
FPGA overhead (Table 4, Virtex-4, 4-port router): DP +28.5% slices over XY at buffer 16,
KSLA k = 4 +21.5%; at buffer 32, +11.4% and +9.9%.

### Task 3 capstone — the c16 coherent matrix (2026-09-17, DONE)

The structural version of the hybrid claim, replacing pooled-across-unlike-
populations evidence: 3 workloads at their c=16 min-PF packings, 7 engineered
placement arms x 8, per-placement knee rung (4–6x own free-flow), 8 seeds,
BL/DP/DPN, registered predictions, ~3,400 runs. Full section at the end of
TOPN-DP-INVESTIGATION.md; auto-analysis in `results_ext/topn/matrix/ANALYSIS.txt`.
Outcome: (1) below the floor NO arm — minCC, maxES, or any E-level climb —
creates DP-over-BL value (all 0.94–1.03; registered P2 FAILED, P4 null: the
escape-metric family is not causal for DP gain — a designed null); (2) above
the floor (PL=1.10xPF arm) DP pays 1.05/1.12/1.35x mean (p99 to 1.76) and DPN
captures it fully (DP/HYB 0.998) at 21–23% activity; N@95 escalation fixes the
single coverage-starved deep cell. Sharpened law: crossing the port floor is
the only lever that creates routing-policy value at these packings, and DPN
collects ~100% of it at ~1/4 the activity. Predictor claim (final wording): **no design-time predictor of policy gain exists
unconditionally** — below the floor none works, above it only E does and only on
ejection-bound packings (p = 0.018, 8 populations). ES and the level forms E50/E40
are retired to a single results sentence; the extension's methodology defines E
alone, plus the PIL/PEL binding classification that scopes it. The CC-covariation
caveat is RETRACTED (2026-09-19): partialling communication cost out leaves E's
correlation unchanged on every ejection-bound population (+0.62->+0.56,
+0.61->+0.65, +0.38->+0.34), so no CC-pinned grid is required. Post-checks (2026-09-18,
`results_ext/topn/matrix/postchecks.txt`): E's capacity claim survives
within-PL-band conditioning on the E1 grid (+0.53/+0.62/+0.94, dose-response)
while its matrix delay correlation is a Simpson artifact; and below-floor
per-placement gain has ~zero split-half seed reliability (pooled +0.06) — the
variation is run-level (temporal interleaving), so offline prediction below
the floor is ill-posed, not just unsolved.

---

## Task 4 — Packing panel completeness (Pathway 5)

Table III's five disagreeing (workload, c) cells, min-PF vs min-traffic orientation:

| cell | min-PF / min-traffic | simulated | source |
|---|---|---|---|
| ResNet-50 c=16 | (2,8) / (4,4) | yes | `res_test1_{bl,dp}`, k 0.4–2.5 |
| DeiT-S c=16 | (1,16) / (4,4) | yes | `res_ladder_deit16_{bl,dp}`, k 0.1–2.0 |
| DeiT-S c=32 | (2,16) / (4,8) | **no** | — |
| VGG-16 c=16 | (4,4) / (8,2) | **no** | — |
| VGG-16 c=32 | (8,4) / (16,2) | yes | `res_ladder_vgg32_{bl,dp}`, k 0.15–2.5 |

Each simulated cell: 3 placements × 3 seeds per arm, both policies. The two missing
cells need ~200 runs under the same protocol. Whether traffic tables exist for
DeiT (32,4,8) and VGG (16,8,2) was not verified (directory listing truncated); generate
with the packing converter if absent. `res_test1c8` is ResNet c=8 (2,4) vs (1,8), not a
min-traffic pair; do not cite it as one.

## Task 5 — Full-width routing figure (Pathway 1)

All populations of `plot_layer_bars.py` (in `hill/`) exist; census 2026-09-13:

| regime | workload | sets | placements | knee cells | seeds/cell |
|---|---|---|---|---|---|
| above | ResNet-50 | `res_ladder` | 24 | 240 | 5 |
| above | DeiT-S | `res_e7` + `res_e3_vit_grid` | 14 + 7 | 147 | 3 |
| above | VGG-16 | `res_e3_vgg_grid` + `_vgg824_grid` + `_vgg842_grid` | 22 + 10 + 8 | 314 | 3 |
| below | ResNet-50 | `res_bf` + `res_f1` | 8 + 8 | 88 | 3 |
| below | DeiT-S | `res_esxd` (ES arm, by the 2026-09-09 decision) | 16 | 48 | 3 |
| below | VGG-16 | `res_f2` | 8 | 40 | 3 |

Totals match the paper (701 above, 128 below). Error bars over seeds are possible
everywhere; 3 seeds per cell is thin, so draw them over cells within a load band rather
than per cell. No runs.

**DONE 2026-09-16.** `tools/plot_routing_wide.py` -> `figs/f_routing_wide.{pdf,png}`
(p99) and `figs/f_routing_wide_mean.{pdf,png}` (`--metric mean`). Two rows (regime) x
three columns (workload); x = load band (set's BL mean delay over its free-flow: <5x,
5-15x, 15-30x, the knee rule's own quantity); box = per-cell BL/DP ratios (IQR,
whiskers 5-95%), diamond = band ratio of pooled means, lines = panel pooled DP and
oracle. Gate passed exactly: p99 2.386/1.231, mean 1.850/1.150, oracle +2.5/+7.7%
(p99) and +1.1/+3.8% (mean) above/below. Fonts embedded TrueType (Type 42).
The palette validator of the dataviz skill could not run (no `node`); the hues are
Fig. 6's own family.

Paragraph for the extension (numbers from the script's per-band table):

> Fig. X spreads the routing panel of Fig. 6 by load band. Above the floor DP's
> pooled gain rises from light load to the knee and fades past it (p99: ResNet-50
> 1.9x -> 4.0x -> 3.0x, VGG-16 1.5x -> 2.4x -> 2.1x across the <5x, 5-15x and
> 15-30x bands; DeiT-S 1.5x -> 1.6x, its ladders not reaching the deepest band) --
> the same peak-at-the-knee shape as C5, not a monotone rise. The median cell
> moves with it (1.2x -> 2.3x, 1.1x -> 1.4x, 1.1x -> 1.9x). Pooled values sit above the medians everywhere because the gain is carried by
> the cells DP rescues, up to 10-60x in the tail. Below the floor the picture is C5's:
> at light load DP is level with BL (pooled 1.00-1.15x, median 1.03x) and loses 29 of
> 72 ResNet-50 and 20 of 32 DeiT-S cells, while the gain concentrates in each packing's
> knee band (ResNet-50 1.5x at 15-30x, VGG-16 1.2x at 5-15x). Of the 15 populated
> bands DP's pooled p99 is above BL in 14; the exception is the DeiT-S ES-arm light
> band (0.85x). Mean delay shows the same shape at smaller magnitudes, with DP behind
> in two bands (ResNet-50 5-15x at 0.99x, DeiT-S light at 0.91x).

**DeiT band top-up DONE 2026-09-16** (probe + traced runs, `results_ext/trace_runs/`:
`tables_topup_*`, `res_topup_*.txt`, traces in `traces_topup_*`; tables generated by
exact linear k-scaling, verified to 4e-7). Probe picked rungs landing in the 15–30×
band: e7 + e3_vit k 0.80/0.85 (set-mean 20.8/28.7× and 18.1/25.7× ff), esxd k
1.00/1.10 (17.9/22.3×; its first candidates 0.70–0.90 all fell below 15×). Figure
regenerated with `--topup` (gate and panel lines stay canonical-only): DeiT above
15–30× = 42 cells, pooled p99 1.29× (fading from the 1.64× knee band, the C5 shape);
DeiT below (ES arm) 15–30× = 32 cells, pooled 1.04×, DP loses 13/32. Zero failures
(the first orchestrator had two shell bugs — an xargs field collapse on empty
DPTRACE and `VAR=x` expanding as a command name — both fixed via a '-' placeholder
and `env`; e7/e3_vit were unaffected, esxd was rerun).

Per-band counts of cells DP loses (p99): above 19/144, 8/48, 8/48 (ResNet), 24/105,
6/42 (DeiT), 45/234, 3/40, 4/40 (VGG); below 29/72, 4/8, 3/8 (ResNet), 6/32, 3/8
(VGG), 20/32, 5/16 (DeiT ES arm).

## Task 8 — Phase-length hypothesis

**Hypothesis (user, 2026-09-15).** Longer phases favour DP, shorter phases favour BL.
Mechanism: after a phase boundary DP's field is wrong until it has refreshed (648
cycles) and the previous window's queues have drained (0.8–1.5k cycles measured);
BL is instantaneous. The longer a window relative to (refresh + tail), the larger the
share of cycles in which DP's field is accurate.

**Why not per workload.** Window lengths from the tables: DeiT-S ~5.8k cycles, ResNet
~5.0k, VGG ~23k. DeiT-S (shortest, gain 1.01× below floor) fits; ResNet (short, gain
1.26×) does not. Three points, one of them the ES-arm population: not a refutation,
but window length alone is not the variable, and phase structure is shared by every
placement of a table, so it cannot explain placement-level variation.

**Metric, per cell.** *Accurate-field fraction* of the placement's top link: from the
offline per-window loads (`tools/table_phase_load.py`), the fraction of that link's
loaded cycles lying more than (refresh + tail) after a boundary. Idle windows do not
count; the tail is set by the load drop at the boundary and lengthens with the rung.
Prediction, registered before computing: DP/BL mean-delay gain rises with the fraction,
BL wins where it is low. Observational test on the 128 below-floor cells, no runs.
Report r, the win-call accuracy, and Spearman alongside Pearson.

**Observational arm RUN 2026-09-16 — NULL, with a sign flip**
(`results_ext/phase_score/task8_observational.txt`, hot links + per-link metrics in
`results_ext/trace_runs/hotlinks_*.csv`). Hot-link boundary turnover / CV vs
per-placement mean gain over knee cells: ResNet (8,1,8) r −0.04/ρ −0.14 (n=8),
ResNet (8,2,4) +0.03/−0.10, pooled ResNet +0.07/−0.06 (n=16); VGG (8,4,2)
**+0.43/+0.31 — the wrong sign for the hypothesis**; DeiT-S ES arm degenerate (the
metric saturates: 13 of 16 placements at turnover 10.0, the hot link going fully idle
at a boundary). Within workload, transition violence at the hot link does NOT predict
the DP/BL gain in either direction. The cross-workload rank match above is therefore
best read as a workload-level confound, as flagged. C8 is strengthened; what remains
of task 8 is the causal stretch test and the run-based per-window decomposition
(task 2), not this predictor.

**Thread closed 2026-09-16 (user's significance challenge, upheld).** The residual
workload-level amplitude match also fails under equal-cell weighting: per-cell gain
ResNet 1.055 (sd 0.20, n 88) vs VGG 1.055 (sd 0.15, n 40), bootstrap P(ResNet>VGG)
= 0.50; only DeiT-S separates (1.004, P = 0.98 vs VGG). The apparent ResNet lead was
an artifact of delay-weighted pooling. Folding frequency in (turnover rate per 10k
cycles: ResNet 0.78, VGG 0.43, DeiT 1.34) fails outright — it swaps ResNet and VGG.
Net: NO phase-structure measure (length, amplitude, frequency, combined, CV)
predicts the below-floor DP gain at any granularity tested; the one robust fact is
that DeiT-S gains nothing below the floor, which has non-phase explanations (zero
placement freedom; ES-arm population). The two same-workload ResNet packings
(identical phase structure, gains 1.36 vs 1.00 pooled) locate the real driver in the
packing's port regime (ejection- vs injection-bound), not in the phase schedule.

**Causal test (the decisive one).** Stretch a table in time: scale every `t_on`,
`t_off` and `t_period` by 2× and 4× with rates unchanged. Per-cycle load, drain tails
and everything spatial stay fixed; only window length moves. Uniform time stretching
keeps the traffic mix, so it does not fall under the rule against scalar rescaling
(PROJECT-RESEARCH-NOTES §31 item 16). A few below-floor placements at their knee rung,
both policies, 3 seeds, 3 stretch factors: ~100 runs. Gain rising with the stretch
confirms the hypothesis with one variable moved; flat gain says the deficit is not a
window-length effect.

**Link to task 3.** The same mechanism predicts that the k-hop control (shorter
refresh) pays most on the cells with the lowest accurate-field fraction. That is task
3's registered prediction; its three-outcome refinement (refresh-limited vs
drain-limited vs intra-phase headroom) is registered under task 3.

**Table-level findings (2026-09-16, `results_ext/phase_score/`, all 34 tables).**
Computed before any new runs; they re-aim the observational arm at amplitude:

- Global phase structure is coarse: 4–5 windows per period; the volume-weighted
  window is 26–60× the 648-cycle refresh in every workload, so on the injected
  schedule no workload is fast-changing relative to the field. Length alone cannot
  carry the hypothesis; the earlier ~5.0k/5.8k/23k "window length" figures refer to
  something else (likely per-layer on-durations) and every table has off-by-one
  1-cycle sliver boundaries (clustered within 2 cycles before counting).
- *Turnover* at a boundary (stopping + starting flow rate over mean rate) dwarfs the
  net step everywhere — e.g. ResNet's first boundary: step +0.03, turnover 1.41 — so
  boundaries re-arrange traffic spatially while the aggregate looks quiet.
- Amplitude is NOT packing-invariant: CV of total rate rises with r (VGG 0.01 at
  r = 1 → 1.09 at r = 32); window length is (±10%).
- Workload ranking, stable across packings — inter-phase (turnover, CV):
  ResNet mildest (max 1.4–1.8) < VGG (2.0–4.0) < DeiT-S (3.2–6.6); intra-phase
  (steady-stretch length): VGG longest > ResNet > DeiT-S. The inter-phase ranking
  matches the pooled DP-gain ordering in all four columns (mean/p99 × below/above);
  the intra-phase ranking does not. n = 3, columns not independent, and matching
  above the floor too hints at a workload confound (e.g. DeiT-S's zero placement
  freedom) — which is exactly why the per-cell hot-link test below is the decisive
  one, with the workload held fixed.

**Relation to C8.** The closed predictor campaign tested spatial and time-integrated
quantities and found none that calls the winner. This is the first temporal
candidate, and task 2 supplies the mechanism the closing rule demands. A positive
result revises C8 openly and gives task 7's schedule a design-time origin; a null
strengthens C8 and the case for online adaptivity. Either is reportable.

## Task 7 — Runtime BL/DP switching on a phase schedule, conditional

**Definition.** The achievable counterpart of task 1's bound: a *phase schedule*, a
per-window table computed offline from the phase-gated oracle's winners, tells the
router which policy to use in each phase window; the router switches at the window
boundaries at runtime. Turns the bound into a measured gain.

**Trigger (both required).** Task 1 shows a large gap between the phase-gated and the
per-cell oracle, AND task 3 shows the refresh-rate control does not move capture. If
either fails the task stays out: with a small gap there is nothing to collect, and if a
fresher field closes the deficit the switch is the wrong mechanism. Without the trigger
this is Paper 2's opening result (temporal, phase-aware selection) and is reserved for it.

**Mechanism.** In the selection step, choose DP or BL by `cycle mod t_period` against
the schedule (one entry per window). DP keeps running during BL windows so its field is
warm when switched in; only the choice of selection function changes. Deadlock freedom
is the routing function's, untouched. ~30 lines; schedule read from a file per placement.

**Runs and gate.** Same 128 below-floor cells, 3 seeds, one arm: 384 runs. Compare
against always-DP and against the task 1 bound; the gain is expected to sit below the
bound since queue state does not follow the switch. Register the predicted fraction of
the bound before running. Report on mean delay; p99 as headline only.

## Task 6 — Second mesh, 7×7×3 (Pathway 2), conditional

All 34 packings fit (max 108 tiles ≤ 147); `DPSIZE = 260` covers 147 nodes
([NoximDefs.h:139](../noxim3d_src/NoximDefs.h)); a ResNet 7×7×3 base table and
`tools/make_7x7x3_accint.py` exist. Against it: `tools/table_link_load.py` (lines 24, 126)
and `tools/table_phase_load.py` (line 105) hardcode 6×6×3, the packing converter has
only 6×6×3 configs (`tools/stage2_dnn_traffic.py:97-131`), and replicating C5/C7 on one
workload is ~1.5–2k sims. Parity caveat: 7×7 is odd×odd, 6×6 even×even, and Stage 1
found parity governs past-knee behaviour; the paper reads only the knee window, which is
the argument for the second mesh being optional. Do only if the reviews ask.

---

## Future work — CiN (compute-in-network): choose the binding term, not just the floor

**Terms.** *Scatter (S)* = a source injects one copy and the network replicates it at a
branch point, instead of the source injecting one copy per consumer. *Reduction (D)* =
partial sums destined for the same accumulator are combined en route instead of all
arriving. PIL/PEL are the peak injection/ejection port loads; PF = max(PIL, PEL) and is
placement-invariant, so neither mapping nor placement can move it — only the dataflow can.

The extension's results make CiN a cross-layer question rather than a throughput one.
Policy value exists only above the port floor, and only where the packing is
**ejection-bound** (E predicts capacity gain at p = 0.018 across 8 populations; at the
same PL/PF band ResNet (8,1,8) eject gives 1.55x where (16,2,8) inject gives 1.05x).
So the binding term decides whether the routing layer has anything to do — and S and D
move the two terms independently.

**Measured headroom, offline from the traffic tables (no simulation).** Per source and
per phase window, 24-57% of injected bytes are replicated copies (mean fanout 1.7-3.4, up
to 23 consumers); per destination, 25-68% of arriving bytes are combinable partial sums
(mean fan-in 1.25-2.70). Applying the ideal of each:

| min-PF pick | binds | PF | PF after S | S gain | regime after S | PEL_D | floor S+D |
|---|---|---|---|---|---|---|---|
| ResNet (16,2,8) | inject | 0.258 | 0.226 | 1.14x | **eject** | 0.119 | 0.167 |
| ResNet (8,2,4) | inject | 0.392 | 0.183 | 2.15x | inject | 0.068 | 0.183 |
| ResNet (32,4,8) | inject | 0.327 | 0.141 | 2.32x | inject | 0.087 | 0.141 |
| VGG (8,4,2) | inject | 0.958 | 0.584 | 1.64x | inject | 0.164 | 0.584 |
| VGG (32,8,4) | inject | 0.760 | 0.543 | 1.40x | **eject** | 0.296 | 0.488 |
| VGG (16,4,4) | eject | 0.943 | 0.943 | none | eject | 0.338 | 0.489 |
| DeiT (8,1,8) | inject | 0.678 | 0.604 | 1.12x | **eject** | 0.329 | 0.465 |
| DeiT (16,1,16) | eject | 0.905 | 0.905 | none | eject | 0.416 | 0.474 |
| DeiT (32,2,16) | inject | 0.773 | 0.531 | 1.46x | inject | 0.312 | 0.531 |

Three readings. (1) **S is a pure win on every injection-bound pick** — seven of seven
gain floor (1.12-2.32x), and three flip to ejection-bound; the ones that flip gain least
in floor and the ones that do not gain most, so neither outcome disappoints. (2) S does
nothing for the two picks that are already ejection-bound, because their floor is PEL.
(3) **Full CiN (S+D) lowers the floor 1.46-2.32x on all nine but drives every one of them
injection-bound**, including the two that are ejection-bound today — because the ejection
side is the more reducible one (46-68% vs 31-57%). Applying every reduction available
would therefore put the design into the regime where this extension shows selection
policy and escape room are both inert.

> **Design rule: apply scatter always; apply reduction only when a lower floor is worth
> more than a routable bottleneck, and never past the point where PEL_D falls below
> PIL_S.** At that point the floor is the lowest available while the bottleneck still
> sits on the links, where DP and DPN can act on it.

The binding term can also be flipped the other way, by concentrating accumulation (fewer
tiles absorbing more partial sums) until PEL exceeds PIL_S. Pairwise merging of the
hottest accumulation groups overshoots — it beats today's floor on ResNet (0.254 vs
0.392, 0.226 vs 0.327) but ends worse on VGG and DeiT — so only selective merging is
viable. That knob is finer than (c,r,s) and sits in the dataflow converter, so it belongs
to the CiN work rather than here.

**What the CiN work has to establish**, given the above is all offline and idealised:
whether a branch point exists on the shared path for the replicated flows (S) and whether
reduction can be done in the router's timing budget (D); what fraction of the ideal
headroom survives those constraints; and the prediction this extension makes — that
flipping a packing to ejection-bound raises DP's gain toward the ejection-bound level
measured here. Scatter is simulatable without router multicast today, as a traffic-table
transformation with proxy tiles re-injecting near the consumer cluster.
