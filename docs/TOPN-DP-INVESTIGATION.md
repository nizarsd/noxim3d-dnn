# Top-N-sinks DP — Turn 1 investigation

Per [TOPN-DP-PROMPT.md](TOPN-DP-PROMPT.md). All facts verified in source or measured
this session (2026-09-16); measurement artifacts under `results_ext/`. The same design
is specced as task 3 of [EXTENSION-PATHWAYS.md](EXTENSION-PATHWAYS.md) ("sink-list
hybrid"), converged on independently before this prompt was read; differences are
flagged in §9.

## 1. DP relaxation structure — clean restriction

Destinations are processed strictly one at a time: `dst_id = (phase / dp_dwell()) %
dp_no_dst()` ([DPNode.cpp:24](../noxim3d_src/DPNode.cpp)). Within a window the
relaxation touches only `cost_mem[dst_id][*]`, `legal_cache[dst_id][*][*]` and the
anchor test `local_id == dst_id` ([DPNode.cpp:49-127](../noxim3d_src/DPNode.cpp)).
The only cross-destination state is `frozen_local_cost[]`, the congestion sample
re-latched at every window start ([DPNode.cpp:49-52](../noxim3d_src/DPNode.cpp)) —
shared input, not shared computation. The untagged DP links are coherent because all
nodes hold the same `dst_id` ([DPNode.cpp:80-81](../noxim3d_src/DPNode.cpp)); any
subset sweep preserves this as long as every node derives the same list. **A
destination subset is a clean restriction.**

## 2. DP cycle scaling — linear in destination count

`dp_pass() = dp_dwell() × dp_no_dst()` with `dp_dwell() = ceil(diameter /
DP_CLOCK_MULT) + 3` ([NoximDefs.h:252-256](../noxim3d_src/NoximDefs.h)); settle
defaults to 0 in all Stage-3 runs, so cycle = pass = 6 × 108 = 648 at 6×6×3. The
cycle is **linear in the number of destinations swept**: N sinks → N × 6 cycles
(15 → 90, 24 → 144). DPSIZE (260) only sizes arrays. Supporting measurement: the
knee-load coherence time of hot-link occupancy is 50–160 cycles
(`results_ext/` ACF analysis), so N ≤ ~25 puts the refresh inside the window that
648 misses — the freshness motivation is measured, not assumed.

## 3. Table layout — no remap needed

Router side: `routing_directions[DPSIZE][DIRECTIONS]`
([TRouter.h:193](../noxim3d_src/TRouter.h)), written per live destination at the
window end ([TRouter.cpp:379-385](../noxim3d_src/TRouter.cpp)), read by full `dst_id`
([TRouter.cpp:586](../noxim3d_src/TRouter.cpp)). DP side: `cost_mem[DPSIZE][6]`,
`legal_cache[DPSIZE][6][6]` ([DPNode.h:26-32](../noxim3d_src/DPNode.h)). Keeping full-
size arrays indexed by real node id and simply never visiting unlisted rows requires
**nothing** — no sparse index, no remap. Unvisited rows stay at their reset values
(−2 / BIG_VALUE), which the selection loop already skips as non-matching. (True
hardware would shrink the arrays; the simulator need not model that.)

## 4. Per-packet policy switch — one line, same turn model

Selection is dispatched once per packet in `selectionFunction`; DP's selector walks
the ranked row and intersects with the routing function's admissible set, with a
fallback at [TRouter.cpp:595](../noxim3d_src/TRouter.cpp). Minimal change: at the
top of `selectionDP`, if the packet's `dst_id` is not in the sink set, `return
selectionBufferLevel(directions);`. BL's inputs (`free_slots_neighbor`) are advertised
unconditionally ([TRouter.cpp:340-344](../noxim3d_src/TRouter.cpp)), so they are live
under `-sel dp`. **Deadlock freedom is unaffected**: both selectors choose only among
`directions`, the admissible set the routing function computed under the one turn
model; selection never adds a turn ([TRouter.cpp:577-596](../noxim3d_src/TRouter.cpp)).

## 5. Sink identification — one-liner from the run table

Volume rank per destination = Σ over its inflow rows of pir × (t_off − t_on), read
from the run's own traffic table (the generated tables already carry mesh node ids —
`gen_tables_generic.py` writes `perm[s], perm[d]`, so no placement translation is
needed at run time). Computed this session in `results_ext/phase_score/` (script
inline; promote to `tools/rank_sinks.py` in Turn 2). No pre-existing ranking script
was found; the §28 ejection-normalisation and hot-tier lists rank links/ports, not
sinks, and were not reused.

## 6. Hot-tier sizes (measured 2026-09-16)

Bytes-coverage N per table (N@80% / N@95%, of total sinks):

| table | sinks | N@80% | N@95% |
|---|---|---|---|
| ResNet (8,2,4) — prompt ref | 91 | ~40 | 57 |
| VGG (8,4,2) — prompt ref | 104 | ~42 | 86 |
| DeiT-S (16,1,16) — prompt ref | 64 | 14 | 45 |
| ResNet (8,1,8) | 89 | 15 | 42 |
| ResNet (16,2,8) min-PF | 45 | 17 | 27 |
| VGG (32,8,4) min-PF | 31 | 13 | 26 |

Two of the prompt's three reference points (ResNet (8,2,4), VGG (8,4,2)) are the
FLAT, injection-bound tables — and also the ones where the traced runs show near-zero
hot-link queues and DP ≈ BL (gain 1.00 / 1.06). The concentrated tables are the
ejection-bound ones and every global min-PF pick. Sweep range from the data:
N ∈ {1, 2, 4, 8, 15, N@80%, N@95%, all}.

## 7. Double-buffering — not needed; the premise is wrong

There is no torn read to fix. `routing_directionsUpdater` is an `SC_METHOD` on the
NoC clock ([TRouter.h:128-130](../noxim3d_src/TRouter.h)); DP publishes at
`phase % dwell == dwell−2` ([DPNode.cpp:116](../noxim3d_src/DPNode.cpp)) and the
router latches one NoC cycle later at `dwell−1`
([TRouter.cpp:378](../noxim3d_src/TRouter.cpp)); `dp_dir` is stable across that
boundary and the six-entry row write completes atomically within the method. A
shorter cycle changes write frequency, not this ordering. `dir_tbl[2]` + active
index is unnecessary; Turn 2 is NOT gated on it. (Same conclusion recorded in
EXTENSION-PATHWAYS.md §3.1.)

## 8. Regression targets

- **transpose1 bit-identical**: the Stage-1 gate (CLAUDE.md validation rule;
  FINDINGS.md Stage-1 section). Flag absent must be bit-identical at HEAD.
- **Full-DP and BL references at the knee** for the three prompt points exist twice:
  the canonical hill results (`res_f1`, `res_f2`, `res_esxd` in
  `results_stage3/mapping_pilot/pool1000/hill/`, read-only) and this session's
  bit-comparable reruns with traces (`results_ext/trace_runs/res_{f1,f2,esxd}.txt`),
  8/8/16 placements × knee rungs × **3 seeds**, deterministic per seed.
- **Gap to the prompt**: no n = 30 references exist for these points; the study
  standard is 3 seeds (paired, deterministic). Turn 2 should either run at 3 seeds
  against the existing references or first extend the references to n = 30
  (~an extra 2×128×27 runs). Flagged as the one open protocol decision.

## 9. Deltas from the prompt (for reconciliation)

- Flag: EXTENSION-PATHWAYS task 3 specs `-dpsinks N` with the list ranked at startup
  from the traffic table; the prompt specs `-dptopn <N> <sinkfile>`. The sinkfile
  form is better for auditability — adopt it, generated by `tools/rank_sinks.py`.
- Semantics agree after 2026-09-16 correction: flag absent = current behaviour
  (bit-identical gate); N = 0 = pure BL via fallback; N = all ≈ full DP. Note
  N = all is NOT bit-identical to `-sel dp` unless the sinkfile order reproduces
  0..107: the sweep order changes which window serves which destination, shifting
  RNG-free but time-dependent field ages. Expect statistical, not bit, identity —
  the prompt already allows this (Turn 2 §2, "report the delta and its cause").
- Registered readings to carry over from EXTENSION-PATHWAYS task 3: recover the
  destination-gated oracle headroom where it is large (+7.0% ResNet (8,2,4),
  +4.7% DeiT-S), hold always-DP where it already wins (ResNet (8,1,8) guard), and
  the coherence-window rationale for why freshness should pay at small N.

## Verdict

**READY** for Turn 2 (different session, per the prompt), with one protocol decision
open: 3-seed against existing references vs extending references to n = 30.

## Turn 2 build — DONE 2026-09-16, all gates passed

Implemented as approved: `-dptopn N sinkfile` (~45 lines over NoximDefs.h, main.cpp,
CmdLineParser.cpp, DPNode.cpp, TRouter.cpp) + `tools/rank_sinks.py`. Semantics:
absent = pure DP; 0 = DP idle, all-BL fallback; N = DP for the listed sinks, BL else.
`dp_pass()` = dwell x sweep size (derived, nothing hardcoded); cinterval untouched.

- **Gate 1, flag absent:** bit-identical to the pre-change binary on a below-floor DP
  cell, a BL cell, and `transpose1` DP (full stdout diff).
- **Gate 2, N = 0 vs `-sel bufferlevel`:** every statistic bit-equal (mean 28.6892,
  thr 0.0166157, p99 189); only config-echo lines differ. Stronger than the
  statistical identity the prompt allows.
- **Gate 3, N = all(89) vs pure DP:** statistically consistent (mean 29.97 vs 29.88,
  thr equal, p99 208 vs 244 at n = 1); expected — the volume-ranked sweep order and
  the 534- vs 648-cycle pass shift field ages, so bit-identity is impossible by
  design (§9).
- **Period check, N = 15:** DPSYNC publish trace shows the 15-sink rotation
  (39, 96, 71, … mesh ids) recurring at exactly 90 cycles.

- **Convergence check (DP_DEBUG, watch sink 39, N = 15):** at the three farthest
  nodes (8–9 hops), mincost settles by tick 9–10 of the 24-tick window and is
  constant through the publish tick — 102/102 window×node checks converged by
  publish; settled values are exact hop costs. The publish margin under `-dptopn`
  is as safe as under pure DP. Debug defines reverted; clean rebuild re-verified
  bit-identical (gate 1 repeated).

Artifacts: `results_ext/topn/` (references, gate outputs, pilot sinkfile, dbg39
trace). The N sweep (sim tests) is the pending decision.

## Probe results — 2026-09-16, 528 runs, 0 failures (`res_probe.txt`)

Two-set probe, arms a (`-dptopn N -cinterval 648`: assignment only, sink fields at
today's freshness) and b (`-cinterval` = rotation period: assignment + freshness),
8 placements × knee rungs × 3 seeds each, against the traced-batch BL/DP baselines.

**ResNet (8,1,8), ejection-bound, N = 15 (period 90): the hybrid beats always-DP.**
Pooled over the 32 knee cells — a/DP 1.15× mean, 1.26× p99; b/DP **1.20× / 1.33×**;
b/BL 1.64× / 1.94×. At the deep knee (k 0.95): DP 159.4 → a 129.2 → b 121.0 mean
(2562 → 1940 → 1818 p99), 6/8 placements. Assignment carries most; freshness adds a
consistent ~4% mean / ~6% p99 on top (b − a), exactly the coherence-window
prediction. Light rungs level, as expected.

**ResNet (8,2,4), injection-bound, N = 40: null — the +7.0% destination-gated
headroom did NOT materialise.** Pooled a/DP 1.00× mean, p99 0.96× (slightly worse);
small mid-ladder wins, losses past the knee. The spatial-oracle estimate
over-promised exactly where the mechanism says the network is empty; the live run
corrects it. (The single smoke cell's big win was seed/placement luck.)

**Reading.** The hybrid improves where steerable congestion exists (in-network
queue mass), and that room is predictable at design time from the packing's
binding: 6 of 9 per-density min-PF picks and ALL THREE global min-PF picks are
ejection-bound (ResNet (16,2,8), DeiT-S (16,1,16), VGG (32,8,4)); the inert cases
are the three inject-bound cells (ResNet c8/c32 row-compressed, VGG c8). Design
rule: sink-list hybrid on ejection-bound packings; plain BL on injection-bound
ones, where the bottleneck is pre-network (source port at 1 flit/cycle, hot-link
queues 0.05 flits, no backpressure path for selection to act through).

Throughput-stat note: `getThroughput` divides by the count of nodes that received
anything (TGlobalStats.cpp:294-300); the hybrid reaching a few extra low-volume
sinks inside the window lowers the reported per-node figure while delivering MORE
flits. Compare delivered counts, not this stat.

## DeiT ES cross + mechanism checks — 2026-09-16

**DeiT cross (288 runs, `res_deit_cross.txt`): double null.** Hybrid = DP on mean on
both ES arms (maxES arm-b 1.02× is noise); minES p99 5–7% worse. maxES does NOT
unlock the hybrid on DeiT — no stacking.

**Three zero/low-cost checks that re-aimed the mechanism:**
1. *Hot-link anatomy*: on bf (the winner) the hot link is the LAST HOP into a top-2
   accumulator in 7/8 placements — steering rebalances the ARRIVAL FACES of interior
   accumulators (consistent with the arrival-face and E findings). On f1/f2/esxd the
   hot links are transit. This INVERTS the first-guess "last hop unfixable" reading.
2. *Hot-tier width* (links within 50% of PL, offline model): bf median 4 (2–6),
   f1 median 5, DeiT median 13 (4–16). The discriminator: queue mass present AND a
   narrow tier with cool neighbours → hybrid pays; wide warm region (DeiT) or no
   queues (inj-bound) → inert.
3. *(16,2,8) cc12 preview* (12 runs, 3 seeds): the recommended design has the most
   concentrated structure yet (tier 2–5, top-5 share to 0.48); hybrid beats DP ~14%
   mean on m1, holds m2's mean with a noisy tail. Guard plausible, not yet proven.

**List-choice bound (user question):** no sink list can rescue injection-bound
packings — always-DP is the superset of every list and it ties BL there; the queue
stands before the first routing decision. Hot sources DO scatter off-list (bf top
sources send only 31% of bytes to the top-15; f1's 17.5%-source sends 5% to the
top-40) — irrelevant where the network is empty, and on bf the win never needed
them. Byte-ranked sinks == hot-tier contributors on ejection-bound packings
(verified on bf); rank-by-hot-tier-contribution is only a sanity check if a future
packing disagrees.

**Arm-a retirement:** b ≥ a everywhere the hybrid wins (bf pooled 47.7/566 vs
50.0/598; cc12 both placements); a's only edges are marginally-less-bad tails in
the inert regime. Arm a survives as a knee-rung spot check only.

## Campaign (launched 2026-09-16, `results_ext/topn/campaign.bash`, stages A–I)

A: VGG (32,8,4) knee probe. B: its below-floor ladder, BL/DP/hyb-b + a-spot, N=13
ci78 — **registered tier prediction** (`results_ext/vgg3284/tier_prediction.txt`):
widths 5–12 median 8, intermediate → modest pooled gain, narrow-tier placements
(4002, 4005) gain most, tier≥10 null. C: bf N-ladder {2,4,8,15,24,40,89}.
D: bf ci-ladder {45,90,162,324,648} at N=15. E: cc12 × 10 seeds (N=17 ci102).
F: VGG (8,4,2) above-floor guard (N=42 ci252). G: bf headline to n=10.
H: DeiT f3 (8,1,8, N=27) + f4 (32,2,16, N=16) — packing-vs-workload test of the
DeiT null. I: N=all vs DP at n=27. ~2,400 runs. The cross-workload regime table
(8 packings × 3 workloads: offline predictors vs measured gain) is the closing
analysis once A–I land.

## CAMPAIGN RESULTS — 2026-09-16, all stages complete, 0 failed runs

**Headline, after the n = 10 corrections (user's challenge on N = 24 upheld).**
3-seed values inflate (N = 15: 1.32× → 1.08×; N = 2: 1.43× → 1.05×), but the
ladder's best point SURVIVES scale: **N = 24 (90% byte coverage, 144-cycle
rotation) beats always-DP 1.19× mean / 1.24× p99 at bf's deep knee, n = 10**,
carried by large rescues on half the placements (wins 4/8). The N curve rises
through coverage (1.05 → 1.08 → 1.19 at N 2/15/24) and collapses to DP at
N = all — so freshness alone (small N) is nearly free but harvests little, and
the gain needs freshness AND near-full coverage together. Everywhere else the
hybrid statistically matches always-DP while sweeping 4.5–43× fewer
destinations — the power/storage result — with small tail costs where inert.

Per stage (gain = pooled-over-cells DP / hybrid; >1 = hybrid better):

| stage | packing (binding) | seeds | hyb/DP mean | hyb/DP p99 | note |
|---|---|---|---|---|---|
| G | ResNet (8,1,8) k0.95 (ejc) | 10 | **1.08** | **1.06** | the one real gain |
| G | ResNet (8,1,8) k0.75 | 10 | 1.01 | 1.04 | tie |
| E | ResNet (16,2,8) cc12, above floor (ejc) | 10 | 1.01 | 0.93 | mean tie; **C7 spread compression retained** (8.2× vs DP 8.6× vs BL 64×); 7% tail cost |
| B | VGG (32,8,4) 4 rungs (ejc) | 3 | 0.91 | 0.94 | loses at knee; per-plc 0.56–1.32; registered tier prediction PARTIALLY failed (median-8 tier behaves wide) |
| H | DeiT (8,1,8) (ejc) | 3 | 1.01 | 0.98 | null (zero placement freedom) |
| H | DeiT (32,2,16) (ejc) | 3 | 0.99 | 0.99 | null — DeiT null on ALL THREE packings: workload term is real |
| — | DeiT (16,1,16) ES cross (ejc) | 3 | 1.00–1.02 | 0.93–0.99 | null |
| — | ResNet (8,2,4) probe (inj) | 3 | 1.00 | 0.96 | tie, mild tail cost |
| F | VGG (8,4,2) above floor (inj) | 3 | 0.97 | 0.94 | small loss |
| C | bf N-ladder {2..89} | 3→10 | — | — | at n = 10 (N 2/15/24): 1.05/1.08/**1.19×** mean, 1.07/1.06/**1.24×** p99 at k 0.95 — rises with coverage, best at N@90%, collapses to DP at N = all ✓; the 3-seed "N = 2 suffices" was noise |
| D | bf ci-ladder | 3 | — | — | best at ci 90 ≈ the coherence prediction; differences within noise |
| I | N = all vs DP, n = 27 | 27 | — | — | statistically identical (49.5 vs 49.7, sd ~7) ✓ |

**Joint gating closes the family.** The (destination × phase) oracle adds ≤1.3
points over destination alone (bf +2.0, f1 +8.3, f2 +2.4, esxd +4.8% vs the
per-cell oracle), and the spatial component was already shown hollow live (f1's
+7.0% → 1.00×). **No static gating of the BL/DP choice — by time, destination, or
both — recovers the below-floor residue.** The strongest form of C8 yet, and the
measured motivation for state-dependent online adaptation (Paper 2).

**Design rule, final form.** Sink-list hybrid at small N on ejection-bound
packings with a NARROW hot tier of accumulator arrival faces (bf-like): matches
DP with a 6–54× shorter rotation and N-row table; N is insensitive across 2–40,
so N = a handful of top accumulators suffices. Injection-bound or wide-tier
(DeiT, VGG (32,8,4)-at-knee) packings: keep plain BL (N = 0); the hybrid is
inert-to-slightly-harmful in the tail there. Tier width is the best offline
discriminator but its threshold sits below 8 — between bf's 4 and VGG's 8 —
and is NOT yet predictive at the midpoint (the registered VGG prediction
partially failed).

## N@90 coverage retests — 2026-09-16 evening

**VGG (32,8,4) knee at N = 22 (90% coverage, ci 132), n = 10 both arms: the loss
is GONE — hyb/DP 1.01× mean / 1.00× p99** (per-placement 0.96–1.16, tight).
Scenario 2 of the registered branches: the N@80 loss (0.87× at this rung) was
under-coverage — 20% of bytes under BL fallback crossing a congested tier — and
coverage removes the harm while the median-8 tier leaves nothing to harvest.
**DeiT ES control at N = 25 (n = 3): still null** (1.01× / 0.96×) — coverage does
not rescue DeiT; the divertibility term is confirmed.

**Design rule, two-condition form:** coverage (N@90 inside the ~150-cycle
coherence window) + freshness buys SAFETY — parity with always-DP at a fraction
of the sweep; a NARROW arrival-face tier additionally buys GAIN (bf: 1.19×/1.24×
at N = 24). Packings whose N@90 × 6 exceeds the window (flat sink tables, and
both inject-bound picks) don't qualify and keep plain BL. Viability is checkable
offline from the table alone.

## N@90 retests + the mapping-metric check — 2026-09-16 late

**cc12 (ResNet (16,2,8), the recommended design) at N = 23, n = 10: gains.**
1.07× mean over DP (was 1.01× at N = 17), tail cost shrunk to 0.95×, and spread
compression BEATS DP's own (5.9× vs 8.6× vs BL 64×). **f4 (DeiT 32,2,16) at
N = 25: still null** (0.98×/0.97×) — DeiT null at its sweet spot on all
packings; consistent mean-tie with a small recurring p99 cost (5/5 populations
≤ 1.0) → non-qualifying packings should run plain BL, not a small-N hybrid.

**SinkES pre-validation: NULL WITH WRONG SIGN — killed before the climb.**
SinkES (byte-weighted reducible arrival-face skew of the top-N sinks, offline
from the route model) vs measured hyb/DP gain at high coverage: bf n = 8
r = −0.57 / ρ = −0.71 (registered direction was positive); VGG (32,8,4) has
almost no metric variance (0.01–0.06). Interpretation: static room anti-predicts
because DP's 648-cycle field exploits persistent skew too — the hybrid's edge is
freshness, so its gain lives where face skew changes FASTER than DP's refresh,
a temporal, runtime-only quantity. Face-count census agrees: the winning bf
placements are NOT interior-sink (0/8 both-top2 at 6 faces), and the two
accidental interior pairs (v3284 *_4004, tier 12) tie. **The mapping
re-engineering question closes as: no offline mapping metric predicts hybrid
gain; the chain stays min-CC + PL guard; C8 extends to the new policy.** The
16-interior-node budget (top-16 sinks = 80–88% of bytes on the c = 16 plane)
remains a geometric observation, not a validated objective.

**Fixed-density comparison plane chosen: c = 16** (user's requirement) — the only
c where all three workloads' min-PF picks are ejection-bound with N@90 periods
inside the window (138/150/150). Two columns for the paper: recommended designs
(c differs) and the c = 16 plane (density fixed). Missing cell: VGG (16,4,4) —
pipeline not yet run.

**Fair predictor check (2026-09-16, final).** Within-population, single n = 10
rung, per-placement offline predictor vs hybrid gain — tier width (+0.14/−0.19/
−0.08 across bf/cc12/v3284), SinkES (−0.57/−0.22/+0.16), top-sink face count
(−0.53 bf, ~0 v3284): ALL null or sign-flipped, with every static "room" measure
anti-correlated on bf, the one population with real gain. Tier width separates
PACKINGS, not placements. Consistent interpretation: static room is what
648-cycle DP already exploits; the hybrid's edge is temporal (room appearing
faster than the refresh), unscorable by static geometry. The predictor question
for the hybrid closes exactly as C8 did for the policies. (cc12 row indicative
only — its placement join is by row order, alias column incomplete.)

## Knee-onset accounting + the interior-sink causal arm — 2026-09-16/17

**Depth audit (user's rule: gains are read at the knee, not below, not in
saturation).** Per-placement depth banding of ALL data: (a) the paper's DP-vs-BL
cells are 81-82% individually light; the strict 15-30x band holds 36 above-floor
cells (DP/BL 2.44x/2.98x there) and ZERO below-floor cells; the published
below-floor 1.15x/1.23x is validated at matched ~5x onset (1.15x/1.26x, n=10) —
the paper's claim survives depth-honest reading. (b) The hybrid at matched onset
LOSES to full DP (0.96x mean / 0.90x p99, bf n=10); all its 1.19-1.4x advantages
are deep-overload rescue (42-57x own-ff). The coherence-window argument is
FALSIFIED in its strong form: a 144-cycle field bought nothing at the knee.
**Final hybrid claim: near-parity at the operating point (worst cost ~4% mean /
10% p99 on one set; 0.99-1.07x elsewhere) at 78-96% less DP-network activity and
an N-row table, plus graceful deep-overload degradation and retained spread
compression. No delay claim at the knee.**

**Interior-sink (6-face) causal arm — CLOSED NULL (predictions in
`results_ext/topn/int6/prediction.txt`, all 4 confirmed).** Constrained search
(top-16 sinks pinned to the 16 interior nodes, then min-CC): the pinning is FREE
offline — CC x0.955-1.031 of same-budget unconstrained, PL LOWER on all four
packings (the naive greedy relocation had cost 1.04-1.58x CC; searching beats
swapping). Regional check: ResNet (16,2,8) keeps tier 4; VGG (16,4,4) widens
9 -> 13-17 (a manufactured DeiT-like warm centre) — interiority is free only
while the region stays light. Simulated at matched (light, 1.4-4x) onset cells,
base vs interior, three policies, c=16 plane + v3284/esxd interior arms, 432
runs, 0 NA: ALL neutral (0.97-1.01x); no policy unlocked, DeiT unchanged.
With SinkES (r=-0.71 wrong sign) and the fair per-placement correlations (all
null), this is the third independent close of mapping-re-engineering-for-the-
policy: **the mapping chain stays min-CC + PL guard; interior sink hosting is a
free option, not an objective.** Sink-weighted path diversity's r=-0.81 on bf
was diagnosed as a congestion-depth proxy (single-k confound; the k* rule).

**Open small items:** n = 10 pass on N = 2 (the extreme hardware claim, ~100
runs) and on VGG (32,8,4) if its loss is to be cited (~700); optional f2 hybrid
fill (~120).

## Closing position — 2026-09-17 (agreed with the user)

**The below-floor capture gap stands, and is now maximally defended.** It survived
a 4.5x faster rotation, sub-cycle sampling (ci sweep: DP's 648 convention retired
in favour of ~162-324, the hybrid ci-insensitive, no optimum law), destination
gating, phase gating, joint gating, six offline room metrics (all null or
inverted under the fair protocol), and engineered placement arms (interior
pinning free-but-neutral; choice-max/ES-level: heterogeneous, prediction failed).
C8 extends to: no offline quantity AND no cheap runtime restructuring of DP
closes it. Only a congestion-STATE-reactive policy remains as a candidate.

**The top-N hybrid's measured ledger** (all at n = 10, honest 4-6x depth):
rotation 648 -> 144 (4.5x); ~78% less DP-network relaxation/switching activity;
24-row table vs 108 (DPSIZE mesh-scaling cap removed); delay within +/-6% of
full DP at every operating point on the c=16 plane and its own packing;
placement-spread compression preserved and extended (cc12 5.9x vs DP 8.6x vs BL
64x; hyb <= DP < BL in all three populations with real spread); more graceful
deep-overload degradation (1.19x/1.24x at 42-57x own-ff); one fewer effective
tuning parameter (ci-robust). Policy value overall obeys the two-regime law:
created by mapping constraints (bf: 4.8 hops, 76% divertible bytes), destroyed
by mapping freedom (min-CC+interior: 1.5-1.7 hops, 49-71% of bytes at one hop,
three-way parity +/-6%; DP does not beat BL anywhere on the compliant plane).

**RL positioning (the extension's forward edge).** Adopting the top-N structure
for the learned stage: state/action space over ~N=13-25 sinks instead of 108
destinations (and independent of mesh size); observations = the listed sinks'
arrival-face states, where steerable congestion measurably lives; the list is
compile-time derivable from the traffic table; phase windows known for
curriculum. The reduction is DNN-tailored in the strict sense — 80-90% of bytes
converge on those sinks across CNN/VGG/transformer alike, a measured invariant
of the traffic class — and the non-learning baseline the RL must beat is this
measured hybrid, not a hypothetical. What the campaign's negatives prescribe for
RL is precise: react to congestion state, since everything structural and
everything precomputed has now been shown insufficient.


---

## The c16 coherent matrix (2026-09-17) — designed three-layer readout

One recipe over the three workloads at their c=16 min-PF packings — ResNet
(16,2,8), VGG (16,4,4), DeiT (16,1,16), the density where all three N@90
rotations fit the coherence window — replacing pooled-across-unlike-populations
evidence with a designed grid. Seven placement arms x 8 placements per packing:
minCC (the interior-pinned min-CC plane, reused), maxES, maxE50, maxE40,
minE40, minE50 (metric climbs from the same starts under CC<=start, PL<=start;
E-level tier >= 3 links), and aboveF (PL = 1.10xPF +/- 2%, the one band all
three packings reach; CC minimised secondarily, CCx ~1.4-1.5). Per-placement
rung nearest 5x own free-flow (band 4-6x; 6/168 cells remained out-of-band
after a rung-patch stage and are excluded), 8 seeds, BL / DP(ci 648) /
DPN(N@90 = 23/25/25, ci = 6N). Predictions registered before the batch
(`results_ext/topn/matrix/PREDICTIONS.md`); ~3,400 runs, zero failures; full
auto-analysis in `results_ext/topn/matrix/ANALYSIS.txt`.

**Terms.** E_L(x) ("level form"): escapable fraction of the tier of links
whose peak-interval load is >= x times the peak link's (E50: x=0.5, E40:
x=0.4) — a load-threshold tier, vs ES's link-count tier (E20-E5).

### Results (BL/DP mean-delay ratio, >1 = DP wins; pooled over in-band cells)

| arm | ResNet | VGG | DeiT | pooled |
|---|---|---|---|---|
| minCC | 0.987 | 1.007 | 0.947 | 0.980 |
| maxES | 1.018 | 0.995 | 0.951 | 0.988 |
| maxE50 | 1.025 | 1.005 | 0.950 | — |
| maxE40 | 0.994 | 1.008 | 0.942 | — |
| minE40 | 1.002 | 0.998 | 0.982 | — |
| minE50 | 1.005 | 0.998 | 0.963 | — |
| **aboveF** | **1.053** | **1.121** | **1.352** | **1.170** (p99 to 1.76) |

DPN vs DP, same cells: DP/HYB = 0.998 pooled aboveF, 0.992 maxES, ~1.01
minCC — iso-performance in every regime, at N@90/108 = 21-23% of the sweep.

### Verdicts against the registered predictions

- **P1 PASS.** minCC parity (0.980): the mapping-freedom regime confirmed on
  the designed grid.
- **P2 FAIL — informative.** maxES does not put DP above BL below the floor on
  these packings (0.988 pooled). No below-floor arm does: all six sit at
  0.94-1.03. The paper's below-floor DP wins do not transfer to the c16
  min-PF plane.
- **P3 not replicated here.** No metric arm is a materially better absolute
  mapping than minCC at matched depth (BL means within ~+/-8%, inside noise;
  VGG's minCC rung sat deeper, 5.5x vs ~5.0x). The earlier maxES refinement
  (other packings, Fisher p=0.016) neither contradicted nor confirmed.
- **P4 effectively NULL.** The level-form causal test: direction-consistent on
  ResNet (+1.5%) and DeiT (+3.5%), absent on VGG — noise-grade magnitudes.
  The strong observational screen (E40 r = -0.46 pooled, ResNet -0.87;
  `corr_levels.txt`) did NOT survive engineering: neither ES nor E40/E50 is
  causal for DP gain. A designed null that retires the ES-mechanism question:
  the escape metrics ride placement covariates, they are not the lever.
- **P5 PASS — the headline.** Above the floor DP pays on all three workloads
  (1.05/1.12/1.35 mean, p99 1.07/1.24/1.76), and DPN captures effectively all
  of it (DP/HYB 0.998) at ~22% activity.
- **P6 held** (ResNet cleanest arms, VGG flattest response, DeiT confounded).

### Coverage refinement (the one DPN failure mode found)

One deep DeiT aboveF cell (esxd_af3, depth 5.9x) had DPN 24% behind DP.
Diagnostic isolates coverage, not freshness or mechanism: DP at ci=150 and
DPN sweeping all sinks both reproduce DP exactly; only the N@90 restriction
lags. N@95 (45 vs 25 sinks, 42% activity) recovers it to -5.6%. Across all 20
in-band aboveF cells N@95 changes nothing else (N@90 ~ N@95 ~ DP), so N@90 is
the right default and N@95 the escalation for deep above-floor cells. N@95 =
27/38/45 sinks (25%/35%/42% activity) per packing.

### The sharpened law

On c=16 min-PF packings, **crossing the port floor is the only lever that
creates routing-policy value** — no offline mapping metric manufactures it
below the floor, in either direction, on any workload — **and wherever that
value exists, the ~24-sink hybrid captures ~100% of it at ~1/4 of the DP
activity.** This is the paper-connecting form of the extension's improvement
claim: the two-regime law (regime decides), the DPN ledger (activity is nearly
free), and a designed null on the predictor family, all on one coherent grid.

### Post-campaign metric scorecard (2026-09-18) — E vs the tier family, and why below-floor prediction is ill-posed

Numbers persisted in `results_ext/topn/matrix/postchecks.txt`.

**E survives, precisely scoped; the tier family falls.** On the matrix's 162
in-band cells, pooled r(E, delay gain) = +0.20 (nominally p~0.01) is a Simpson
artifact: within regime it is null (below floor -0.04 n=142; aboveF -0.29
n=20) — the aboveF cells have both higher E and higher gain, and E acts as an
accidental regime label. ES is null everywhere (-0.16). The same conditioning
applied to E's un-retracted CAPACITY claim (E1 grid, gain = k*_DP/k*_BL, E
engineered 0.05-0.74 at fixed PL bands) does the opposite: within-band r =
+0.53 / +0.62 / +0.94 at PL/PF 1.10/1.33/1.56 (pooled within-band +0.70 >
raw +0.62), with a visible dose-response in every band and the effect
amplifying with depth above the floor. Verdict: cite E for capacity, above
floor, on engineered populations — nothing else in the escape family carries
any validated claim. (The PL-argmax link is only ~5-30% of the tier metrics'
integrated load, so this is a family-wide null across genuinely different
windowings, not one number re-measured.)

**Below-floor DP-gain variation is run-level, not mapping-level.** Split-half
seed reliability of per-placement below-floor gain (seeds 1-4 vs 5-8): +0.09 /
-0.05 / +0.13 per packing, pooled +0.06 (n=142); per-seed sd (0.07-0.23)
dwarfs placement-level sd (0.03-0.09). The apparent 0.84-1.21 spread across
placements is seed-noise sampled 8 times. So offline prediction below the
floor is not merely hard, it is ill-posed: the gain belongs to the individual
run (packet interleaving against the phase structure), and no static
description of the placement contains it. This retroactively explains the
level-form screen mirage (E40 r=-0.87 on n=8 estimates of ~0.1 reliability)
and is the designed-data form of the port-bound mechanism: below PF the
binding resource is the ejection port, which no path choice can route around;
the mean effect is zero and the variance is transient alignment.

**The closing frame.** Regime decides whether routing can matter (port-bound
below PF: no; link-bound above: yes); E meters how much, but only once links
bind; DPN collects whatever exists at ~1/4 the activity; and below the floor
the only thing left is zero-mean run-level noise that would require runtime
adaptivity to touch — the quantified, and small, remaining opening for the
learned stage.
