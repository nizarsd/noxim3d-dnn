# PD–PO–Mapping design flow

**Status: 2026-09-02.** Derived from ~36,000 simulation runs across ResNet-50,
VGG-16 and DeiT-S on 6×6×3, plus offline metric studies over 2,000 scored
placements. Every step is marked with its evidence level — read those markers
before citing anything here.

**Superseded since the 2026-08-26 revision** (four items, all in Step 5 and
"Not established"): DP is now the right policy in **both** regimes, not only
above the floor; DP **does** compress placement spread; PL is spot-validated
online; and PV has been tested and failed. A free **maxES** climb has been added
to Step 4. The claim-level record is
[PROJECT-RESEARCH-NOTES.md](PROJECT-RESEARCH-NOTES.md) §33 (C0–C8) — if this
doc and §33 disagree, §33 wins.

Companion docs: [MAPPING-FORMULATION.md](MAPPING-FORMULATION.md) (problem
statement), [PACKING-CRS-SWEEP.md](PACKING-CRS-SWEEP.md) (the `(c,r,s)` sweep),
[FINDINGS.md](FINDINGS.md) (Stage 1 DP-vs-BL).

---

## Notation

| symbol | name | what it measures | placement-dependent? |
|---|---|---|---|
| **PD** | packing density | `c` = crossbars per tile | — (hardware) |
| **PO** | packing orientation | `(r,s)` with `r·s = c` | — (architecture) |
| **PIL** | peak injection load | max over PE→router ports, flits/cycle | no |
| **PEL** | peak ejection load | max over router→PE ports | no |
| **PF** | port floor | `max(PIL, PEL)` | **no** |
| **SC** | sustained convergence | `max_p (1/T)·∫ load_p(t) dt`; `SC ≤ PF`, `k_max = 1/SC` | **no** |
| **ES** | escape slope | `E₂₀ − E₅`, load-weighted escapable fraction of the top-20% vs top-5% hottest links | yes |
| **PL** | peak link load | max over directed router→router channels | **yes** |
| **BIND** | binding port | `max(PL, PF)` | yes |
| **PLf** | forced link load | PL counting only edges *every* admissible path uses | yes |
| **CC** | comm cost | `Σ flits × hops` | yes |
| **PV** | path variety | bytes-weighted mean `log₂(#minimal paths)` | yes |
| **PR** | peak router load | max over nodes of inject+eject+transit | yes |

Units: flit = 4 B ([stage2_core.py:56](../tools/stage2_core.py)), NoC clock 1 ns
([main.cpp:120](../noxim3d_src/main.cpp)) → **1 flit/cycle = 4 GB/s = 32 Gbit/s**
per port and per directed link. `flit_rx`/`flit_tx` are separate channels
([TNoC.cpp:78–123](../noxim3d_src/TNoC.cpp)), so PIL and PEL are independent and
PF is their **max**, never their sum.

`k` scales `LOAD_SCALE` from the workload baseline. **PL, CC and PR scale
linearly with `k`; PV is exactly invariant; every ratio (PL/PF) is invariant.**

---

## Step 0 — Inputs

Layer shapes, crossbar 128×128 with 1-bit cells and 8 bit-planes per INT8
weight, mesh 6×6×3 = 108 nodes, `-size 16 16`, buffer 16, routing
`oddevenbalanced`.

## Step 1 — PD: choose `c`

Hardware budget: crossbars provisioned per tile. Set by area and cost, **not by
the network**. Different `c` means different silicon, so `c` values compare on
area and throughput as well as delay — not on delay alone.

## Step 2 — PO: choose `(r,s)`

The dominant lever. `r` groups rows (internalises reduce traffic), `s` groups
columns (internalises scatter). `s` also controls **which port binds**: high `s`
→ ejection-bound, high `r` → injection-bound.

```
filter   tiles ≤ 108                     fit
filter   sustained port rate ≤ 1         feasibility  (only 5 of 34 points fail)
rank     min PF                          the delay floor
report   k_max = 1/sustained             throughput ceiling
report   burst ratio = PF / sustained    how far peak diverges from average
```

**✅ Established — PF is the dominant lever.** Between k=1.60 and k=1.80 on 24
placements, binding load moved 0.627 → 0.705 (+12.4%) and below-floor delay moved
80.3 → 124.6 (**+55%**) — an elasticity of ~4.4. Placement, by contrast, buys
1.7–1.9× and only above the floor.

**⚠️ Do not select on min total bytes.** It picks the burstiest packings: VGG's
min-bytes `(32,16,2)` has burst 5.0× and peak PF 1.95 versus `(32,8,4)`'s 0.76.
The green *GLOBAL MIN* cells in `packing_crs_sweep.xlsx` optimise the wrong
quantity.

**✅ Established — min-PF beats min-bytes, measured.** ResNet c=16, min-PF
`(16,2,8)` vs min-bytes `(16,4,4)`, min-CC mapping on both arms, 3 placements ×
3 sim seeds per rung (`test1_po.py`, `res_test1_{bl,dp}.txt`): **2.78× lower
port floor for 7.1% more bytes** buys **11.6× mean delay and 18.7× p99** at
k=1.0, and 13.8× / 20.3× under DP — not policy-dependent. Both arms sit *below
their own floor* (PL/PF 0.42–0.55 min-bytes vs 0.53–0.58 min-PF, the min-bytes
arm the better-placed one), so the gap is orientation, not placement. The two
objectives disagree in **5 of 9 (workload, c) cells** at 1.27–3.15× in PF
(`results_stage3/packing_pf/packing_sc.csv`); ResNet c=16 is the only ResNet
cell where they disagree, so the other four rest on the PF→delay mechanism
rather than on runs. Note `test1c8_po.py` carries a stale copy of this
docstring — it runs (8,2,4) vs (8,1,8), min-PF vs *ejection-bound*, and is not
a second min-bytes contrast.

**⚠️ SC is the feasibility filter, never the ranking key.** Selecting on SC
would pick DeiT `(16,4,4)`, which sits 2.8× above the port floor. In 3 of the 5
disagreeing cells the min-bytes pick has *lower* SC than the min-PF pick — total
bytes tracks the time-average, delay is set by the peak.

**⚠️ Feasibility is SUSTAINED rate, not peak.** PF is a peak over one interval
that is only 13% of the period. 18 of 34 points have PF > 1 but only **5** have
sustained > 1 — the rest are burst-limited and bufferable. ResNet has **zero**
truly infeasible points.

All 9 min-PF points (3 workloads × 3 values of `c`) are below 1.0, so **PO choice
alone always reaches a feasible design**.

## Step 3 — Choose `k` per (workload, `c`)

One `k` shared by every PO at a given `c`, so orientation is compared at equal
load. Tuning `k` per `(c,r,s)` would confound the PO effect with a load effect.

Constraints: `PF·k < 1` and `PL·k < 1`. Choose the value that puts the *near-tied*
POs in an informative regime — PF-dominated pairs are already ranked
analytically by `k_max` and need no simulation.

**✅ Established** — traffic character is fully preserved under `k`: spatial
distribution, phase windows and relative flow volumes are untouched, and the
hinge condition `PL > PF` selects the same placements at any load (verified: the
same 7 of 24 at both k=1.60 and k=1.80).

## Step 4 — Placement

```
step 1        min CC           the classical objective; start here
step 2        max ES           FREE climb: max ES s.t. CC <= CCmin AND PL <= PL(minCC)
step 3        min PL           only if searching further; BIND = max(PL,PF), r = +0.86
target        PL < PF if reachable
do NOT        optimise PV (tested, failed) or PLf (83% collinear with PL)
              do NOT buy ES with CC -- +15% CC costs +3.7-6.7% free-flow delay
verify        check PL after the search rather than constraining it up front
```

**✅ Established — the free maxES climb.** At fixed PF, guarded PL and zero CC
budget, maximising `ES = E₂₀ − E₅` improves knee delay causally. Paired
interventions (minES vs maxES, same seed, CC and PL matched by construction) on
three workloads — ResNet (8,2,4), DeiT (16,1,16), VGG (8,4,2); 3-arm Fisher:
BL p99 p=0.016, BL delay 0.025, DP delay 0.046. Worth ~5–12% mean delay and up
to 1.4–1.7× p99 at the knee, either policy, at **zero cost by construction**.
Knee-local and policy-agnostic.

**⚠️ Scope — ensemble traffic, and the flow already selects for it.** The lever
needs congestion built from many flows, not one. It is null on VGG (32,4,8),
where one pair carries 92% of the peak link (λ_max 0.870). Detect this in
advance with the **free-ES headroom check** (correct 4 of 4): if ES will not
move inside the min-CC level set, the packing is dominant-flow-bound and there
is nothing to collect. All nine min-PF points have λ_max 0.063–0.436, inside the
measured ensemble range — minimising PF lands the design in the regime where the
lever works.

**✅ Established — the hinge at PF.** Delay is flat against PL below the floor and
steep above it. Replicated across k=1.60/1.80 × BL/DP, 2,880 runs, zero failures:

| | k=1.60 BL | k=1.80 BL | k=1.60 DP | k=1.80 DP |
|---|---|---|---|---|
| r(BIND, avg) | +0.840 | **+0.857** | +0.729 | +0.747 |
| hinge R² | 0.705 | 0.735 | 0.536 | 0.559 |
| below-floor slope | t = −0.04 | t = −0.16 | t = −0.47 | t = −0.31 |
| above-floor slope | **t = +4.67** | **t = +5.13** | **t = +3.57** | **t = +3.61** |

Below the floor PL varies 3.07× and moves delay 1.15–1.18×; above it PL varies
1.20× and moves delay 1.71–1.85×. The slope ratio is 64–72×.

**✅ CC is free.** Adding CC to a BIND model changes adjusted R² by ≤0.01
(t = +0.87 at k=1.80, +0.59 at k=1.60), and r(CC, PL) = +0.37 — mildly *aligned*,
so minimising CC weakly helps PL rather than fighting it.

**⚠️ PV is null and should not be optimised.** At fixed PL and CC over a 4.4× PV
range: r(PV, avg) = +0.092 (p = 0.69). PV and CC are one axis under directed
search — driving CC to its extremes swings PV 22× as a side effect. "Min CC and
max PV" asks for both ends of the same stick.

**⚠️ PR is a trap.** It flips sign between datasets (+0.635 in one, −0.801 in
another) because it is dominated by the invariant inject/eject terms. Never use
it as a predictor.

## Step 5 — Routing policy

```
escapable = 1 − PLf/PL     at the hot link
  ≲ 10%   BL suffices; DP buys nothing
  ≳ 40%   BL badly underperforms its own PL estimate; DP recovers most of it
```

PL assumes each flow spreads evenly over all admissible paths — i.e. a perfect
balancer. BL is not one. **PL over-predicts performance in proportion to how much
load is escapable.**

**⚠️ Provisional — 2 placements, n=10, one packing, one load point.** ResNet
(16,2,8), k=2.00, PL matched to 0.5%, both just above PF:

| map | PL | PLf | escapable | CC | PV | BL avg | DP avg | DP gain |
|---|---|---|---|---|---|---|---|---|
| m1 | 0.2652 | 0.2624 | **1.1%** | 2.53 | 0.27 | 99.5 | 100.4 | +0.9% ns |
| m2 | 0.2638 | 0.1382 | **47.6%** | 3.49 | 0.60 | 367.7 | 109.3 | **−70.3%** (t=−6.20) |

p99: 1129 → 1213 (ns) for m1; **7444 → 1429 (−80.8%, t=−5.00)** for m2.
Throughput identical throughout (0.0327 flit/cycle/IP) — neither is saturated.

**Prefer a low-escapable placement over one that needs DP.** m1 under plain BL
(99.5 / 1129) beats m2 under DP (109.3 / 1429) on both metrics. DP repairs
placement damage; it does not reach anywhere a good placement could not.

**⚠️ Do not read this as "avoid escape".** It says do not *rely* on DP to undo a
bad placement. It is not in tension with the maxES climb of Step 4, which raises
escape **shape** at fixed PL and zero CC — a different quantity from the escape
**level** at a worse PL that this pair contrasts. Escape level is not a mapping
objective (its sign flips once the congestion confound is removed); escape shape
is.

**⚠️ SUPERSEDED — the table below is the 2026-08-26 reading and is retained for
history only.** It was measured on 24 placements at two loads. The 829-cell
recomputation (C5/C8, knee-window placement×rung cells, 3 seeds each) shows
**always-DP leads always-BL in both regimes and at every load band including
free-flow**: 1.850× delay / 2.386× p99 above the floor, 1.150× / 1.231× below
it, winning 87%/83% of cells above and 76%/63% below. **Run DP everywhere,
unconditionally.** What remains offline-unpredictable is *which* cells DP loses
below the floor, not whether to use it.

*(historical, 24 placements, n=30)*

| k | regime | DP−BL avg | p | DP−BL p99 | p |
|---|---|---|---|---|---|
| 1.60 | below PF | **−0.0%** | 0.980 | +0.7% | 0.653 |
| 1.60 | above PF | **−10.0%** | 0.0005 | **−10.0%** | 0.0023 |
| 1.80 | below PF | −1.1% | 0.366 | −2.0% | 0.087 |
| 1.80 | above PF | **−6.7%** | 0.0083 | **−5.7%** | 0.039 |

**⚠️ Both sentences that followed this table are retracted.** (i) "DP's regime
is above PF, and only there" — superseded above. (ii) "DP does not flatten the
placement spread" — contradicted by C7: DP compresses placement spread in **8 of
8 qualifying populations**, spanning 3 workloads, 3 densities, 8 orientations
and both regimes (e.g. ResNet (8,1,8) above floor 31.81× → 18.76×; ResNet (16,2,8)
with PL pinned 64.26× → 8.57×). The two arms quoted in the old sentence were
**PL-varying**, where compression is not expected — DP cannot compress variation
caused by PL itself, since that is BIND. Compression is read in the knee window;
past the knee saturation equalises placements and DP can widen spread.

---

## Two structural rules

**PF and PL scale together, so `PL/PF` is roughly packing-invariant.** Lowering
PF does *not* make the link-bound regime easier to reach. Measured on ResNet:

| | PL range | PF | max PL/PF | share of range above floor |
|---|---|---|---|---|
| (8,2,4) | 0.081–0.604 | 0.3916 | **1.54** | **41%** |
| (16,2,8) | 0.064–0.332 | 0.2582 | 1.29 | 28% |

PF fell 34%, the achievable PL ceiling fell 45%. Choose PO on PF for the delay
floor — not to manipulate which port binds.

**BIND must be a peak, not a time-average.** The link-dominated phase is 13% of
the period; injection is co-binding or dominant for the other 87%. Even so, peak
BIND beats duration-weighted BIND at both loads (+0.857 vs +0.800 at k=1.80).
Queueing built during the short burst drains through the rest of the period, so
the peak governs average delay.

---

## Not established

- ~~**Whether PV gives DP headroom independently.**~~ **RESOLVED — tested and
  failed.** PV is null as an objective and buys no DP headroom; it costs CC
  (r = +0.86) and returns nothing. Its only retained role is absorbing diverted
  load. Do not optimise it.
- **Whether the hinge generalises beyond (8,2,4).** It rests on **7 above-floor
  placements**, r = +0.756 at p = 0.049. (16,2,8) offers *less* above-floor room,
  so the cheaper fix is to re-target the (8,2,4) search densely in PL 0.40–0.60.
- **The escapable-fraction rule at n > 2.**
- **PL and PLf are offline models; PL is now spot-validated, not generally
  validated.** DPTRACE on one placement, 7 links spanning ranks 1–50
  (2026-08-31): measured/predicted **0.88–1.01** under BL, rank order ρ = **+0.89**.
  The model runs slightly high on hot links, and DP shifts load off the top link
  onto cool ones (rank-50 reads 1.25× model). Still unvalidated in general —
  `-detailed` reports per-(src,dst) pairs, not per-link, so per-link truth needs
  a DPTRACE rerun per link. Say so when citing.

## Data

`results_stage3/mapping_pilot/pool1000/hill/` — scored pools, placements
(`selected*.csv`, permutations included), traffic tables, raw results
(`res*.txt`), and the search/analysis scripts. Gitignored: regenerate rather than
commit. All searches are seeded and reproducible.
