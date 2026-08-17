# Handover

Newest section first. Older handovers kept below for context.

---

# Machine migration + Stage 3 state — 17 August 2026

Moving from the i7-10510U dev box (4 cores / 8 threads, 15 W, thermally throttled,
8 GB) to an **i7 13th-gen, 10 cores / 16 threads, 32 GB**.

## Setup on the new machine

1. **SystemC 2.3.3 at `$HOME/tools/systemc-2.3.3-install`.** Use that exact path and
   `Makefile.defs` needs no edit — it is already `$(HOME)`-relative.
2. `make` — `*.o`, `noxim` and `noxim_1x` were deliberately excluded from the archive.
3. **Verify determinism before trusting any run.** Runs are deterministic per seed and
   every published number depends on that (CLAUDE.md: non-identical output when it
   should be identical is a bug, not noise).

```
./noxim -dimx 6 -dimy 6 -dimz 3 -buffer 16 -routing oddeven -sel dp \
  -cinterval 648 -size 16 16 -warmup 9720 -sim 124328 -samp 1 \
  -traffic table traffics_dnn_6base/rn50_6b_ls0.026_diag_accint.txt -seed 2
```

| config (seed 2, ls 0.026, ci 648, 3 passes) | delay | throughput | max delay |
|---|---|---|---|
| interior placement (`_diag_accint.txt`), DP | **104.168** | 0.0170293 | 3112 |
| edge placement (`_diag.txt`), DP | **182.155** | 0.0170411 | 7642 |

Last-digit differences = GCC codegen drift in float summation, tolerable but means old
and new rows are not strictly poolable. Material differences = stop and investigate.

## Parallelism

`-P 8` on the old box measured a **2.9× contention factor** (8 jobs delivering under 3
jobs of throughput), mostly thermal. Use **`-P 12`** on the new box —
`run_6x6x3.bash --jobs 12`; its default is still 8. Memory is a non-issue (~50 MB per
sim). Caveat: 10 cores / 16 threads is a hybrid part, so runs landing on E-cores finish
later and each `xargs` wave is paced by its slowest job. Wall-clock only; results are
timing-independent. Expect **4–6×** faster batches — the 120-run n=30 comparison drops
from ~20 min to ~4.

## Where the work stands

**Primary setup** (see `memory` / `MAPPING.md`): 6×6×3, ResNet-50 stage-3 bottleneck,
**92 tiles at 8 crossbars/tile** (the base partition — *not* the older inflated
108-tile artefacts in `traffics_dnn/`), XY-diagonal placement, `-routing oddeven`,
`-cinterval 648`, `-warmup 9720`, `-sim 124328` (3 whole block passes).
`dp_cycle = (ceil(diameter/4)+3)·nodes = 648` here; the scripts' printed
`DP_CYCLE = 2·nodes·(diam+3) = 3240` is the legacy 1×/settle-1 formula — fine for
warmup sizing, **wrong for `-cinterval`**.

**The Stage 3 result** (FINDINGS.md, `STAGE3-MAPPING-FINDINGS.md`): DP's null result on
DNN traffic is a **placement funnel**, not a DP defect. conv2's 18→1 reduction landed on
mesh-edge nodes whose arrival face is fixed by geometry, so no selection policy could
rebalance the last hop. Swapping the two accumulators to interior nodes (pure
transposition, same graph/rates/windows) moves DP from +5.0% to **−28.96% vs bufferlevel**
(t = −3.51, n = 30) at ls 0.026, and the **tail is better still: −41.1%, t = −4.10**.

**Carry this qualification with the number.** At ls 0.020 (below the knee) the same swap
gives only −1.94% (t = −1.08) — the funnel must be *loaded* for un-funnelling it to pay.
Claim to use: *"past the knee, placement decides whether DP can win"*, **never a bare
−29%**. Throughput is invariant everywhere (all |t| ≤ 1.65); the entire effect is latency.

**Knee (interior placement, BL, 3 seeds):** 18.52 @0.014 → 31.84 @0.020 → 47.40 @0.023 →
63.49 @0.024 → 70.05 @0.025 → **191.93 @0.026**. The elbow is between **0.025 and 0.026**
(2.74× step vs ≤1.5× everywhere below), so 0.026 is *just* past the knee — the right
operating point, not deep saturation.

## Immediate next steps

1. **30-seed DP-vs-BL at ls 0.025**, interior placement — the last point on the linear
   ramp, and the load where the DP-vs-BL crossover should sit. Tables for
   ls 0.014–0.030 are all generated and assert-checked as
   `traffics_dnn_6base/rn50_6b_ls<LS>_diag_accint.txt`.
2. **Write the ls-0.020 qualification into FINDINGS.md and `STAGE3-MAPPING-FINDINGS.md`
   §3** — both currently state −29% without its load condition. **Outstanding.**
3. Finish the interior knee sweep proper (`results_6b_knee_int/` has only the 9 BL
   points above plus 3 stale rows).
4. Then VGG-16 and the transformer per `MAPPING.md` — score placements with
   `oe_arrival_faces.py` *before* simulating, never geometrically.

## Housekeeping

- **13 commits unpushed** on `main`. Remote is SSH (`git@github.com:nizarsd/...`), so
  pushing needs `gitkeygen.txt` — which is in the archive and is a **private key**.
  Keep the archive off shared storage. The key and `noxim_*` are now gitignored.
- `results_*/` is gitignored by design; the runner scripts plus each doc's timing
  derivation are the record. The archive carries the n=30 datasets anyway
  (`results_6b_accint/`, `results_6b_ls020/`).
- Untracked scratch left behind deliberately: `handover-venues.patch`,
  `readme-dnn.diff`, `plot_channel_trace.py.ci100`.

---

# Handover — Stage 2 state as of 2026-08-13

Recovered from two worktree sessions whose working folders were deleted. **No work was
lost** — both commits are on `main`. This file exists so the context survives next time.

## Where things stand

`main` @ `8ec5fa9`, 2 commits ahead of `origin/main` (nothing pushed).

| commit | contents |
|---|---|
| `d2382ce` | STAGE2.md §9.3 correction — 60 → 92 tiles, retarget 5×5×3 → 6×6×3 |
| `8ec5fa9` | `stage2_dnn_traffic.py`, `noximrun_dnn_traffic.bash`, `traffics_dnn/` + verification CSVs |

## Decisions resolved in the lost sessions

These are settled — don't relitigate them:

- **Shortcut owns crossbar tiles.** The projection stores its 512×1024 weights on real
  nodes, so it contributes scatter + psum-reduction traffic, not just a skip flow. This is
  what pushed the block from 60 → **92 tiles**.
- **Mesh is 6×6×3** (108 nodes) — 92 tiles fit with 16 spare; 5×5×3 (75) does not. 6×6×3
  was already swept in Stage 1, so DP-vs-BL comparability survives.
- **Crossbar stays 128×128.** (256×256 was costed and rejected.)
- **Both row and column splits are needed**, not one or the other: column split = different
  output channels → input fan-out/multicast; row split = different input channels →
  partial-sum reduction.
- **Tiles are a converter-only concept.** The simulator only ever reads
  `src dst pir por t_on t_off t_period`; tiles just decide which node IDs appear in rows.
- Tuning applied at the end: `CYCLES_PER_MAC = 1.3e-4`, `SIM_DP_CYCLES = 80`.

## Sweep status — complete and aggregated

All 42 runs finished (7 load scales × 2 selections × 3 seeds). `summary.csv`,
`summary_mean.csv` and `summary_compare.csv` are rebuilt in `results_dnn_scale_sweep/`.

**The sweep is mis-centred — this is the main problem with it.** Only `ls=0.01` is a
lightly-loaded point; by `ls=0.02` delay is already 29× unloaded, and throughput departs
from linear at `ls=0.03`. The knee sits between **0.02 and 0.03**, so six of seven points
are past it and `ls ≥ 0.12` is hard-saturated (throughput ceiling ~0.0070 flits/cycle/IP;
+67% offered load from 0.12→0.20 buys +2% delivered).

| ls | thru/IP | vs linear | delay | × unloaded |
|---|---|---|---|---|
| 0.01 | 0.00095 | 1.00 | 32 | 1× |
| 0.02 | 0.00191 | 1.01 | 955 | 30× |
| 0.03 | 0.00269 | 0.95 | 2766 | 86× |
| 0.05 | 0.00400 | 0.84 | 5033 | 155× |
| 0.08 | 0.00582 | 0.77 | 8074 | 250× |
| 0.12 | 0.00687 | 0.60 | 19313 | 597× |
| 0.20 | 0.00701 | 0.37 | 33775 | 1044× |

### DP vs BL — one real result, the rest is noise

At n=3, **no delay difference is statistically significant** (Welch t < 2.8 everywhere).
The tempting +15.9% delay reduction at `ls=0.12` is t=2.18 — not significant. This is
exactly the FINDINGS.md trap.

**The solid finding is throughput at saturation:** at `ls=0.20` DP delivers **+6.8%**
(t=7.70, no seed overlap) — 1,989,731 vs 1,863,366 flits.

**The −9.8% delay at `ls=0.20` is confounded, not a regression.** DP accepted 6.8% more
traffic, so it sits further up the same delay curve. Do not report it as "DP loses".

Possible cross-validation of the Stage 1 parity finding: 6×6×3 is **even×even** in X/Y, and
FINDINGS.md says even×even reverses just past the knee — DP's delay advantage peaks at
`ls=0.12` then flips at `0.20`. Same shape, but not significant at n=3.

### To make this publishable

1. Dense load points between **0.01 and 0.04** to actually locate the knee.
2. More seeds (n=3 → ~10) at the knee and at saturation.
3. Lead with the throughput result; the delay story needs the knee first.

## Open items

1. **Routing choice for DNN traffic** (STAGE2.md §8) — still unresolved. The generated
   table runs on `oddevenbalanced` by default: the better DP substrate, not the fastest
   routing.
2. **Verify the flows-CSV / volume-matrix agreement.** The *superseded* converter
   (`stage2_resnet_traffic.py`, since deleted) had a 0.0016-packet mismatch — too large for
   float64 rounding, so likely a real aggregation bug in `to_rows`. Whether it carries into
   the rewritten `stage2_dnn_traffic.py` was never checked.
3. **Reading the results:** quote **absolute delay** alongside any DP-vs-BL percentage, and
   locate this pattern's *own* knee first. The FINDINGS.md routing-variant study produced a
   headline "+53%" that was really BL degrading faster than DP.
4. **Transformer workload omits residual connections** — blocking for that workload.
   `transformer_layers()` in `stage2_dnn_full.py` models each encoder block as
   q/k/v/o/ff1/ff2 in a pure sequential chain. A real block has a residual around the
   attention sublayer and another around the FFN sublayer: **2 per block, 24 across 12
   blocks**. These are long-range flows, the analogue of ResNet-50's 12 identity shortcuts
   (mean hop 3.78 vs 3.53 for all other flows). Omitting them understates the transformer's
   non-locality and so understates DP's opportunity, since DP's advantage comes from seeing
   congestion several hops out. Fix as `kind="identity"` — zero crossbars, traffic only,
   window spanning the bypassed sublayer — **before running any transformer simulation or
   comparing it against ResNet-50**.

## Publication targets (checked Aug 2026)

**NOCS no longer exists** — NOCS 2023 was the final edition; the organisers closed the
symposium. Any older plan naming NOCS as the priority-establishing venue is out of date.
**NoCArc** (where c2 was published) has a stale site showing only NoCArc 2024 @ MICRO-57;
status unknown, worth emailing the organisers. **VLSI-SoC 2026** (c1, c10 venue) has closed
— abstract 20 Apr, paper 27 Apr 2026; watch for the 2027 CfP around Jan–Feb. Best papers
there are invited to an ACM JETC special issue (j7's venue).

Two live targets:

| venue | deadline | notes |
|---|---|---|
| **DATE 2027**, Dresden, 22–24 Mar 2027 | regular: abstract **13 Sep 2026**, paper **20 Sep 2026** (AoE, firm) | Lists "Network on chip and on-chip communication" explicitly. c5 was published at DATE. |
| **DATE 2027 LBR** | **not yet announced** — full CfP pending | 2-page extended abstract (+1 page refs only), blind review, interactive session. LBR deadlines fall *after* the regular one; expect ~Nov 2026–Jan 2027. |
| **SAMOS 2027**, Samos, July 2027 | submissions **Feb 2027**, notification May 2027 | SAMOS 2026 was **cancelled**; returns 2027. Springer LNCS, DBLP-indexed; selected papers invited to an IJPP special issue. |

Watch <https://www.date-conference.com/call-for-papers> for the DATE 2027 full CfP (LBR
dates). One aggregator lists the DATE regular deadline as 7 Sep rather than 13/20 Sep —
verify against the official page before planning.

**Suggested sequence:** the 20 Sep regular deadline is likely too tight (Stage 3 not
started). Target **DATE 2027 LBR** when that call opens to establish priority, then
**SAMOS 2027** (Feb) for the full paper. Two shots without compressing the work.

**What would be publishable** (Stage 2 alone is not — a converter is tooling):
Stage 2 + Stage 3 together, with the *finding* as the contribution. Candidate claims,
depending on results: (a) congestion-aware selection policies evaluated on synthetic
traffic do not transfer as expected to DNN inference traffic — nobody has compared
selection policies under DNN traffic, as Krishnan uses fixed X–Y routing and the DSE
literature fixes routing entirely; (b) whether Stage 1's diameter/parity mechanism
survives phased DNN traffic; (c) if congestion never materialises, the negative result
extended to 3D and adaptive routing, *provided* the load-scale threshold is quantified.
Needs all three workloads, both synthetic and DNN baselines on the same meshes, and at
least two mesh sizes — otherwise "3D" is asserted rather than examined.

## Repo hygiene (noted, not yet done)

- `.claude/` is untracked but **not** gitignored — `git add -A` from main would sweep it in.
- `gitkeygen.txt` is an **OpenSSH private key**, untracked and not gitignored, in a repo
  whose `origin` is public.
- Branch `claude/folder-contents-review-46d44e` is fully merged into `main` and can be deleted.

## Recovering a lost session

Transcripts outlive their working directory. They live in
`~/.claude/projects/<path-with-slashes-as-dashes>/<session-uuid>.jsonl`, one JSON object per
line with `type` of `user` / `assistant`.
