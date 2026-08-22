# 2026-08-21 Discussion Summary — DP+RL Direction and ResNet-50 Stage-3 Conv2 Packing Study

**Date:** 2026-08-21  
**Project:** NoC for DNN  
**Scope warning:** All numerical crossbar/packing/traffic results in this note apply **only to the ResNet-50 stage-3 conv2 layer used in today's discussion**, represented as:

\[
3\times3\times256 \rightarrow 256
\]

with a \(128\times128\), 1-bit/cell crossbar, 8-bit weights/activations, and 16-bit partial sums (psums). They must **not** be treated as results for all ResNet-50 layers or for VGG/ViT. The formulas can be reused, but each layer must be recalculated from its own dimensions.

---

## 1. DP + RL line of thought

### 1.1 What DP currently represents

The distributed DP mechanism can be interpreted as:

\[
C_i(d,a,t)
=
c_i(t)+h+C_j(d,t)
\]

for router \(i\), destination \(d\), permissible output action/direction \(a\), and neighbor \(j\) reached by \(a\).

Where:

- \(C_i(d,a,t)\): estimated cost of taking direction \(a\) from router \(i\) toward destination \(d\);
- \(c_i(t)\): local congestion-related cost at router \(i\);
- \(h\): per-hop cost;
- \(C_j(d,t)\): neighbor \(j\)'s propagated cost-to-go toward destination \(d\).

Thus DP already provides a **spatial, destination-indexed cost-to-go field**.

### 1.2 Why RL may help

The possible RL contribution is **temporal accuracy**.

DP mainly reflects the current/recent congestion state. Under periodic or phase-structured DNN traffic, a path that looks attractive now may become congested before the packet traverses it.

The desired split is therefore:

\[
\boxed{\text{DP = spatial cost knowledge}}
\]

\[
\boxed{\text{RL = temporal knowledge / temporal correction}}
\]

A candidate hybrid cost is:

\[
C^{hybrid}_{i,d,a}
=
C^{DP}_{i,d,a}
+
\Delta^{RL}_{i,d,a}
\]

with routing restricted to OEB-permissible directions.

### 1.3 Prediction-horizon idea

An early idea was to predict future cost at a destination-dependent horizon:

\[
\hat C_i(d,t+\tau_{i,d})
\]

where \(\tau_{i,d}\) depends on the remaining distance/travel time to destination \(d\).

This is conceptually correct, but it creates a difficult explicit prediction-horizon problem: each destination requires a different useful horizon.

### 1.4 Alternative: RL action as a temporal correction

A more direct idea is for RL to learn a correction:

\[
a^{RL}_{i,d,a} = \Delta C_{i,d,a}
\]

rather than predicting a future cost at a preselected horizon.

Concern: if a router is rewarded only from its own queue occupancy, it could learn to advertise an artificially high cost, push traffic elsewhere, and appear locally successful while worsening network performance.

### 1.5 Reward candidates discussed

Two main reward signals were identified.

#### Destination average end-to-end delay

For packets \(p\) arriving at destination \(d\):

\[
D_p=t^{arr}_p-t^{inj}_p
\]

and:

\[
\bar D_d
=
\frac{1}{N_d}
\sum_{p\rightarrow d}D_p
\]

where:

- \(D_p\): end-to-end delay of packet \(p\);
- \(N_d\): number of packets arriving at destination \(d\) during the measurement window;
- \(\bar D_d\): average end-to-end delay of packets arriving at \(d\).

A destination-level reward could be:

\[
r_d=-\bar D_d
\]

This aligns routers serving the same destination with an end-to-end objective, but the reward is delayed and noisy.

#### Destination-specific local waiting

A local signal was also proposed:

\[
W_{i,d,a}
\]

defined as waiting/queuing experienced at router \(i\), **only for flits destined for \(d\)** and associated with permissible direction \(a\).

This gives faster local credit assignment, but by itself can still encourage congestion displacement.

A possible combined reward is:

\[
r_{i,d,a}
=
-\alpha W_{i,d,a}
-(1-\alpha)\bar D_d
\]

where \(0\leq\alpha\leq1\).

**Reward choice remains unresolved.**

### 1.6 OEB restriction

RL should only consider OEB-permissible actions:

\[
a\in A^{OEB}_{i,d}
\]

where \(A^{OEB}_{i,d}\) is the set of legal OEB output directions from router \(i\) toward destination \(d\).

This:

- preserves the established deadlock-free routing law;
- removes illegal actions from exploration;
- directly reduces the action space;
- reduces the effective state-action space;
- means router/destination cases with only one permissible direction require no RL choice.

### 1.7 Convergence concerns

Simultaneous learning by many routers creates a multi-agent, non-stationary environment:

- one router changes its bias;
- traffic moves;
- another router's congestion changes;
- that router then changes its policy;
- traffic can move back.

Possible consequences include oscillation and convergence to a locally stable but globally suboptimal equilibrium.

A promising stabilizing principle is a **two-time-scale system**:

- DP updates/converges relatively quickly to maintain spatial consistency;
- RL changes its temporal correction more slowly.

For periodic DNN traffic, useful convergence may mean a stable **phase-dependent** policy rather than constant Q-values:

\[
\Delta^{RL}_{i,d,a}(t)
\rightarrow
\Delta^*_{i,d,a}(\phi)
\]

where \(\phi\) is the recurring DNN traffic phase.

### 1.8 Current DP+RL candidate

The current conceptual direction is:

1. OEB defines legal directions.
2. DP supplies spatial cost-to-go.
3. RL supplies a bounded temporal correction/bias.
4. Selection is made from the combined cost.
5. RL is judged using actual traffic outcomes.

Conceptually:

\[
a^*
=
\arg\min_{a\in A^{OEB}_{i,d}}
\left[
C^{DP}_{i,d,a}
+
\Delta^{RL}_{i,d,a}
\right]
\]

This remains a **future-stage concept**, not a locked implementation.

---

# 2. Crossbar background clarified today

## 2.1 What one crossbar represents

The working crossbar is:

\[
128\times128
\]

with one bit stored per cell.

Therefore total stored binary-weight capacity is:

\[
128\times128=16{,}384\text{ bits}
\]

With 8-bit weights, one logical weight/output channel requires eight bit-slices. A 128-column crossbar therefore supports:

\[
128/8=16
\]

logical 8-bit output-channel weight columns.

Thus one CB can be viewed logically as handling:

- up to 128 input positions;
- weights for 16 output channels at a time.

---

# 3. ResNet-50 stage-3 conv2 mapping — today's numerical example only

The layer used throughout today's packing analysis is:

\[
3\times3\times256\rightarrow256
\]

## 3.1 Meaning of \(3\times3\times256\)

The \(256\) is the number of **input feature channels**, not the image size.

For one spatial output position, one convolutional filter consumes:

\[
3\times3\times256=2304
\]

input values.

The output tensor is generally:

\[
H_{out}\times W_{out}\times256
\]

where \(H_{out}\) and \(W_{out}\) were not needed for the packing arithmetic below.

## 3.2 Input-axis crossbar count

One CB accepts 128 input positions, so:

\[
R_{xb}
=
\frac{3\times3\times256}{128}
=
\frac{2304}{128}
=
18
\]

Thus the input dimension is split over **18 CB slices**.

Each slice computes a partial sum for the same output group. These 18 partial sums must eventually be accumulated; they are not fed into another ordinary CB.

## 3.3 Output-axis crossbar count

The layer has 256 output channels.

One CB supports 16 logical 8-bit output channels:

\[
128/8=16
\]

therefore:

\[
C_{xb}
=
\frac{256}{16}
=
16
\]

equivalently:

\[
C_{xb}
=
\frac{256\times8}{128}
=
16
\]

## 3.4 Total crossbars

The full weight mapping therefore requires:

\[
N_{CB}
=
R_{xb}C_{xb}
=
18\times16
=
\boxed{288\text{ CBs}}
\]

This is fixed for this layer.

Changing \(c\), \(r\), or \(s\) does **not** change the required 288 working CBs. It only changes how they are grouped into tiles and how many unused CB slots appear because of fragmentation.

## 3.5 MACs per spatial output position

For one output channel and one spatial output position:

\[
3\times3\times256=2304\text{ MACs}
\]

For all 256 output channels at that spatial position:

\[
2304\times256
=
589{,}824\text{ MACs}
\]

The whole layer would require:

\[
589{,}824\times H_{out}\times W_{out}
\]

MACs.

---

# 4. Packing notation

Let:

\[
c=r\,s
\]

where:

- \(c\): crossbars per tile (packing density);
- \(r\): number of CBs grouped along the **input axis**;
- \(s\): number of CBs grouped along the **output axis**.

For this layer:

\[
R_{xb}=18,\qquad C_{xb}=16
\]

The tile grid is:

\[
N_{tile,row}=
\left\lceil\frac{18}{r}\right\rceil
\]

\[
N_{tile,col}=
\left\lceil\frac{16}{s}\right\rceil
\]

and:

\[
N_{tiles}
=
\left\lceil\frac{18}{r}\right\rceil
\left\lceil\frac{16}{s}\right\rceil
\]

## 4.1 Meaning of \(r\)

Increasing \(r\) places more input-axis partial-sum contributors inside one tile.

Therefore larger \(r\):

- internalises more psum accumulation;
- reduces the number of network-level psum contributors.

The number of network psum contributors per accumulator group is approximated by:

\[
N_{psum}
=
\left\lceil\frac{18}{r}\right\rceil
\]

## 4.2 Meaning of \(s\)

Increasing \(s\) puts more output-side CB groups sharing the same input activation inside one tile.

Therefore larger \(s\):

- internalises more input/activation broadcast;
- reduces the number of separate NoC destinations that need the same input slice.

The number of input-delivery groups is:

\[
N_{in}
=
\left\lceil\frac{16}{s}\right\rceil
\]

The effective sharing factor cannot exceed the 16 output-axis CB groups present in this layer:

\[
s_{eff}=\min(s,16)
\]

## 4.3 Accumulator groups

The number of independent output/accumulator groups is:

\[
N_{acc}
=
\left\lceil\frac{16}{s}\right\rceil
\]

The figure discussed today showed one accumulator group \(A_0\); other output groups were present but not highlighted.

---

# 5. Fixed-density assumption for Stage-3 packing sweep

For a fixed \(c\), today's agreed first-order Stage-3 abstraction is:

> Treat intra-tile processing and intra-tile communication overhead as approximately constant/abstracted for fixed \(c\), and study the **NoC-visible traffic consequences** of changing \((r,s)\).

Physically, intra-tile overhead is not exactly identical because:

- larger \(r\) requires more local psum accumulation;
- larger \(s\) requires more local activation fan-out.

However, explicitly modelling these circuit-level differences would introduce a second microarchitecture study and would confound the NoC-focused experiment.

Therefore the current Stage-3 packing sweep focuses on:

- activation/input NoC traffic;
- psum/reduction NoC traffic;
- number of active/allocated tiles;
- CB fragmentation/utilization;
- source-destination pattern;
- fan-in/fan-out;
- NoC congestion and hotspot formation.

---

# 6. Unified packing sweep for this conv2 layer

Crossbar utilization is calculated as:

\[
U_{CB}
=
\frac{288}{N_{tiles}c}
\]

and unused allocated capacity is:

\[
F_{CB}
=
\frac{N_{tiles}c-288}{N_{tiles}c}\times100\%
\]

**Important correction made during the discussion:** unused percentage must be calculated relative to **allocated CB capacity**, not relative to the fixed 288 CBs required by the layer.

| \(c\) | \(r\) | \(s\) | Tile grid | Tiles | Allocated CBs | Used CBs | Unused CBs | Unused % of allocated | Input groups \(\lceil16/s\rceil\) | Psum contributors \(\lceil18/r\rceil\) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | 1 | 8 | 18×2 | 36 | 288 | 288 | 0 | 0% | 2 | 18 |
| 8 | 2 | 4 | 9×4 | 36 | 288 | 288 | 0 | 0% | 4 | 9 |
| 8 | 4 | 2 | 5×8 | 40 | 320 | 288 | 32 | 10% | 8 | 5 |
| 8 | 8 | 1 | 3×16 | 48 | 384 | 288 | 96 | 25% | 16 | 3 |
| 16 | 1 | 16 | 18×1 | 18 | 288 | 288 | 0 | 0% | 1 | 18 |
| 16 | 2 | 8 | 9×2 | 18 | 288 | 288 | 0 | 0% | 2 | 9 |
| 16 | 4 | 4 | 5×4 | 20 | 320 | 288 | 32 | 10% | 4 | 5 |
| 16 | 8 | 2 | 3×8 | 24 | 384 | 288 | 96 | 25% | 8 | 3 |
| 16 | 16 | 1 | 2×16 | 32 | 512 | 288 | 224 | 43.75% | 16 | 2 |
| 32 | 1 | 32 | 18×1 | 18 | 576 | 288 | 288 | 50% | 1 | 18 |
| 32 | 2 | 16 | 9×1 | 9 | 288 | 288 | 0 | 0% | 1 | 9 |
| 32 | 4 | 8 | 5×2 | 10 | 320 | 288 | 32 | 10% | 2 | 5 |
| 32 | 8 | 4 | 3×4 | 12 | 384 | 288 | 96 | 25% | 4 | 3 |
| 32 | 16 | 2 | 2×8 | 16 | 512 | 288 | 224 | 43.75% | 8 | 2 |
| 32 | 32 | 1 | 1×16 | 16 | 512 | 288 | 224 | 43.75% | 16 | 1 |

For \((c,r,s)=(32,1,32)\), \(s=32\) exceeds the layer's \(C_{xb}=16\), so half of the output-side tile capacity is structurally unused. The effective input sharing remains 16.

---

# 7. Initial “crossing-point” idea

A first visual idea was to regard the point where:

\[
N_{in}
\approx
N_{psum}
\]

as the communication sweet spot.

For this layer, count-balanced/crossing regions are approximately:

- \(c=8\): between \((2,4)\) and \((4,2)\);
- \(c=16\): around \((4,4)\);
- \(c=32\): between \((4,8)\) and \((8,4)\).

If the later crossing-side choices were provisionally treated as sweet spots, the corresponding tile counts would be:

| \(c\) | Provisional crossing choice | Tiles |
|---:|---:|---:|
| 8 | (4,2) | 40 |
| 16 | (4,4) | 20 |
| 32 | (8,4) | 12 |

However, this was subsequently refined.

---

# 8. Why the simple crossing is not the minimum-traffic point

The crossing balances **counts**, not payload volume.

Under today's first-order data-width assumptions:

- activation width = 8 bits;
- psum width = 16 bits.

One input-side CB slice contains:

\[
128\times8
=
1024\text{ activation bits}
\]

whereas one 16-output-channel psum vector contains:

\[
16\times16
=
256\text{ psum bits}
\]

Thus one activation-slice payload is:

\[
1024/256=4
\]

times the payload of one 16-output psum vector.

In addition, the layer has 18 input-axis CB slices and 16 output-axis CB groups. Therefore equal **counts** of input groups and psum contributors do not imply equal NoC bit volume.

---

# 9. First-order NoC communication model for this conv2 layer

The following is an analytical proxy **per spatial output position**.

## 9.1 Activation traffic

For every input-axis slice, one 128-value activation block is delivered to each output-side tile group:

\[
V_{act}(r,s)
=
18
\left\lceil\frac{16}{s}\right\rceil
(128)(8)
\]

so:

\[
\boxed{
V_{act}(r,s)
=
18
\left\lceil\frac{16}{s}\right\rceil
1024
}
\]

bits per spatial output position.

## 9.2 Psum traffic

After local reduction of \(r\) input-axis slices inside a tile, the network has:

\[
\left\lceil\frac{18}{r}\right\rceil
\]

contributors for each output value.

For 256 output channels at 16-bit psum width:

\[
\boxed{
V_{psum}(r,s)
=
256
\left\lceil\frac{18}{r}\right\rceil
16
}
\]

bits per spatial output position.

This is a first-order communication-volume proxy. Exact packet count/hops depend on accumulator placement, packetization, tile mapping and routing.

## 9.3 Total communication proxy

\[
\boxed{
V_{NoC}(r,s)
=
V_{act}(r,s)+V_{psum}(r,s)
}
\]

---

# 10. Communication-volume results

| \(c\) | \((r,s)\) | Tiles | Unused % | Activation bits | Psum bits | **Total bits / spatial output position** |
|---:|---:|---:|---:|---:|---:|---:|
| 8 | (1,8) | 36 | 0% | 36,864 | 73,728 | **110,592** |
| 8 | (2,4) | 36 | 0% | 73,728 | 36,864 | **110,592** |
| 8 | (4,2) | 40 | 10% | 147,456 | 20,480 | **167,936** |
| 8 | (8,1) | 48 | 25% | 294,912 | 12,288 | **307,200** |
| 16 | (1,16) | 18 | 0% | 18,432 | 73,728 | **92,160** |
| 16 | (2,8) | 18 | 0% | 36,864 | 36,864 | **73,728** |
| 16 | (4,4) | 20 | 10% | 73,728 | 20,480 | **94,208** |
| 16 | (8,2) | 24 | 25% | 147,456 | 12,288 | **159,744** |
| 16 | (16,1) | 32 | 43.75% | 294,912 | 8,192 | **303,104** |
| 32 | (1,32) | 18 | 50% | 18,432 | 73,728 | **92,160** |
| 32 | (2,16) | 9 | 0% | 18,432 | 36,864 | **55,296** |
| 32 | (4,8) | 10 | 10% | 36,864 | 20,480 | **57,344** |
| 32 | (8,4) | 12 | 25% | 73,728 | 12,288 | **86,016** |
| 32 | (16,2) | 16 | 43.75% | 147,456 | 8,192 | **155,648** |
| 32 | (32,1) | 16 | 43.75% | 294,912 | 4,096 | **299,008** |

---

# 11. Current communication minima for this conv2 layer

Under the analytical traffic model above:

### \(c=8\)

Two configurations tie:

\[
(1,8)\quad\text{and}\quad(2,4)
\]

both at:

\[
110{,}592\text{ bits/output position}
\]

Both use:

\[
36\text{ tiles}
\]

with 0% fragmentation.

### \(c=16\)

Minimum:

\[
\boxed{(2,8)}
\]

with:

- 18 tiles;
- 0% fragmentation;
- 36,864 activation bits;
- 36,864 psum bits;
- 73,728 total bits/output position.

### \(c=32\)

Minimum:

\[
\boxed{(2,16)}
\]

with:

- 9 tiles;
- 0% fragmentation;
- 18,432 activation bits;
- 36,864 psum bits;
- 55,296 total bits/output position.

The neighboring \((4,8)\) configuration is close:

\[
57{,}344\text{ bits/output position}
\]

but requires 10 tiles and wastes 10% of allocated CB capacity.

---

# 12. Why equal payloads would move the optimum toward the crossing point

If activation and psum communication had equal cost per communication unit, the total communication objective would approximately take the form:

\[
T(r,s)
\propto
\frac{A}{s}
+
\frac{B}{r}
\]

subject to:

\[
rs=c
\]

The continuous minimum occurs when the two communication contributions are balanced. Therefore the point where input traffic and psum traffic cross would approximately be the minimum-communication region, subject to discrete ceiling effects.

For this actual conv2 model, the communication units are not equally weighted. Activation delivery carries a much larger payload per input slice, so the optimum shifts toward **larger \(s\)**, i.e. toward stronger input sharing.

This explains why the simple count crossing is not the measured analytical communication minimum.

---

# 13. Communication minimum is not automatically hotspot minimum

A key distinction established today is:

\[
\boxed{\text{minimum NoC bit volume} \neq \text{guaranteed minimum hotspot/congestion}}
\]

Lower communication volume is generally favorable, but hotspot formation also depends on:

- which tiles communicate;
- fan-in and fan-out;
- accumulator location;
- physical tile placement;
- source-destination distance;
- route overlap;
- TSV usage in the 3D mesh;
- routing/selection behavior.

Therefore:

- **communication volume can be screened analytically;**
- **hotspot/congestion behavior must be evaluated in the NoC simulator.**

This is an important motivation for the Stage-3 traffic/mapping experiments.

---

# 14. Current Stage-3 interpretation from today's discussion

The packing study has two distinct dimensions:

## Density

\[
c\in\{8,16,32\}
\]

## Packing shape

For each fixed \(c\), sweep the valid factor pairs:

\[
r\,s=c
\]

This separates:

1. **How many CBs are placed in each tile?** — density \(c\)
2. **Which communicating CBs are colocated?** — packing shape \((r,s)\)

For fixed \(c\), intra-tile overhead is abstracted as constant at this stage, so the experiment isolates how \((r,s)\) changes NoC traffic.

The full causal chain is:

\[
\boxed{
\text{layer dimensions}
\rightarrow
(R_{xb},C_{xb})
\rightarrow
(c,r,s)
\rightarrow
\text{logical tiles}
\rightarrow
\text{activation + psum flows}
\rightarrow
\text{physical tile placement}
\rightarrow
\text{NoC congestion/hotspots}
}
\]

---

# 15. Main findings from today's session

1. The ResNet-50 stage-3 conv2 example requires exactly:

   \[
   \boxed{288\text{ working CBs}}
   \]

   for every packing configuration considered.

2. Crossbars-per-tile \(c\) is not sufficient to describe the architecture. Packing shape matters:

   \[
   \boxed{c=r\,s}
   \]

3. Larger \(r\) internalises psum reduction; larger \(s\) internalises activation sharing.

4. For fixed \(c\), the first Stage-3 model can reasonably abstract intra-tile communication/processing and focus on **NoC-visible traffic**.

5. Fragmentation must be reported as unused percentage of **allocated CB capacity**.

6. A simple crossing of input-group count and psum-contributor count is **not** the true minimum-communication point when the two traffic types carry different payloads.

7. Under 8-bit activation and 16-bit psum assumptions, activation-side communication is weighted more heavily, shifting good packings toward larger \(s\).

8. Analytical minimum communication for this layer is currently:
   - \(c=8\): \((1,8)\) and \((2,4)\) tie;
   - \(c=16\): \((2,8)\);
   - \(c=32\): \((2,16)\).

9. The corresponding tile counts are:
   - \(c=8\): 36 tiles;
   - \(c=16\): 18 tiles;
   - \(c=32\): 9 tiles.

10. Minimum communication volume does not guarantee minimum hotspots. Tile placement and NoC simulation are still required.

11. These numerical minima are **conv2-specific** and must not be generalized to the other ResNet-50 layers before repeating the arithmetic for each layer.

---

# 16. Next logical step

For Stage 3:

1. repeat the \((R_{xb},C_{xb})\) and \((c,r,s)\) arithmetic for every selected DNN layer/block;
2. determine candidate low-communication/high-utilization packings analytically;
3. generate the corresponding traffic tables;
4. map the resulting logical tiles onto the 3D NoC;
5. compare NoC latency, congestion, hotspot formation, DP behavior, and sensitivity to mapping;
6. determine whether the communication-minimizing packing also minimizes network congestion in practice.

---

# 17. Preliminary novelty check for the full Stage-3 design flow

**Status:** Preliminary targeted literature check, not a systematic review.  
**Important:** This section supports positioning and planning only. It is **not sufficient to make a “first work to...” claim**. A reviewer-style literature search should still be performed before finalizing novelty claims.

## 17.1 Full design flow being proposed

The intended contribution is broader than the conv2 \((r,s)\) packing sweep. The complete flow is:

\[
\boxed{
\text{DNN}
\rightarrow
c
\rightarrow
(r,s)
\rightarrow
\text{traffic}
\rightarrow
\text{3D mapping}
\rightarrow
\text{3D NoC}
\rightarrow
\{\text{BL},\text{DP}\}
\rightarrow
p99
}
\]

More explicitly:

\[
\text{layer dimensions}
\rightarrow
(R_{xb},C_{xb})
\rightarrow
\underbrace{c}_{\text{CBs/tile}}
\rightarrow
\underbrace{(r,s)}_{\text{packing orientation}}
\]

\[
\rightarrow
\{\text{activation flows},\text{psum flows},\text{fragmentation}\}
\rightarrow
\underbrace{\text{3D tile placement}}_{x,y,z}
\]

\[
\rightarrow
\underbrace{\text{NoC congestion/hotspots}}_{\text{mapping-dependent}}
\rightarrow
\underbrace{\text{DP vs BL}}_{\text{non-local vs local congestion awareness}}
\rightarrow
\underbrace{p99}_{\text{tail-performance / inference-time estimate}}
\]

The important research question is therefore not merely “what is the best packing?” but:

> **How do crossbar density and packing orientation propagate through 3D placement into traffic morphology, hotspot formation, the relative value of local versus distributed non-local congestion metrics, and tail inference performance?**

## 17.2 Novelty assessment by component

| Component | Prior-art overlap | Novelty potential inside the proposed flow |
|---|---|---|
| Crossbar density \(c\) | Considerable prior work | Low alone |
| Input sharing / partial-result summation | Explicitly established in prior PIM work | Low alone |
| Fixed-\(c\), systematic \((r,s)\) packing-orientation sweep | Exact formulation not found in this targeted check | Moderate–high |
| Analytical activation/psum traffic + fragmentation model | Related packing/utilization work exists | Moderate |
| 3D DNN/PIM mapping | Existing work | Low–moderate alone |
| **Impact of \((r,s)\) on the best 3D placement and hotspot morphology** | Less directly covered by the works checked | **High potential** |
| p99/tail latency as an evaluation metric | Established metric | Moderate as part of the full flow |
| DP versus local buffer level (BL) | Local/non-local congestion-aware routing is established | Moderate alone |
| **Interaction between packing/mapping and DP-vs-BL relative performance** | Exact combined question not found in this targeted check | **High potential** |
| **End-to-end cross-layer design flow** | Exact combination not found in this targeted check | **Strongest novelty candidate** |

## 17.3 Prior work that overlaps specific pieces

### Long et al. — input sharing and partial-result summation are not new

Y. Long, D. Kim, E. Lee, P. Saha, B. A. Mudassar, X. She, A. I. Khan, and S. Mukhopadhyay,  
**“A Ferroelectric FET-Based Processing-in-Memory Architecture for DNN Acceleration,”**  
*IEEE Journal on Exploratory Solid-State Computational Devices and Circuits*, vol. 5, no. 2, pp. 113–122, 2019.  
DOI: **10.1109/JXCDC.2019.2923745**

Relevant overlap:

- explicitly identifies **row-wise input sharing**;
- explicitly identifies **column-wise output/partial-result summation**;
- proposes a hierarchical NoC for input broadcast and on-the-fly partial-result processing.

Implication for this project:

> The basic observation that orthogonal crossbar groupings trade input sharing against partial-result reduction **cannot be claimed as novel**.

The possible novelty is instead the systematic treatment of the **packing orientation \((r,s)\) at fixed density \(c\)** as a design variable whose consequences are propagated through 3D placement, congestion, routing-metric effectiveness, and tail performance.

### Haensch — physical crossbar packing/utilization is not new

W. Haensch,  
**“A Simple Packing Algorithm for Optimized Mapping of Artificial Neural Networks onto Non-Volatile Memory Cross-Bar Arrays,”**  
arXiv:2411.04814, 2024.  
DOI: **10.48550/arXiv.2411.04814**

Relevant overlap:

- maps neural-network layers onto physical crossbar arrays arranged in tiles;
- optimizes physical tile use/area;
- shows that minimum tile count is not necessarily the physical optimum.

Implication:

> Crossbar packing, utilization, tile count, and fragmentation are established research concerns. The contribution should not be framed simply as “a packing algorithm.”

### TEFLON — 3D dataflow-aware PIM NoC is not new

G. Narang, C. Ogbogu, J. R. Doppa, and P. P. Pande,  
**“TEFLON: Thermally Efficient Dataflow-aware 3D NoC for Accelerating CNN Inferencing on Manycore PIM Architectures,”**  
*ACM Transactions on Embedded Computing Systems*, vol. 23, no. 5, Article 78, 2024.  
DOI: **10.1145/3665279**

Relevant overlap:

- ReRAM/PIM CNN inference;
- monolithic 3D NoC;
- dataflow-aware mapping/communication;
- performance and thermal optimization.

Implication:

> “DNN mapping onto a 3D PIM NoC” is not itself a novelty claim.

The stronger question is whether **crossbar packing orientation changes the resulting 3D traffic/hotspot structure and therefore changes the best mapping and routing-selection policy**.

### TTNNM — thermal/traffic-aware neural-network mapping on 3D NoC is not new

X. Li, W. Fan, H. Zhang, J. Ji, T. Cheng, S. Li, L. Li, and Y. Fu,  
**“TTNNM: Thermal- and Traffic-Aware Neural Network Mapping on 3D-NoC-based Accelerator,”**  
*Proceedings of GLSVLSI 2024*, pp. 364–369, 2024.  
DOI: **10.1145/3649476.3658703**

Relevant overlap:

- neural-network mapping;
- 3D-NoC accelerator;
- traffic-aware and thermal-aware placement.

Implication:

> 3D traffic-aware NN mapping is already represented in the literature. The present study must differentiate itself through the upstream \((c,r,s)\) packing dimension and the downstream routing-metric/tail-latency analysis.

### MCAR — local versus non-local congestion awareness is not new

R. Xie, J. Cai, X. Xin, and B. Yang,  
**“MCAR: Non-local adaptive Network-on-Chip routing with message propagation of congestion information,”**  
*Microprocessors and Microsystems*, vol. 49, pp. 117–126, 2017.  
DOI: **10.1016/j.micpro.2016.11.013**

Relevant overlap:

- explicitly distinguishes **local adaptive routing** from **non-local adaptive routing**;
- propagates distant congestion information;
- motivates non-local information as providing a wider view of network state.

Implication for terminology:

> In the paper, DP should preferably be described as a **distributed non-local / multi-hop destination-aware congestion metric**, rather than simply a “global congestion metric.”

BL remains the **local buffer-occupancy metric**.

This makes the Stage-3 comparison more precise:

\[
\boxed{
\text{BL: local congestion information}
}
\]

versus

\[
\boxed{
\text{DP: distributed destination-conditioned non-local cost-to-go}
}
\]

### GRIP — p99 inference latency is established as a meaningful accelerator metric

K. Kiningham, C. Re, and P. Levis,  
**“GRIP: A Graph Neural Network Accelerator Architecture,”**  
arXiv:2007.13828, 2020.

Relevant overlap:

- evaluates accelerator inference using **99th-percentile latency**;
- demonstrates that p99 is a legitimate tail-performance metric for accelerator evaluation.

Implication:

> p99 itself is not novel, but it strengthens this project's evaluation because mean NoC latency can hide packing-induced hotspot/tail behavior.

Given the current first-order DNN timing abstraction, the most defensible initial wording is:

> **p99 communication-aware inference-time estimate**

rather than hardware-accurate p99 inference latency.

---

# 18. Revised novelty claim

The novelty should **not** be stated as any of the following:

- “first to map a DNN onto crossbars”;
- “first to exploit input sharing”;
- “first to aggregate partial sums”;
- “first crossbar packing method”;
- “first DNN accelerator using 3D NoC”;
- “first traffic-aware 3D mapping”;
- “first non-local congestion-aware routing”;
- “first use of p99 latency.”

Those individual components have clear prior art.

## 18.1 Candidate headline claim

A stronger and more defensible formulation is:

> **A cross-layer design-space exploration methodology for 3D NoC-based DNN accelerators that jointly considers crossbar packing density and orientation, crossbar utilization, activation/partial-sum communication, 3D tile placement, tail inference performance, and the sensitivity of local versus distributed non-local congestion-aware routing to the resulting DNN traffic.**

The key causal chain is:

\[
\boxed{
(c,r,s)
\rightarrow
\text{communication morphology}
\rightarrow
\text{3D spatial traffic}
\rightarrow
\text{hotspots}
\rightarrow
\text{DP/BL relative performance}
\rightarrow
p99
}
\]

The strongest contribution is therefore **the interaction across these levels**, not any one element by itself.

## 18.2 Why the DP-vs-BL dimension strengthens the study

Stage 1 already showed that DP does **not** universally outperform BL on synthetic traffic.

That result creates a stronger Stage-3 question:

> **Does DNN crossbar packing and 3D mapping create spatial traffic structures for which a distributed destination-aware cost-to-go metric becomes materially more useful than a local buffer-occupancy metric?**

This can be tested by examining whether different packings/mappings produce cases such as:

\[
\text{packing A: DP}\approx\text{BL}
\]

but:

\[
\text{packing B: DP}>\text{BL}
\]

and then explaining the difference through:

- traffic concentration;
- fan-in/fan-out;
- accumulator-region hotspots;
- 3D path overlap;
- vertical-link usage;
- downstream congestion visibility.

This would turn DP-versus-BL from a generic algorithm comparison into a **traffic-structure-dependent architectural result**.

## 18.3 Why 3D must be more than “the simulator is 3D”

The 3D contribution should test whether the third dimension materially changes the optimum.

For the same logical workload and \((c,r,s)\), investigate:

- alternative \(z\)-placements;
- planar versus vertical communication;
- TSV concentration;
- vertical shortcuts;
- path overlap;
- hotspot geometry;
- whether the communication-minimum packing remains the congestion-minimum packing;
- whether DP gains change because congestion is distributed differently in 3D.

A strong result would show:

\[
\boxed{
\text{packing optimum depends on 3D placement/topology}
}
\]

rather than merely showing that 3D reduces average hop count.

## 18.4 Role of p99

Mean latency alone may hide the tail created by:

- many-to-one psum reductions;
- activation fan-out;
- accumulator hotspots;
- concentrated vertical links;
- mapping-dependent route overlap.

Therefore evaluate both central and tail metrics, including:

\[
p99(T_{\text{inference}})
\]

or, under the current first-order model:

\[
\boxed{
p99\text{ communication-aware inference-time estimate}
}
\]

The important question is whether a packing with low **average** communication still produces poor **tail** behavior because of localized congestion.

---

# 19. Revised novelty assessment

Based on the targeted works checked above:

| Proposed contribution | Current assessment |
|---|---|
| \(c\) sweep alone | Weak novelty |
| \((r,s)\) mechanism alone | Weak; underlying input-sharing/output-summation mechanism exists |
| Fixed-\(c\), systematic \((r,s)\) packing orientation | Moderate–high potential |
| Analytical communication + utilization optimizer | Moderate–high potential |
| 3D mapping alone | Weak–moderate |
| \((r,s)\) × 3D placement × hotspot interaction | High potential |
| DP vs BL alone | Moderate / already rooted in established local-vs-non-local routing literature |
| Packing/mapping-dependent **DP-vs-BL crossover** | High potential |
| p99 alone | Not novel |
| Full \(c\rightarrow(r,s)\rightarrow3D\rightarrow DP/BL\rightarrow p99\) flow | **Strongest novelty potential** |

**Current qualitative assessment:** approximately **8–9/10 research-contribution potential**, conditional on the experiments demonstrating genuine cross-level interactions rather than independent parameter sweeps.

The paper becomes substantially weaker if it only reports:

- several \(c\) values;
- several \((r,s)\) values;
- several mappings;
- DP and BL results;

without demonstrating causal interaction between them.

The desired result is instead:

\[
\boxed{
(r,s)
\rightarrow
\text{traffic morphology}
\rightarrow
\text{3D hotspot morphology}
\rightarrow
\text{DP/BL relative effectiveness}
\rightarrow
p99
}
\]

If that chain is empirically demonstrated across ResNet-50, VGG-16, and ViT-Base, it forms a much more coherent and differentiated contribution.

---

# 20. Novelty claims that still require verification

Before manuscript submission, perform a focused reviewer-style literature search specifically attempting to falsify each of the following possible claims:

1. No prior work systematically treats \(r\) and \(s\), at fixed \(c=rs\), as an explicit packing-orientation design space balancing activation sharing against psum reduction.
2. No prior work derives an analytical \(r,s,c\) communication/utilization objective and then validates its predicted packing optimum through a 3D NoC.
3. No prior work shows that crossbar packing orientation changes 3D hotspot morphology sufficiently to change the preferred physical mapping.
4. No prior work evaluates whether crossbar packing/mapping changes the relative effectiveness of **local** versus **distributed non-local destination-aware** congestion metrics.
5. No prior work carries this complete chain through to p99 communication-aware inference-time estimation.

Until these checks are complete, manuscript wording should use:

- “we investigate”;
- “we jointly explore”;
- “we develop a cross-layer methodology”;
- “to our knowledge” only after a systematic search;

and should avoid an unqualified **“first”** claim.
