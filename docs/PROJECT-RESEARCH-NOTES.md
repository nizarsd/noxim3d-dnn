# NoC for DNN — Project Research Notes, Decisions, Findings, and Open Questions

**Project:** NoC for DNN  
**Document role:** Living project-wide research record. Update this file as assumptions, measurements, experimental designs, novelty checks, and stage decisions evolve. It is intentionally not tied to a single date or session.

**Scope warning for the conv2 numerical example:** All numerical crossbar/packing/traffic calculations in the relevant sections apply **only to the ResNet-50 stage-3 conv2 example**, represented as:

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

# 3. ResNet-50 stage-3 conv2 mapping — numerical example only

The layer used throughout the packing analysis is:

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

Under the current first-order data-width assumptions:

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

After local reduction of \(r\) input-axis slices inside a tile, there are:

\[
\left\lceil\frac{18}{r}\right\rceil
\]

contributor tiles per output value. One contributor tile hosts the accumulator, so its own partial sum does **not** cross the NoC. The network-visible contributor count is therefore:

\[
\left\lceil\frac{18}{r}\right\rceil-1.
\]

For 256 output channels at 16-bit psum width:

\[
\boxed{
V_{psum}(r,s)
=
256
\left(
\left\lceil\frac{18}{r}\right\rceil-1
\right)
16
}
\]

bits per spatial output position.

This mandatory minus-one correction has been checked against generated flows: current ResNet conv2 has \(2\times17=34\) reduction flows, and Transformer ff2 has \(3\times11=33\).

This remains a first-order communication-volume proxy. Exact packet count and hop work depend on accumulator placement, packetization, tile mapping, and routing.

## 9.3 Total communication proxy

\[
\boxed{
V_{NoC}(r,s)
=
V_{act}(r,s)+V_{psum}(r,s)
}
\]

---

# 10. Corrected communication-volume results

| \(c\) | \((r,s)\) | Tiles | Unused % | Activation bits | Psum bits | **Total bits / spatial output position** |
|---:|---:|---:|---:|---:|---:|---:|
| 8 | (1,8) | 36 | 0% | 36,864 | 69,632 | **106,496** |
| 8 | (2,4) | 36 | 0% | 73,728 | 32,768 | **106,496** |
| 8 | (4,2) | 40 | 10% | 147,456 | 16,384 | **163,840** |
| 8 | (8,1) | 48 | 25% | 294,912 | 8,192 | **303,104** |
| 16 | (1,16) | 18 | 0% | 18,432 | 69,632 | **88,064** |
| 16 | (2,8) | 18 | 0% | 36,864 | 32,768 | **69,632** |
| 16 | (4,4) | 20 | 10% | 73,728 | 16,384 | **90,112** |
| 16 | (8,2) | 24 | 25% | 147,456 | 8,192 | **155,648** |
| 16 | (16,1) | 32 | 43.75% | 294,912 | 4,096 | **299,008** |
| 32 | (1,32) | 18 | 50% | 18,432 | 69,632 | **88,064** |
| 32 | (2,16) | 9 | 0% | 18,432 | 32,768 | **51,200** |
| 32 | (4,8) | 10 | 10% | 36,864 | 16,384 | **53,248** |
| 32 | (8,4) | 12 | 25% | 73,728 | 8,192 | **81,920** |
| 32 | (16,2) | 16 | 43.75% | 147,456 | 4,096 | **151,552** |
| 32 | (32,1) | 16 | 43.75% | 294,912 | 0 | **294,912** |

---

# 11. Current communication minima for this conv2 layer

Under the corrected analytical traffic model:

### \(c=8\)

Two configurations tie:

\[
(1,8)\quad\text{and}\quad(2,4)
\]

at:

\[
106{,}496\text{ bits/output position}.
\]

Both use 36 tiles with 0% fragmentation.

### \(c=16\)

Minimum:

\[
\boxed{(2,8)}
\]

with:

- 18 tiles;
- 0% fragmentation;
- 36,864 activation bits;
- 32,768 psum bits;
- 69,632 total bits/output position.

### \(c=32\)

Minimum:

\[
\boxed{(2,16)}
\]

with:

- 9 tiles;
- 0% fragmentation;
- 18,432 activation bits;
- 32,768 psum bits;
- 51,200 total bits/output position.

The neighboring \((4,8)\) configuration is close at 53,248 bits/output position, but requires 10 tiles and wastes 10% of allocated CB capacity.

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

A key distinction established in the analysis is:

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

# 14. Current Stage-3 interpretation from the recorded discussion

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

# 15. Current findings from the packing analysis

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


---

# 21. Phase-aware static mapping metrics

All static mapping metrics are computed **offline from the traffic table and mesh, without simulation**, and all are **phase-gated**. A phase is a maximal time window in which the active-flow set is constant according to `t_on`, `t_off`, and `t_period`.

The hard rule is:

\[
\boxed{\text{Do not aggregate flows from disjoint phases as if they contend simultaneously.}}
\]

For mapping \(m\) and phase \(p\), compute the metrics below using only the active flow set \(F_p\).

## 21.1 Metric 1 — phase-gated volume-weighted OEB path diversity

For each active flow \(f\):

- \(v_f\): flow volume or offered rate, consistently defined;
- \(n_f\): number of **legal minimal paths under the actual OEB turn model** from source to destination.

The phase diversity score is:

\[
D_p
=
\frac{\sum_{f\in F_p} v_f n_f}
{\sum_{f\in F_p} v_f}
\]

when normalized for comparison across phases of differing load.

Also record **destination arrival-face diversity**: the number of distinct legal destination input ports through which the traffic can arrive. A large raw path count that collapses onto one final input port is not useful last-hop diversity.

Report:

- duration-weighted mean diversity across phases;
- bottleneck phase diversity \(\min_p D_p\);
- the phase and hotspot sink associated with the minimum.

Interpretation: \(D\) asks **whether adaptive routing has usable alternatives**.

## 21.2 Metric 2 — phase-gated peak offered link / arrival-face load

For each phase \(p\):

1. Enumerate legal minimal paths for each active flow.
2. As a static ideal-adaptive proxy, distribute each flow's offered rate uniformly across its legal paths.
3. Accumulate offered rate onto each link / destination arrival face.

For link \(\ell\):

\[
\lambda_{\ell,p}
=
\sum_{f\in F_p}
\lambda_f
\Pr(\ell\mid f)
\]

and:

\[
L_p
=
\max_\ell \lambda_{\ell,p}
\]

with headline:

\[
L^*
=
\max_p L_p.
\]

Also record:

- phase producing \(L^*\);
- link / arrival face producing \(L^*\);
- sink in-degree;
- fraction of phase volume converging on the hotspot sink.

**Important:** the current project evidence already gives **peak arrival-face load** predictive value, so it should remain the primary load-concentration metric; generic peak-link load can be retained as a secondary diagnostic.

The uniform-spread assumption must be stated explicitly. It represents an idealized adaptive-routing proxy, not the behavior of DP or BL themselves.

Interpretation: \(L^*\) asks **where and how strongly traffic concentrates**.

## 21.3 Metric 3 — communication cost

For each flow \(f\):

- \(B_f\): actual communication volume in bits, bytes, or flits;
- \(h_f\): 3D Manhattan hop count.

Then:

\[
C
=
\sum_f B_f h_f.
\]

If \(B_f\) is in flits, \(C\) is in flit-hops. If data-width asymmetry must be preserved, bit-hops or byte-hops are safer.

For a phase:

\[
C_p
=
\sum_{f\in F_p} B_f h_f.
\]

If \(B_f\) already denotes total phase volume, do **not** multiply by phase duration again. If a rate \(\lambda_f\) is used instead, then:

\[
C_p
=
T_p
\sum_{f\in F_p}\lambda_f h_f.
\]

Interpretation: \(C\) asks **how much total network work the mapping creates**.

## 21.4 Joint interpretation

| Diversity \(D\) | Peak load \(L^*\) | Expected interpretation |
|---|---|---|
| High | High | Congestion exists and alternatives exist — adaptive selection has opportunity |
| Low | High | Structural funnel — little routing policy can recover |
| High | Low | Comfortable network — expect DP ≈ BL |
| Low | Low | Little congestion and little route choice — policy largely irrelevant |

The three metrics are complementary:

\[
\boxed{
C=\text{network work},\quad
L^*=\text{bottleneck concentration},\quad
D=\text{routing opportunity}.
}
\]

A central Paper-1 hypothesis is that the classical minimum-\(C\) mapping may be **incomplete** for an adaptive NoC if it reduces path diversity or increases concentrated arrival-face load.

---

# 22. Experiment to test how diversity and peak load affect mean and p99

The experiment must remain **phase-aware throughout**.

## 22.1 Offline mapping population

For each workload and fixed architectural point \((c,r,s)\):

1. Generate a large offline population of legal tile/accumulator mappings.
2. For every mapping \(m\), compute:
   \[
   D_{m,p},\quad L^*_{m,p},\quad C_{m,p}
   \]
   for every phase \(p\).
3. Identify the critical phase(s), especially those with high load and/or low diversity.
4. Use \(C\) as a hop/communication confound control rather than allowing it to vary unnoticed.

No NoC simulations are needed during this screening stage.

## 22.2 Small structured simulation subset

Do **not** simulate dozens of mappings with 30 seeds immediately.

Select a small set spanning qualitatively different phase-gated metric regions, e.g.:

- low \(D\), low \(L^*\);
- high \(D\), low \(L^*\);
- low \(D\), high \(L^*\);
- high \(D\), high \(L^*\);
- current edge baseline;
- current metric-selected interior baseline.

This yields approximately six mappings per workload.

Run both:

\[
\boxed{\text{BL}}
\qquad\text{and}\qquad
\boxed{\text{DP}}
\]

initially with a modest seed count (e.g. \(n=10\)), promoting only decisive/interesting cases to \(n=30\). Existing n=30 ResNet edge/interior results should be reused rather than rerun.

## 22.3 Phase-specific dependent variables

For each mapping, policy, seed, and phase, measure:

\[
\overline T_{m,p}
\]

= mean packet delay for traffic belonging to phase \(p\), and:

\[
T^{99}_{m,p}
\]

= p99 packet delay for that phase.

Whole-run summaries are secondary; they must be derived only after phase-level analysis.

Also calculate DP-vs-BL benefit:

\[
G_{\text{mean},m,p}
=
\frac{\overline T^{DP}_{m,p}
-
\overline T^{BL}_{m,p}}
{\overline T^{BL}_{m,p}}
\]

and:

\[
G_{99,m,p}
=
\frac{T^{99,DP}_{m,p}
-
T^{99,BL}_{m,p}}
{T^{99,BL}_{m,p}}.
\]

Negative values mean DP is better.

## 22.4 Hypotheses

The planned hypotheses are:

\[
H_1:\ C\text{ strongly affects mean delay.}
\]

\[
H_2:\ L^*\text{ predicts p99 more strongly than mean delay.}
\]

\[
H_3:\ D\text{ alone does not guarantee lower delay.}
\]

\[
H_4:\ D\times L^*\text{ predicts when DP gains over BL.}
\]

\[
H_5:\ \text{high }L^*,\text{ low }D
\Rightarrow
\text{poor p99 for both policies.}
\]

The most interesting region is:

\[
\boxed{\text{high load}+\text{high diversity}}
\]

because congestion exists but the routing policy has choices with which to react.

If \(\arg\max_p L_p\) and \(\arg\min_p D_p\) identify the same phase and that phase also dominates measured p99, the analysis may legitimately focus on that critical phase rather than treating all phases as equally important.

---

# 23. Current workload blocks used for representative DNN traffic

The current representative block-level workloads are:

- **ResNet-50 stage-3 bottleneck:** conv1 → conv2 → conv3 plus projection shortcut / residual merge.
- **VGG-16 block 3:** conv5 → conv6 → conv7, purely sequential.
- **Transformer encoder block:** crossbar-mapped linear phases \(Q,K,V,O,FF1,FF2\), with \(Q/K/V\) sharing the block input and firing in parallel after the DAG dependency fix.

These are intended as **representative DNN communication motifs**, not complete full-network traffic fidelity.

The current Transformer modeling boundary omits:

\[
QK^T,\quad \text{softmax},\quad A V,\quad \text{LayerNorm}
\]

because these do not correspond to stored-weight crossbar operations in the current model. This must be stated as a limitation whenever Transformer results are presented.

---

# 24. Codex / implementation synchronization rule

Codex should **not** be assumed to inherit all discussion history from this ChatGPT Project.

Therefore:

\[
\boxed{
\text{discussion / decision}
\rightarrow
\text{this living project note or repository MD}
\rightarrow
\text{Codex implementation}
\]

Important locked assumptions, experimental protocols, measured results, retractions, and open issues should be committed or otherwise made available in project/repository Markdown files before expecting Codex to act on them.

This file is intended to serve as one such durable, project-wide research record.
---

# 25. Active repository baseline (merged from the archived 20–22 Aug record)

**Status date:** 22 Aug 2026. This section supersedes dated operational summaries while preserving their historical record in the archive.

## 25.1 Converter and DAG state

The active converter stack is model-agnostic **stage2_core.py** plus thin model definitions for ResNet, VGG, and Transformer. The ResNet regression gate remains byte-for-byte equality with the frozen generator and the committed base table.

The Transformer trunk no longer serializes Q, K, and V. Explicit dependencies allow Q/K/V to read the block input and execute concurrently. Phase construction advances by dependency level, each layer retains its own end time, and validation accumulates injection by actual window overlap. ResNet and VGG retained their prior flow structure under this change.

The current Transformer scope is still the stored-weight linear work only: Q, K, V, O, FF1, and FF2. QKᵀ, softmax, A·V, and LayerNorm are outside the current traffic model.

## 25.2 Active tables and timing

| Workload | Active table family | Period |
|---|---|---:|
| ResNet-50 bottleneck | **traffics_dnn_current/..._base.txt** and **..._base_interior.txt**, cpm \(2\times10^{-4}\), load scale 0.026 | 38,536 |
| ResNet diagnostic side experiment | **traffics_dnn_6base/rn50_6b_ls0.026_diag{,_accint}.txt** | 38,536 |
| Transformer encoder | DAG-fixed **transformer_encoder1_xb256_6x6x3_dag_cpm5e-5{,_interior}.txt** | 58,097 |
| VGG-16 block 3 | **vgg16_block3_xb128_6x6x3_cpm2.5e-5{,_interior}.txt** | 115,606 |

The pre-DAG Transformer tables and the ResNet \(10^{-4}\)-cpm tables are historical only and must not be used for active comparisons.

Current Transformer windows are Q/K/V \([0,5809)\), O \([5809,11618)\), FF1 \([11618,34857)\), and FF2 \([34857,58096)\). Runs use one period of warmup and two measured periods.

The DP cycle on the 6×6×3 substrate is 648 cycles. The different workload timing constants remain a modeling compromise. Current reporting should normalize operating points by reduction-sink ejection capacity rather than compare raw cpm values as if they were physical constants.

## 25.3 Instrumentation and figures

The simulator has environment-gated per-packet barrier tracing with offline grouping for reduction-barrier time. The trace path is bit-exactly inactive when the gate is unset.

Tile-level traffic DAGs exist for the ResNet bottleneck, VGG block 3, and the DAG-fixed Transformer encoder. Scatter edges constrain rank only when they ride the producer's window; block-input delivery riding a consumer window does not create a false dependency. The ResNet projection shortcut is therefore parallel with the trunk, and Q/K/V occupy the same Transformer rank.

---

# 26. Current measured Stage-3 results

All headline placement comparisons use the 6×6×3 substrate, relaxed OEB, no-skip, occupancy-cost DP versus buffer level, buffer 16, packet size 16 flits, and convergence interval 648. Throughput remained invariant and no deadlock was observed.

## 26.1 Transformer and VGG at their current knees

| Workload | Placement | DP mean | DP p99 | BL mean | BL p99 | DP vs BL mean / p99 |
|---|---|---:|---:|---:|---:|---:|
| Transformer, \(k=0.38\) | edge | 109 | 980 | 113 | 992 | −3.4% / −1.2% |
| Transformer, \(k=0.38\) | interior centroid | 186 | 1,841 | 315 | 6,216 | **−40.9% / −70.4%** |
| VGG, \(k=0.06\) | edge | 156 | 1,073 | 116 | 869 | **+33.9% / +23.6%** |
| VGG, \(k=0.06\) | interior centroid | 167 | 1,298 | 243 | 3,183 | **−31.5% / −59.2%** |

These are \(n=10\). Transformer edge is a tie, not a sign-reversal claim. VGG is the genuine edge case where DP loses. Edge+DP remains the best absolute configuration for Transformer; interior placement makes the policy choice matter, not the network universally faster.

## 26.2 ResNet box mapping at matched settings

The natural converter box mapping is the active ResNet base. At cpm \(2\times10^{-4}\), load scale 0.026, matched warmup/simulation, and \(n=30\):

| Placement | Metric | DP | BL | DP vs BL | paired \(t\) | DP better |
|---|---|---:|---:|---:|---:|---:|
| edge | mean | 155.2 | 120.4 | +28.8% | +5.42 | 5/30 |
| edge | p99 | 2,367.3 | 1,795.1 | +31.9% | +3.42 | 9/30 |
| interior | mean | 207.9 | 272.8 | **−23.8%** | −5.35 | 24/30 |
| interior | p99 | 2,815.6 | 5,648.1 | **−50.2%** | −8.94 | 29/30 |

This is the strongest current DP result. The earlier claim that the box mapping suppresses DP was caused by unmatched timing/load settings and is not part of the active findings.

The diagonal mapping remains a separate sender-spread side experiment, not a mapping-ladder rung. At matched settings its interior p99 result is −37.2% for DP versus BL, but it carries a placement-selection-rule confound and has better absolute delay than the box mapping.

## 26.3 Locked interpretation

- Short edge routes reduce absolute delay but pin heavy reductions to constrained arrival faces.
- Interior placement adds hops yet makes congestion spatially routable.
- DP can exploit non-local downstream information; BL may collapse when a locally attractive neighbor feeds the same downstream funnel.
- A larger relative DP gain does not imply a better absolute mapping.
- Mapping is an enabling condition for congestion-aware selection, not merely a background parameter.

---

# 27. Placement metric and mapping ladder

The placement scorer now ports the relaxed OEB behavior actually compiled in the simulator. Planar and vertical options coexist in the relevant ascending and descending cases. Historic modified2 behavior remains available only for reproduction.

The scorer evaluates all sinks; display depth no longer changes the objective. Peak arrival-face load is the primary placement objective because it has measured predictive ordering across four matched ResNet placements:

| Peak arrival-face load | DP-vs-BL p99 |
|---:|---:|
| 0.190 | −50.2% |
| 0.254 | −37.2% |
| 0.297 | +5.1% |
| 0.382 | +31.9% |

Worst-face/mean-face is only meaningful for the same sink and must not replace the peak-load objective.

The active mapping ladder is:

1. edge control;
2. metric-selected interior placement;
3. later NSGA mapping.

ResNet uses box edge and box interior as rungs 1–2 and is complete at \(n=30\). The diagonal mapping is orthogonal sender-spread analysis. Transformer and VGG need their interior controls regenerated under the same phase-aware peak-arrival-face rule before promotion to \(n=30\).

---

# 28. Reduction-sink ejection bandwidth is the current load normalization

At true model rates, the hottest reduction sink is oversubscribed relative to its one-flit-per-cycle ejection port. The current load scale should therefore be interpreted as the fraction of real demand simulated.

| Workload | Hot sink demand at scale 1 | Scale for one port | Scale used | Knee \(k\) | Effective scale | Port fraction at knee |
|---|---:|---:|---:|---:|---:|---:|
| ResNet conv2 | 18.4 flits/cycle | 0.0542 | 0.026 | 1.00 | 0.0260 | **48.0%** |
| Transformer ff2 | 23.9 | 0.0419 | 0.050 | 0.38 | 0.0190 | **45.4%** |
| VGG conv7 | 147.6 | 0.0068 | 0.050 | 0.06 | 0.0030 | **44.3%** |

All three current workloads knee at approximately 44–48% of the dominant sink's ejection bandwidth. This is independently consistent with the ResNet trace observation at 48% of a port.

The current decision is to retain the existing MACs-times-cpm converter model and report operating point as a fraction of sink capacity. VGG remains deliberately time-compressed; regenerating it with a spatially derived duration is optional and would cost roughly ten times the simulation time.

---

# 29. Current packing formulation and corrected whole-block ResNet sweep

For each layer \(l\):

\[
N_{\text{tiles},l}
=
\left\lceil\frac{R_{xb,l}}{r}\right\rceil
\left\lceil\frac{C_{xb,l}}{s}\right\rceil,
\qquad rs=c.
\]

The current tables use \((c,r,s)=(8,1,8)\). Larger \(r\) internalizes more reduction; larger \(s\) internalizes more activation sharing.

The network reduction term is always:

\[
\left\lceil\frac{R_{xb,l}}{r}\right\rceil-1,
\]

because the accumulator is hosted on one contributor tile.

For the full representative ResNet block, the raw grids are conv1 \(4\times16\), conv2 \(18\times16\), conv3 \(2\times64\), and projection shortcut \(4\times64\), totaling 736 working crossbars.

| \(c\) | \(r\) | \(s\) | Tiles | Allocated CBs | Used CBs | Unused CBs | Unused % | Scatter traffic | Reduce traffic | Total NoC traffic |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | 1 | 8 | 92 | 736 | 736 | 0 | 0% | 94,208 | 147,456 | 241,664 |
| 8 | 2 | 4 | 92 | 736 | 736 | 0 | 0% | 188,416 | 53,248 | 241,664 |
| 8 | 4 | 2 | 112 | 896 | 736 | 160 | 17.86% | 376,832 | 16,384 | 393,216 |
| 8 | 8 | 1 | 192 | 1,536 | 736 | 800 | 52.08% | 753,664 | 8,192 | 761,856 |
| 16 | 1 | 16 | 46 | 736 | 736 | 0 | 0% | 47,104 | 147,456 | 194,560 |
| 16 | 2 | 8 | 46 | 736 | 736 | 0 | 0% | 94,208 | 53,248 | **147,456** |
| 16 | 4 | 4 | 56 | 896 | 736 | 160 | 17.86% | 188,416 | 16,384 | 204,800 |
| 16 | 8 | 2 | 96 | 1,536 | 736 | 800 | 52.08% | 376,832 | 8,192 | 385,024 |
| 16 | 16 | 1 | 176 | 2,816 | 736 | 2,080 | 73.86% | 753,664 | 4,096 | 757,760 |
| 32 | 1 | 32 | 34 | 1,088 | 736 | 352 | 32.35% | 34,816 | 147,456 | 182,272 |
| 32 | 2 | 16 | 23 | 736 | 736 | 0 | 0% | 47,104 | 53,248 | **100,352** |
| 32 | 4 | 8 | 28 | 896 | 736 | 160 | 17.86% | 94,208 | 16,384 | 110,592 |
| 32 | 8 | 4 | 48 | 1,536 | 736 | 800 | 52.08% | 188,416 | 8,192 | 196,608 |
| 32 | 16 | 2 | 88 | 2,816 | 736 | 2,080 | 73.86% | 376,832 | 4,096 | 380,928 |
| 32 | 32 | 1 | 160 | 5,120 | 736 | 4,384 | 85.63% | 753,664 | 0 | 753,664 |

The communication minima are:

- \(c=8\): \((1,8)\) and \((2,4)\) tie;
- \(c=16\): \((2,8)\);
- \(c=32\): \((2,16)\).

All minimum points have zero unused crossbar capacity. This alignment is workload-specific and must be tested separately for VGG and Transformer.

The packing sweep remains analytical first. The ADC organization must be fixed before claiming a compute/communication U-curve: per-crossbar ADC banks imply no density penalty, while tile-level sharing implies a serialized compute penalty. The simulator does not model intra-tile contention, so any such penalty is an explicit analytic assumption.

---

# 30. Current contribution framing

The active cross-layer claim is that the design space is not separable:

\[
(c,r,s)
\rightarrow
\text{traffic morphology}
\rightarrow
\text{3D placement and hotspots}
\rightarrow
\text{DP/BL relative effectiveness}
\rightarrow
\text{mean and p99}.
\]

The strongest current evidence is:

1. packing density and orientation determine how much reduction remains on the NoC;
2. placement determines whether that congestion is structurally pinned or routable;
3. peak arrival-face load predicts the sign and magnitude of the DP-vs-BL p99 effect across matched ResNet placements;
4. the three workloads knee at a common fraction of dominant-sink ejection capacity;
5. DP is not universally better than BL, making traffic-structure-dependent crossover the important result.

These points support a cross-layer DSE contribution. They do not support an unqualified first-work claim; Section 20's reviewer-style novelty checks remain mandatory.

---

# 30a. Partial-sum width — decided, and it is a convention not a derivation

**Decision: INT8 activations, INT32 partial sums (`BYTES_PER_ACT = 1`,
`BYTES_PER_PSUM = 4`).** This is the existing setting — unchanged since the
original converter commit `8ec5fa9` — so no table is regenerated and every
published number stands. Verified directly from the committed ResNet table:
conv2 reduce is 34 flows × 100,352 B over 128 ch × 196 positions = **4 B/element**.

**It is not derivable.** For 8-bit operands on a 128-row array the precision
floor is 16 + 7 = 23 bits, i.e. **24-bit**, so INT32 is one byte wider than the
arithmetic requires. The three self-consistent options are:

| activations | derived psum | psum:act | reduce share (ResNet) |
|---|---|---|---|
| INT8 | 24-bit | 3:1 | ~76% (untested) |
| INT8 | INT32 (convention) | **4:1** | **81.8%** ← adopted |
| INT16 | 32-bit (24+7=31→32) | 2:1 | 69.1% |

The INT16/32-bit row is *derivable* but self-defeating: doubling activations
restores a 2:1 ratio, which is **exactly the 16-bit-psum tables ×2** (verified,
2.0000× on every traffic class), so it reproduces the weaker 16-bit results.

**Statement for the paper.** INT32 is the conventional digital accumulator
width. It is *wider* than both the 24-bit floor and ISAAC's 16-bit datapath, and
recent work quantizes inter-tile psums to INT8 (APSQ). It therefore **overstates
reduction traffic**, which is the traffic the contribution exploits — so it is
the *favourable* direction, not a conservative one. Earlier notes calling INT32
"conservative" were **wrong and are retracted**. The defence is the measured
robustness below, not the width itself.

**Accumulation headroom does not justify it here.** `reduce_within` is a **star**
— every `(r,c)` ships its own output directly to `acc(c)`, so no running sum ever
crosses the network, and each flow carries one tile's 16-bit shift-added result.
Packing is exact (`packets = ceil(bytes/64)`), so there is no word-alignment
waste either. Headroom becomes a real argument only under **tree reduction**
(Section 4 alternative, unimplemented), where intermediates travel and 24-bit
would be derivable.

## 30b. 16-bit robustness runs — ResNet and VGG hold, Transformer does not

Generated `traffics_dnn_p16/` via a new `DNN_BYTES_PER_PSUM` env override
(default 4, so existing tables regenerate byte-for-byte — verified).

- **ResNet, n=30:** edge +20.8%, interior **−18.4% mean / −44.4% p99** (t −3.21 /
  −6.52). Every sign and significance verdict reproduced.
- **VGG, n=10:** edge +32.5%, interior **−15.9% / −47.7% p99**. Reproduced.
- **Transformer: does not reproduce.** Tested at its edge knee, its interior knee
  (k=1.0, n=30: **+7.8%…+14.3%, DP significantly worse**), past the knee, and in
  saturation. DP is null or worse at **every usable operating point**. The single
  favourable number (−21.0% p99) comes from ~1.9× past the knee where BL p99 is
  ~10× its knee value — not a reportable operating point.

**Why, computed without simulation:** placement headroom is the gap between the
hottest sink and the cluster beneath it. **ResNet has 2 sinks within 20% of its
peak (2.0× span); the Transformer has 13 (1.25× span)**, exhausted after three
relocations. Moving 6 sinks instead of 3 leaves the peak unchanged at 0.217 on
the same node. Scope claim: *the mechanism needs a deep, isolated reduction
funnel; the transformer encoder has neither.* This also predicts a nearly flat
Transformer NSGA front in \(f_1\).

## 30c. Crossbar-size uniformity is available at zero cost (open decision)

`tools/stage2_vitsmall.py` — DeiT-S (d=384, ff=1536, Touvron et al. ICML 2021) at
**XB=128**, `cpm 2e-4`. Its tile grid is *identical* to ViT-Base@256 (q/k/v/o 3×3,
ff1 3×12, ff2 12×3 = 108 tiles, depths 2/2/2/2/2/11) and its phase windows match
exactly. **The tables are a pure ×2.0 rescale** (identical src/dst/windows, pir
ratio min = max = 2.000000), confirmed **seed-for-seed: 40/40 bit-identical** runs
at both psum widths. So adopting it makes all three workloads 128×128 **with no
re-runs** — a relabelling, not new science.

ViT-Base cannot be used at 128 (432 tiles > 108 nodes). Going the other way — 256
for all — is worse: ResNet/VGG drop to **23 tiles (21% occupancy)** and their
funnels halve (depth 17 → 8), weakening the phenomenon.

**Do not vary crossbar size and psum width together** (e.g. TF at 256/32 with the
others at 128/16). Each choice is individually derivable, but the width is
exactly what decides whether the Transformer result holds, so the combination
reads as parameter-shopping.

## 30d. Report the result in two dimensions

Recorded in full in the `dp-relative-vs-absolute` memory. Summary:

1. **Relative policy advantage** — interior placement makes DP beat BL:
   ResNet box −50.2% p99 (n=30), Transformer −70.4%, VGG −59.2%.
2. **Absolute performance** — interior is usually *not* the fastest mapping.
   Best p99 config: ResNet box **edge+BL** (1795), VGG **edge+BL** (869),
   Transformer **edge+DP** (980) — but ResNet **diag** is the counterexample,
   where **int+DP (1439) is outright best**, −39.3% vs edge+DP.

**The framing that makes it a contribution:** real 3D mappings are
multi-objective, and thermal / power-density / hotspot constraints can force
non-minimum-hop placements. **DP recovers 83–92% of the tail penalty of a
displaced placement** — under BL, being pushed interior costs +215% (ResNet),
+527% (TF), +266% (VGG) on p99; under DP, +19%, +88%, +21%.

So the mapping objective is **not** "maximise DP advantage" (that drives the
search toward deliberately bad placements) but **minimise absolute delay subject
to the constraint set, with DP making the constrained region affordable**. The
NSGA demonstration is that the DP front dominates the BL front *across* the
constrained region, not at one point.

⚠ Thermal and power-density constraints are **motivation, not measurement** —
noxim models neither. Cite the 3D-IC thermal literature or state it as the design
scenario the interior placements stand in for.

---

# 30e. Paper story — the cross-layer narrative (high level, then detail)

The agreed narrative order for Paper 1: state the thesis, give the causal chain,
then descend into the evidence link by link. This section is the reference text
for that story. Numbers are carried from the sections above and from
`results_stage3/mapping_pilot/` (see §30e.7 for provenance).

## 30e.1 Level 0 — the thesis and the message

> In an IMC DNN accelerator the NoC's workload is **decided upstream at packing,
> not at the network**. Packing orientation fixes an invariant port floor *and*
> the number of active tiles; mapping fixes the peak link load; delay — hence
> inference time — is set by whichever of the two binds. Adaptive routing pays
> only where the binding resource still has escapable alternatives.

**Message:** the layers are not separable, so the minimum-communication-volume
packing is not the minimum-latency packing after 3D placement:

\[
PO^*_{BW}\neq PO^*_{Arch}.
\]

**Secondary message:** DP is *not* universally better than BL. The
traffic-structure-dependent crossover is the result, not a defect.

## 30e.2 Level 1 — the causal chain

```
PD = c              design-time hardware: crossbars provisioned per tile
   |  enumerate PO = (r,s),  r*s = c
PO                  logical grouping
   |--> tile grid   ceil(R_xb/r) x ceil(C_xb/s)  -> ACTIVE TILES + fan-in/fan-out
   |--> PF          port floor (reduction exposed vs internalised, sink fan-in)
   |
ACTIVE TILES  ---->  defines the mapping PROBLEM (tiles vs nodes, idle slack)
   |
MAPPING       ---->  PL   (peak link load; the only placement-visible term)
   |
BIND = max(PF, PL)  ---->  mean delay, p99  ---->  inference time
   |
   +----------------->  whether SELECTION (DP vs BL) has anything to exploit
```

**This chain is the candidate Paper-1 flow figure** (see §30e.8).

## 30e.3 Level 2 — evidence, link by link

**PD/PO → PF.** `(r,s)` at fixed `c` decides how much reduction is internalised
on-tile versus exposed to the NoC, which sets the flow graph's injection and
ejection load. Placement can only *relabel* which node carries it, never lower it
— verified identical to 6 dp across 9 random permutations. For ResNet-50 stage-3
at `(8,2,4)`: injection **0.3916**, ejection 0.1270 at `k=1`; injection saturates
at `k=2.55`. At `(16,2,8)` the floor is **0.2582**.

Feasibility is a separate and weak filter — sustained rate ≤ 1 rejects only 5 of
34 `(c,r,s)` points. **Peak PF is the delay lever, not the filter.**

**PO → active tiles.** The same choice sets the size and shape of the placement
space. ResNet-50 stage-3 block, 108 nodes (from the §29 grids):

| c | (r,s) | active tiles | idle nodes | occupancy |
|---:|---|---:|---:|---:|
| 8 | (1,8) | 92 | 16 | 85% |
| 8 | (2,4) | 92 | 16 | 85% |
| 8 | (4,2) | 112 | — | **infeasible** |
| 16 | (2,8) | 46 | 62 | 43% |
| 32 | (2,16) | 23 | 85 | 21% |

**Mapping → PL.** Placement moves only transit. Over 1000 random placements PL
spans 0.122–0.364 (**2.98×**); a PV-constrained hill-climb widens it to
0.127–0.490 (**3.86×**) while holding path diversity to ±0.9%. PL is genuinely
actionable, but only within that reachable range.

**BIND → delay — the hinge.** This is the pivot of the paper.

- **Below the floor, placement is inert.** A 2.3× spread in peak transit link
  load produced **−0.1%** mean delay, t = −0.02 (n=30 seeds, `k=1.5`), with signs
  inconsistent across four comparisons. Seeds required to resolve it: **226,857**.
  The effect is *absent*, not underpowered. Only 1 of 200 random mappings had
  transit exceeding the floor at all.
- **Above the floor, PL turns on hard.** Hinge regression over 24 hill-climbed
  placements at `k=1.80`, n=30 seeds each (BL):

  | model | R² | below-floor slope | above-floor slope |
  |---|---:|---|---|
  | avg delay ~ PL | 0.404 | — | — |
  | avg delay ~ PL + hinge@floor | **0.735** | −5 (t=−0.16, ns) | **+655 (t=+5.13, p<0.0001)** |

  DP on the same 24: r = +0.535, hinge R² 0.559, above-floor slope +562
  (t = +3.61).

Every earlier null in the mapping study was measured entirely below the floor,
which is **why** it was null.

**Selection.** Same structure one level down, sized by the **escapable fraction**
\(1 - PL_{forced}/PL\):

| regime | n | BL | DP | DP − BL | placement spread BL → DP |
|---|---:|---:|---:|---|---|
| below floor | 17 | 124.6 | 123.1 | −1.1% (t=−0.90, ns) | 1.151× → 1.257× |
| above floor | 7 | 160.5 | 149.6 | **−6.7% (t=−2.65, p=0.008)** | 1.710× → 1.792× |

Below the floor DP **substitutes** for placement (best-vs-worst gap 1.235× under
BL collapses to 1.034× under DP). Above the floor it does not: it shaves the
level but leaves the placement spread as wide as it found it. Escapable fraction
sizes the gain directly — 1.1% escapable → 0% gain, 47.6% → 70%.

This is the same mechanism as the edge→interior arm of §26 (ResNet −50.2% p99,
Transformer −70.4%, VGG −59.2%): interior placement does not make the network
faster, it makes congestion escapable. Reader-facing form: **DP recovers 83–92%
of the tail penalty of a displaced placement** (§30d), which is what makes a
thermally or physically constrained mapping affordable.

## 30e.4 Why this is cross-layer, in the strong sense

"Cross-layer" is only load-bearing if it means **the sign of an effect in one
layer changes with a decision made in another layer** — not merely that two
things were tuned together. Three measured couplings, each conditional rather
than additive:

1. **Packing gates placement.** A well-chosen `(r,s)` drives the design
   injection-limited and placement goes inert. A placement algorithm cannot be
   evaluated without naming the packing it sits on; on `(8,2,4)` every placement
   heuristic scores identically, and that is a property of the packing.
2. **Placement gates routing.** DP *loses* at edge (+28.8% mean, ResNet box,
   t=+5.42) and *wins* at interior (−50.2% p99, t=−8.94, 29/30 seeds). Same
   policy, same workload, opposite sign. "DP beats BL" is not a policy result,
   only a policy-at-a-mapping-point result.
3. **The pre-NoC objective mispicks.** Minimum communication *bytes* is not
   minimum latency after placement — demonstrably wrong for VGG and DeiT-S. This
   is the direct falsification of the decoupled flow.

## 30e.5 The layer stack and the scope boundary

| Layer | Decision | Quantity it fixes | Timescale |
|---|---|---|---|
| Device / architecture | XB size, ADC organisation, **PD = c** | crossbars per tile | design-time, hardware |
| Logical mapping | **PO = (r,s)**, `rs = c` | **PF**, active tiles, fan-in structure | per workload, possibly per layer |
| Physical mapping | tile → node in 3D | **PL** | per workload |
| Network | turn model + selection (BL / DP) | escapable fraction of BIND | runtime |
| System | — | mean / p99 → inference time | — |

Conventional flows run this top-down against **pre-NoC objectives** —
utilisation, tile count, fragmentation, total communication volume — and pass a
frozen decision downstream with no feedback from achievable network performance.

**Scope boundary, to be stated explicitly.** Three adjacent layers are coupled
here — packing → placement → selection — with PD as a design-time outer loop.
This is *not* algorithm-level co-design: the DNN is fixed, there is no
quantisation or pruning feedback, the mesh is pinned at 6×6×3, and thermal is
motivation rather than measurement. Claiming the three and naming the rest as
deliberately fixed outer loops reads as scope control; an unbounded "cross-layer"
claim invites the reviewer to ask why topology and network were not co-optimised
too.

## 30e.6 Cross-layer exploration — the methodological claim

The contribution is a **nested design-space exploration**, not a mapping
heuristic:

\[
PO^*_{Arch}
=
\arg\min_{PO}
\left[
\min_{M\in\mathcal M(TT_{PO})} J_{NoC}(TT_{PO},M)
\right]
\]

For each PD, enumerate the small discrete PO set; each PO induces its own traffic
table **and its own placement space**; search that space; compare POs only at
their best achievable placement. The methodological claim is that **the inner
loop must be solved before the outer loop can be compared at all** — a PO
evaluated on one arbitrary placement is not evaluated. That is exactly what the
decoupled flow does when it selects packing on utilisation or communication
volume.

Selection policy stays **outside** the objective by construction: DP-vs-BL is
characterised on the chosen points and never optimised for, or the search would
drift toward deliberately bad placements in order to flatter DP. (Same rule as
the PD–PO prompt document.)

## 30e.7 Provenance and what is still soft

The floor/hinge results above come from `results_stage3/mapping_pilot/` and were
**not previously recorded in this file**:

- `mapping_pilot/README.md` — the (8,2,4) invariant floor and the placement null
  (408 runs).
- `mapping_pilot/pool1000/hill/README.md` — the PV-constrained hill-climb, the
  hinge regression and the DP-by-regime split (1440 runs, k=1.80, n=30).

Soft points, all of which must be stated or closed before submission:

1. **PL is an offline model, never measured online.** The model spreads each flow
   evenly over all OEB-admissible minimal paths; a real selection policy does
   not. `-detailed` reports per-(src,dst) pairs, not per-link.
2. **The hinge is replicated across two load levels, but on one packing.**
   24 placements, only **7** above the floor. Replicated over k=1.60 and k=1.80
   × BL and DP, 2,880 runs, zero failures — hinge R² 0.705/0.735 (BL) and
   0.536/0.559 (DP), below-floor slope non-significant throughout, above-floor
   slope t = +3.57…+5.13. Table in `docs/PD-PO-DESIGN-FLOW.md` Step 4. What is
   *not* replicated is the packing: everything is ResNet \((8,2,4)\).
3. **Above-floor scatter is wide** (127.6–218.3 across PL 0.455–0.490): PL sets
   the *onset* of the effect, it does not order what happens past it. The top
   point sits at 0.882 of capacity and is partly a saturation effect.
4. **`PL_forced` is retracted as a predictor** — 83% collinear with PL, adds
   nothing over BIND. It survives only as a diagnostic at equal PL, and as the
   escapable-fraction numerator.
5. Transformer and VGG remain at n=10 on the edge/interior arm.
6. **The "two channels" mechanism below is a hypothesis, not a measurement.**

**[HYPOTHESIS, untested]** Packing plausibly gates placement through *two*
independent channels: the **floor** (PF sets the bar PL must clear before
placement is visible) and the **slack** (active-tile count sets how freely
placement can spread — 92 tiles on 108 nodes is a tight permutation problem,
23 tiles on 108 leaves 85 idle nodes where a search can drive PL below any
floor). Both push the same way, so a dense low-tile-count packing would tend to
make placement inert for two different reasons a single-layer study could not
separate. This would explain the `(16,2,8)` screen result — lowering PF did not
buy above-floor room because tile count halved at the same time — but the
tile-count channel has **not** been isolated experimentally. Do not present it as
a finding.

## 30e.8 Figures the story needs

- **Flow figure (the chain of §30e.2)** — PD → PO → {PF, active tiles} → mapping
  → PL → BIND → delay/p99, with the selection box hanging off BIND as a
  characterisation rather than an objective. Not yet drawn. The contrast against
  the decoupled flow is specified in `docs/PD-PO-ARCHITECTURE-AWARE-PROMPTS.md`
  (Prompts 2 and 3).
- **Hinge figure** — `figs/hill_pl_hinge.png` exists.
- **Metric-space figure** — `figs/pool1000_hill_metric_space.png` exists (shows
  what the directed search bought over random sampling).
- **Packing figure** — `figs/fig_packing_rs.{dot,pdf,png}` exists (conv2's 18×16
  grid packed three ways at c=8).

## 30e.9 Directions out

1. **DP is spatial only; it needs a temporal term.** The cost field is a
   snapshot, and DNN traffic is phase-structured — the correct field is knowable
   at cycle 1 of a burst. Phase-indexed DP is the non-learning baseline; the RL
   contribution must beat it. This is Paper 2 / Stages 4–7.
2. **Thermal-aware analysis and mapping.** Currently the *motivation* for
   interior placement, not a measurement (noxim models neither thermal nor power
   density). Making it a measurement converts "DP makes constrained placements
   affordable" from a framing into a result.
3. **Router design for DNN NoCs.** The bottleneck is a reduction sink's single
   ejection port, 18–148× oversubscribed at true rates (§28). That is an
   architecture problem rather than a routing one — multi-port ejection,
   in-router accumulation, or a reduction-aware NI.

---

# 31. Active open work

1. Regenerate Transformer and VGG interior controls using the common phase-aware peak-arrival-face rule, moving only the hot layer's current argmax sinks.
2. Run those edge/interior controls with matched seeds, initially \(n=10\) and promote decisive cases to \(n=30\); reuse completed ResNet \(n=30\) runs.
3. Complete the offline phase-aware mapping population using \(D_p\), \(L_p^*\), and \(C_p\), then select the small structured simulation subset in Section 22.
4. Derive the full VGG and Transformer \(c,r,s\) tables from their actual model definitions and verify the \((8,1,8)\) tile counts against the DAG before using any result.
5. Decide the ADC organization before modeling a density-dependent compute penalty.
6. Keep the diagonal ResNet mapping separate unless its interior nodes are reselected under the corrected common scorer.
7. Resolve the documentation contradiction between published unmodified OEB wording and the relaxed OEB substrate used by the active runs.
8. Decide whether to regenerate VGG with the spatial duration; if not, state its deliberate time compression.
9. Add a second mesh size so the 3D claim is examined rather than asserted.
10. Check **MAX_STATIC_DIM** and **DPSIZE** before any larger topology.
11. Re-measure the carried-over claims that no-skip beats skip and random beats buffer level before using them; they remain unverified.
12. Verify the DP cost read path is atomic across the two clock domains and plot the DP cost field over time if that simulator-level question is reopened.
13. Decide whether to adopt DeiT-S at **XB=128** so all three workloads share one crossbar size (Section 30c). Costs nothing — verified 40/40 bit-identical — but relabels the workload and needs the Touvron citation.
14. Promote Transformer and VGG to \(n=30\) at the 32-bit setup. Both are currently \(n=10\) with wide intervals; today's work showed \(n=10\) reversing a conclusion (a Transformer point read +0.6% at \(n=10\) and **+20.2%, significant**, at \(n=30\)). ~240 sims.
15. **Packing is not a free variable in the generator.** `stage2_core.py` sets `cols = cout` with no `N_bits`, so a tile is one row-group × one output-channel group and its 8 crossbars are the 8 **bit-planes**: measured across all 13 layers of all three workloads, \(r=1\) and \(s=N_{bits}=8\), always. \(r>1\) is forbidden by the `R >= base_R` assert (`stage2_core.py:106`). Any \(c,r,s\) study therefore needs converter work, and the documents' "output grouping" reading of \(s\) must first be reconciled with the code's bit-plane reading.
16. Never rescale a table by a single scalar to match a different psum width. Reduce halves while scatter does not, so no scalar restores the mix: matching peak arrival-face load over-drove total load by 34%, and matching total load under-drove reduce to 0.74× while over-driving scatter to 1.49×. Locate each configuration's own knee instead.

---

# 32. Document maintenance rule

This file is the **single active source of truth** for project-wide research state.

- Update this file when an assumption, protocol, measurement, correction, retraction, or open item changes.
- Keep focused companion documents for detailed derivations, implementation history, or archived snapshots, but do not let them become competing current-state summaries.
- The archived dated session note is historical evidence only.
- When another document conflicts with this file, resolve the conflict here and mark the other statement as historical or superseded.

---

# 33. Paper 1 thesis — the four-claim conclusion set

**Status:** Locked as the paper's thesis and contribution. All results are organised to support one of these four claims; anything unsupported gets revised. The spatially-aware policy used to demonstrate the claims is DP.

**Claim 1 — BIND determines delay.** What determines average delay and p99 — and hence inference time — is a single quantity, with high confidence and high correlation: BIND equals max of PF and PL. PF is the local injection/ejection port floor set by packing; PL is peak load in the network. Whichever is larger binds. Delay tracks BIND, not the individual terms.

**Claim 2 — Where PL is below PF, mapping is inert, and that is a licence not a limitation.** For mappings that do not alter BIND, no mapping choice changes delay; average and p99 stay almost the same across very different placements. The determining layer there is PO, packing orientation, not placement. Design rule: once PL below PF is verified, the mapping budget is free — spend it on thermal, communication cost, energy, load balancing, or any other objective, at no latency penalty. This converts the earlier apparent null into a positive licence for multi-objective mapping.

**Claim 3 — Where PL exceeds PF, mapping determines delay.** For mappings that cannot keep PL under the floor, control shifts from packing to placement, and the mapping sets average delay.

**Claim 4 — In the above-floor regime the mapping lever is escape room at the binding link, and it is close to free.** Where PL exceeding PF is unavoidable, what decides whether a congestion-aware policy can recover the added delay is the load-weighted escape room on the link that binds:

\[
D_{esc}
=
\frac{\sum_f \lambda_f\,\phi_f\,(1-\phi_f)}{\sum_f \lambda_f\,\phi_f},
\qquad\text{at the } PL\text{-argmax link,}
\]

where \(\phi_f\) is the fraction of flow \(f\)'s OEB-admissible minimal paths that cross that link, so \(\phi_f = 1\) means forced — the link is a cut edge of \(f\)'s path DAG and no selection policy can divert it. \(D_{esc}\) is the component of path diversity that actually produces escapable load: it tracks the escapable fraction \(E = 1 - PL_f/PL\) at \(r = +0.85\) to \(+0.96\) in every population scored, whereas global path variety tracks it at only \(+0.43\), and not at all under a directed search.

**\(D_{esc}\) is not bought with communication cost.** It is decoupled from PL — the full 0–1 range of \(E\) is available within every PL quartile, \(r(E,PL) = -0.148\) — and decoupled from CC, \(r(D_{esc},CC) = +0.040\). At matched path variety it is *negatively* priced: partial \(r(E,CC\mid PV) = -0.28\). What **is** expensive is global path variety, \(r(PV_{global},CC) = +0.56\) in a random pool and \(+0.87\) under directed search — and that component does not deliver escape room, \(r(E,PV_{global}) = -0.045\) in the very sweep built to maximise it.

Consequence, revised: the classical minimum-communication-cost mapping is **not wrong** above the floor, it is **incomplete**. CC and escape room are largely orthogonal, so minimising CC neither buys nor forfeits \(D_{esc}\). Escape room has to be a separate search objective, not a by-product of any cost or variety term.

**CONFIRMED OFFLINE 2026-08-27 — open item 3 closed.** A hill-climb targeting \(D_{esc}\) directly, above the floor, with CC left free (n=22, `desc_price.py` → `desc_price.csv`) gives \(r(D_{esc},CC) = -0.221\) (ns); the top and bottom halves of the \(D_{esc}\) range differ by 3.3× in escape room and **+0.007 in CC** (t=+0.01, p=0.99). In the same population \(r(PV_{global},CC) = +0.859\) and \(r(D_{esc},PV_{global}) = -0.044\). Escape room is free, global path variety is expensive, and the expensive term buys none of the useful one. Not an argmax artifact: four placement pairs share the *identical* hot link at opposite \(D_{esc}\) extremes (0.000 vs 0.201), and in three of four the high-\(D_{esc}\) member is also cheaper in CC.

**\(D_{esc}\) is itself the link-conditioned diversity measure.** The relevant diversity is \((1-\phi_f)\), the share of \(f\)'s paths avoiding \(\ell^*\), so \(D_{esc}\) is *load × diversity transverse to the bottleneck*. There is no separate PV to pair with it. Path **count** is the wrong primitive: \(n_f=100\) with every path crossing \(\ell^*\) yields zero divertibility, \(n_f=2\) with one avoiding it yields 0.5. \(PV_{global}\) is weighted by flow volume and never sees hop count or link occupancy; \(PV_{local}\) has the right weighting but keeps \(\log_2 n_f\), a whole-flow count that credits paths which also cross \(\ell^*\) — a half-conversion, and the reason it behaved inconsistently.

**Where PV does matter — the absorption question (open).** Offline PL assumes even spreading. Where \(D_{esc}\) is high, a real policy pulls load *off* \(\ell^*\), so the realised online peak is below the offline PL. What decides the net gain is where that load lands: with few distinct alternatives it re-concentrates on one alternate link and no peak reduction results; with many it spreads. So **\(D_{esc}\) says how much can leave, PV says whether the alternatives absorb it.** This makes offline PL an upper bound whose looseness is \(D_{esc}\), and predicts the second-hottest link limits the achievable gain. Checkable offline by recomputing the link field after removing the escapable share from \(\ell^*\). Not run.

**REVISED 2026-08-27 — Claim 4 restated as a placement-freedom licence.** Simulation on two independent above-floor populations (PV sweep, \(n=21\), \((8,2,4)\), PL and CC pinned, BL+DP \(n=30\); cc12, \(n=12\), \((16,2,8)\), \(k=2.0\), BL+DP \(n=10\)) does **not** support \(D_{esc}\) as a predictor of DP gain, and supports a different and simpler statement instead.

**What DP does.** DP does not make good placements faster — on the fastest placements BL matches or beats it (DP loses on 6/21 and 3/12). What DP does is remove the tail and compress the spread:

| population | avg spread BL → DP | CV BL → DP | worst case |
|---|---|---|---|
| PV sweep \(n=21\), PL pinned | 1.59× → **1.45×** | 0.145 → **0.101** | 194 → 153 |
| cc12 \(n=12\), PL pinned | 64.3× → **8.6×** | 2.551 → **1.123** | 5566 → 732 |
| PL sweep \(n=7\), PL varying | 1.71× → 1.79× | 0.174 → 0.209 | — |
| PL sweep \(n=7\), \(k=1.60\) | 1.85× → 1.81× | 0.199 → 0.210 | — |

The two populations that narrow are the two with **PL pinned**; the two that do not are the two with PL varying (0.41–0.49). DP cannot compress spread caused by PL itself — that is BIND, and no routing decision changes what a link must carry. It compresses the spread caused by everything else.

**Claim 4, restated.** *Above the floor, routing selection determines delay and p99. DP recovers the loss BL incurs and narrows the variation of both across placements of equal PL — which returns placement freedom, so the mapping can be optimised for fault tolerance, thermal balance, or other objectives at little latency cost.* This is the Claim 2 licence extended above the floor: below the floor the mapping budget is free because mapping is inert; above the floor it is largely free **once PL is chosen**, because DP flattens what remains. Claim 4 therefore sits directly beneath Claim 1 rather than competing with it.

**What predicts DP's gain: how badly BL is doing.** \(r(\log BL, \text{gain}) = +0.807\) over the pooled \(n=33\) (\(R^2 = 0.652\)); \(r(BL, \text{gain}) = +0.684\). Excluding the two BL-collapse cases, \(r = +0.465\) (\(p = 0.008\), \(n=31\)). BL delay is not an offline quantity, so this is a description, not a design rule.

**\(D_{esc}\) and \(E\) do not predict DP gain across packings.** Pooled \(n=33\): \(r(D_{esc}, \text{gain}) = +0.142\) (ns), \(r(E, \text{gain}) = +0.120\) (ns); adding \(D_{esc}\) to a \(\log BL\) model *lowers* adjusted \(R^2\) (0.641 → 0.636, \(t = -0.79\)). Within each population separately they are strong but **opposite in sign** — \(r(E,\text{gain}) = -0.512\) in the PV sweep, \(+0.792\) in cc12; \(r(E, BL) = -0.819\) versus \(+0.757\). A predictor that reverses between packings is a proxy, not a mechanism — the same failure mode as \(PR\) (§ earlier). The offline geometry results above stand; only the tie to *measured delay* fails.

**What \(E\) does predict, within a fixed packing, is BL delay.** At pinned PL and CC (PV sweep, \(n=21\), BL spanning 1.59×): \(r(E, BL) = -0.819\), \(r(D_{esc}, BL) = -0.775\), against \(PV_{local}\) \(-0.368\) (ns) and \(PV_{global}\) \(+0.092\) (ns). More escape room means BL is *already fast*, which is precisely why \(E\) predicts DP gain negatively there: escape room removes DP's opportunity rather than creating it.

> **⚠️ Claim 4 items 1, 2 and 4 REMAIN OPEN.** Everything above it rests on
> offline path geometry over existing placement populations — **no simulation**.
> It supersedes the earlier wording ("buy path diversity with communication
> cost"), whose premise that diversity and CC are inversely coupled is not
> supported by the measured matrix. Open before this claim is written up:
>
> 1. **Does \(D_{esc}\) predict measured delay and DP−BL gain above the floor?**
>    Current support is the m1/m2 escapable-fraction pair — 2 placements, n=10
>    seeds, \((16,2,8)\), one load point — plus the regime split. That is a
>    two-point observation, not a result.
> 2. **\(D_{esc}\) is the DP-exploitable quantity; BL realises only a subset.**
>    *(Reworded 2026-08-27 — the earlier version had this backwards.)*
>    \(\phi_f\) is a whole-path property, so \(\phi_f=1\) means \(\ell^*\) is a cut
>    edge of \(f\)'s path DAG and no policy can divert \(f\); \(\phi_f<1\) means
>    complete \(\ell^*\)-avoiding routes exist. DP propagates cost-to-go and can
>    place \(f\) on one from injection, so it acts on the full \((1-\phi_f)\); BL
>    sees one hop and can only take a branch at the node it occupies, a strict
>    subset. Prediction: \(D_{esc}\) tracks DP gain more tightly than BL, and the
>    DP−BL difference is the part BL's horizon cannot reach. Untested.
> 3. **Does \(D_{esc}\) stay free in CC when a search targets it directly?** The
>    negative partials come from a search optimising PL with CC left free, so
>    they describe the region that search traversed, not the whole space.
> 4. **Sample.** All scored populations are ResNet \((8,2,4)\); only 28
>    placements sit above the floor and 21 of those have PL frozen by
>    construction. The geometry relations are regime-independent and unaffected,
>    but anything tying \(D_{esc}\) to *delay* needs an above-floor population
>    that does not yet exist.
>
> Scoring code and data: `results_stage3/mapping_pilot/pool1000/hill/`
> — `escapable_analytic.py`, `e_vs_pl_cc.py`, `corr_matrix.py`,
> `plf_vs_pv.py` and their CSVs. `metrics.py` is unmodified.

**Structural point.** The regime boundary is the contribution. It tells a designer which layer to optimise, and in the free regime it licenses spending the mapping budget elsewhere — more useful than any single delay number.

**Terminology.** The regime boundary is the design-space line where PL crosses PF. The hinge is the statistical device that detects and measures it. One phenomenon, two vocabularies: argue the regime boundary in the text, cite the hinge regression as evidence.

**Evidence provenance, to keep straight.** Claim 1 rests on the hinge regression: R-squared 0.735 mean under BL, 0.559 under DP, above-floor slope significant, below-floor slope flat and non-significant. The roughly seventy percent figure on both mean and p99 came from a high-versus-low diversity comparison at fixed above-floor PL, so it is **Claim 4 evidence, not a BIND fit** — do not attach it to Claim 1.


