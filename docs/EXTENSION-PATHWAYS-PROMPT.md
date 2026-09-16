# Claude Code prompt — extension pathways for Paper 1 (next iteration)

## Context

Paper 1 has been submitted to DATE 2027 as a full paper. Two branches follow the decision:
accepted → extend to a journal; rejected → extend to CODES+ISSS (ESWEEK, TCAD track). Both
branches need the same material: depth on existing contributions, not new direction. Nothing
here should become Paper 2 (temporal/phase-aware routing) or the post-programme CiN extension.

This turn is **investigate-only**. Do not run new simulations, do not modify simulator source.
Produce `docs/EXTENSION-PATHWAYS.md` and stop.

## What to produce

For each pathway below: what exists in the repo today, what is missing, the run count and
approximate wall-clock cost to close it, and any blocker. Cite file paths and line numbers for
every claim about repo state. If something is unverifiable from the repo, say so rather than
inferring.

### Pathway 1 — Routing-regime split at full width

The three-panel per-layer p99 figure has the routing panel split into below-floor and
above-floor sub-groups. The paper version is single-column. Establish what the full-width
version would show: which workloads and densities have both regimes populated, seed counts per
cell, and whether the below-floor cells have enough seeds for error bars.

### Pathway 2 — Second mesh size

`docs/PROJECT-RESEARCH-NOTES.md` §31 item 9 leaves a second mesh size open. Candidate is
7×7×3 (147 nodes). Determine: which packings fit (ResNet (8,1,8) at 92 tiles is expected to;
confirm others), whether the placement tooling and the floor computation work unchanged at the
new size, and what the minimum run set is to replicate C5, C7 and the knee-window result at
the second size. Report whether the knee-window argument (all results read in the knee window,
so past-knee parity effects do not apply) is enough on its own that the second mesh is
optional rather than required.

### Pathway 3 — DP refresh-rate test

A reviewer will ask why the below-floor deficit is not simply a DP refresh-rate artifact.
Scope one experiment: rerun the below-floor cells at DP cycle 162 instead of 648 and check
whether the efficiency-gap capture (currently 71–78%) moves. Report: which cells, how many
runs, and — critically — whether the double-buffering torn-read hazard (materialised routing
table written at the DP clock, read at the router clock) is fixed. If it is not fixed, this
pathway is blocked; state that and outline the `dir_tbl[2]` + atomic active-index fix as a
separate task. Do not implement it in this turn.

### Pathway 4 — DP vs BL runtime attribution

Deepen the efficiency-gap result by decomposing the below-floor loss at runtime. Establish
what DPTRACE currently logs, whether it can run on all three workloads at acceptable overhead
(the validation run was seven links — was that a ceiling or a choice?), and what analysis
scripts exist. The target decomposition is: fraction of loss in drain tails vs reconvergence,
and its distribution by phase window and by link class (hot-tier vs relief). **Attribute on
mean delay or per-link blocking cycles only** — p99 does not decompose across links or phases
and must be reported as headline, not decomposed. Flag any existing script that violates this.

Stop at decomposition. Do not propose or evaluate policies that would recover the loss.

### Pathway 5 — Packing panel completeness

Confirm which workload × density cells have both min-bytes and min-PF orientations simulated
(C2(a) says the two objectives disagree in 5 of 9 cells). List the cells, the seed count in
each, and whether any needed for an all-three-workloads packing panel are missing.

## Out of scope — do not investigate

- Temporal or phase-aware routing (Paper 2)
- In-network reduction/scatter (CiN)
- EWMA estimator beyond noting whether the queued single test overlaps with Pathway 3
- Crossbar 256×256 or any packing-set change

## Output format

`docs/EXTENSION-PATHWAYS.md` with one section per pathway, each ending in a one-line status:
READY / NEEDS RUNS (n) / BLOCKED (reason). Close with a table summarising all five. Keep it
under 200 lines. Commit it; do not commit anything else.
