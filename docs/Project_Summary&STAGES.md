# Research Programme — Project Summary & Staged Execution Plan

Canonical reference for the project definition and stage sequence.
Source: `NoC_for_AI_Project_Knowledge_Base.docx` (§1, §3, §4).

---

# Part I — Project Summary

## Researcher

Dr. Nizar Dahir — ORCID 0000-0003-3466-0982. Associate Professor & Head of
Applied Information Systems, College of Excellence, University of Baghdad.
PhD Newcastle, UK Global Talent Visa (Royal Academy of Engineering).

**All work is software/simulation only.** No fabrication, FPGA, or ASIC access.
Target: respected microelectronics journals and conferences.

## Verified publication record

Confirmed live from DBLP, 2 July 2026. **All novelty claims and baseline
comparisons must be grounded in this list. Do not invent or assume publications.**

### Journal articles

| ID | Title | Venue | Year |
|----|-------|-------|------|
| j7 | Thermal and Performance Efficient On-Chip Surface-Wave Communication for Many-Core Systems in Dark Silicon Era | ACM JETC 18(3) | 2022 |
| j6 | Power density aware application mapping in mesh-based NoC: an evolutionary multi-objective approach | Integration – VLSI Journal 81:342–353 | 2021 |
| j5 | Network-on-Chip Multicast Architectures Using Hybrid Wire and Surface-Wave Interconnects | IEEE TETC 6(3) | 2018 |
| j4 | Modeling and Tools for Power Supply Variations Analysis in NoCs | IEEE Trans. Computers 63(3):679–690 | 2014 |
| j3 | Thermal Optimization in 3D Chip Multiprocessors Using Dynamic Programming | ACM TECS 13(4s) | 2014 |
| j2 | Highly adaptive and deadlock-free routing for 3D networks-on-chip | IET Comput. Digit. Tech. 7(6):255–263 | 2013 |
| j1 | Dynamic programming-based runtime thermal management (DPRTM) for 3D-NoC | ACM TODAES 19(1) | 2013 |

### Conference papers (selected)

| ID | Title | Venue | Year |
|----|-------|-------|------|
| c11 | Optimized task graph mapping on a many-core neuromorphic supercomputer | HPEC | 2017 |
| c10 | LeAF: a low-overhead asymmetric frequency controller for NoC routers | VLSI-SoC | 2017 |
| c7 | Fault tolerant task mapping on many-core arrays | SSCI | 2016 |
| c5 | Hybrid wire-surface wave for one-to-many communication in NoC | DATE | 2014 |
| c4 | Dynamic Thermal-Adaptive Routing Strategy for NoC | PDP | 2014 |
| c3 | Minimizing power supply noise through harmonic mappings in NoC | CODES+ISSS | 2012 |
| c2 | Deadlock-free and plane-balanced adaptive routing for 3D NoC | NoCArc@MICRO | 2012 |
| c1 | Communication centric on-chip power grid models for NoC | VLSI-SoC | 2011 |

### Research DNA

- 3D NoC routing — deadlock freedom, adaptive routing, turn models (j2, c2, c4)
- Power supply integrity — modelling, tools, harmonic mapping (j4, c3, c1)
- Thermal optimisation in 3D CMPs — dynamic programming, runtime control (j3, j1, c4)
- Multi-objective evolutionary mapping — NSGA-II, power-density aware (j6)
- Surface-wave interconnects — hybrid NoC, multicast, dark silicon (j7, j5, c5)
- Neuromorphic many-core — task graph mapping on SpiNNaker (c11)
- FPGA / reconfigurable — adaptive DVFS, frequency controllers (c6, c10)

## The active project — Idea 1

**RL-based adaptive routing for DNN inference traffic in 3D NoC.**

Four other proposals exist (2: PSN + transformers; 3: thermal-aware CNN mapping
via NSGA-III; 4: surface-wave NoC for DNN accelerators; 5: GNN fault-tolerant
routing) — see `NoC_AI_Research_Proposals_v3.docx`. **Background reference only.
Do not propose switching to them.**

### Problem and motivation

DNN inference layers produce highly unbalanced, time-varying traffic that static
routing handles inefficiently. The 3D odd-even and plane-balanced routing of
j2/c2 use fixed rule sets. An RL agent trained on simulated DNN traffic can learn
a policy that outperforms static methods with no hardware change.

### Novelty claim

First RL-guided 3D turn-model router specialised for DNN inference traffic
profiles. The baseline is the researcher's **own** prior published routing
(j2, c2), so the novelty claim is directly grounded and the improvement precisely
quantifiable.

### Literature landscape (confirmed July 2026)

| Year | Work | Scope | Gap |
|------|------|-------|-----|
| 2020 | CURE (Wang & Louri, IEEE TPDS) | 2D mesh, synthetic | 2D only |
| 2022 | DeepNR (Microprocessors & Microsystems) | 2D mesh, PARSEC | 2D, no DNN workload |
| 2023 | RLARA (Electronics 12(23)) | 3D NoC, fault tolerance | 3D but not DNN-workload-aware |
| 2024 | DRLAR (Computer Networks) | 2D mesh, synthetic | 2D, synthetic only |
| 2024 | Survey: ML for NoCs (Zhang et al., JPDC) | Survey | No new contribution |
| — | **This work** | 3D NoC + RL on profiled DNN traffic vs own turn-model baseline | **Confirmed gap** |

**Reviewer risk to pre-empt:** RLARA (2023) is closest — 3D + RL, but fault
tolerance with TSV-awareness, trained on synthetic traffic. Differentiate on
(1) workload-specific optimisation vs fault tolerance, (2) DNN-profiled traces vs
synthetic, (3) direct quantified comparison against the author's own peer-reviewed
baseline.

### MDP design (Stage 7 candidate — NOT settled)

- **State:** local queue depths (4 input buffers, 0–16 flits); vertical TSV link
  utilisation as 3D congestion proxy; **DNN phase token** (one-hot layer type —
  the proposed novel component absent from prior RL-NoC work); destination offset
  (dx, dy, dz) capped at ±4 hops.
- **Action:** output port from {N,S,E,W,Up,Down}, masked by the j2 turn model
  (typically 2–4 valid choices) — deadlock freedom guaranteed by construction.
- **Reward:** −(local queue delay) − α·(link utilisation) + β·(load-spreading bonus).

> The phase token is a **candidate design only**. Stage 6 evidence must confirm
> or revise it before it is committed to.

### Evaluation metrics

| Metric | Target |
|--------|--------|
| Average packet latency | 15–30% reduction vs j2 baseline during bursts |
| Throughput (accepted flits/cycle) | Higher sustained than baseline |
| Energy per packet | Lower than baseline (McPAT/ORION, hop-count proxy) |
| Deadlock freedom rate | 100%, by action masking + empirical validation |
| Training convergence | PPO vs DQN curves |
| Inference overhead (ns/decision) | Negligible vs routing latency |

### Target venues

IEEE Transactions on Computers (primary; j4 published there) · Integration – VLSI
Journal (j6) · IEEE TVLSI · conference-first route for priority.
Near-term deadlines: DATE 2027 LBR (~Nov 2026–Jan 2027), SAMOS 2027 (~Feb 2027).

### Tools

Noxim (3D-extended fork, this repo) · BookSim2 · Python + Stable Baselines3
(PPO/DQN) · PyTorch (traffic profile generation) · Gym-style env wrapping Noxim.

---

# Part II — Staged Execution Plan

Source: knowledge base §4.

**Rationale for staging:** get a working pipeline producing real results before
committing to the novel contribution, and gather evidence rather than designing
on assumptions. **Stages run in order. Do not jump ahead.**

---

## The seven stages

### Stage 1 — Install and validate 3D Noxim + modified odd-even routing
Toolchain sanity check. Get the simulator compiling; confirm the modified
odd-even routing (j2/c2) reproduces expected baseline latency/throughput on
standard synthetic traffic.

### Stage 2 — Source or generate DNN traffic traces
Generate DNN traffic (PyTorch hooks / Timeloop / ASTRA-sim) and convert to the
simulator's traffic-table format. Placed before the RL work because every later
stage depends on this data existing.

> **Checkpoint A** — synthetic and DNN traffic both run through the baseline router.

### Stage 3 — Baseline characterisation: DNN vs synthetic traffic
Run DNN traces and synthetic traffic (uniform, hotspot, transpose) through the
same baseline. Compare latency, throughput, congestion hotspot patterns. This is
the evidence confirming (or challenging) that DNN traffic differs enough to
justify specialised routing. De-risks all later stages.

### Stage 4 — Minimal RL routing agent, generic congestion objective
Simplest working RL router (PPO or DQN; plain state: queue depth + link
utilisation only). Train and test on **synthetic traffic first** — isolates
"does the RL pipeline work at all" from "does it help with DNN traffic".

> **Checkpoint B** — a working RL agent that matches or beats the baseline on synthetic traffic.

### Stage 5 — Run the generic RL agent on DNN traffic, unmodified
No DNN-specific design changes. Observe where it helps and where it falls short.
The gap is the real evidence motivating a DNN-aware redesign.

### Stage 6 — Analyse distinguishing features of DNN traffic
Using Stage 3 + Stage 5 results together, identify concretely what makes DNN
traffic hard for a generic agent: burst timing, spatial locality, layer-phase
transitions. Evidence-driven, not open-ended.

**Gate:** determine whether failures are **temporal** (late reaction to bursts /
phase shifts) or **spatial**. Stage 7's design depends on the answer.

### Stage 7 — Design and train the DNN-aware RL router
The novel contribution, informed by Stage 6 findings. The "DNN phase token"
state-space addition is a **candidate, not a settled design** — Stage 6 must
confirm or revise it before it is committed to.

---

## Current position (as of 18 Aug 2026)

**Stages 1–3: complete.** Stages 4–7: not started.

### Deviation from the plan — read this before acting

The plan assumed the non-learning baseline was settled at Stage 1. It was not.
Stage 3 characterisation revealed that **DP (the global congestion-aware
selection policy) fails under DNN traffic**, for reasons that took several
sessions to isolate:

- DP's congestion term was averaged over a window tied to the DP cycle and reset
  each interval, diluting bursts to near zero. The cost field collapsed to pure
  hop count.
- The DNN mapping placed aggregation hotspots (conv2: two tiles, 18 incoming
  flows each, ~32–38% of all traffic) on the mesh **edge**, limiting usable input
  ports. The experiment was measuring an ejection-port limit, not routing quality.
- Under minimal-only routing, all legal paths have equal hop count, so the
  per-hop term cancels in the argmin and **congestion is the sole discriminator**.
  With a diluted signal, DP degenerates to arbitrary tie-breaking.

This grew into a body of work not present in the original plan: mapping/placement,
path diversity, congestion estimator design, and phase-indexed DP.

### Consequence — two-paper split

- **Paper 1 — mapping / design-space exploration.** Two-stage mapping
  (crossbars→tiles = packing, determines the traffic graph; tiles→NoC = placement,
  determines path diversity and hop count). Absorbs the Stage 3 findings.
  Mesh fixed at 6×6×3 across all workloads — the NoC is the object of study and
  cannot also be a variable.
- **Paper 2 — routing / selection.** RL vs DP; local-vs-global, temporal-vs-spatial.
  This is Stages 4–7. Deferred; inherits a validated baseline and a known-good
  mapping from Paper 1.

### Standing rules

1. **Do not jump to Stage 7 design work.** The DNN phase token is not settled.
2. **Phase-indexed DP is the non-learning baseline the RL contribution must beat.**
   It is deliberately oracle-ish (it is given the layer schedule). Label it as a
   strong baseline, not a competitor.
3. Novelty claims and literature comparisons must be grounded in the verified
   publication record (knowledge base §1). Do not invent publications.
4. The repo is authoritative. Run `git ls-files` and read all `.md` files before
   advising on any stage; chat attachments may be stale.

### Related documents in this repo

- `FINDINGS.md` — Stage 1 DP-vs-bufferlevel results
- `PERFORMANCE.md` — correctness fixes and profiling
- `STAGE2.md` — Stage 2 traffic-representation decisions
- `SESSION-NOTES.md` — **current state**: latest results, open items, and work queue
- `MAPPING-FORMULATION.md` — two-stage mapping formulation (packing, then placement)
- `CROSSBAR-ADC-PACKING.md` — crossbar/ADC constraints behind the `c`/`r`/`s` notation
- `docs/archive/STAGE3-MAPPING-FINDINGS.md` — aggregation hotspot, interior placement
  (superseded; see SESSION-NOTES §5.1 for the corrections to it)
