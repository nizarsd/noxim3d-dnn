# PD–PO Architecture-Aware Co-Design Prompts

This file consolidates the three working prompts developed for the NoC-for-DNN project.

---

# Prompt 1 — Architecture-Aware PD–PO Optimization Flow

Develop the architecture-aware PD–PO optimization flow for the NoC-for-DNN mapping framework.

Definitions:
- PD = Packing Density c: number of crossbars physically provisioned per tile; primarily a design-time/hardware parameter.
- PO = Packing Orientation (r,s), where r*s=c: workload-dependent logical grouping of those crossbars.
- PO is discrete/quantized. Example for PD=8: {(1,8),(2,4),(4,2),(8,1)}.
- PO may differ between DNN layers/phases.
- Each PO produces a different traffic table TT because r and s determine how much reduction and scatter communication is internalized within a tile versus exposed to the NoC. PO may also change logical tile count.

Architecture-aware optimization flow:

PD=c
→ enumerate every valid PO_i=(r_i,s_i)
→ generate corresponding TT_i
→ for TT_i generate/search many legal 3D placements M_ij
→ evaluate each placement using phase-aware static metrics:
  C = communication cost / network work
  L = peak link or arrival-face load / hotspot concentration
  D = legal OEB path diversity / routing opportunity
→ perform multi-objective placement optimization: minimize C, minimize L, maximize D
→ obtain Pareto-optimal placement set for each PO
→ select representative/best Pareto placements
→ run expensive Noxim simulations
→ measure absolute mean and p99 communication latency
→ compare the best achievable performance of each PO
→ select architecture-aware PO*
→ repeat across PD values if PD is also part of the design-space exploration.

For each PO:

M*_PO ∈ Pareto_M {min C(PO,M), min L(PO,M), max D(PO,M)}

Then use Noxim to determine which Pareto candidates actually minimize absolute mean/p99 latency.

Important methodological rule: Do NOT optimize for DP-vs-BL improvement. DP advantage must remain an experimental outcome, otherwise the mapping search would be biased toward making DP look good.

After selecting good mappings independently, evaluate both:
- BL: local buffer-level selection
- DP: distributed destination-aware non-local cost-to-go selection

Then determine under which PD/PO/traffic/mapping conditions DP provides additional benefit.

Core conceptual chain:

PD → PO_i → TT_i → {M_ij} → Pareto(C,L,D) → Noxim → mean/p99 → architecture-aware PO*

The key point is that this is a nested PO + 3D-placement co-design problem. A PO does not correspond to one placement: each PO generates its own TT, and that TT has a large placement space that must be searched before POs can be compared fairly.

---

# Prompt 2 — Contribution Figure Relative to Existing Literature

Create a publication-quality conceptual figure illustrating how the proposed architecture-aware PD–PO methodology differs from conventional DNN/CIM mapping flows in the existing literature.

The figure should emphasize the conceptual contribution, not implementation details.

LEFT — Conventional / existing approach

DNN layer → Crossbar partitioning / packing → Fixed packing decision → Traffic generation → NoC tile placement / mapping → NoC execution

Annotate: “Crossbar packing optimized primarily for utilization, tile count, communication volume, or other pre-NoC objectives.”

Show the NoC architecture as downstream of packing. There should be NO feedback from NoC placement characteristics to the packing decision.

Indicate that existing literature contains important individual components: crossbar partitioning/packing and utilization optimization; input sharing and partial-sum reduction; DNN/PIM tile mapping; communication/traffic-aware NoC placement; 3D NoC mapping; congestion-aware routing.

Do NOT imply that no prior work performs any cross-layer optimization. The distinction being illustrated is the specific PD–PO–traffic–3D-placement coupling proposed here.

RIGHT — Proposed architecture-aware PD–PO co-design

Physical Packing Density PD=c → Enumerate discrete Packing Orientations PO_i=(r_i,s_i), r_i*s_i=c.

For c=8 illustrate PO1=(1,8), PO2=(2,4), PO3=(4,2), PO4=(8,1).

Each PO must branch into a DIFFERENT traffic table: PO1→TT1, PO2→TT2, PO3→TT3, PO4→TT4.

Annotate: “PO changes scatter/reduce communication morphology, logical tile structure and potentially fragmentation.”

For EACH TT_i show a placement search: TT_i → {M_i1,M_i2,...,M_in} → 3D-NoC-aware placement optimization.

Evaluate candidate placements using phase-aware static metrics C (communication cost/network work), L (peak link or arrival-face load/hotspot concentration), D (legal minimal OEB path diversity/routing opportunity).

Then show Pareto search: min C, min L, max D → selected Pareto placements → Noxim simulation → absolute mean latency + p99 latency → compare best achievable result for each PO → Architecture-aware PO*.

Emphasize the nested optimization:

PO*_c = arg min_PO [best achievable 3D placement performance for TT_PO]

rather than:

PO*_BW = arg min_PO [scatter volume + reduction volume]

CENTRAL CONTRIBUTION MESSAGE:
“Packing orientation is not selected independently of the communication architecture. Each PO induces a different traffic topology, and each traffic topology has its own 3D placement space. POs are therefore compared only after architecture-aware placement optimization.”

Show hypothesis PO*_BW ≠ PO*_Arch with caption: “The minimum-bandwidth packing need not be the packing that achieves minimum latency after 3D placement.”

OPTIONAL SECONDARY ANALYSIS: Selected mappings → BL vs DP → mean/p99 comparison. Label “Routing-policy characterization — not an optimization objective.” Mappings must NOT be optimized to maximize DP's advantage over BL.

TIMESCALE DISTINCTION:
PD(c): hardware/design-time parameter.
PO(r,s): discrete workload/layer/phase-dependent mapping parameter.
3D placement: architecture-dependent mapping parameter.

If appropriate show PO potentially changing between DNN layers/phases, but PO* must emerge from architecture-aware evaluation rather than being predetermined.

STYLE: DATE/IEEE quality, clean vector-style block diagram, white background, minimal text, readable at two-column width, and no unsupported “first” claim.

---

# Prompt 3 — Complete Publication Figure Specification

Create a publication-quality conceptual figure illustrating the contribution of the proposed architecture-aware PD–PO methodology relative to existing DNN/CIM mapping approaches.

The purpose of the figure is to make the methodological novelty immediately clear. Emphasize the coupling between crossbar packing orientation, the resulting traffic table, and 3D NoC placement. Do not claim “first” or imply that individual components such as crossbar packing, traffic-aware mapping, 3D placement, or congestion-aware routing are themselves new.

## A. Conventional / architecture-oblivious flow
Show: DNN/layer → crossbar partitioning/packing → packing selected using pre-NoC criteria → traffic generation → NoC placement/mapping → NoC execution.
Typical pre-NoC criteria: utilization, fragmentation, tile count, scatter volume, reduction volume, total communication volume.
Show PO*_BW = argmin_PO[Vscatter(PO)+Vreduce(PO)] or PO*_pre-NoC = argmin_PO Jpre-NoC(PO). The key point is packing → traffic → placement with no feedback from achievable 3D placement to PO selection.
Acknowledge prior work on packing/utilization, input sharing, psum aggregation, DNN/PIM mapping, communication-aware mapping, 2D/3D placement, thermal-aware placement, and congestion-aware routing.

## B. Proposed architecture-aware PD–PO co-design
Start with PD=c, labelled primarily hardware/design-time. PD specifies crossbars provisioned per tile. Enumerate the small discrete PO set PO_i=(r_i,s_i), r_i*s_i=c. Example c=8: (1,8),(2,4),(4,2),(8,1). Emphasize exhaustive enumeration.

## C. Each PO creates a different TT
Explicitly branch PO1→TT1, PO2→TT2, etc. Changing r,s changes scatter/reduce traffic, internalized vs NoC-visible communication, logical tile count, fragmentation, source/sink structure, fan-out/fan-in and traffic concentration. TT_i=TT(PO_i), generally TT_i≠TT_j.

## D. Each TT has many 3D placements
For each TT_i show TT_i→{M_i1,...,M_in}. Each M_ij is a legal physical placement of TT_i's logical tiles onto the 3D NoC. POs cannot be fairly compared using one arbitrary placement; each PO gets its own placement optimization.

## E. Architecture-aware placement evaluation
For every M_ij compute phase-aware C=communication cost/network work, L=peak link or destination-arrival-face load/hotspot concentration, D=legal minimal OEB path diversity/routing opportunity. Do not combine disjoint phases as if they contend.

## F. Multi-objective placement search
For each TT independently: minimize C, minimize L, maximize D. Show TT_i→search{M_i1...M_in}→Pareto_i(C,L,D). Do not impose an arbitrary weighted sum initially.

## G. Noxim validation
C/L/D are placement-search surrogates, not final performance objectives. Select a small representative subset from each Pareto set → Noxim → mean latency + p99 latency. Ultimately use p99 communication-aware inference time or p99 inference time if the timing model supports it.

## H. Fair PO comparison
Only after each PO searches its own placement space compare best achievable results. Show PO1→TT1→placement optimization→P1*, etc. Then PO*_Arch = argmin_PO[best achievable NoC performance for TT_PO], compactly PO*_Arch = argmin_PO_i[min_{M∈M(TT_i)} J_NoC(TT_i,M)].

## I. Central contrast/hypothesis
Prominently contrast PO*_BW = argmin_PO[Vscatter+Vreduce] with PO*_Arch = argmin_PO[best achievable 3D-NoC performance after placement optimization]. Show hypothesis PO*_BW≠PO*_Arch and caption: “The minimum-bandwidth packing orientation need not be the minimum-latency packing orientation after 3D placement.” Explain that slightly higher traffic may yield lower hotspots, better spatial distribution, greater legal path diversity, better 3D utilization, or lower arrival-face concentration.

## J. Layer-/phase-dependent PO
PD=c is primarily hardware/design-time; PO=(r,s) is a logical/workload mapping decision and need not be global across the DNN. For each layer/phase: enumerate PO candidates → TT + placement optimization → PO*_l. Do not draw Layer1→PO1 as predetermined. If changing PO requires weight movement/reprogramming, flag reconfiguration cost for later; if PO is logical grouping only, it may change cheaply at layer boundaries. Do not assume either without verification.

## K. PD exploration
Optional outer loop PD∈{8,16,32,...}. For each PD enumerate valid PO → TT per PO → optimize placement → evaluate NoC → select PO*_PD. Then compare PDs. Conceptually PD* = argmin_c[min_PO min_M J(c,PO,TT_PO,M)]. Emphasize PD is more strongly tied to physical architecture than PO.

## L. DP vs BL — downstream characterization
After architecture-aware PO/placement selection: selected placement → BL vs DP → mean/p99. BL is local buffer-occupancy congestion information; DP is distributed destination-aware non-local cost-to-go. Put this in a dashed “Routing-policy characterization” box. DP-vs-BL improvement must NOT be an optimizer objective. First optimize absolute communication performance; only afterwards ask when DP adds benefit over BL.

## M. Full proposed flow
PD=c → enumerate discrete PO_i=(r_i,s_i) → each PO_i generates TT_i → each TT_i has its own {M_ij} → phase-aware C,L,D → Pareto search min C,min L,max D → selected Pareto placements → Noxim → absolute mean+p99 → compare best achievable performance across PO → PO*_Arch. Optional outer PD loop; optional per-layer/phase PO*_l; separate BL-vs-DP characterization.

## N. Core contribution message
“Packing orientation is treated as an architecture-dependent mapping variable: each discrete PO induces a different traffic topology, and each traffic topology is evaluated over its own 3D placement space before PO selection.”
Short alternative: “Optimize the placement induced by each packing — then compare packings.”

## O. Relation to existing literature
Acknowledge prior work on crossbar partitioning/packing/utilization, input sharing/psum reduction, communication-volume-aware DNN mapping, PIM/NoC accelerator mapping, traffic-aware NoC placement, thermal-aware 3D placement, adaptive/congestion-aware routing. Proposed investigated coupling: PD→PO→PO-dependent TT→PO-specific 3D placement optimization→architecture-aware PO selection. Do not state existing approaches universally select packing before architecture unless the literature review supports it. Suggested labels: “Typical decoupled / pre-NoC packing formulation” vs “Proposed architecture-aware PD–PO/placement co-design.”

## P. Visual design requirements
DATE/IEEE-paper-quality vector-style block diagram; white background; minimal decoration; readable at two-column width; short equations; clearly distinguish PD, PO, TT, M, C/L/D and simulator mean/p99. Emphasize PD→multiple PO, PO→one distinct TT, TT→many placements.

The reader should understand within ~10 seconds:
Typical decoupled: packing→traffic→placement.
Proposed: PD→enumerate PO→different TT per PO→optimize many 3D placements for every TT→compare each PO at its best achievable architecture-aware placement→select PO*.

Visual centerpiece:
PO*_BW = argmin_PO(Vscatter+Vreduce)
versus
PO*_Arch = argmin_PO[min_M J_NoC(TT_PO,M)]
with experimentally tested possibility PO*_BW≠PO*_Arch.

Do not make unsupported “first” claims.
