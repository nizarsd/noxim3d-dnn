# Paper 1 — structure draft (for discussion, nothing locked)

DATE 2027 — CFP verified 2026-09-04 (date-conference.com/call-for-papers):
**6 pages of content, plus ONE extra page for references only** (nothing else may
spill onto page 7). PDF only; A4/Letter, double column, Times, min 10pt, no Type-3
fonts. **Double-blind**: no author names or acknowledgements; prior work by the same
authors cited in the third person. Abstract **13 Sep 2026 AoE**, full paper
**20 Sep 2026 AoE**, notification 23 Nov 2026, camera-ready 16 Dec 2026.
Every paragraph below is one line = its job.
Slots: ~5 total. Claims per §33 (C0–C8).

**⚠️ Partly superseded (2026-09-02).** Three things moved after this draft:
always-DP is now the design rule in **both** regimes (not "conditional below
the floor"); the free **maxES** climb is a step in the flow and one of the four
contributions; and the C2a packing result is measured at 11.6×/18.7×, not just
1.56–1.80× in k*. Numbers below are marked where they are stale. The current
exhibit budget and contribution list live in the paper-writing plan.

---

## Title (undecided)

1. *Communication-Aware Design-Space Exploration for IMC DNN Accelerators:
   Co-Optimizing Crossbar Packing, Tile Placement, and Adaptive 3D-NoC
   Selection* ← current favourite
2. *Partial-Sum Reduction as a First-Class Constraint in IMC Accelerator DSE*
3. *The Port Floor: Packing, Placement, and Adaptive Selection Regimes in
   3D-NoC IMC Accelerators*

## Abstract (~150 w) — write last

problem (reduction traffic, oversubscribed sink) → the layer attribution
(packing sets PF, placement sets PL, BIND = max) → three findings (regime
boundary; min-bytes is the wrong packing objective; DP = robustness lever, not
speed lever) → design rule → one headline number per finding.

---

## §1 Introduction — 0.75 pp, no figure

- **P1 hook-a:** minimum-traffic packing is not minimum-latency packing —
  the two objectives pick different orientations in 5 of 8 cells; the floor
  penalty reaches 2.8× for 8% traffic. (PO*_BW ≠ PO*_Arch)
- **P2 hook-b:** the regime numbers — the same placement effort moves delay
  1.15× below the floor and up to 31.8× above it; which regime you are in was
  decided upstream, at packing.
- **P3:** the cross-layer chain (PD → PO → {PF, tiles} → placement → PL →
  BIND → delay) + contributions as 4 bullets: layer attribution (C0/C1),
  regime boundary + knee band (C2/C3), the two faces of adaptive selection
  (C5/C7), the negative result that motivates learned selection (C8).
- **P4:** scope in one sentence (one mesh, simulation, thermal as motivation
  only; RL deferred to Paper 2) + organisation.

## §2 Background & related work — 0.5 pp

- **P1:** IMC packing/tiling literature optimises pre-NoC objectives
  (utilisation, tile count, volume) with no feedback from achievable network
  performance.
- **P2:** NoC mapping assumes a fixed packing; adaptive-routing work assumes
  both; baseline routing = own prior 3D turn-model work.
- **P3:** the gap = the coupling itself; no unqualified "first" claim.

## §3 System model & metrics — 0.75 pp — **Tab 1: metric definitions**

- **P1:** architecture (6×6×3, 128×128 crossbars, INT8/INT32 convention +
  why it is the safe direction), three workloads, phase-windowed traffic.
- **P2:** packing semantics — r internalises reduction, s internalises input
  sharing; tile-grid formula; sink oversubscription (18–148×) and the 44–48%
  knee normalisation.
- **P3:** the five metrics (PF, PL, BIND, E, k*) — table + one sentence each;
  PF placement-invariance stated here (C0 evidence lands in results).

## §4 Cross-layer design flow — 0.75 pp — **Fig 1: flow figure**

- **P1:** the nested DSE: each PO induces its own traffic table *and* its own
  placement space; POs compared only at their best placement (the flow figure
  contrasts this with the conventional decoupled flow).
- **P2:** offline scorer (path-enumeration PL/E) + constrained hill-climb
  placement search.
- **P3:** measurement protocol as method contribution: per-mapping k*, gains
  read at pre-specified loads only, knee-window discipline; simulator setup;
  ~20,600 sims / 0 failures.

## §5 Results — 2.25 pp — by regime, DP enters only in R3

- **R1 — packing sets the operating point** [C0, C2a] — **Fig 2: F0**
  - PF invariant + 5.8× span; orientation alone moves k* 1.56–1.80× at
    min-CC mapping; F0's within-c argmin split; PF beats sustained-rate as
    the ranking metric (4× closer).
- **R2 — the regime boundary and the knee band** [C1, C2b/c, C3, C6] —
  **Fig 3: regime map (BL only)**
  - C1 one sentence: CC sets where the curve starts, BIND where it bends.
  - hinge evidence; above floor placement spreads 4.6–31.8×, r(PL/PF, delay)
    positive 5/5.
  - below floor: spread lives only in the knee band (1.34× → 13.6× → 1.28×);
    the licence with its load condition — never "mapping is inert".
  - min-CC captures nearly all of it (≤1.14× past it; accepted-partial with
    error bars stated).
  - C6 one sentence: above-floor is reached only by deliberate provisioning.
- **R3 — adaptivity as a throughput lever** [C5, C4] — no slot, prose
  - above floor unconditional (1.153×/1.364×, 65/71); below floor conditional
    on knee + placement (1.10–1.35× by arm, peak at each packing's own knee).
  - ⚠️ **stale framing**: on the 829-cell recomputation always-DP leads in both
    regimes — 1.850×/2.386× above, 1.150×/1.231× below, ahead at every load band.
  - C4 one sentence: PL predicts capacity (β −0.584, negative 5/5), E does
    not (retracted).
- **R4 — adaptivity as a robustness lever, and its limit** [C7, C8] —
  **Fig 4: C7 compression** + **Tab 2: oracle table**
  - C7: compression 8/8 qualifying populations; mechanism = worst-case rescue
    (5566→732); cannot compress PL-caused spread; window = the knee.
  - C8: always-DP is the right default in **both** regimes; what stays offline-
    unpredictable is *which* cells it loses below the floor. Oracle over
    always-DP is **1.011×/1.025× above** the floor and **1.038×/1.077× below**
    (the old 1.042×/1.116× pair is superseded). Bridge to online selection.
- **R5 — scope, threats, design rule** — prose + boxed rule
  - offline-model caveat (PL validated as moderate capacity predictor only),
    one mesh, INT32 convention, max/min-at-3-seeds caveat, retractions named.
  - **Design rule box:** orientation on PF (11.6×/18.7× over the classical
    min-bytes pick) → min-CC map → **free maxES climb** (zero CC/PL cost) →
    min PL if searching further → **DP everywhere, unconditionally**.

## §6 Conclusion & directions — 0.25 pp

- design rule recap in two sentences.
- the **efficiency gap** as the bridge to online selection: DP captures 98–99%
  of the achievable improvement above the floor but only 76–81% below it, and
  the deficit is temporal. (Term note: this is *runtime gain*, not "reserve" —
  one term per concept.)

## References — OFF-BUDGET (page 7, references only)

The 0.5 pp previously reserved here returns to the body: Results 2.25 → 2.5 pp,
or the Discussion subsection if it is short.

---

## Slot summary

| slot | object | § | claim | state |
|---|---|---|---|---|
| Fig 1 | flow figure (nested vs decoupled) | 4 | method | undrawn |
| Fig 2 | F0 packing design space | 5.R1 | C0/C2a | drawn — `figs/fig0_packing_designspace` |
| Fig 3 | regime map, delay vs PL/PF, BL only | 5.R2 | C2b/C3 | regenerate from E1+below-floor data |
| Fig 4 | C7 compression (f5 variants exist) | 5.R4 | C7 | drawn, pick variant |
| Tab 1 | metric definitions | 3 | — | trivial |
| Tab 2 | always-BL / always-DP / oracle | 5.R4 | C5/C8 | ⚠️ regenerate — 829-cell numbers |
| — | maxES paired table, 3 workloads | 5 | C4b | candidate slot, not in this draft |

Inline-only (no slot): C4 table → one sentence; knee-band triplet; C1 CC
numbers; C2a's 11.6×/18.7× priced onto F0's ResNet arrow; C6; hinge
coefficients (Fig 3 caption); z-sensitivity; DPTRACE PL validation.
Dropped: below-floor DP-vs-load curve, thermal Pareto figs, coefficient table.

## Open questions for discussion

1. Title — 1, 2, 3, or new?
2. Does C2c (min-CC captures nearly all; accepted-partial) get its own
   paragraph in R2, or a hedged sentence? It is honest but weakens the
   placement-search story.
3. Design rule box — in R5, or promoted to the intro (P3) as the payoff?
4. Is C1 (CC sets the start) worth its sentence in R2, or does it distract
   from the BIND story?
5. Fig 4 variant: `f5_two_regime` vs `f5_cc12_compression` vs the approved
   box+slope design.
6. Abstract emphasis: DSE-flow story (title 1) vs floor-phenomenon story
   (title 3) — decides P1-vs-P2 ordering tension in the intro too.
7. Where does "the eight claims" numbering surface, if at all? (Paper likely
   never says "C7" — claims map silently onto sections.)
