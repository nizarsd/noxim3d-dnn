# Noxim3D — Research Findings: DP vs bufferlevel

Rolling record of the DP-vs-BL selection study on odd-even-balanced routing.
Engineering/perf notes are in [PERFORMANCE.md](PERFORMANCE.md).

Fixed conditions unless stated: routing `oddevenbalanced`, traffic `transpose1`,
Poisson injection, buffer 16, seeds {2, 6, 10}.

---

## Experimental method

- **DP-aware timing** (derived from mesh, single source of truth in
  [NoximDefs.h](NoximDefs.h)):
  - `DP_DWELL = diameter + 3`, `diameter = (X-1)+(Y-1)+(Z-1)`
  - `DP_CYCLE = 2 · nodes · DP_DWELL` (converge + settle)
  - `CINTERVAL = DP_CYCLE` (congestion cost recomputed once per DP reconfiguration)
  - `WARMUP = 3 · DP_CYCLE`, `SIM = 20 · DP_CYCLE`
  - Rationale: warmup must cover DP field warm-up (~1 DP_CYCLE) + network fill;
    3× is comfortably above the real settling time (measured ~2–3× for these sizes).
- **Workflow:** coarse 1-seed knee-finder → 3-seed fine sweep centred on the knee.
- **Caveat learned the hard way:** a coarse grid can *step over a sharp peak*.
  It agreed with the fine sweep for 8×8×3 (peak near a coarse point) but badly
  under-reported 4×4×3 (peak at 0.036 fell between coarse points 0.035/0.040,
  giving +10.9% instead of the true +33%). Always fine-sweep before trusting a peak.
- **NaN gotcha (fixed):** before the odd-even-balanced fix, NaN delay/throughput
  meant a *routing stall*, not a warmup problem — the buggy `routingOddEven1()`
  stalled the network so no packets were received in the measured interval →
  divide-by-zero. Long warmup only exposed it earlier. See
  [PERFORMANCE.md](PERFORMANCE.md) §1. If NaN reappears, suspect routing/deadlock,
  not the timing.
- **DP convergence check:** the cost-to-go field reaches exact hop-distance costs
  (100·hops + accumulated buffer-occupancy congestion) within `hop_distance`
  cycles and holds stable through the dwell window — verified via `-DDP_DEBUG`.

## Reproduction

Runner: [`noximrun_buffer_sweep_parallel.bash`](noximrun_buffer_sweep_parallel.bash)
(or the sequential [`noximrun_buffer_sweep.bash`](noximrun_buffer_sweep.bash)).
Timing is auto-derived from the mesh; everything not set below is left at Noxim
defaults. Invocation template:

```
DIMX=<X> DIMY=<Y> DIMZ=3 \
PIR_LIST="<grid>" \
SEEDS="2 6 10" \                 # coarse knee-finder for 8x8x3 used SEEDS="2"
BUFFER_LIST="16" \
WARMUP_DP_CYCLES=3 SIM_DP_CYCLES=20 \
ROUTING=oddevenbalanced TRAFFIC=transpose1 \
OUTDIR=results_knee_<mesh> JOBS=8 \
bash noximrun_buffer_sweep_parallel.bash
```

Read `OUTDIR/summary_compare.csv` for the DP-vs-BL means (delay reduction %).

Per-mesh PIR grids actually used (coarse locates the knee; the fine sweep gives
the tabulated peak):

| mesh | coarse knee-finder | fine sweep (3 seeds) |
|------|--------------------|----------------------|
| 4×4×3 | `0.030 0.035 0.040 0.045 0.050 0.055 0.060` | `0.036 0.037 0.038 0.039 0.041 0.042 0.043 0.044` (reuses coarse 0.035/0.040/0.045) |
| 5×5×3 | — (swept directly across the knee) | `0.020 0.022 0.024 0.025 0.026 0.028 0.030` |
| 6×6×3 | `0.012 0.015 0.018 0.020 0.022 0.025 0.028 0.030` | `0.018 0.019 0.020 0.021 0.022 0.024 0.026` |
| 7×7×3 | `0.010 0.013 0.015 0.017 0.019 0.021 0.024` | *(not yet run — see Open items)* |
| 8×8×3 | `0.008 0.010 0.012 0.014 0.016 0.018 0.020` | `0.012 0.013 0.014 0.015 0.016 0.017 0.018` |

Seeds: all sweeps used `SEEDS="2 6 10"` **except** the 8×8×3 coarse knee-finder,
which used `SEEDS="2"` (single seed — the 1-seed knee-finder was only needed once
the meshes got large enough to be slow). The 7×7×3 peak is therefore coarse-grid
(3-seed) and still wants a fine sweep to confirm.

## Headline result — size × parity (Z = 3 series)

Peak = best DP delay reduction vs BL near the knee. "Past-knee" = behaviour once
past the congestion knee into saturation.

| mesh | X/Y parity | diameter | knee (PIR) | peak DP benefit | quality | past-knee |
|------|-----------|----------|-----------|-----------------|---------|-----------|
| 4×4×3 | even | 8  | ~0.036 | **+33.1%** @0.036 | fine | reverses (~0.042) |
| 5×5×3 | odd  | 10 | ~0.025 | **+64%**   @0.022–0.025 | fine | wins through |
| 6×6×3 | even | 12 | ~0.020 | **+68.2%** @0.021 | fine | reverses (~0.024) |
| 7×7×3 | odd  | 14 | ~0.014 | **+82.4%** @0.015 | coarse | wins wide (to ~0.021) |
| 8×8×3 | even | 16 | ~0.014 | **+75.8%** @0.014 | fine (3-seed) | reverses (~0.018) |

### Two robust conclusions

1. **Peak DP benefit scales with size/diameter within a parity class.**
   - Even series: +33% (d8) → +68% (d12) → +76% (d16).
   - Odd series: +64% (d10) → +82% (d14).
   - Odd meshes also sit *above* the even trend at comparable diameter (a parity
     boost): odd d14 (+82%) tops even d16 (+76%).

2. **X/Y parity governs past-knee behaviour.**
   - **Odd × odd** meshes (5, 7) sustain DP's win over a *wide* band past the knee.
   - **Even × even** meshes (4, 6, 8) reverse to a DP *loss* just past the knee,
     then converge back toward tied in deep saturation (both policies overloaded).

### Why (mechanism, partly hypothesis)

DP's value is global, multi-hop congestion awareness; BL sees only one hop.
That value grows with (a) path length / diameter, (b) congestion depth, and
(c) path diversity. Larger meshes have more of all three → bigger peak. The
odd/even split is a property of the **odd-even-balanced routing**, whose turn
legality branches on coordinate parity — odd×odd geometries give DP more usable
path diversity past the knee, so it keeps winning; even geometries run out of
alternative paths in saturation and DP's rerouting churn then hurts.

*Confounds controlled:* the size series holds Z = 3 and X = Y, isolating X/Y
parity. The apparent "5×5×3 is an outlier / size doesn't scale" seen early on was
an artifact of comparing a coarse 6×6×3 peak to a fine 5×5×3 peak — it dissolved
once both had fine data.

## Below the knee

At low PIR both policies behave similarly; DP can be marginally *worse* (its
coarser per-cycle direction updates cost a few cycles of latency with no
congestion to route around). DP only pays off from the knee onward.

## Vertical scaling (Z series)

Does increasing **Z** (vertical depth) help DP the way increasing X/Y does? Test:
fix X=Y=5 (odd), raise Z. 5×5×5 has diameter 12 — the *same* diameter as planar 6×6×3.

| mesh | diam | Z parity | peak DP benefit | quality |
|------|------|----------|-----------------|---------|
| 5×5×5 | 12 | odd | **+70.6%** @0.014 | fine, 5-seed |

- **Vertical ≈ planar for DP's peak:** 5×5×5 (+70.6%) ≈ 6×6×3 (+68.2%) at equal
  diameter — diameter drives the peak regardless of *which* dimension supplies it
  (diameter hypothesis in dimension-agnostic form). Node counts differ (125 vs 108),
  so the cross-comparison is interpretive; the 5×5×Z series itself is the clean control.
- **Sharp-peak Z signature (lesson):** the 5×5×5 knee peak is very narrow. The coarse
  1-seed grid (0.012/0.015) stepped over it (read +17% then ~0%) and *mis*-suggested
  "Z suppresses DP"; only the fine 0.001-spaced 5-seed sweep revealed +70.6% at 0.014.
  Vertical congestion transitions abruptly — always fine-sweep in Z.
- Past-knee behaviour of 5×5×5 (odd X/Y) not yet fully mapped — open.

## DP settle window (`-dpsettle`) — less settle is better

`dp_settle` is the idle "hold" phase where DP routes on a frozen converged field
before re-probing/reconfiguring. Now runtime-tunable: **`-dpsettle N`** →
settle = N·dp_pass, dp_cycle = (1+N)·dp_pass (align `-cinterval` to dp_cycle).
**Default is now 0.**

DP-vs-BL delay reduction at the knee, by settle multiple:

| settle k | 3×3×3 @0.05 | 5×5×5 @0.014 |
|----------|-------------|-------------|
| **0** | **+28.8%** | **+74.0%** |
| 1 (old default) | +16.3% | +72.1% |
| 2 | +14.2% | — |
| 3 | −30.0% | — |
| 4 | −42.9% | — |

- **`settle=0` (continuous reconvergence) is best-or-tied everywhere tested; more
  settle only degrades DP** (it routes on an increasingly stale field).
- **Benefit is size-dependent:** small/fast meshes gain a lot (3×3×3 ~doubles the
  reduction), large meshes marginal (5×5×5 +1.9pp). Freshness matters most when
  congestion mixes fast relative to the converge sweep.
- **Implication:** the size/parity/Z results above (all run at settle=1) *understate*
  DP, most at the small end. Large-mesh trends move <2pp, so the parity/Z conclusions
  still hold — the small end just nudges up.
- **Not `CINTERVAL`:** that sets the congestion-sampling period (`cost_to_go`), not the
  reconfigure cadence. Settle lives in the compiled `dp_cycle()/dp_pass()/dp_settle()`
  ([NoximDefs.h](NoximDefs.h)); see [PERFORMANCE.md](PERFORMANCE.md).

## Routing-variant study: turn exclusivity ↔ saturation throughput

Three `oddevenbalanced` (OEB) variants tested, **all deadlock-free** (each is a turn-set
subset/superset of the published baseline), differing only in vertical↔planar turn
**exclusivity** in [`routingOddEvenBalanced`](TRouter.cpp):

| variant | up branch | down branch | planar/vertical coupling |
|---------|-----------|-------------|--------------------------|
| **baseline** (published) | exclusive | coexisting | medium (asymmetric) |
| **modified** (UP-always) | coexisting | coexisting | **max** |
| **modified2** | exclusive | exclusive | **min** |

**Coupling governs saturation throughput, monotonically.** transpose1, 4×4×3, PIR 0.035,
settle=0, absolute **BL delay: modified 290 > baseline 85 > modified2 23** (DP: 135 / 69 / 25).
Less planar↔vertical coexistence ⇒ less flow coupling ⇒ shallower back-pressure trees ⇒ knee
pushed to higher PIR. modified collapses the knee (11–24× worse than baseline on random @0.041);
modified2 pushes it far out (delay still 102 at 0.045 where baseline is 528, modified 1753).

**DP-vs-BL % is misleading in isolation.** modified's headline "+53% DP reduction" came from
degrading BL faster than DP — *both* were 2–3× slower than baseline absolutely. modified2 shows
*negative* DP-vs-BL at these PIRs because it is now **below-knee** there. Lesson: quote **absolute
delay** and re-locate each routing's **own knee** before trusting a DP reduction %.

**Tension — best routing ≠ best DP substrate.** modified2 (min coupling) is the fastest routing
but strips the path diversity DP exploits, so DP has little to optimize (went negative). "Fastest
routing" and "largest DP-vs-BL gap" diverge — directly relevant to choosing routing for DNN
traffic ([STAGE2.md](STAGE2.md)).

**Scope:** measured on **4×4×3 + transpose1 only** (random run lost to a script typo). OEB is
parity/size dependent (above), so generality is unverified. Binaries on disk (gitignored):
`noxim`=modified2, `noxim_ref`=modified, `noxim_base`=baseline. The DP legality mirror
`can_turnOddEvenBalanced` ([DPNode.cpp](DPNode.cpp)) matches the router modulo the documented
source-independence terms (`cz==sz`/`c0==s0`/`c1==s1` dropped/proxied).

### modified2 across sizes — knee shifts right, DP benefit is size-dependent

Knee sweep of modified2 vs the FINDINGS baseline (transpose1, buffer 16, seeds {2,6,10},
`-dpsettle 1`, DP-aware timing per mesh). modified2's knee moves to **higher PIR** on every mesh,
and its DP-vs-BL peak is **size-dependent** (partial — 8×8×3 / 5×5×5 pending):

| mesh | baseline peak | modified2 peak (settle=1) | note |
|------|--------------|---------------------------|------|
| 4×4×3 | +33.1% @0.036 | **negative everywhere** | DP benefit killed (mesh too small) |
| 5×5×3 | +64% @0.024 | +64.5% @0.030 | preserved, knee shifted right |
| 6×6×3 | +68.2% @0.021 | ≥+20% @0.026 (undersampled) | grid gap 0.026–0.032 misses the peak |
| 7×7×3 | +82.4% @0.015 | +74.4% @0.021 | mostly preserved, knee shifted |

**"modified2 kills DP's benefit" (from 4×4×3 alone) does NOT generalize** — it holds only on the
*smallest* mesh; on larger meshes DP's win is preserved, just relocated to a higher knee. Good for
DNN traffic (large meshes). Caveat: the extended PIR grid jumped past the shifted knee (gap
~0.026–0.032), so mid-size peaks here are **lower bounds** pending infill.

### settle under modified2 (5×5×3) — settle=0 best, but match the window

Clean settle comparison, **matched sim window** (sim=39000 for both; cinterval aligned per settle:
settle=0→975, settle=1→1950):

| | peak red% @0.030 | BL delay | DP delay |
|---|---|---|---|
| settle=1 | +64.5% | 343.8 | 121.9 |
| **settle=0** | **+71.5%** | 343.8 (identical) | **98.0** |

**settle=0 wins by ~7 pp** — BL is identical (bufferlevel ignores settle); settle=0's DP delay is
~20% lower (fresher congestion field from more frequent reconfiguration). Confirms "settle=0 best"
for modified2. **Methodology caveat:** compare settles over the **same sim window** — settle=0's
FINDINGS-native timing gives it *half* the sim (dp_cycle halves), deflating its BL and fabricating
a false settle=1 "win" (the raw native-timing numbers showed +44% vs +64%, an artifact).
modified2+settle=0 (+71.5%) also **exceeds** the baseline 5×5×3 peak (+64%, settle=1) — a genuine
DP gain on this mesh. Consequence: the settle=1 knee sweep above **understates** modified2 by
~5–7 pp/mesh.

## Stage 2 — DNN traffic: DP's advantage is a property of the *placement*, not the traffic

First DP-vs-BL results under a DNN-derived traffic table rather than a synthetic
pattern. Subject: ResNet-50 stage-4 bottleneck block, 128×128 crossbars, 8 per tile,
92 tiles on **7×7×3** (62.6% occupancy), `oddevenbalanced` = **modified2**, `settle=0`,
buffer 16, fixed 16-flit packets, `ls = 0.022` (this pattern's own knee — delay 91 at
0.022 against 394 at 0.025). Timing: `SIM=206674`, `WARMUP=14994`, giving exactly 5
whole block passes in the measured window. All runs `-samp 1`.

### The headline number, and the finding that qualifies it

| | BL delay | DP delay | DP-vs-BL | paired t | p | wins |
|---|---|---|---|---|---|---|
| **current placement** (n=30) | 92.53 | 81.63 | **+11.77%** | 2.95 | **0.006** | 22/30 |
| **XY-diagonal placement** (n=30) | 85.87 | 95.23 | −10.90% | −1.97 | 0.059 | 12/30 |

Paired within policy, current → diagonal:

| policy | change | paired t | p | 95% CI |
|---|---|---|---|---|
| bufferlevel | **−7.20%** (faster) | 2.07 | 0.048 | [+0.08, +13.24] cycles |
| **dp** | **+16.65%** (slower) | **−3.34** | **0.002** | [−21.92, −5.26] cycles |

**Changing only the tile→node mapping inverts the sign of DP's advantage.** The
diagonal table is a *node relabelling* of the current one — identical traffic graph,
`pir`, phase windows and total volume — so placement is the single variable.

Pairing is the correct test throughout: both arms share a seed and injection is
open-loop, measured inter-arm correlation r = 0.300. Unpaired Welch on the current
placement gives t = 2.47 against the paired 2.95.

### Not a knee artefact, and not a mistuned DP

- DP is negative at **all three** diagonal load points (0.016 / 0.022 / 0.028:
  −3.09%, −12.17%, −7.13%).
- Both placements sit on the same delay curve — BL 24 → 91 → 878 (current) vs
  27 → 85 → 876 (diagonal) — so the knee did not move despite +49% hops.
- `current` and `diagonal` sit at nearly **equal BL delay** (92.53 vs 85.87) with
  opposite DP outcomes. Congestion level does not explain it.
- Three DP timing configurations tested at ls=0.022, n=10; none beats the default
  (`settle 0`, `cinterval 4998`): `settle 0/ci 2499` +1.79% slower,
  `settle 1/ci 2499` +1.88% slower. So "DP was badly tuned" is excluded.

### Why: DP does not win by exploiting path diversity

A Python port of `routingOddEvenBalanced` ([oeb_path_diversity.py](oeb_path_diversity.py))
enumerates the minimal paths the router admits per flow. DP and BL are *provably
identical* on a flow with one admissible path.

The current placement lands the partial-sum reduction axis **along a mesh axis**:
40.9% of all bytes are pure-Y displaced, and an axis-aligned flow admits exactly one
path (`e0 == 0` returns a single direction). Only **25.5% of bytes** have any routing
choice; the diagonal walk lifts that to 67.2%, at +49% hops.

A 2×2 over (diversity, hops), built by searching tile→node permutations for target
coordinates ([search_placement.py](search_placement.py)), n=10 per new cell:

| cell | diversity | hops | BL | DP | DP-vs-BL |
|---|---|---|---|---|---|
| current | 25.5% | 3.33 | 91.08 | 79.88 | +12.30% |
| **CELL A** | 25.5% | **4.96** | 138.37 | 90.62 | **+34.51%** |
| **CELL B** | **67.2%** | 3.33 | 39.66 | 38.48 | +2.97% |
| diagonal | 67.2% | 4.96 | 85.29 | 95.67 | −12.17% |

Marginal effects on delay: hops 3.33→4.96 costs DP +57.4% but BL **+71.1%**;
diversity 25.5%→67.2% saves DP −21.3% but BL **−45.5%**.

**Longer paths hurt bufferlevel more than DP** (lookahead is worth more when routes
are long), while **path choice helps bufferlevel about twice as much as DP**. The
diagonal placement supplied both at once and BL's diversity gain outweighed DP's hop
gain — hence the inversion. There is a real interaction: extra hops *help* DP when
choice is scarce (+12.3 → +34.5) and *hurt* it when choice is plentiful
(+2.97 → −12.17).

⚠ **Attribution caveat.** The searched cells hit their (diversity, hops) targets by
scattering layers: intra-layer tile spread is 3.03 (current), 4.04 (diagonal), 4.91
(A), 4.97 (B). Layer locality therefore varies across every contrast and is a third,
uncontrolled variable. It does not *order* the outcomes (+12.30, −12.17, +34.51,
+2.97 sorted by scatter shows no trend), but the single-variable readings above are
not airtight. A locality-constrained search is the fix, and may not have a solution.

### Throughput is invariant; the entire effect is in delay

All eight cell × policy means span **0.014235–0.014353 flits/cycle/IP (0.83%)** and
242,028–242,975 delivered flits (0.39%), while delay spans **260%** (38.48 → 138.37).
Nothing is saturated and no policy accepts more traffic than another, so the
acceptance-rate confound that invalidates the 6×6×3 `ls=0.20` delay figure (see
Stage 2 handover) is absent here. Note this contrasts with Stage 1's 6×6×3 result,
where the only solid finding was a *throughput* one (+6.8% at saturation).

### 6×6×3 (n=5, indicative only)

DP is negative under **both** placements (−2.60% current, −6.12% diagonal); its
current placement already sits at 45.3% diversity — the diverse end — and the
diagonal there moves hops only +9%. DP sd is 14.33 vs BL's 6.75, so DP is also the
erratic arm on this mesh. Its knee is at **ls ≈ 0.013** (steepest rise 0.012→0.014,
2.75×); the older `results_dnn_scale_sweep` grid was entirely past it.

### Implementation detail worth knowing when reading these numbers

`dpProcess` performs **one Bellman-Ford relaxation per `dp_clock` tick** — cost
propagates one hop per tick, which is why `dp_dwell = diameter + 3` is propagation
time, not margin. But congestion is snapshotted **once per `dp_pass`**
(`frozen_local_cost` at `phase == 0`) and reused for all `num_dst` destination fields:
at 7×7×3 that is one sample per 2499 cycles, so destination 146's field is built from
buffer occupancy 2482 cycles old. Also note the sweep scripts' `DP_CYCLE = 2·nodes·dwell`
matches `dp_cycle()` only at `settle=1`; at the actual `settle=0` the real period is
half (2499, not 4998), so `WARMUP` is 6 real DP cycles rather than the 3 claimed.
Left as-is deliberately — conservative, and every result above is on it.

### The mechanism: a funnel at the reduction sinks (6×6×3, n=30)

**Why DP failed on DNN traffic.** Each of the following was tested and excluded as the
cause: DP convergence lag (4× `dp_clock` — no gain), congestion-sampling staleness
(`-cinterval` 100–648 — no gain), phase transitions (measuring only conv2's stationary
interior, cycles 10k–25k — no gain), path diversity (OE + diagonal gives 83% of bytes a
routing choice and 10.3 paths/flow — still zero), and hop length (4.96 vs transpose1's
6.20). What remained is **where** the congestion sits.

conv2's reduction sends 18 tiles → 1 accumulator. Those two accumulators take **15.2% of
all traffic each** (4 nodes carry 55%), and the base placement put them at mesh-edge
coordinates (4,0,0) and (4,0,1) — 4 and 5 faces instead of 6, two of them receiving
nothing. Under minimal routing the arrival face is fixed by where the sender is, not
chosen, so **no selection policy can rebalance the last hop**. `DPTRACE` confirms it: the
busiest input link into node 4 was full **73.5% of cycles** (mean queue 12.61/16) while an
interior control link never queued a single flit (0.00 occupancy).

**The test** — swap the two accumulators onto interior nodes (1,1,1) and (3,4,1). A pure
transposition: identical traffic graph, rates and phase windows, asserted in the generator.
`ls=0.026`, OE, `-cinterval 648`, 3 block passes, n=30 paired seeds:

| placement | BL delay | DP delay | DP vs BL | t | DP wins |
|---|---|---|---|---|---|
| edge (4,0,0)/(4,0,1) | 161.67 | 169.80 | +5.03% | 0.65 | 15/30 |
| **interior (1,1,1)/(3,4,1)** | 191.93 | **136.35** | **−28.96%** | **−3.51** | 23/30 |

p ≈ 0.0015. Effect and significance grew monotonically with seeds (−17.4%/t=−1.11 at
n=12 → −25.7%/t=−2.73 at n=22 → −29.0%/t=−3.51 at n=30), unlike the false positives below.
**Double dissociation:** the same swap makes DP **19.7% faster** (t=−3.05) and bufferlevel
**18.7% slower** (t=+2.54). Edge placement pens unroutable congestion in a corner; interior
placement makes the same congestion routable and in everyone's way — DP exploits it,
bufferlevel cannot. Throughput is invariant (0.01704–0.01714) as everywhere else in Stage 2.
This is the **first genuine DP win on DNN traffic**.

**Placement must be scored on routing-admitted arrival faces, not geometry.**
`oe_arrival_faces.py` enumerates every admissible minimal OE path and records the final
hop. Its prediction for node 4's busiest face is 0.297 flits/cyc against **0.274 measured**
by DPTRACE (8%); a naive "one face per displaced dimension" estimate gives 0.118 — wrong by
2.3×. Scored correctly, the conv2 swap improved worst-face/mean-face **3.68× → 2.33×** and
**3.72× → 2.07×**. A second swap moving conv1's accumulators (fan-in 3–4, 25% of traffic)
to interior nodes was scored **3.89×/3.90× — no better than the 3.23×/4.00× it replaced**,
because OE admits only 4 of node 52's 6 geometric faces. Measured outcome: **+2.61%,
t=0.45 — nothing**, as predicted before the runs completed. The geometric metric would have
predicted a gain and been wrong.

**The tail moves further than the mean.** Max delay, interior placement:
DP 5,723 vs BL 9,709 — **−41.1%, t = −4.10, 25/30 seeds**, more significant than the mean
effect. And the largest single effect in the set is what interior placement does to
*bufferlevel's* tail: **+61.5%, t = 5.11**, with only 4/30 seeds improving. Caveat: max
delay is one extreme order statistic per run and right-skewed (sd 2,487–3,860), so the
t-test is indicative only — medians agree (5,243 vs 8,783) and the win counts are
distribution-free, but a Wilcoxon signed-rank test is the correct one and has not been run.

### The −29% is a past-knee number and does not generalise (n=30 at ls 0.020)

| load | placement | BL | DP | DP vs BL | t |
|---|---|---|---|---|---|
| 0.020 | edge | 32.96 | 34.42 | **+4.42%** | 2.45 |
| 0.020 | interior | 31.84 | 31.22 | −1.94% | −1.08 |
| 0.026 | edge | 161.67 | 169.80 | +5.03% | 0.65 |
| 0.026 | interior | 191.93 | **136.35** | **−28.96%** | −3.51 |

Below the knee the placement fix does not let DP overtake bufferlevel. But the placement
effect **on DP itself** is the most significant result anywhere in this study:
interior − edge at ls 0.020 is **−9.29%, t = −6.88** (27/30 seeds — variance is tiny down
here, sd ≈ 2 against ≈ 55 at 0.026), against bufferlevel's −3.41% (t = −1.70). So interior
placement reliably helps DP at *both* loads; what load changes is whether that is enough to
overtake bufferlevel. Note the **double dissociation does not reproduce at 0.020** —
interior placement helps bufferlevel too (−3.4%) rather than hurting it (+18.7% at 0.026),
so "interior hurts BL" is itself past-knee. Peak arrival-face load is 0.146 flits/cycle at
0.020 versus 0.300 at 0.026: **the funnel has to be loaded for un-funnelling it to pay.**
All of this coheres with the Stage 1 result that DP pays off at or above the knee.

**Claim to use: *"past the knee, placement decides whether DP can win"* — never a bare
−29%.**

**Knee location, interior placement** (bufferlevel, 3 seeds, same config): 18.52 @0.014 →
31.84 @0.020 → 47.40 @0.023 → 63.49 @0.024 → 70.05 @0.025 → **191.93 @0.026**. The elbow
sits between **0.025 and 0.026** — a 2.74× step against ≤1.5× everywhere below, and the
first point where delivered throughput stops tracking offered load. So 0.026 is *just* past
the knee, not deep saturation, which is the right operating point for a DP comparison.
Relocating the accumulators moved *who wins past the knee*, **not where the knee is** —
consistent with the funnel being a latency mechanism, not a capacity one.

**Remaining caveat.** A fan-in-3 sink cannot fill six faces however it is placed;
conv1-type hotspots need a wider phase window or a split reduction (tree, 18→6→2→1, max
fan-in 3, ~44% more bytes), not relocation.

## Open items

- **Routing-variant generality** — modified2 (both-exclusive OEB) only tested on transpose1
  4×4×3; sweep {random, transpose, hotspot, bit-reversal} × {odd/even, Z-heavy meshes} to each
  routing's **own knee**, reporting absolute delay **and** DP-vs-BL, before adopting a routing
  for DNN traffic. Decide the target metric first (latency/throughput vs DP gap).
- **Finish the modified2 knee sweep** — 8×8×3 + 5×5×5 pending; re-run at **settle=0** (true
  numbers, ~5–7 pp higher) and **infill PIR 0.026–0.032** to pin the mid-size peaks (6×6×3, 7×7×3).
- **7×7×3 peak is coarse-only** (+82.4%) — fine-sweep 0.013–0.016 to confirm.
- **Deep-saturation reversal point of odd meshes** — 5×5×3 only swept to 1.2×
  knee; push further to locate where it finally reverses.
- **Isolate DP-vs-routing:** re-run one odd/even pair under a parity-agnostic
  routing (e.g. `fullyadaptive`) to confirm the parity split is routing-induced.
- **Mechanism test:** instrument per-link load-balance (coefficient of variation)
  to directly test the path-diversity explanation for the even-mesh reversal.
- **(Stage 2) Locality-constrained placement search** — CELL A/B confound layer
  scatter with the variable they were built to isolate. Re-search with an
  intra-layer-spread term pinned near current's 3.03; if no solution exists at
  hops 4.96, that itself says hops and locality are not independently controllable
  on this mesh and the 2×2 as posed is unrealisable.
- **(Stage 2) n=30 on CELL A** — the +34.51% that overturns the "hops hurt DP"
  reading is the least-replicated number in the section (n=10). 20 runs.
- **(Stage 2) Validate the routing port** — `oeb_path_diversity.py` reproduces the
  router by construction and by the axis-aligned single-path argument, but has
  **not** been cross-checked against simulator hop traces. Do this before any
  path-count number goes in a paper.
- **(Stage 2) Deadlock argument** — the claim that all three OEB variants are
  deadlock-free rests on "turn-set subset/superset of the published baseline",
  which is only valid for a **subset**. `modified2` (in use) is the restrictive
  variant so is plausibly safe; `modified` is a superset and its claim is
  unjustified. No deadlock detector is compiled in (`TRouterTCandNormal.cpp` is not
  in the Makefile), so delivery statistics are the only evidence — clean at the
  knee, but 6×6×3 `ls=0.20` shows max delay at 98.7% of the sim window in all 6
  runs (saturation starvation, packets delivered — not deadlock, but that point's
  delay figure is uninterpretable).

## Log

- Size × parity (Z=3): 4×4×3, 5×5×3, 6×6×3, 7×7×3, 8×8×3.
- Z series: 5×5×5 (diameter 12, vs planar 6×6×3).
- Settle sweeps: 3×3×3 and 5×5×5 at the knee (k=0..4) → `settle=0` best; default set to 0.
- Raw CSVs in `results_knee_*` (gitignored — regenerate). Peaks/knees as tabulated above.
- **Stage 2 (DNN traffic, 7×7×3 ResNet-50 block):** `results_block_ls022_n30` (current
  placement, n=30), `results_diag_ls022` (diagonal, n=30 + 0.016/0.028 probes),
  `results_hopdiv` (CELL A/B, n=10), `results_knee_6x6x3` (6×6×3 knee finder),
  `results_diag_6x6x3` (6×6×3 placement pair, n=5), `results_ci2499` /
  `results_settle_grid` (DP timing negatives). All gitignored — the runner scripts
  `run_*.bash` are the record and each carries its timing derivation.
