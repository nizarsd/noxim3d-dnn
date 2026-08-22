# Related Work — verified citations

Bibliographic details verified against publisher records (Aug 2026). Claims marked
**[verified]** were checked against the paper's full text; others are from abstracts or
indexing records only.

---

## 1. Krishnan et al. — the closest methodological precedent

> Krishnan, G., Mandal, S. K., Chakrabarti, C., Seo, J.-S., Ogras, U. Y., & Cao, Y.
> "Impact of On-chip Interconnect on In-memory Acceleration of Deep Neural Networks."
> *ACM Journal on Emerging Technologies in Computing Systems* **18**(2), Article 34,
> April 2022, 22 pages. doi:10.1145/3460233. arXiv:2107.02358.

Note on the year: online publication July 2021, ACM issue date April 2022 — indexing
services list both. Cite as 2022 for the journal version.

**Why it matters:** published in JETC (same venue as j7), it is the near-precedent for
this project's whole Stage 2 approach — layer-to-tile mapping plus per-pair injection
rates fed to a cycle-accurate NoC simulator (customised BookSim).

### Verified claims

- **Layer-to-tile mapping [verified, §3.2]:** "The mapping of the DNN is performed such
  that each tile can have at least one layer while no layer is divided between two tiles."
  Direct support for our partitioning choice.
- **Crossbar-count formula [verified, Eq. 2]:**
  `crossbars = Σ_i ceil((Kx_i · Ky_i · C_i)/PE_x) · ceil((C_{i+1} · N_bits)/PE_y)`
  Note the **`N_bits` factor on the column term** — weight precision multiplies the
  column count (8-bit weights on 1-bit cells need 8 columns per logical column).
- **Injection-rate formula [verified, Eq. 3]:**
  `λ_{i,j,k} = (A_i · N_bits · FPS) / (T_i · T_{i-1} · W · freq)`
  where `A_i` = activations in layer i, `T_i` = tiles in layer i, `W` = bus width.
  Equal injection rate assumed between all tile pairs in consecutive layers. **Directly
  reusable for computing our `pir` values.**
- **Layer-by-layer, not pipelined [verified, §5]:** they "adhere to layer-by-layer design
  instead of a layer-pipelined design, since a pipelined design introduces pipeline
  bubbles ... and complicates the control logic." Supports our strict-sequential timing.
- **Tile composition [verified, §5.2]:** a *homogeneous tile* = 4 CEs, each CE = 4 PEs
  (crossbars) → **16 crossbars per tile**, one NoC router per tile. Three-level
  interconnect: NoC between tiles, H-Tree between CEs, bus between PEs.
- **Crossbar size [verified, §5.2]:** 256×256 chosen after sweeping 64×64–512×512;
  lowest EDAP for 75% of the 8 DNNs sampled.
- **Design parameters [verified, Table 2]:** 32 nm, 1 GHz, 8-bit data precision,
  1 bit/cell, 4-bit flash ADC, NoC bus width 32, 1 virtual channel, buffer size 8,
  3 router pipeline stages, X–Y routing.

### Finding that directly challenges this project's premise

**[verified, §6.3]** Their congestion analysis concludes there is **no congestion** in the
NoC under DNN traffic: 64–100% of queues are empty when a new flit arrives; average queue
length 0.004–0.5; worst-case latency deviates from average by ≤ 6 cycles (MAPD 0% for
MLP/ResNet-50/DenseNet-100). They state injection rate is "always low (less than one
packet in 100 cycles)."

Implication for Stage 2/3: under layer-to-tile mapping at realistic FPS, DNN traffic may
be **too sparse to stress the network at all** — in which case DP ≈ BL and the Stage 1
mechanism never activates. This is the single biggest risk to the project's premise and
must be checked early (Stage 3 / Checkpoint A). Mitigations if it materialises: raise the
FPS/load-scale factor, shrink the mesh relative to the model, or target the burst phases
specifically rather than average load.

---

## 2. SIAM — chiplet-based IMC benchmarking

> Krishnan, G., Mandal, S. K., Pannala, M., Chakrabarti, C., Seo, J.-S., Ogras, U. Y.,
> & Cao, Y. "SIAM: Chiplet-based Scalable In-Memory Acceleration with Mesh for Deep
> Neural Networks." *ACM Transactions on Embedded Computing Systems* **20**(5s),
> Article 68, October 2021, 24 pages. doi:10.1145/3476999. arXiv:2108.08903.

ESWEEK–TECS special issue; presented at CODES+ISSS 2021 (same venue as c3). Integrates
device, circuit, architecture, NoC, NoP and DRAM models end-to-end. Open-source:
github.com/gkrish19/SIAM-...

## 3. Mandal et al. — latency-optimised NoC for IMC

> Mandal, S. K., Krishnan, G., Chakrabarti, C., Seo, J.-S., Cao, Y., & Ogras, U. Y.
> "A Latency-Optimized Reconfigurable NoC for In-Memory Acceleration of DNNs."
> *IEEE Journal on Emerging and Selected Topics in Circuits and Systems* **10**(3),
> 2020, 362–375.

Custom NoC synthesised per DNN traffic pattern. Useful contrast: this project keeps a
*regular* 3D mesh and varies routing/selection instead of the topology.

## 4. Interconnect survey for DNN accelerators

> Nabavinejad, S. M., Baharloo, M., Chen, K.-C., Palesi, M., Kogel, T., & Ebrahimi, M.
> "An Overview of Efficient Interconnection Networks for Deep Neural Network
> Accelerators." *IEEE JETCAS* **10**(3), 2020, 268–282.

## 5. Simulator baselines

- **BookSim2:** Jiang, N., Becker, D. U., Michelogiannakis, G., Balfour, J., Towles, B.,
  Shaw, D. E., Kim, J., & Dally, W. J. "A Detailed and Flexible Cycle-Accurate
  Network-on-Chip Simulator." *IEEE ISPASS* 2013, 86–96. (Used by Krishnan et al.)
- **Garnet:** Agarwal, N., Krishna, T., Peh, L.-S., & Jha, N. K. "GARNET: A Detailed
  On-Chip Network Model Inside a Full-System Simulator." *IEEE ISPASS* 2009, 33–42.
  No router-level multicast — breaks multicast into unicasts at the NI (per gem5 docs),
  the precedent for our source-replication approach (STAGE2.md §9.4).

## 6. RL-for-NoC prior work (Stage 7 novelty positioning)

Tracked in the project knowledge base; not re-verified here. CURE (Wang & Louri, IEEE
TPDS 2020), DeepNR (Microprocessors & Microsystems 2022), RLARA (Electronics 2023),
DRLAR (Computer Networks 2024). None combine 3D NoC + RL + DNN-workload traffic.

---

## Open verification items

- Citation counts were **not** verified — check Google Scholar before any ranking claim.
- Eyeriss / Eyeriss v2 (within-layer mapping contrast) cited from memory only; verify
  before use.
