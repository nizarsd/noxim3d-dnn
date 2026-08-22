# Session notes — 20 Aug 2026 (to revisit)

Captured for later decisions. Nothing here is locked.

---

## 1. Where we stand

**Converters (new, uncommitted).** `stage2_core.py` (model-agnostic engine, extracted
from the frozen `stage2_dnn_traffic.py`) + thin model files `stage2_resnet.py`,
`stage2_vgg.py`, `stage2_transformer.py`.
- Regression gate: `stage2_resnet.py` reproduces `stage2_dnn_traffic.py` **byte-for-byte**.
- Residual engine generalised: `proj` (ResNet, has tiles) vs `identity` (transformer, 0 tiles).
- `transformer_layers()` residual fix landed in `stage2_dnn_full.py` (24 for 12 blocks;
  the single-block table needs **2**).
- **Trunk DAG fix (21 Aug).** The trunk was a strict *chain*, so q→k→v were serialised —
  a fabricated dependency (they are parallel; all three read the block input). Added an
  optional `DEPS = {layer: [producer,…]}`; absent ⇒ the old chain, so ResNet/VGG are
  untouched. `build_phases` now runs a level at a time (each layer keeps its own `t_off`;
  the level advances by its slowest member), `build_flows` takes producers from `DEPS`,
  and `validate` stacks cumulative pir **by window overlap** instead of by phase name
  (required — concurrent layers share a window). Gate re-run and passed: ResNet data rows
  + all 3 CSVs byte-identical; VGG flow structure/bytes/classes identical.

**Timing knob.** `CYCLES_PER_MAC = 1e-4` in the transformer/VGG model files;
**ResNet is 2e-4** (changed 21 Aug) so it stays comparable with the published
STAGE3-MAPPING-FINDINGS runs, which are all at 2e-4 / `t_period` 38,536. At 2e-4
`stage2_resnet.py` reproduces the committed `_base.txt` **byte-for-byte** — the ResNet
regression gate. ResNet phases: conv1 `[0,5138)` = 7.93× DP_CYCLE, conv2 `[5138,28259)`
= 35.68×, conv3 `[28259,38535)` = 15.86×. The `_cpm1e-4*` ResNet tables are superseded.
Real `dp_cycle = nodes·(ceil(diam/4)+3) = 648` (not the legacy 3240; the `2×` was the
1×-clock/settle-1 margin).

⚠ This breaks the "same HW ⇒ same constant" rationale — ResNet now runs at a different
cpm from TF/VGG. Deliberate: comparability with published numbers beats cross-workload
uniformity for now. Revisit when the phase-duration model is settled (§5).

**Tables in use (short = default).**
| WL | table | t_period |
|---|---|---|
| ResNet | `traffics_dnn_current/…_base.txt` + `…_base_interior.txt` (**cpm 2e-4**, ls 0.026) | 38,536 |
| ResNet (diag) | `traffics_dnn_6base/rn50_6b_ls0.026_diag{,_accint}.txt` (same cpm/ls) | 38,536 |
| Transformer | `traffics_dnn_current/transformer_encoder1_xb256_6x6x3_dag_cpm5e-5.txt` | **58,097** |
| VGG | `traffics_dnn_current/vgg16_block3_xb128_6x6x3_cpm2.5e-5.txt` | 115,606 |
Interior variants exist for TF and VGG (`…_interior.txt`). The TF interior variant is a
pure relabel: swap ff2's accumulators off the x=0 face — `24↔62, 60↔63, 96↔61`.

The pre-DAG TF tables (`…_xb256_6x6x3_cpm5e-5*.txt`, `t_period` 69,717) are kept but
**superseded**. TF phase windows now: q/k/v `[0,5809)` concurrent, o `[5809,11618)`,
ff1 `[11618,34857)`, ff2 `[34857,58096)` — 4 levels, shortest = 9.0 × DP_CYCLE.
Runs use `-warmup 58097 -sim 116194` (1 period warm, 2 measured).

**Instrumentation.** `BARRIERTRACE` env-gated per-packet dump in `TStats.cpp`
(bit-exact no-op when unset) + `barrier_group.py` offline grouping → measured
reduction-barrier time.

**Figures.** Tile-level traffic DAGs via Graphviz: `dag_{resnet50_bottleneck,
vgg16_block3,transformer_encoder}.{dot,pdf,png}` (generated from flows+placement CSVs;
placement-independent). Generator: scratchpad `traffic_to_dot.py`.
- The transformer DAG is regenerated from the **DAG-fixed** flows: q/k/v share rank
  `[0,5809)`; `q→k`, `q→v` are the block-input scatter, not a handoff. Annotated that q
  also holds the block input and that k has no consumer (QK^T not modelled).
- **Rank rule (decided, keep):** a scatter edge constrains rank only when it rides the
  *producer's* window (`phase == src layer`). A block-input delivery rides the
  *consumer's* window and must not push the consumer to a later rank. Side effect on
  ResNet — the `shortcut` cluster now sits **alongside** conv1 rather than after it,
  which is correct: the projection branch spans `[0, 38,535)`, parallel to the whole
  trunk. VGG unaffected.
- `fig_packing_rs.{dot,pdf,png}` — the c/r/s packing figure (see §4).

---

## 2. Key measured results (this session)

Substrate: 6×6×3, relaxed OEB, noskip, `-dpcost occupancy` vs bufferlevel,
buffer 16, `-size 16 16`, `-cinterval 648`, n=10 seeds. Throughput invariant
everywhere (no deadlock).

**Knees (BL, 1 seed):** TF ≈ k **0.38** (DAG-fixed table; was 0.40 pre-fix — q/k/v now
inject concurrently, so peak load per k is higher); VGG ≈ k 0.06.

**DP vs BL at the knee — placement decides whether the policy matters:**

| WL | placement | DP mean | DP p99 | BL mean | BL p99 | DP vs BL (mean / p99) |
|---|---|---|---|---|---|---|
| TF (k=0.38) | edge | 109 | 980 | 113 | 992 | −3.4% / −1.2% (tie) |
| **TF (k=0.38)** | **interior centroid** | **186** | **1,841** | **315** | **6,216** | **−40.9% / −70.4%** |
| VGG (k=0.06) | edge | 156 | 1,073 | 116 | 869 | **+33.9% / +23.6%** (DP loses) |
| **VGG (k=0.06)** | **interior centroid** | **167** | **1,298** | **243** | **3,183** | **−31.5% / −59.2%** |

TF rows are the **DAG-fixed** table, n=10 seeds, k=0.38. DP wins on all 10 seeds under
interior (range −41.5% … −83.5% p99), so no single outlier carries it. Superseded pre-fix
TF numbers (chain, k=0.42): edge +0.1%/−8.5%, interior centroid −37.1%/−56.1%, and a
naive "interior corners" variant at +12%/−10.0% — same shape, smaller interior margin.

⚠ **Do not read a sign flip into the TF rows.** TF edge is a *tie*, not a DP loss; the
sign flip is **VGG only**, where DP genuinely loses at edge. (A 1-seed run briefly showed
TF edge at −29% p99 — that was seed noise, refuted at n=10.)

⚠ **Edge+DP is still the best absolute configuration** at every k (TF: DP edge p99 980 vs
DP interior 1,841). Interior does not make the network faster — it makes the *policy
choice* matter. Frame it that way.

**Energy of interior placement (pure relabel):** VGG +0.02%, TF +2.9% — near-free.

**Placement rule that worked:** put each accumulator at the **centroid of its own
senders**, snapped to a free interior node, hot sinks first, mutually separated.
Naive "interior corners" was *worse* (more hops, no win).

**Mechanism.** Hop count dominates absolute delay; path diversity only pays in the
**tail under congestion**. Edge = short paths (better baseline) but the funnel is
pinned to one arrival face ⇒ **BL collapses**. Interior = a few more hops but routable
congestion ⇒ DP exploits it, BL cannot. Magnitude tracks how *localizable* a workload's
reductions are (TF ff2 senders localized ≫ VGG's spread across the box).

### 2.1 ResNet on the current substrate (22 Aug, n=30)

Published `diag` tables **unmodified** (`rn50_6b_ls0.026_diag.txt` / `..._diag_accint.txt`,
two-pair swap `4↔43, 40↔63` → accumulators at (1,1,1)/(3,4,1)), ls 0.026, cpm 2e-4,
warmup 9,720 / sim 124,328, `-samp 1`. Throughput 0.016597–0.017480.

| placement | metric | relaxed OEB + noskip (n=30) | published **OE** (n=30) |
|---|---|---|---|
| edge | mean | **+22.9%, t=+3.35**, 9/30 (DP significantly worse) | +5.03%, t=0.65 (nothing) |
| edge | p99 | +5.1%, t=+0.51 | — |
| interior | mean | −14.5%, t=−1.89, 20/30 (**not significant**) | **−28.96%, t=−3.51**, 23/30 |
| interior | **p99** | **−37.2%, t=−3.62**, 24/30 | **−41.1%, t=−4.10** |

Effect of the swap **per policy** (edge→interior): DP −35.1% mean (t=−8.22), BL −6.6%
(t=−0.87). The published OE double dissociation (DP 19.7% faster **and** BL 18.7% slower)
does **not** transfer: on relaxed OEB the swap helps DP enormously and does nothing
measurable to BL — relaxing the turn model already hands BL the extra paths.

⚠ The mean gap is **not** sample size: the progression is flat (−13.0 → −12.2 → −14.5 at
n=10/20/30) whereas the published OE progression grew (−17.4 → −25.7 → −29.0).
**The −29% is OE-specific — do not quote it for relaxed-OEB results.** What transfers is
the **tail** (−37.2% vs −41.1%) and the edge/interior dissociation.

Determinism baseline re-verified: `./noxim`, OE, seed 2, interior, DP →
**104.168 / 0.0170293 / 3112**, exactly as HANDOVER records. (`noxim_rx_noskip_p99` under
`-routing oddeven` gives 104.838 / max 1942 — noskip is compiled in, so it is *not* an OE
stand-in.)

#### 2.1a box vs diag at matched settings — box interior is the strongest DP result yet

Both mappings at **cpm 2e-4, ls 0.026, warmup 9,720 / sim 124,328, n=30**, relaxed OEB +
noskip, so **sender spread is the only difference**. Box confines conv2's senders to
x∈{0,4,5}; diag spreads them over all six columns. Tables:
`..._base.txt` / `..._base_interior.txt` (swap **`4↔52, 40↔58`**, both face-free, chosen by
minimising peak arrival-face load) vs `rn50_6b_ls0.026_diag*.txt`.

| map | placement | metric | DP | BL | DP vs BL | t | DP better |
|---|---|---|---|---|---|---|---|
| box | edge | mean | 155.2 | 120.4 | +28.8% | +5.42 | 5/30 |
| box | edge | p99 | 2,367.3 | 1,795.1 | +31.9% | +3.42 | 9/30 |
| **box** | **interior** | **mean** | **207.9** | **272.8** | **−23.8%** | **−5.35** | **24/30** |
| **box** | **interior** | **p99** | **2,815.6** | **5,648.1** | **−50.2%** | **−8.94** | **29/30** |
| diag | edge | mean | 200.9 | 163.4 | +22.9% | +3.35 | 9/30 |
| diag | edge | p99 | 2,370.9 | 2,256.8 | +5.1% | +0.51 | 13/30 |
| diag | interior | mean | 130.5 | 152.7 | −14.5% | −1.89 | 20/30 |
| diag | interior | p99 | 1,439.3 | 2,292.9 | −37.2% | −3.62 | 24/30 |

Throughput invariant in both (0.0166–0.0178).

1. **Box interior is the project's strongest DP result** — −50.2% p99 at **t=−8.94**, DP
   winning **29/30 seeds**; far more significant than diag's −37.2% (t=−3.62), and its
   mean effect is significant where diag's is not.
2. **RETRACTED: "box kills DP."** Earlier box runs (cpm 1e-4, k=0.50 ⇒ ls 0.013, 10-pass
   window, n=10) gave interior **+20.5%** mean, 0/10 seeds, and were read as ResNet-box
   being a DP-hostile mapping. At matched settings the same mapping gives **−23.8%**.
   The sign flip was **cpm and load**, not the mapping. Do not cite the 1e-4 box numbers.
3. **Also retracted:** the claim that the old interior swap failed because node 59 sat on
   the x=5 face. `4:58,40:59` scores **0.381**, identical to the face-free `4:52,40:58`.
   The face bug cost nothing measurable.
4. **Edge is the same in both mappings** (+28.8% box, +22.9% diag) ⇒ the edge penalty is a
   property of edge-pinned sinks, not of sender spread.
5. **The placement metric predicted the ordering** — 4 points, monotone:
   peak 0.190 (box int) → −50.2% p99; 0.254 (diag int) → −37.2%; 0.297 (diag edge) →
   +5.1%; 0.382 (box edge) → +31.9%. First evidence the scorer has predictive value.
6. **Absolute delay still favours diag** (interior DP 130.5 vs 207.9). Box concentrates
   traffic, so its baseline is worse and DP recovers proportionally more — the same
   pattern as edge-vs-interior. The mapping that is worse *absolutely* is where the
   policy matters *most*.

⚠ **Confound:** box's interior nodes were selected by the corrected peak-arrival-face
metric; diag's came from the older OE-based scoring. Part of box's advantage may be
selection quality rather than sender spread. Re-selecting diag's interior nodes with the
same scorer would close that gap — **not done**.

**DECISION (22 Aug): `box` is the ResNet base for the mapping ladder.** Reasons: it is the
converter's natural output, it matches TF and VGG (both box) so the three workloads share a
mapping family, and it carries the strongest measured result (−50.2% p99, t=−8.94). The
ladder rungs are therefore `..._base.txt` (edge) and `..._base_interior.txt` (interior),
cpm 2e-4 / ls 0.026, **already at n=30**.

`diag` is retained as a **separate side experiment on sender spread**, not a ladder rung.
Its question — does spreading a hot layer's senders across the full x extent change the
policy's value, holding sink interiority fixed — is real but orthogonal to the ladder, and
it carries the selection-rule confound above. Do not mix diag rows into ladder tables.

### 2.2 Placement scorer fixed to the simulated turn model (22 Aug)

**The problem.** `oe_arrival_faces.py` scored placements under OEB-**modified2**, while
every relaxed-OEB result is simulated with planar/vertical *coexisting*. In
[TRouter.cpp:1751](../noxim3d_src/TRouter.cpp) `routingOddEvenBalanced` the `//else` is commented out in
**both** the descending and ascending branches — that commenting-out *is* the relaxation.

**The fix.** Added `route_relaxed()` to `oeb_path_diversity.py` (a port of the C++ as
compiled); `route()` is kept so historic modified2 analysis still reproduces. In
`oe_arrival_faces.py`, `--routing oeb` now means **relaxed and is the default**; `oeb2`
selects modified2. Two divergences, both now correct:
- `ez>0` (down): planar options and `DOWN` coexist (was: planar branch returned early).
- `ez<0` (up): `UP` is appended alongside the planar options (was: mutually exclusive).

**Also fixed:** the `OBJECTIVE` line only scanned the top-`N` nodes, so its value moved
with `--top` (0.230 at `--top 1` vs 0.297 at `--top 3`, same table). It now scores **all**
sinks; `--top` is display-only. Verified invariant at 0.297 for `--top` 1/3/6/20 (89 sinks).

**Validation — the fix moves the model from wrong to matching.** ResNet node 4 vs the
`DPTRACE` measurement of **0.274** flits/cyc:

| turn model | peak | worst/mean | vs measured |
|---|---|---|---|
| oe | 0.297 | 3.68× | +8% |
| **oeb (relaxed, fixed)** | **0.297** | **3.68×** | **+8%** |
| oeb2 (modified2, old) | 0.197 | 2.45× | **−28%** |

Structural check over 348 node pairs: 0 non-minimal paths, 0 cases where relaxed admits
*fewer* paths than modified2 (proper superset), axis-aligned flows still unique; where
they differ relaxed admits **2.98× more paths on average** (max 18.3×).

**Consistent cross-workload placement metric (relaxed OEB, all sinks scored):**

| WL | peak edge → interior | worst/mean edge → interior |
|---|---|---|
| ResNet | 0.297 → 0.254 (−14%) | 3.68× → **4.00×** |
| TF | 0.412 → 0.330 (−20%) | 5.27× → 5.05× |
| VGG | 0.301 → 0.232 (−23%) | 4.06× → 3.33× |

⚠ **Use peak arrival-face load, not worst/mean.** Peak falls in all three and tracks the
measured DP gains; worst/mean *rises* for ResNet (3.68→4.00) because after the swap the
hottest node is a different low-fan-in sink (node 28, fan-in 3), not conv2's. Worst/mean
is only meaningful held to the same sink.

✅ **Peak arrival-face load has now been validated as predictive** (§2.1a): across four
ResNet placements at matched settings it orders the measured DP-vs-BL p99 effect
monotonically — 0.190 → −50.2%, 0.254 → −37.2%, 0.297 → +5.1%, 0.382 → +31.9%. It is
also the metric that selected box's interior nodes. **Adopt it as the placement
objective**; it is the only cross-workload placement number with measured predictive
value.

⚠ FINDINGS.md's "conv2 swap improved worst-face/mean-face 3.68× → 2.33×" is an **OE**
number and does **not** reproduce under relaxed OEB.

⚠ The interior arm is **not** constructed consistently across workloads: ResNet moves 2 of
20 accumulators (conv2 only, chosen by OE arrival-face scoring), TF 3 of 27 (ff2 only,
sender centroid), VGG **6 of 6** (all layers, sender centroid). All moved sinks do go from
≥1 face to **zero** faces (fully interior) — that much is uniform. Mean sender hops is not
a usable proxy: it rises in two cases (TF node 96, VGG node 60).

### 2.3 The knee is set by the reduction sink's ejection port (derived, 22 Aug)

From the ADC model (CROSSBAR-ADC-PACKING §2–3), under a **spatial** mapping every
fully-mapped layer is ADC-bound and takes the same time:

```
cycles per crossbar pass = S · N_bits = 16 · 8 = 128
layer duration           = HW · S · N_bits          (independent of MACs, XB, R, C)
```

At **true** injection rates the hottest reduction sink demands far more than a node's
**1 flit/cycle** ejection port can absorb. So `LOAD_SCALE` is not a free knob — it is the
*fraction of real demand* being simulated:

| WL | sink | flits/cyc at ls=1 | ls_max (=1 port) | ls used | knee k | effective ls | **% of port** |
|---|---|---|---|---|---|---|---|
| ResNet | conv2 | 18.4 | 0.0542 | 0.026 | 1.00 | 0.0260 | **48.0%** |
| TF | ff2 | 23.9 | 0.0419 | 0.050 | 0.38 | 0.0190 | **45.4%** |
| VGG | conv7 | 147.6 | 0.0068 | 0.050 | 0.06 | 0.0030 | **44.3%** |

**All three knee at 44–48% of the sink's ejection bandwidth** — three networks, two
crossbar sizes, fmaps from 196 to 3,136 passes, an 8× spread in `cpm`, one number. The
knee is a property of the **reduction sink's single ejection port**, not of the mesh,
the routing, or the workload.

**Independently corroborated:** FINDINGS.md §"placement funnel" reports from `DPTRACE` on
ResNet node 4 that the busiest input link was full 73.5% of cycles at **"48% of a port"** —
measured by a different route, matching the 48.0% this derivation predicts.

**Consequence for `cpm`.** The spatial model gives no single constant (equivalent cpm is
per-layer: ResNet conv2 2.17e-4, VGG conv7 2.17e-4, TF ff2 5.43e-5). But the *hot* window
is what matters, and two of three are already right:

| hot layer | current window | spatial window | error |
|---|---|---|---|
| ResNet conv2 | 23,121 | 25,088 | +8.5% |
| TF ff2 | 23,239 | 25,216 | +8.5% |
| VGG conv7 | 46,242 | 401,408 | **+768%** |

So the 8× `cpm` spread is **cosmetic for ResNet and TF** — only the cheap phases are
mis-sized, and they do not drive congestion. **VGG is the outlier** (its table is 8.7×
too fast); its knee still lands at 44% of port, so it is a deliberate time-compression,
not an error, but it must be declared. Whole-table t_period under the spatial model would
be ResNet ×2.0, TF ×1.7, **VGG ×10.4** (1,204,224 cycles).

**Decision: do not replace `MACs × cpm` in the converter.** Report the operating point as
**% of sink ejection capacity** instead of as `cpm`/`LOAD_SCALE` — derived, workload-
independent, and it retroactively justifies every load scale used. VGG regeneration at
cpm 2.17e-4 is optional and costs ~10× sim time. **Not done.**

---

## 3. Proposed contributions (draft)

1. First DP-vs-BL (congestion-aware vs local selection) comparison under **DNN
   inference traffic**; includes the negative case where local sensing is worse than none.
2. **Placement is the enabling condition** — sender-centroid interior placement flips
   DP from losing to winning on two workloads; near-free on energy.
3. **Mechanism**: hop-count vs path-diversity trade; why BL collapses and DP does not.
4. **Tooling/method**: 3-workload DNN→NoC converter on one mesh + measured
   reduction-**barrier time** endpoint (not a pooled-latency proxy).
4b. **The knee is a sink-ejection-bandwidth property** (§2.3): normalising load by the
   reduction sink's 1 flit/cycle port puts all three workloads' knees at **44–48%**, and
   shows the sink is **18–148× oversubscribed** at true rates. This is the strongest
   motivation for the packing/placement work — `r`-grouping and interior placement are the
   two ways to attack a structurally underprovisioned sink — and it makes `LOAD_SCALE` a
   derived quantity rather than a tuning knob.
5. *(with the c-sweep)* **Packing density as a first-class mapping variable**;
   R-vs-C grouping decouples density from reduction-internalisation.
6. *(with the c-sweep)* A **sweet spot in c**: on-tile serialisation vs network transfer.

**Framing:** the design space is not separable — the value of the routing/selection
policy is *conditional on the mapping point*. Prior IMC DSE fixes routing; NoC work
fixes mapping.

**Title candidates** (undecided):
1. *Communication-Aware DSE for IMC DNN Accelerators: Co-Optimizing Crossbar Packing,
   Tile Placement, and Adaptive 3D-NoC Selection* ← current favourite
2. *Partial-Sum Reduction as a First-Class Constraint in IMC Accelerator DSE*
3. *Beyond Peripheral Cost: Reduction-Traffic-Aware Packing and Placement for 3D-NoC IMC*
4. *ADC-Aware Packing and Reduction-Sink Placement for Congestion-Adaptive 3D NoCs*

---

## 4. Crossbars-per-tile (`c`) sweep — plan, not yet run

### Notation (fixed — supersedes any "R-grouping / C-grouping" wording elsewhere)

A layer's weight matrix splits into an `R_xb × C_xb` grid of crossbars, where
`R_xb = ceil(k²·Cin / XB)` (**input** axis) and `C_xb = ceil(Cout·N_bits / XB)`
(**output** axis).

| sym | is | spans | shares | effect |
|---|---|---|---|---|
| `c` | crossbars per tile (density) | — | — | `r · s = c`; tiles/layer = `ceil(R_xb/r) · ceil(C_xb/s)` |
| `r` | **input grouping** | input channels (different Cin slices) | the same output-channel slice | members' outputs are partial sums of the **same** value → local add **internalises reduction** |
| `s` | **output grouping** | output channels (different Cout slices) | the same input activations | one activation delivery feeds all `s` → **internalises input broadcast**; psum count unchanged |

Counterintuitive but load-bearing: it is *input* grouping that internalises the *reduction*.

**Network reduction depth = `ceil(R_xb/r) − 1`** — minus one because `acc(c) = node[(0,c)]`,
i.e. the accumulator is *hosted on* the r=0 tile, so its own partial sum never crosses the
network. Verified against the flows: TF ff2 has `R_xb=12, C=3` and 33 reduce flows = 3×11;
ResNet conv2 has `R_xb=18, C=2` and 34 = 2×17.

**Current tables are `(c=8, r=1, s=8)`** — verified from the grids: ResNet `conv2 (18,2)`
= `18 × (16/8)`; TF `q (3,3)` = `3 × (24/8)`. Maximum input reuse, **zero** reduction
internalisation, which is why depth = `R_xb − 1` exactly.

⇒ Density (`c`) and hotspot preservation (`r`) are **independent** knobs.

**Sweep arms:**
- pure output grouping `(r=1, s=c)` — density only, funnel fully preserved;
- pure input grouping `(r=c, s=1)` — maximum internalisation, funnel destroyed;
- **shape flip at fixed `c`**, e.g. `(1,8) → (2,4)` — holds density, tile count, occupancy,
  boxes and compute window constant; only reduction depth changes. Confound-free, and for
  ResNet it is exact for every layer (36/8/16/32 tiles either way, depth 17 → 8).

Figure: `fig_packing_rs.{dot,pdf,png}` (generator in scratchpad `packing_rs_dot.py`) —
ResNet conv2's 18×16 grid packed three ways at c=8, depths 17 / 8 / 2.

**Tile counts (108 nodes), N_bits=8:**
| WL | `r=c` (input grp) 8/16/32 | `s=c` (output grp) 8/16/32 |
|---|---|---|
| ResNet | 104 / 60 / 30 | 92 / 46 / 23 |
| VGG | 128 (>108) / 80 / 38 | 90 / 45 / 23 |
| TF | 144 (>108) / 64 / 34 | 108 / 66 / 33 |

⚠ The `s=c` column re-derives correctly from the grids (ResNet = 736 crossbars → 92/46/23).
The `r=c` column does **not** reproduce from the same grids (TF at `r=8` derives to ~240
tiles, not 144) — **re-verify before use**; it was likely computed under a different rule.
Note also that pure input grouping is infeasible on 6×6×3 for TF and VGG at c=8.

6 configs/workload (3 densities × 2 groupings); ×2 if edge+interior placements.
Occupancy falls hard with c (ResNet 85% → 43% → 21%) — density and occupancy are
confounded unless mesh size or workload span is varied independently.

**The trade-off to measure (the sweet spot):**
- ↑c ⇒ more on-tile reduction ⇒ **less network traffic / lower NoC delay**
- ↑c ⇒ ADC conversions serialise + deeper H-tree ⇒ **longer compute window**,
  modelled as `cpm(c) = cpm_ref·(c/c_ref)` under **tile-level ADC sharing**
  (under per-crossbar ADC banks there is no penalty and no trade-off — decide which).
- Per c, regenerate BOTH the grid/boxes (traffic) and `CYCLES_PER_MAC` (window);
  longer window automatically lowers `pir`.
- Endpoint: **barrier time** folds compute window + network delay into one number ⇒ U-curve.
- Honest caveat: the simulator models no intra-tile contention, so `cpm(c)` is an
  *assumed analytic* penalty. State S and the linearity assumption.

⚠ **Feasibility check done — a U may not be reachable in absolute barrier time.**
Barrier = compute window + network drain, and the windows dwarf the drain on 2 of 3
workloads:

| WL | phase windows (cycles) | tail at knee | drain share |
|---|---|---|---|
| ResNet | 2,569 / 11,560 / 5,138 | ~1–3k | ~10–20% |
| TF | 5,809 ×4 / 23,239 ×2 | 1.0–6.2k | ~20–100% |
| VGG | 23,120 / 46,243 ×2 | 1.1–3.2k | ~5% |

With `cpm(c) ∝ c`, doubling c adds a whole window (+11.6k on ResNet conv2) to save at
most the drain (~2k) ⇒ **monotonic increasing, no U**. Under the currently-[ASSUMED]
per-crossbar ADC banks there is no window penalty at all ⇒ monotonic *decreasing*, also
no U. Only **TF under interior placement** is drain-dominated enough for a U to exist.
Decide the ADC organisation first; the free §5 arithmetic (intra- vs inter-tile bandwidth
crossing) may be the better place for the trade-off curve than simulation.

---

## 5. Open items

- Interior placement is a manual quick tweak, not NSGA-optimised.
- n=10 for TF and VGG (paper wants ~30). **ResNet is done at n=30** on both mappings
  (§2.1, §2.1a). TF/VGG at n=30 is ~240 sims on existing tables.
- **Mapping ladder** (MAPPING-FORMULATION §5): rung 1 = edge, rung 2 = metric-selected
  interior, rung 3 = NSGA. ResNet base **fixed to box** (§2.1a); ResNet rungs 1–2 done at
  n=30. Outstanding to make rungs 1–2 valid controls across workloads:
  - regenerate **TF** and **VGG** interior variants under the *common* rule — hot layer's
    sinks only (VGG currently moves all 6, i.e. not a "minimal tweak"), selected by
    minimising **phase-aware** peak arrival-face load;
  - then n=30 on both rungs for TF and VGG (~240 sims).
- Fold phase-awareness into `oe_arrival_faces.py` (scratchpad `phase_faces.py` prototypes
  it). The current scorer sums windows that never coexist; harmless on today's tables
  (phase-blind peak == dominant-phase peak for both ResNet and TF) but wrong in general.
  Proposed f₁ = duration-weighted mean of per-phase peaks, with per-phase max as a
  constraint; f₂ = traffic-weighted mean hop count. Path diversity stays a diagnostic.
- Re-select **diag**'s interior nodes with the corrected scorer *if* the sender-spread side
  experiment is pursued (no longer blocking the ladder — diag is not a rung).
- ~~Phase duration is `MACs × cpm` rather than the spatial `HW × S × N_bits`~~ —
  **worked through in §2.3 (22 Aug).** Resolved as: keep `MACs × cpm`; the error is
  cosmetic for ResNet/TF (hot window within 8.5% of spatial) and 8.7× for VGG, which is a
  declared time-compression. Report the operating point as % of sink ejection capacity.
  Remaining sub-item: decide whether to regenerate VGG at cpm 2.17e-4 (~10× sim time).
- ResNet now runs at cpm **2e-4** while TF/VGG are at 1e-4 model / 5e-5 & 2.5e-5 tables —
  three different rationales, none physical. §2.3 makes this defensible *post hoc*
  (all three land at 44–48% of port) but the paper needs that framing, not the cpm values.
- Transformer omits QK^T / softmax / A·V / LayerNorm (no stored weights ⇒ no crossbar).
  Standard modelling boundary, and it *under*-counts reductions — the safe direction — but
  must be stated. Adding digital attention engines needs no extra nodes if co-located with
  their source accumulators; see the c-sweep, which frees nodes anyway.
- Edge-vs-interior is 2 points, not a diversity *sweep*; diversity score not yet computed.
- ~~`oe_arrival_faces.py` implements OEB-modified2, not the relaxed model~~ — **fixed
  22 Aug, see §2.2.** Remaining: `oe_arrival_faces.py` is now the placement scorer of
  record, but placements themselves are still hand-made, not searched against it.
- Turn-model contradiction: `MAPPING-FORMULATION` says "published j2/c2, unmodified"; the
  locked memory runs relaxed OEB. Unresolved in the docs.
- `_flows/_placement/_volume.csv` for the rescaled tables still reflect the originals.
- Decide ADC organisation (per-crossbar banks vs tile-level sharing) — it decides whether
  the `c` trade-off exists at all.
- Second mesh size still outstanding (publishability bar: "3D examined, not asserted").

### 5.1 Carried over from `STAGE3-UPDATE-AND-WORK-QUEUE.md` (18 Aug, now retired)

That doc's work queue is otherwise spent — Lever 1 (EWMA) is implemented and written up
in FINDINGS.md; the diversity sweep and packing-figure tasks are §4/§5 above. These items
are the remainder, and they carry that doc's original **[VERIFY]** caveat: the numbers
were captured from a voice session and were never checked against the repo.

- **Selection-policy ranking at the knee** [VERIFY, ~50 seeds]: DP-occupancy-noskip ~129 >
  DP-occupancy-skip ~136 > DP-nocost (within 1–2% of occupancy) > random ~140 >
  bufferlevel. Two claims worth re-measuring on the locked substrate, because the paper's
  framing leans on them: (a) **no-skip beats skip**, reversing the earlier
  "first-free-port is best" finding, which was obtained under the exclusivity-constrained
  turn model; (b) **random beats bufferlevel** — local buffer emptiness anti-correlates
  with downstream congestion, the emptiest neighbour being empty *because* it feeds a
  hotspot. That second one is billed as **the paper's motivating example** and is still
  unverified.
- **Full load sweep** on 6×6×3 with interior aggregators — locate the peak and test for
  past-knee reversal. 6×6×3 is even×even, so Stage 1 predicts reversal shortly past the
  knee; everything measured so far is a single load point near the knee. Report max delay
  alongside mean.
- Verify the **DP-cost read path**: directions table vs read-at-decision-time. If a
  directions table exists, the two-clock-domain setup needs a shadow copy + pointer swap
  at end-of-dwell to avoid torn reads.
- Plot the **DP cost field over time** to confirm dilution-to-zero graphically.
- Check `MAX_STATIC_DIM` and `DPSIZE` headroom before any Z-sweep topology (relevant to
  the second-mesh-size item above).
- Correction of record: the share of total traffic into the two conv2 aggregation sinks is
  **~32–38%**, not the ~72% recorded in `STAGE3-MAPPING-FINDINGS.md`. Conclusion unchanged
  — ~38% converging on two edge-pinned tiles (18 incoming flows each) still dominates the
  measurement and masks routing effects.
