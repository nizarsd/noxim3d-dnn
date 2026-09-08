# Paper 1 — the eight claims (C0–C8)

> **Provenance.** Extracted from `docs/PROJECT-RESEARCH-NOTES.md` §33 on
> 2026-09-02, at commit `2e38a61`. §33 in that file is the authoritative
> record; this is a standalone copy for use as project knowledge in chats
> that do not have the repository. **If they disagree, §33 wins.**
>
> Project: Noxim3D — a SystemC cycle-accurate 3D NoC simulator used to study
> how an in-memory-computing DNN accelerator should be packed, mapped and
> routed. Substrate: 6×6×3 = 108 tiles of 128×128 crossbars. Workloads:
> ResNet-50, VGG-16, DeiT-S. ~36,000 simulations, 0 true failures.
>
> **One edit against §33:** the "thesis, one breath" paragraph below has been
> corrected. §33 still carries the pre-retune wording ("below the floor the
> choice between policies is a coin flip"), which C8's retune superseded —
> always-DP leads BL in both regimes. The corrected wording matches C8 and
> the conclusion section further down.

## Metric names

Port and link capacity are both 1 flit/cycle = 4 GB/s (flit = 4 B, clock 1 ns);
injection and ejection are independent channels.

| symbol | meaning | placement-dependent? |
|---|---|---|
| **PD** / **PO** | packing density `c` / orientation `(r,s)`, `r·s = c` | no |
| **PIL** / **PEL** | peak injection / ejection load | no |
| **PF** | port floor = `max(PIL, PEL)` — never their sum | no |
| **SC** | sustained convergence = `max_p (1/T)·∫ load_p(t) dt`; `SC ≤ PF`, `k_max = 1/SC` | no |
| **PL** | peak link load (inter-router, first hop included) | yes |
| **ES** | escape slope = E₂₀ − E₅ (load-weighted escapable fraction, top-20% vs top-5% hottest links) | yes |
| **BIND** | `max(PL, PF)` — the delay predictor, r ≈ +0.86 | yes |
| **CC** | communication cost | yes |

---

# 33. Paper 1 thesis — the eight-claim conclusion set

**Status: LOCKED, synced 2026-08-31 to the claim-set artifact** ("The Eight
Claims", claude.ai/code/artifact/ad29f1c7-494b-48c5-854a-5883d09e5987, label
`predictor-campaign`) — the artifact is the authoritative rendering; this
section is its in-repo record. Evidence base: ~36,000 simulations, 0 true
failures, under `results_stage3/mapping_pilot/pool1000/hill/` and
`results_stage3/z_sensitivity/`.

**This supersedes the four-claim set of 2026-08-27 and both of its Claim-4
drafts** ("buy path diversity with communication cost"; "D_esc is the lever" —
both retracted below). The superseded text is in git history. Offline-geometry
results that survive the supersession are listed at the end of this section.

**Thesis, one breath:** Packing sets the achievable operating point. Placement
decides whether you reach it. Adaptive routing buys throughput only under two
conditions — but buys robustness across placements of equal PL under none. DP
is the right fixed policy in both regimes; what no offline metric can call is
*which* placements it wins on below the floor.

**Reading discipline:** all gains are measured at each placement's own capacity
point \(k^*\) or at loads fixed in advance — never at an operating point derived
from the results being compared. Compression and gain live in the knee window
(BL mean \(\lesssim 30\times\) free-flow); reading saturated rungs inverts them.
Max/min over fewer than ~10 placements is unstable.

## Group 1 — the frame: which quantity belongs to which layer

**C0 — The two terms of BIND belong to different design layers.** *(verified)*
\(PF\) is fixed by \((c,r,s)\) and is invariant to placement (identical to 6 dp
across 9 permutations; spans 5.8× over ResNet's 11 feasible points). \(PL\) is
fixed by the placement (spans 7.5× within the single packing (8,2,4)).
\(BIND = \max(PF, PL)\) is where the two layers meet; C2–C3 say which holds
control where.

**C1 — Delay has two terms, and BIND governs only one.** *(verified)*
A floor set by hop count (CC), plus congestion set by BIND. BIND sets where the
curve bends; CC sets where it starts. At identical BIND (same packing, both
below floor): **+15% CC → +3.7 to +6.7% free-flow delay, across three arms** —
enough to flip the ranking between capacity and delay-at-load.

## Group 2 — which layer controls where

**C2 — Below the floor, orientation sets the achievable delay; placement
decides whether you get it.** *((a),(b) verified; (c) partial)*

- **(a)** At fixed PD, orientation changes capacity **1.56–1.80× in \(k^*\)**,
  with mapping held at min-CC on both arms (`test1_po.py` / `test1c8_po.py`) —
  so this is orientation, not placement. \((16,2,8)\) vs \((16,4,4)\): 1.80×;
  \((8,2,4)\) vs \((8,1,8)\): 1.56×. The lower-PF orientation wins in both.

  The \((16,4,4)\) arm is also the **min-bytes** orientation, so this pair
  prices F0's ResNet arrow directly: **2.78× lower port floor for 7.1% more
  bytes** buys **11.6× mean delay and 18.7× p99** at matched load
  (\(k=1.0\), BL; 13.8× / 20.3× under DP). Both arms sit **below their own
  floor** (PL/PF 0.42–0.55 min-bytes vs 0.53–0.58 min-PF, the min-bytes arm
  being the better-placed one), so the gap is not a placement artifact —
  min-PF is the PO-layer design choice, measured. Coverage: min-bytes and
  min-PF disagree in **5 of 9 (workload, \(c\)) cells**, costing 1.27–3.15×
  in PF (`results_stage3/packing_pf/packing_sc.csv`); ResNet \(c{=}16\) is
  the only ResNet cell where they disagree, so ResNet is complete and the
  other four cells rest on the measured PF→delay mechanism, not on new runs.
  Note \((8,2,4)\) vs \((8,1,8)\) is min-PF vs the *ejection-bound*
  orientation, **not** a second min-bytes contrast (`test1c8_po.py` carries a
  stale copy of the c=16 docstring).
- **(b)** Placement is **not second-order**: its spread exists only in a band
  around the knee. Same 8 below-floor placements of (8,1,8)
  (`belowfloor_mapping_impact.log`):

  | \(PF\cdot k\) | delay spread | p99 spread | |
  |---|---|---|---|
  | 0.26 | 1.34× | 1.67× | light load |
  | 0.46 | **13.62×** | **22.64×** | the knee |
  | 0.67 | 1.28× | 1.31× | saturated |

  Measured under BL; under DP the knee spread is 7.6× — see C7.
- **(c)** But **min-CC already captures nearly all of it.** Searching past
  min-CC returns ≤1.14× delay, ≤1.34× p99 at best, and 1.00× on ResNet (8,2,4)
  from free-flow to 106× ff, at pre-specified loads. *Accepted as partial* —
  n ≈ 6 effective pairs, one rung; error bars ±0.06 delay, ±0.14 p99.
  The ResNet-vs-DeiT split is a **workload property, not occupancy**: the DeiT
  density series gains at every occupancy (37% → 1.105×, 61% → 1.136×,
  100% → 1.052×) while ResNet at 85% is null — tile count cannot explain it,
  and the gain is not monotone in density.

**Second-order term, retained:** at equal PF (DeiT (16,1,16) vs (16,2,8), PF
within 0.4%, sustained rate 2.98× apart) \(k^*\) still spreads 1.30× — bursts
matter — but PF is ~4× closer in log terms than the sustained rate as a
predictor. **Rank orientations on PF** (sustained-rate ranking retracted).

**C3 — Above the floor, placement determines delay.** *(verified)*
Spreads of 4.6× to 31.8× across placements, on all three workloads. With E7
(DeiT n=7→21), \(r(PL/PF,\text{delay})\) is **positive in every population** —
the earlier DeiT null (+0.00) was undersampling; it reads +0.52 at n=21.

## Group 3 — what predicts it

**C4 — Peak link load predicts capacity, but escape *shape* is a free,
causal delay lever.** *(a) verified · (b) verified, 3 workloads · E-as-level
retracted*

**(a) Capacity.** Regressed on \(PL/PF\) and \(E\), read at matched congestion
(4× own free-flow). \(r(PL)\) is negative in **5 of 5 populations**; \(E\)'s
sign flips and its coefficient is 4× smaller:

| population | n | r(PL) | r(E) | R(PL+E) |
|---|---|---|---|---|
| ResNet (8,1,8) | 24 | −0.541 | −0.170 | 0.560 |
| VGG grid | 20 | −0.580 | +0.327 | 0.741 |
| VGG (8,2,4) | 10 | −0.633 | +0.020 | 0.635 |
| VGG (8,4,2) | 8 | −0.838 | +0.285 | 0.957 |
| DeiT-S (E7) | 21 | −0.561 | +0.091 | 0.571 |
| **pooled** | **69** | **β −0.584** | **β +0.143** | **0.582** |

**(b) Delay at the knee.** What escape *level* fails to do, escape *shape*
does — and causally, not just correlationally. At fixed PF, guarded PL and
**CC ≤ CCmin** (zero communication-cost budget), maximising
\(ES = E_{20} - E_5\) improves delay at the knee. Paired interventions
(minES vs maxES, same seed, same CC and PL by construction) on three
workloads:

| arm | best cell | mean delay | best placement | mean p99 | best p99 |
|---|---|---|---|---|---|
| DeiT (16,1,16) | k 0.55, BL | 1.246× | 1.845× | 1.433× | 2.988× |
| VGG (8,4,2) | k 0.55, BL | 1.138× | 1.641× | 1.276× | 2.245× |
| ResNet (8,2,4) | k 1.15, DP | 1.126× | 1.321× | 1.258× | 1.688× |

3-arm Fisher: **BL p99 p = 0.016, BL delay 0.025, DP delay 0.046** (DP p99
0.081). Effect is knee-local (gone one rung past) and policy-agnostic — the
collecting policy varies by arm. So at min-CC, **up to 46% mean delay and
67% p99** remain available at zero cost (20%/30% at arm level), where the
+15% CC budget of C1 bought E but paid it straight back in floor delay
(net ≈ 1.00× at load).

**Scope: ensemble traffic, and the flow already selects for it.** The lever
needs congestion built from *many* flows rather than one. It is null on
VGG (32,4,8), where a single pair carries 92% of the peak link and 22% of
the hot tier (λ_max = 0.870) — no free ES headroom exists there, and none
appears even at a matched 1.19× CC budget with 6× the ES contrast.

Three advance-computable tests agree on the boundary, in increasing order of
directness: single-flow rate λ_max (≤ 0.44 in every ensemble case measured,
0.87 in the dominant one), top-flow share of the hot tier (5–17% vs 22%),
and the **free-ES headroom check** — the direct one, correct in 4 of 4 tests
(three positives, one null), and cheap (an offline climb, minutes).

**Min-PF orientations sit inside the regime.** All nine min-PF points (one
per workload × c) have λ_max in 0.063–0.436, the measured-ensemble range,
while the dominant packing is not min-PF at its c (VGG's c = 32 min-PF is
(32,8,4), PF 0.760, λ_max 0.434). Evidence: three confirmed by intervention
(ResNet (8,2,4), DeiT (16,1,16), VGG (8,4,2)), one by screen
(VGG (32,8,4)), five consistent by λ_max alone. This is mechanistic, not
coincidental — a fat flow inflates the port load at its endpoints, so
minimising PF avoids orientations whose traffic one pair dominates. The
design flow's own first step therefore lands in the regime where the lever
works, and the headroom check becomes confirmation rather than a gate.

**Layer assignment — the same split as C0, one layer down.** *SC* is fixed
by the packing: once \((c,r,s)\) are chosen no downstream decision changes
it. It caps throughput (k_max = 1/SC) and, across the min-PF ensemble
packings measured, grades how much runtime gain that packing leaves behind.
*ES* is the handle that **passes to the mapping layer**: it is set by the
placement, and it is an **objective, not a forecast** — maximise it inside
the min-CC level set rather than reading it off. So where C0 pairs a
packing-fixed quantity with a mapping-set one for the *delay regime*
(PF / PL), SC / ES is the corresponding pair for the *runtime gain*.

**The zero-budget condition is part of the claim.** The measured effect
holds at CC ≤ CCmin. ES bought with communication cost is not the same
lever: +15% CC costs +3.7–6.7% free-flow delay (C1) and the E-budget
frontier shows the useful escape only becomes reachable at 1.10–1.12× CC,
where cost and benefit cancel (net ≈ 1.00× at load). Maximise ES *inside*
the min-CC level set; do not buy it.

**Corollary.** Across these packings the residual runtime gain is *graded*
by both quantities: **ES (delay ρ = −0.98, n = 9, exact p = 0.00002)** and
**SC (p99 ρ = +0.95, exact p = 0.00025)** — ES from the mapping side, SC
from the packing side. Within a packing, which placement collects the gain
remains offline-unpredictable (C8).

## Group 4 — what the policy buys: two faces of one lever

**C5 — DP as a throughput lever: unconditional above the floor.** *(verified)*
Above the floor DP wins outright: **1.153× delay / 1.364× p99** (n=71, 65/71
wins; +E7: DeiT n=21 gives 1.53×/2.70×, 16/21). Best single placement
1.640×/2.352× — replicates on all 3 workloads. Below the floor it is
conditional — load near the knee AND the right placement:

| arm | binding | mean | best | at |
|---|---|---|---|---|
| ResNet (8,1,8) | ejc | 1.334× | 2.15× | \(PF\cdot k\) 0.55 (not min-PF) |
| ResNet (8,2,4) | inj | 1.101× | 1.37× | 0.45 (min-PF at c=8) |
| VGG (8,4,2) | inj | 1.354× | 1.85× | 0.81 (min-PF at c=8, 8/8) |

The peak tracks **each packing's own knee**, not a fixed \(PF\cdot k\). Every
arm built by a normal mapping search came out flat because those searches drive
PL down — see C8.

**C7 — DP as a robustness lever, unconditional in regime: it returns the
mapping freedom PL took away.** *(verified — CLOSED 2026-08-30)* DP narrows
the spread of delay across placements **wherever that spread exists** —
**8 of 8 qualifying populations**, spanning 3 workloads, 3 densities, 8
orientations, and **both regimes (above and below the floor alike)**. Mechanism: **rescue of the worst placements** — on the fastest
placements BL matches or beats DP; the worst case improves up to 7.6×
(5566 → 732 ns). Read in each population's compression window:

| population | n | spread BL → DP | ratio |
|---|---|---|---|
| cc12 ResNet (16,2,8), PL pinned | 12 | 64.26× → 8.57× | 7.50 |
| DeiT-S (8,1,8) above (E7) | 21 | 7.08× → 3.30× | 2.15 |
| VGG (8,2,4) above, at knee | 10 | 5.25× → 1.79× | 2.93 |
| VGG (8,4,2) above | 8 | 50.42× → 21.66× | 2.33 |
| ResNet (8,1,8) below | 8 | 13.62× → 7.64× | 1.78 |
| ResNet (8,1,8) above | 24 | 31.81× → 18.76× | 1.70 |
| VGG (32,8,4) above | 22 | 20.00× → 15.35× | 1.30 |
| PV sweep ResNet (8,2,4), PL pinned | 21 | 1.59× → 1.45× | 1.09 |

Where PL is pinned, compression also appears in CV (1.43× and 2.27×) — the
whole distribution tightens, not just the tail. **DP cannot compress variation
caused by PL itself** (that is BIND): the two PL-varying arms show none
(1.71×→1.79×, 1.85×→1.81×). The two non-compressing cases are the two
*predicted failure modes*, not anomalies: past the knee saturation equalises
placements (VGG (8,2,4) reads 0.69× at 22× ff but 2.93× at its knee), and with
nothing to compress there is no compression (ResNet (8,2,4) below-floor spreads
only 1.05–1.43× under BL; DP never exceeds 1.01×). **The window belongs to the congestion, not to
the policy.** Placement spread is itself a knee phenomenon — over the same 8
placements it runs 1.34× at PF·k 0.26, **13.62× at the knee**, and 1.28×
saturated (C2b): placements are interchangeable at light load and uniformly
bad in saturation, and only near saturation does the steep queueing
nonlinearity amplify small load differences into large delay differences
(*critical amplification*). DP compresses whenever there is variation to
compress; variation lives at the knee. That is also why the robustness
window coincides with the throughput window of C5. Scope: compression ratios are max/min
statistics over 7–24 placements at 3 sim seeds; the PL-pinned CV results are
the tightest-measured members.

**C8 — DP is the right default in both regimes; the residue below the floor
is offline-unpredictable.** *(verified · no predictor found)* Always-DP beats
always-BL everywhere, at every load band including free-flow. Above the floor
it is effectively optimal — a perfect per-cell oracle adds 1.1–2.5%. Below the
floor DP still loses 24–37% of cells (1.10–1.19× each), leaving an oracle
ceiling of 3.8–7.7%. Knee-window placement×rung cells, 3 sim seeds each
(above: 6 grids, n = 701; below: 3 PL-spread sets, n = 128):

| regime | metric | always BL | always DP | oracle | DP vs BL | oracle vs DP | DP wins |
|---|---|---|---|---|---|---|---|
| above | delay | 83.6 ns | 45.2 | 44.7 | 1.850× | 1.011× | 610/701 (87%) |
| above | p99 | 1384 ns | 580 | 566 | 2.386× | 1.025× | 580/701 (83%) |
| below | delay | 45.2 ns | 39.3 | 37.9 | 1.150× | 1.038× | 97/128 (76%) |
| below | p99 | 581 ns | 472 | 438 | 1.231× | 1.077× | 81/128 (63%) |

*This supersedes the earlier row reporting always-DP as worse below the floor
(0.995× / 0.970×, 84/162): that population could not be reproduced from any
identifiable set, and its absolute values (~20 ns ≈ 2.5× free-flow) indicate
light-load rungs. The claim that "DP costs 0.5–3% on the mean below the floor"
is retracted — DP is ahead at light (1.045×), knee (1.084×) and saturated
(1.262×) loads alike.* Figure: `figs/f6_policy`.

**What remains true, and is the claim's content:** *which* cells DP loses is
called by nothing offline. E flips sign, E_transit is actively harmful, PL/PF
is weak below the floor, CC is null, and ~30 further candidates failed this
session at seed level. What does predict DP's advantage is how badly BL is
doing — observable only at runtime. So the decision a designer faces is not
"which policy" (always DP) but whether an online policy can claim the
remaining 4–8%, which is the next stage's target.

## Group 5 — scope

**C6 — The regime where adaptivity pays for throughput is not naturally
reachable.** *(verified)* Above-floor is entered by **deliberate provisioning
only**: min-CC mapping, thermal spreading (3 model fidelities), link faults,
TSV clustering, and multi-tenancy all leave \(PL/PF < 1\).

## Retractions in force

1. **Sustained rate as the orientation-ranking metric** — tested; PF is ~4×
   closer to measured \(k^*\).
2. **E_transit as objective or gate** — degrades placements under both
   policies (n=56).
3. **E (and D_esc) as a mapping objective or DP-gain predictor** — sign flips
   once the congestion confound is removed (C4).
4. **"Mapping is inert below the floor"** — contradicted by the 13.6× knee
   spread (C2b). Use the banded form: inert at light load and in saturation,
   decisive at the knee.

## Design rule (paper-facing)

Pick the orientation on **PF**. Map with **min-CC**, then run the free
**maxES** climb (max ES s.t. CC ≤ CCmin, PL ≤ PL(minCC)): if ES moves
(≥ ~+0.05), keep the maxES placement — it buys ~5–12% mean delay and up to
1.43× p99 at the knee, under either policy, at zero CC/PL cost (**3
workloads** — ResNet (8,2,4), DeiT (16,1,16), VGG (8,4,2); 3-arm Fisher:
BL p99 p = 0.016, BL delay 0.025, DP delay 0.046); if ES will not move,
the packing is in the dominant-flow regime and there is nothing to collect (the checkpoint IS the
applicability test — VGG (32,4,8) has neither headroom nor, when a budget
forces the contrast, any effect). If searching further, minimise **PL**.
**Run DP everywhere, unconditionally** — it is
ahead of BL in both regimes and at every load band, by 1.85×/2.39× above the
floor and 1.15×/1.23× below it (C8), and it also compresses placement spread
(C7). Above the floor that is within 1–3% of a perfect oracle; below it a
further 4–8% remains, reachable only with an online signal no offline metric
supplies (C8).

## Conclusion and next stage — DP's efficiency gap

**DP is the right fixed policy in both regimes; the open problem is that it
is far less efficient below the floor than above it, and the deficit is
temporal.** Measured over knee-window placement×rung cells (ABOVE: 6 grids,
n = 701; BELOW: 3 PL-spread sets, n = 128; 3 sim seeds per cell):

| regime | metric | always BL | always DP | oracle | available | DP achieves | **DP captures** |
|---|---|---|---|---|---|---|---|
| above | delay | 83.6 ns | 45.2 | 44.7 | 1.870× | 1.850× | **99%** |
| above | p99 | 1384 ns | 580 | 566 | 2.446× | 2.386× | **98%** |
| below | delay | 45.2 ns | 39.3 | 37.9 | 1.193× | 1.150× | **81%** |
| below | p99 | 581 ns | 472 | 438 | 1.326× | 1.231× | **76%** |

*Capture = (BL − DP)/(BL − oracle) on delay, the fraction of the achievable delay reduction DP takes; switched from (r_DP−1)/(r_oracle−1) on 2026-09-08 — same pooled values, 98/96/78/71 → 99/98/81/76.*

DP wins 87%/83% of cells above and 76%/63% below, and is ahead at every load
band including free-flow. (This supersedes the earlier "always-DP is worse
below the floor" row, which could not be reproduced from any identifiable
population and reads at ~2.5× free-flow, i.e. light load.) Figure:
`figs/f6_policy` — DP/BL versus congestion per (arm, rung), and the
three-policy comparison by regime.

**Why the remaining work must be online, in five steps.** (1) The policy
question is settled — DP is best as a fixed choice everywhere — so further
gain requires a *better DP*, not a different policy. (2) Above the floor
nothing is left (oracle +1–3%), and by C6 that regime is not naturally
reachable. (3) Below the floor DP still loses 24–37% of cells at 1.10–1.19×
each; the switching oracle is +4–8%. (4) That residue is unreachable from
design time — ~30 offline metrics failed at seed level, and the
exhaustiveness is C8's evidence. (5) The mechanism is temporal: drain tails
of 0.8–1.5k cycles at phase boundaries, core relief that is temporal rather
than spatial, and a cost field reconverging in 648 cycles against
5k–23k-cycle phase windows.

**The target, as an efficiency gap.** Raise below-floor capture from 76–81%
toward the **98–99% the same policy already achieves above the floor**. The
above-floor figure proves the gap is closable in principle — identical
spatial machinery, different congestion statistics: above the floor
congestion is *persistent*, so a 648-cycle reconvergence is accurate almost
everywhere; below it congestion is *transient* and boundary-clustered, so
the same lag lands precisely on the events that matter. The oracle is a
BL/DP *switching* bound, so an improved DP is not obliged merely to match BL
on the cells it loses — 100% capture is a floor on the target, not a cap.

## Bridge to the next stage

The **runtime gain** — baseline (min-CC + BL) p99 over the best runtime arm
(minCC+DP / fairE+BL / fairE+DP) at the best knee-window rung — sits at the
knee, spans **1.06–1.69× p99 (1.06–1.44× delay) across the ten arms**,
is seed-unpredictable offline (see below), and DP-collected on tails. That
gain is the target of the online-adaptivity stage (improved temporal+spatial
DP; the bar is always-DP, the ceiling is the oracle's +4.2%/+11.6%).

## The predictor campaign — outcome (2026-08-31)

An exhaustive attempt to predict runtime gain offline. Net result: **no
offline quantity predicts it at either granularity**, and the exhaustiveness
is itself the strongest evidence behind C8. ~15,000 additional sims.

- **SC (sustained convergence, `max_p (1/T)·∫load_p dt`) — dead as an
  unscoped predictor; survives RE-SCOPED as an unvalidated hypothesis.**
  Unscoped: in-sample ρ = +0.930 (n = 9), one registered pass (ResNet
  (16,1,16): predicted ≥1.43×, measured 1.694×), then a registered fail
  (VGG (32,4,8): predicted 1.8× p99, measured 1.106×) and pooled-n=10
  collapse (p99 Pearson +0.14). **Scoped to ensemble-regime packings**
  (top-flow T5 dominance ≲ 17% / nonzero free-ES headroom — both
  measurable offline before any gain), the ordering holds at **p99
  Spearman +0.946 (n = 9, exact p = 0.00025)** with VGG in-scope via
  (8,4,2) at its flow-protocol gain (1.213×/1.391×, baselines completed
  2026-08-31; 7/9 arms now flow-protocol). The boundary is mechanistic
  (ensemble metrics fail on single-commodity congestion) and coincides
  with the maxES applicability boundary (4/4 tests) — but the scope was
  set AFTER the falsification, so this is a re-scoped hypothesis needing
  one registered in-scope out-of-sample test before any predictive claim.
  SC's unconditional roles remain definitional: k_max = 1/SC, SC ≤ PF.
- **The escape family — every variant null as a predictor.** E, ES at 18+
  spans, phase-gated forms, absolute/period-integrated forms, PV_SC, E_SC,
  hot-tier ΣPL/E at 4 widths, relief = supply×absorption (raw, path-
  bottlenecked, horizon-discounted), and all combinations: |r| ≤ ~0.4 at
  seed level (most ≤ 0.2), nothing survives out-of-sample or CC control as
  a *predictor*. Within-packing gain remains offline-dark (C8 upheld
  against ~30 challengers).
- **The one constructive survivor: maxES as an intervention** (see design
  rule above). Causal paired tests confirm on THREE workloads — ResNet
  (8,2,4), DeiT (16,1,16), VGG (8,4,2) (3-arm Fisher: BL p99 p = 0.016,
  BL delay 0.025, DP delay 0.046, DP p99 0.081; knee-local,
  policy-agnostic — the collecting policy varies by arm); VGG (32,4,8)
  null even at 6× contrast under a matched 1.19× CC budget. Boundary =
  dominant-flow congestion — a property of that PACKING (one pair owns
  92% of the peak link / 22% of the hot tier, λ_max 0.87), not of VGG the
  workload (at (8,4,2): λ_max 0.22, 5% share, headroom +0.154) — detected
  in advance by the free-headroom checkpoint.
- **Mechanism map (verified, descriptive):** min-CC adjacency locks the
  hot core (single-path, E≈0 — a theorem of the objective, not a bug);
  core relief is **temporal** (measured drain tails 0.8–1.5k cycles);
  below the floor absorption never binds (path-bottleneck-corrected slack
  ≥ 90% everywhere) so supply is the only pipe; the one causal spatial
  knob is **shoulder drainage** (what maxES sets); exploitation of
  alternatives is horizon-limited (BL ≈ 2 hops, DP ≈ 10 — measured
  directly: DP used a rank-50 receiver BL ignored).
- **PL spot-validated online** (retiring "never validated"): DPTRACE on 7
  links, ranks 1–50: measured/model 0.88–1.01 under BL, rank order
  ρ = +0.89; model biased slightly high; DP shifts load from the top link
  (0.80×) onto cool ones (1.25×).

## Surviving offline-geometry results (supporting material, not claims)

- **Escape room is free; global path variety is expensive** (`desc_price.py`,
  n=22): \(r(D_{esc},CC) = -0.221\) (ns) vs \(r(PV_{global},CC) = +0.859\);
  3.3× escape room for +0.007 CC. Kept as the F3/desc-price exhibit; it
  explains *why* rescue costs nothing, but neither quantity predicts gain (C4).
- **The absorption question** (open, offline-checkable): \(D_{esc}\) says how
  much load can leave \(\ell^*\); whether the alternatives absorb it decides
  the realised peak. Recompute the link field after removing the escapable
  share — not run, and not needed for Paper 1.
- ~~Convergence-axis observation~~ — promoted 2026-08-30 to the sustained
  convergence subsection above, after the ResNet (16,1,16) out-of-sample
  pass.

**Terminology.** The regime boundary is the design-space line where PL crosses
PF; the hinge is the statistical device that detects it. Argue the regime
boundary in prose, cite the hinge regression as evidence. "The knee" is a
load point (onset of congestive delay growth); the regime boundary is a
design-space line — do not conflate them.
