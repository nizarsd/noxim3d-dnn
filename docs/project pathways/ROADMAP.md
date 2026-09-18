# NoC for AI — Programme Roadmap (updated 2026-09-19)

Companions: `PAPER2-RL.md` (Paper 2), `LOSS-DECOMPOSITION-PROMPT.md` (extension
mechanism / CiN opener). CiN design brief: pending from the user. Evidence:
`docs/TOPN-DP-INVESTIGATION.md`, `docs/EXTENSION-PATHWAYS.md`,
`results_ext/topn/matrix/{ANALYSIS.txt,postchecks.txt}`.

## Where we are (what holds, 2026-09-19)

Paper 1: full text due 2026-09-20 (abstract submitted). Eight locked claims C0–C8,
~36k sims. Extension campaigns since 09-13 added ~8k runs. The facts every plan below
must use:

| # | fact | source |
|---|---|---|
| 1 | **DPN (top-N-sinks DP) is built, gated, campaigned.** DP/DPN = 0.998 over 68 matrix cells (3 workloads, both regimes); 98.9% mean / 96.7% p99 of DP's gain on the paper's 230-cell ResNet ladder — at N@90 = 23/25/25 of 108 destinations (21–23% activity, rotation 138–150 vs 648). Coverage rule: N@90 default, N@95 (27/38/45) for deep above-floor cells. DPN belongs to the **extension**, not Paper 2. | TOPN-DP-INVESTIGATION |
| 2 | **Refresh does not help — confirmed.** ci sweep (648 → 162–324 marginal for DP; DPN ci-insensitive); 4.5× faster rotation = iso-performance; phase-gated oracle +0.2–0.5%. Anticipation axis is dead. | TOPN §ci; EXTENSION-PATHWAYS task 1/3 |
| 3 | **Regime law, isolated.** Below the port floor no engineered mapping creates policy value (six metric arms + a max-E arm at E = 1.000, CCx 1.2–1.3: all 0.94–1.04). Above it DP pays 1.05/1.12/1.35× mean; crossing costs CCx ≥ 1.4. Escape room buys +1.5–3.2%, crossing buys +5–35%. | matrix/ANALYSIS, TOPN §CC-matched |
| 4 | On the flow's own output packings (c16 min-PF) **DP ≈ BL below the floor** (0.99/1.01/0.95). The paper's 1.15–1.26× below-floor wins and 71–78% capture are from other packings. | matrix/ANALYSIS |
| 5 | **Below-floor gain is run-level noise:** split-half reliability r = 0.06 (n = 142). Offline prediction there is ill-posed. A per-cell switching oracle below the floor partly selects noise → the "22–29% gap" is inflated; re-estimate split-half before using it as a prize. | postchecks §4 |
| 6 | **Predictors:** ES/E50/E40 — designed nulls, both directions. E — predicts capacity gain only above the floor **and** on ejection-bound packings (+0.62 ResNet (8,1,8), +0.61 VGG (8,2,4); null on injection-bound VGG (32,8,4) n = 22). New offline candidate: **PIL/PEL binding**. Confirmation pending from the min-E/max-E arms. | memory e-predicts-only-ejection-bound |
| 7 | **Hot-sink counts:** N@80 = 13–17, N@90 = 23–25, N@95 = 27–45 on c16 min-PF packings; 80–90% of bytes on 13–25 sinks is the invariant. (Earlier "c=16 → ~9" is wrong.) | TOPN §6 |
| 8 | `-sel random` exists (`TRouter.cpp:637`); random floor still unmeasured on DNN traffic. | source |
| 9 | Packing rule boundary: min-PF payoff scales with the floor gap (VGG c16 pair, 1.27× gap → 1.75× tail-only at the knee, inverts in saturation). | results_ext/fig6ext |
| 10 | **CiN headroom (offline, from `packing_pf.csv`):** every min-PF pick is injection-bound; scatter (S) lowers PIL → PEL and flips it ejection-bound with floor gains 1.1–3.1× (ResNet (8,2,4) 3.1×, VGG (8,4,2) 1.9×, DeiT (32,2,16) 1.9×). Reduction (D) on ejection-heavy orientations: VGG c8 1.6×, ResNet c8 2.0×, c16 1.4–1.45×. Ceilings — need the replicable/reducible byte share per packing. Scatter also converts port-bound into link-bound congestion, i.e. manufactures the regime where DP/DPN pay. | this note |

Publication plan: Paper 1 accepted → journal extension; rejected → CODES+ISSS (TCAD track).
Same extension material either way.

## Phase 0 — status

| # | task | status |
|---|---|---|
| 0.1 | extension pathways costing | done → EXTENSION-PATHWAYS.md |
| 0.3 | refresh confirmation | done: no gain (fact 2) |
| 0.4 | random-among-legal-ports floor, 3 workloads at the knee | **open** — ~200 runs (8 min-CC placements × own knee × 8 seeds) |
| 0.5 | top-N Turn 1 + Turn 2 + campaign | done (fact 1) |
| 0.6 | CiN Turn 1 | awaiting brief; headroom table already computed (fact 10) |
| 0.7 | CI/duty axis | done downward (648 retired). **Upward untested**: rotation/ci ladder above 648 on DPN, ~100 runs — sizes Paper 2's duty axis |

## Phase 1 — Paper 1 extension (contributions, not tables)

E1 DPN (fact 1) · E2 regime law (fact 3) · E3 predictor verdict (fact 6) · E4 ill-posedness
(fact 5) · E5 boundary conditions (facts 4, 9; ci convention; CCx ≥ 1.4 to cross) · E6 RL bridge.
Exhibits: DPN bars (done), regime-law bars (done, 3 arms/workload), E dose-response
(to build), DPN design table, appendix arm table. Fig 6 and all published numbers stay.

Open scope items: DeiT c32 packing pair (~100 runs, completes C2(a)); second mesh 7×7×3 —
only if reviews ask (≥ 1 week); no-skip vs skip — state as the fixed configuration, retract
the comparative claim, no runs; noise-corrected below-floor oracle — no runs, existing data.

## Phase 2 — Paper 2 (see PAPER2-RL.md)

Axis decided: cost and duty at constant gain; anticipation dead. Stage 1 must match DPN
(0.998 at N = 23–25). Prize re-scoped: no delay margin on stationary traffic; margins are
N at constant gain, duty, and membership under **sink-set change** — a non-stationary
scenario must be defined before stage 1 is designed.

## Phase 3 — CiN (cross-layer flow that designs PF)

S-FIRST on the injection-bound min-PF picks (fact 10) is the relevant router for the flow's
own outputs; D-FIRST on ejection-heavy orientations at c8. Turn 1 = the two offline checks
(replicable share of PIL per source; PL/PF after the flip) + `LOSS-DECOMPOSITION-PROMPT.md`
as the opening exhibit (drain share = the term reduction attacks). Simulatable without router
multicast: proxy-tile re-injection near consumer clusters (traffic-table transformation).

## Phase 4 — gated

Dynamic merge/split; RTL on a hardware question only; TM only if not a DNN profile under
PF/PL/BIND; thermal only with a traffic-side mechanism.

## Kills (current)

- CiN: reducible/replicable share makes every reachable packing < 1.5× → CiN is a footnote.
- CiN regime claim: DP capture does not rise when a flipped packing crosses PL/PF = 1 → provisioning only.
- Paper 2: agent cannot match DPN at equal N → stages 2–3 do not open.
- Paper 2: no non-stationary scenario where membership changes delay → paper is "DPN + hysteresis".
- Paper 2 duty: gain falls immediately above rotation 648 → duty axis flat.
