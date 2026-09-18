# Registered predictions — c16 coherent matrix campaign

Registered 2026-09-17, BEFORE any main-batch run. Search (phase 1/1b) and the
level-metric screen on existing int-arm cells (corr_levels.txt) are the only
inputs. Probes select rungs only; no outcome data has been seen.

**Design:** 3 workloads at their c=16 min-PF packings — ResNet (16,2,8),
VGG (16,4,4), DeiT (16,1,16) — 7 placement arms x 8 placements, per-placement
knee rung (nearest 5x own free-flow, band 4-6x), 8 seeds.
Arms: minCC (existing int runs), maxES, maxE50, maxE40, minE40, minE50
(all CC<=start, PL<=start, below floor), aboveF (PL = 1.10xPF +/- 2%, CC
minimised secondarily). Policies: BL/DP/DPN on minCC, maxES, aboveF; BL/DP on
the four E-race arms. DPN: per-packing N@90 = 23/25/25, ci = 6N.

## Predictions

P1 (minCC, existing data): three-way parity, |gain| <= 6% mean — the
mapping-freedom regime.

P2 (maxES): DP >= BL at the knee below floor (the paper's maxES direction);
DPN within +/-6% of DP at 21-23% of DP's sweep activity.

P3 (max-arm race, delay vs minCC under both policies): maxES remains the best
free mapping refinement; maxE50/maxE40 improve less or not at all. A level-form
win here overturns the ES refinement claim.

P4 (min arms, the causal DP-gain test): minE40 manufactures DP-over-BL gain —
its DP/BL ratio exceeds the minCC arm's, strongest on ResNet (screen r=-0.87),
weak on VGG (screen ~0 to -0.27). minE50 second. If the max arms also raise DP
gain, the level metrics are confounded with something else and the screen's
sign was accidental. The effect must be broad-tier (E30-E50 co-moving), not
specific to the 40% constant — if it exists only at exactly one level it is
noise and will be reported as such.

P5 (aboveF): DP > BL clearly (above-floor regime, both mean and p99); DPN
within +/-6% of DP; spread across placements DPN <= DP < BL.

P6 (workload ordering of discrimination): ResNet > DeiT > VGG. DeiT caveat:
its engineered arms overlap (maxE40 carries near-maxES ES), so DeiT
attribution between ES and E40 is expected to be weak by construction.

## Falsifiers

- P4 fails if minE40's DP/BL gain <= minCC's (ResNet, 8 placements, 8 seeds).
- P3 fails if a maxE arm beats maxES on mean delay at matched depth under BL.
- P2/P5 fail if DPN deviates from DP by more than 6% in the arm's pooled mean.
