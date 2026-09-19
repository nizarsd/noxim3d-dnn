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
- **P3 direction-consistent but marginal.** On the paper's own instrument
  (paired p99, minCC start vs its maxES climb, 23 pairs) the refinement is
  1.10/1.08/1.11x per workload, mean 1.098x, wins 14/23 — log-t 1.97
  (p~0.06), sign test ns. Same direction as the paper's 1.26-1.43x at
  smaller magnitude; the c16 plane neither overturns nor independently
  confirms the refinement claim.
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

**Below-floor DP-gain variation is run-level, not mapping-level — and this is a
property of the regime.** Split-half seed reliability of per-placement gain
(seeds 1-4 vs 5-8), recomputed 2026-09-19 over every arm built since:

| population | n | split-half r | implied 8-seed reliability |
|---|---|---|---|
| c16 below floor (all arms) | 208 | **+0.172** | 0.294 |
| c16 **above** floor | 32 | **+0.940** | 0.969 |
| ResNet (8,1,8) below floor (independent packing) | 12 | +0.087 | 0.161 |

Same protocol, same seeds, same metric in both regimes: above the floor
placements differ systematically and the measurement is highly reliable; below
it they do not. (The earlier figure, +0.06 on n=142, is superseded by +0.172 on
n=208; the conclusion is unchanged and now has an internal control.) The apparent 0.84-1.21 spread across
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

### The CC-matched control (2026-09-18) — the regime law isolated

The matrix's above-floor arm differed from min-CC on three axes at once: load
(PL/PF 0.5 -> 1.1), communication budget (CCx 1.0 -> 1.43-1.50) and escape
room (E 0.008/0.063/0.144 -> 0.107/0.574/0.455). The gain could therefore have
belonged to any of them. The control separates them: from the same eight
min-CC starts per packing, climb E under CC <= 1.45x start and PL <= 0.90xPF —
maximal escape room, comparable budget, still below the floor. The climb
reaches **E = 1.000 on all 24 placements at CCx 1.16-1.33**, i.e. MORE escape
room than the above-floor arm for LESS communication cost.

| workload | arm | E | CCx | PL/PF | BL/DP | p99 | wins |
|---|---|---|---|---|---|---|---|
| ResNet | min-CC | 0.01 | 1.00 | 0.50 | 0.987 | 0.965 | 4/8 |
| | max-E below floor | 1.00 | 1.33 | 0.56 | 1.002 | 0.986 | 3/8 |
| | above floor | 0.11 | 1.56 | 1.09 | **1.053** | 1.073 | 4/6 |
| VGG | min-CC | 0.06 | 1.00 | 0.52 | 1.007 | 1.026 | 4/8 |
| | max-E below floor | 1.00 | 1.22 | 0.59 | 1.039 | 1.042 | 6/8 |
| | above floor | 0.57 | 1.49 | 1.10 | **1.121** | 1.241 | 7/8 |
| DeiT | min-CC | 0.14 | 1.00 | 0.45 | 0.947 | 1.045 | 1/8 |
| | max-E below floor | 1.00 | 1.16 | 0.48 | 0.969 | 1.125 | 2/6 |
| | above floor | 0.46 | 1.32 | 1.10 | **1.352** | 1.760 | 4/6 |

Maximal escape room below the floor is worth **+1.5% / +3.2% / +2.2%** over
min-CC; crossing the floor is worth **+5.3% / +12.1% / +35.2%** with less
escape room in two of three workloads. So the regime is the operative
variable, not escape room and not the communication budget — the port floor is
not a proxy for path diversity, it is the condition that makes any of it
matter. Escape room contributes a consistent but second-order benefit below
the floor (positive in all three workloads, largest on VGG, 6/8 placements),
worth a sentence and not a claim.

This also retires the earlier worry that the six-arm null was specific to
min-CC-rooted mappings: the CC-budgeted, maximal-E arm fails to create policy
value too. Runs: `results_ext/topn/matrix/{arms3_*.csv,res_bE.txt,
run_spec_bE.txt}`, 24 placements x BL/DP/DPN x 8 seeds, per-placement knee rung
(4.3-5.5x own free-flow), 3 cells out of band and excluded.

### Matched-CC min-E / max-E contrast (2026-09-19) — inconclusive on E, null holds

Four further arms complete the 2x2 at equal communication spend per workload
(target CCx = the above-floor arm's achieved mean, 1.52-1.56): min-E and max-E,
below the floor (PL <= 0.90xPF) and above it (PL in 1.08-1.12xPF). 48
placements, BL/DP/DPN, 8 seeds, own-knee rungs; 1,152 runs, 0 failures.

Achieved contrast: below floor E = 0.000 vs 1.000 (full range); above floor
E = 0.10/0.39/0.00 vs 0.21/0.59/0.36 (holding PL in band fights escape room, so
the contrast is ~2x, not full range).

E effect (max-E minus min-E, mean BL/DP at matched CC):

| workload | binds | below floor | above floor |
|---|---|---|---|
| ResNet (16,2,8) | inject | +0.010 | +0.078 (n = 4 vs 6) |
| VGG (16,4,4) | eject | +0.012 | **-0.049** (n = 6 vs 5) |
| DeiT (16,1,16) | eject | +0.080 | +0.359 (**n = 1 vs 1**) |

**Verdict: inconclusive, and not supporting the ejection-bound hypothesis** —
the sign is negative on one ejection-bound workload, positive on the
injection-bound one, and DeiT's above-floor "effect" rests on a single
placement per arm. Two reasons the instrument cannot decide effects this size:
the climbs shift each placement's knee, so cells drift out of the 4-6x band
(DeiT above floor kept 1 of 8, ResNet max-E above kept 4 of 8); and with
below-floor per-cell reliability r = 0.06, 6-8 placements cannot separate
0.01-0.08 from seed noise. The E1-grid contrast that did resolve an effect used
24 placements and the capacity outcome, which integrates a ladder rather than
one rung.

**What these arms do confirm:** the below-floor null survives two further
manipulations. At matched CC (1.52-1.56) and with escape room driven to its
extremes (E = 0.000 and E = 1.000), all three workloads remain at 0.93-1.05.
Combined with the six metric arms and the cheap max-E arm, no placement
property tested - slope, level, single-link escapable fraction, in either
direction, at min or matched communication cost - creates selection-policy
value below the port floor.

**To settle inject-vs-eject** the outcome must change, not the sample: run the
same 48 placements as ladders and score capacity gain (k*_DP/k*_BL), which also
puts them on the k*_DP convention. ~1,200 runs. Data:
`results_ext/topn/matrix/{arms5_*,arms6_*}.csv`, `res_b2.txt`, `res_minE.txt`.

### E predicts DP gain only on ejection-bound packings (2026-09-19)

**Terms.** A packing is *ejection-bound* when its port floor PF = max(PIL, PEL)
is set by the ejection term (PEL), *injection-bound* when set by injection
(PIL). E is the escapable fraction at the PL-argmax link.

The earlier replication check found E predicting capacity gain on two of five
engineered-E populations and failing on three. The two that worked were both
ejection-bound, but "injection-bound" was confounded with "VGG" (two of the
three injection-bound populations were VGG, and the DeiT one had a defective
grid with a single low-E cell). Two new grids break the confound, giving each
binding class all three workloads:

- **DeiT (16,1,16)**, ejection-bound, 9 of 12 cells hit both targets
- **ResNet (8,2,4)**, injection-bound, 6 of 12 cells hit both targets

Protocol as in E1/E3: PL targets 1.10 and 1.33 x PF crossed with E targets 0.05
and 0.74, 3 reps, phase-A PL climb then phase-B E climb, hits and misses
reported; 7-rung ladders under BL and DP, 3 seeds; 714 runs, 0 failures.

| population | binds | n | capacity low-E -> high-E | r(E, capacity gain) |
|---|---|---|---|---|
| ResNet (8,1,8) | eject | 24 | 1.063 -> 1.185 (+0.123) | **+0.62** |
| VGG (8,2,4) | eject | 10 | 1.049 -> 1.106 (+0.057) | **+0.61** |
| DeiT (16,1,16) *new* | eject | 9 | 1.038 -> 1.159 (+0.121) | **+0.38** |
| ResNet (8,2,4) *new* | inject | 6 | 0.925 -> 0.993 (+0.069) | +0.35 |
| VGG (8,4,2) | inject | 8 | 1.092 -> 1.211 (+0.119) | +0.26 |
| DeiT (16,2,8) *new* | inject | 15 | 1.062 -> 1.066 (+0.004) | +0.05 |
| VGG (32,8,4) | inject | 22 | 1.070 -> 1.054 (-0.016) | +0.01 |
| DeiT (8,1,8) *defective grid* | inject | 7 | 1.055 -> 1.025 (-0.030) | -0.03 |

**Every ejection-bound population ranks above every injection-bound one**
(min eject +0.38 > max inject +0.35): exact permutation p = **0.018** over the
eight populations, p = 0.029 excluding the defective DeiT (8,1,8) grid (which
has a single low-E cell, in one PL band only, so its E contrast is confounded
with PL — it is reported but carries no weight). Class means: eject r = +0.54,
inject r = +0.13.

**Three matched pairs.** Each pair is one workload at one density, differing
only in which port binds:

| pair | ejection-bound | injection-bound |
|---|---|---|
| ResNet c=8 (92 tiles each) | (8,1,8) **+0.62** | (8,2,4) +0.35 |
| VGG c=8 | (8,2,4) **+0.61** | (8,4,2) +0.26 |
| DeiT c=16 (66 tiles each, PF 0.905 vs 0.909) | (16,1,16) **+0.38** | (16,2,8) **+0.05** |

Three of three in the predicted direction. The DeiT pair is the tightest
control available — same workload, same density, same tile count, floors 0.4%
apart — and it is also the best-conditioned population in the set: DeiT (16,2,8)
carries n = 15 cells with E moved 0.06 -> 0.55 at matched PL and **CC within
0.5%** between the low- and high-E groups, so E is varied with load and
communication cost both held. It shows no response (+0.004 capacity, r = +0.05)
while its ejection-bound twin shows +0.121 at r = +0.38.

**Mechanism.** When PF is set by injection, packets queue at their own source
port before entering the network, so escape room on the hot link cannot help;
when PF is set by ejection, the congestion lives on links converging on hot
sinks, which is exactly where alternative paths exist and what E measures. The
c16 above-floor arm agrees: injection-bound ResNet (16,2,8) gains least (1.05x)
while ejection-bound VGG (16,4,4) and DeiT (16,1,16) gain 1.12x and 1.35x. One
population makes the point sharply: ResNet (8,2,4), injection-bound, is the only
one where DP *loses* capacity (0.93-0.99).

**Robustness: the injection null is not a failed manipulation.** E was moved
across essentially the same range in both classes — spans 0.66-0.75 in four of
five injection-bound populations (the fifth, DeiT (16,2,8), spans 0.51 after its
high target was lowered to a reachable 0.55). Normalising the response by that
span separates the classes just as cleanly:

| population | binds | E span | dCapacity/dE |
|---|---|---|---|
| ResNet (8,1,8) | eject | 0.69 | **0.265** |
| DeiT (16,1,16) | eject | 0.69 | **0.142** |
| VGG (8,2,4) | eject | 0.75 | **0.101** |
| ResNet (8,2,4) | inject | 0.66 | 0.075 |
| VGG (8,4,2) | inject | 0.74 | 0.074 |
| DeiT (16,2,8) | inject | 0.51 | 0.022 |
| VGG (32,8,4) | inject | 0.73 | 0.001 |
| DeiT (8,1,8) | inject | 0.70 | -0.008 |

Min eject 0.101 > max inject 0.075: perfect separation on slope too, class means
0.169 vs 0.033 — a five-fold difference in response per unit of escape room. The
DeiT pair is again the sharpest: the injection-bound twin's slope is 0.022
against 0.142, so its narrower span accounts for none of the gap (at the twin's
slope, a 0.51 span would have returned +0.072 capacity; it returned +0.004).

**Scope and caveats.** The comparison is between populations (n = 8), not within
— the unit of the claim is the packing. Per-population n is 6-24, and CC was not
held fixed inside the grids (spread +8 to +36% between low- and high-E groups),
so E and communication cost co-vary; a CC-pinned version is the obvious
follow-up. [SUPERSEDED 2026-09-19 — the CC caveat is retracted; see "The CC
caveat on E is retracted" at the end of this file. E survives partialling CC
out, and no CC-pinned grid is needed.] Below the floor the question does not arise: E is null there in both
binding classes (inject: ResNet (16,2,8) +0.010, ResNet (8,2,4) fairE capacity
1.017 -> 1.000; eject: VGG (16,4,4) +0.012, DeiT (16,1,16) +0.080), tested at a
full E = 0 -> 1 contrast at matched CC.

**The predictor statement the extension can make:** E predicts how much capacity
DP recovers when the design is above the port floor AND the packing is
ejection-bound; it predicts nothing below the floor, and nothing on
injection-bound packings. That is a conditional, mechanism-bearing rule rather
than the unconditional predictor the paper's escape-slope framing implied.
Runs: 1,344 ladder runs across the three new grids, 0 failures. Data:
`results_ext/ebind/` (grid_*.csv, res_ebind.txt, ANALYSIS.txt).

### Correction and enlargement of the ResNet above-floor sample (2026-09-19)

The first ResNet (16,2,8) above-floor arm had six in-band cells and gave BL/DP
1.053, which I read as support for the binding rule ("injection-bound packings
gain least"). Eight further placements were built at the same band
(PL/PF 1.06-1.10, min-CC in band) and, after a ladder patch (their knees sit
between k=1.8 and k=2.1, 3.0x -> 8-11x), seven landed in band. Two corrections
follow.

**ResNet's above-floor gain is larger and far more variable than six cells
showed.** Pooled over 13 cells: BL/DP **1.201, range 0.91-2.84** (the new cells
alone give 1.328). So the earlier 1.05 was a small-sample artifact of unusually
mild placements, not a consequence of injection binding. The binding result
itself is unaffected — it rests on the eight engineered-E grids and the capacity
outcome, not on these cells — but the anecdote should not be repeated.

**The N@95 "regression" on ResNet was noise.** With 13 cells the paired
difference between DP/DPN at N@90 and at N@95 is +0.008 (t = 0.44, p = 0.66);
VGG -0.003 (p = 0.50) and DeiT -0.024 (p = 0.46) are likewise indistinguishable.
The honest statement is that **gain is flat in N from 23 to 27 to 108
destinations**, with one exception that is a cell rather than a workload:
DeiT's deepest placement (esxd_af3, 5.9x free-flow) starves at N@90
(DP/DPN 0.761) and recovers at N@95 (0.944). N@90 remains the default because
it is the cheapest coverage at which no cell is known to starve, not because
larger N is harmful.

**Pooled DPN position, all cells (T1 rebuilt):** below floor DP/DPN 0.998 /
0.994 / 1.022; above floor 0.990 / 1.018 / 0.979, gain retained 90% / 117% / 78%.
DPN tracks DP within 3% in every workload and regime; the direction of the
residual varies with the sample, so "DPN exceeds DP" should be stated as
"matches DP within a few percent".

**Terminology note (2026-09-19).** The DPN-vs-DP share is named **gain retained**
= (BL/DPN - 1)/(BL/DP - 1), the project's phrasing from TOPN-DP-PROMPT ("fraction
of full-DP gain retained"). It is NOT the paper's *capture*, which is DP's share
of the BL->oracle delay reduction; the two must not share a name. Gain retained
exceeds 100% where DPN beats full DP, which happens because its rotation is
4.3-4.7x fresher for the sinks it tracks. Being a ratio of small numbers it
amplifies: VGG's 1.8% delay difference reads as 25 points. Quote DP/DPN
(0.968-1.018 across all cells) for how close the policies are, and gain retained
for how much of the available benefit survives the restriction.

### T1 as it stands (2026-09-19)

Final shape after stripping everything F1 already shows and everything derived:

| workload | N | rotation | activity | BL/DP | BL/DPN | DP/DPN |
|---|---|---|---|---|---|---|
| ResNet-50 (16,2,8) | 23/27 | 138/162c | 21/25% | 1.201 | 1.178 / 1.177 | 0.976 / 0.968 |
| VGG-16 (16,4,4) | 25/38 | 150/228c | 23/35% | 1.121 | 1.134 / 1.138 | 1.013 / 1.016 |
| DeiT-S (16,1,16) | 25/45 | 150/270c | 23/41% | 1.352 | 1.267 / 1.338 | 0.975 / 0.999 |
| full DP | 108 | 648c | 100% | 1.000 | — | — |

Paired entries read value@N90 / value@N95. DPN sweeps N of 108 destinations, so
rotation and table size shrink in proportion; DP/DPN > 1 means DPN is faster.
Above-floor placements only (13/8/6 per workload — those with both coverages, so
every column rests on the same cells), each at its own knee rung, 8 seeds.

**Two corrections made while building it.** (1) An earlier version divided N@95
gains measured on 13/8/6 cells by DP's gain measured on 23/19/8 — different
populations, which inflated ResNet's apparent retention from 88% to 130%. Every
column is now matched. (2) The column named "capture" was renamed **gain
retained** and then dropped from the table altogether: it is a ratio of small
numbers (VGG's 1.8% delay difference reads as 25 points) and it collided with
the paper's own *capture*, which is DP's share of the BL->oracle reduction.
DP/DPN is the honest closeness measure and is what the table now carries.

### F2 rebuilt on the enlarged ResNet sample (2026-09-19)

The regime figure now reads 1.20 / 1.12 / 1.35 above the floor against 1.01 /
1.03 / 0.93 (E = 0) and 1.02 / 1.05 / 1.01 (E = 1) below it, all arms at the same
communication budget (CCx ~ 1.5). ResNet's above-floor bar uses the 13 cells
rather than the original 6, so all three workloads show a clear lift and the
figure no longer has an apparent outlier to explain.

Caption point to keep: the above-floor bars are means over placements that
genuinely differ (ResNet spans 0.91-2.84), not a tight effect with measurement
scatter — above-floor per-placement gain has split-half reliability 0.94, so the
spread is real heterogeneity between placements.

Not added, and why: the ResNet (8,1,8) below-floor arms (an all-ejection-bound
variant would mix protocols, since that packing's above-floor data is the E1
grid, and its 12 cells span 0.65-1.17); the N@95 runs (a DPN property, so T1/F1);
the E-binding grids (F3's material).

### Extension methodology: E only, ES retired (decided 2026-09-19)

**Claim as it should be stated.** *No design-time predictor of selection-policy
gain exists unconditionally.* Below the floor none works — engineered contrasts
in both directions, on three workloads, leave DP at BL. Above the floor the
single-link escapable fraction **E** works, and only on ejection-bound packings
(8 populations, perfect rank separation, p = 0.018, 3/3 matched pairs,
slope-robust).

**What changes in the extension's methodology section.**

1. **E is the only design-time metric defined there**: E = 1 - PLf/PL at the
   PL-argmax link, presented with its two scope conditions (PL above PF, and PF
   set by the ejection term) rather than as a general predictor.
2. **The binding classification is promoted into methodology**, because it is now
   part of the predictor's definition of validity: a packing is ejection-bound
   when PF = PEL, injection-bound when PF = PIL; both are placement-invariant
   properties of the packing.
3. **ES is removed from methodology.** The escape slope is not proposed, defined
   as a contribution, or motivated there. It appears only in the results, as a
   prior-work metric (the conference paper's) that was engineered in both
   directions and moved nothing — alongside the level forms E50 and E40, in a
   single sentence, not a subsection.
4. **The DATE paper is unaffected**: its ES usage is a mapping refinement claim
   (maxES vs minES, paired, p = 0.016) that this campaign neither reproduces nor
   contradicts at c16 (1.10x, p ~ 0.06). The extension cites it as prior work and
   states the scope narrowing rather than a retraction.

One sentence for the results: *the escape slope and the level forms E50 and E40
were engineered in both directions across three workloads and moved nothing; only
the single-link escapable fraction survives, and only above the floor on
ejection-bound packings.*

### The E claim, restated on matched pairs (2026-09-19, supersedes the 8-population wording)

The eight-population permutation test (p = 0.018 raw, 0.036 depth-controlled)
pools packings that differ in workload and density, so "every ejection-bound
population ranks above every injection-bound one" was resting partly on those
differences. Restricting to **matched pairs** — one workload at one density, only
the binding term differing — is the clean design:

| pair | packing | PF | tiles | binds | n | r(E, capacity) | beta_E |
|---|---|---|---|---|---|---|---|
| ResNet-50 c=8 | (8,1,8) | 0.480 | 92 | eject | 24 | **+0.62** | **+0.60** |
| | (8,2,4) | 0.392 | 92 | inject | 6 | +0.35 | +0.55 |
| VGG-16 c=8 | (8,2,4) | 1.782 | 92 | eject | 10 | **+0.61** | **+0.63** |
| | (8,4,2) | 0.958 | 104 | inject | 8 | +0.26 | +0.09 |
| DeiT-S c=16 | (16,1,16) | 0.905 | 66 | eject | 9 | **+0.38** | **+0.36** |
| | (16,2,8) | 0.909 | 66 | inject | 15 | +0.05 | +0.06 |

**3 of 3 pairs favour the ejection-bound member, on the raw correlation and with
PL/PF partialled out.** Sign test p = 0.125 one-sided — the floor for three pairs,
so the design is clean but underpowered; the pooled test is significant but
confounded. Report both, primary on the pairs.

**Two corrections this analysis forced.** (1) Cross-pair comparisons of beta_E are
not meaningful: ResNet (8,2,4)'s +0.55 exceeds DeiT (16,1,16)'s +0.36, which
looked like a broken separation until the comparison was made within pairs.
(2) Half-split (low-E vs high-E) deltas are unreliable in these grids because PL
bands are unbalanced across the E groups — VGG (8,4,2) shows +0.119, the largest
of any population, entirely from one cell at PL/PF 1.52 (capacity 1.371). Its
rank correlation is -0.24. Quote correlations, never half-splits.

**Gain levels for the same pairs** (capacity k*_DP/k*_BL, pooled): ejection-bound
1.094 (n = 43), injection-bound 1.056 (n = 29) — so the binding claim is about
*whether E predicts*, not about which class gains more; the level difference is
small and reverses on delay at k*_DP. ResNet (8,2,4) is the one population where
DP loses capacity outright (0.948).

**p99 adds nothing here**: r(mean gain, p99 gain) = +0.99 over 72 cells (rho 0.97,
7% discordant pairs), with p99 amplifying by a median 1.8-2.6x. Quote mean and
state the amplification once.

### The CC caveat on E is retracted (2026-09-19)

Earlier entries flagged that E co-varies with communication cost inside the
grids (+8 to +36% spread between the low-E and high-E groups) and listed a
CC-pinned grid as the experiment needed to close it. Tested directly instead:

| packing | binds | n | CC spread | r(E,cap) | r(CC,cap) | r(E,CC) | r(E,cap given CC) |
|---|---|---|---|---|---|---|---|
| ResNet (8,1,8) | eject | 24 | 36% | +0.62 | +0.33 | +0.57 | **+0.56** |
| VGG (8,2,4) | eject | 10 | 26% | +0.61 | -0.06 | +0.26 | **+0.65** |
| DeiT (16,1,16) | eject | 9 | 26% | +0.38 | +0.44 | +0.20 | **+0.34** |
| ResNet (8,2,4) | inject | 6 | 22% | +0.35 | +0.06 | +0.86 | +0.59 |
| VGG (8,4,2) | inject | 8 | 13% | +0.26 | +0.16 | +0.42 | +0.21 |
| DeiT (16,2,8) | inject | 15 | 10% | +0.05 | -0.29 | -0.11 | +0.02 |

CC is a weak, sign-inconsistent predictor on its own (+0.44 to -0.29), and
partialling it out leaves E unchanged on every ejection-bound population
(+0.62 -> +0.56, +0.61 -> +0.65, +0.38 -> +0.34). **E is not standing in for
communication cost, and the CC-pinned grid is not needed.** The matched-pair
ordering survives on two of three pairs after the control; the exception is
ResNet (8,2,4), whose injection-bound coefficient rises on 6 cells with
r(E,CC) = 0.86 — the most collinear and least stable fit in the set, already
flagged elsewhere.

Residual wording for the paper: state that the effect is robust to controlling
for communication cost, and note that statistical control is not the same as
designed balance — one sentence, not an experiment.
