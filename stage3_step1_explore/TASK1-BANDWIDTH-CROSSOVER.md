# Task 1 — Intra-tile vs inter-tile bandwidth crossover (arithmetic, no simulation)

**Date:** 23 Aug 2026
**Status:** computed, then **partially invalidated** by a check against the
Stage-2 generator's own traffic tables. Read §5 before citing any number.
**Artifacts:** `bw_crossover.py`, `bw_crossover2.py`, `bw_crossover.csv`,
`bw_crossover.json`, `bw_crossover.png`

## 1. Model

Constants per `docs/CROSSBAR-ADC-PACKING.md` §0: 128×128 crossbar, 8-bit weights
→ 16 usable weight columns, 16-bit partial sums (derived, §2.2), tree reduction,
`crossbars = ceil(k²·Cin/128) · ceil(Cout·8/128)`.

Per layer: `R = ceil(k²Cin/128)` row groups, `C = ceil(Cout·8/128)` column groups,
`P` output positions. With `T` crossbars/tile packed along the row-group axis,
tiles spanned per column group = `ceil(R/T)`:

- inter-tile psum bits = `(ceil(R/T) − 1) · C · P · 16`
- intra-tile psum bits = `(R − ceil(R/T)) · C · P · 16`

Reported as **demand**, not service — intra-tile contention and ADC serialisation
unmodelled, per the declared limitation in `CROSSBAR-ADC-PACKING.md` §5.

## 2. Results as computed (row-major packing, full networks)

Model size: ResNet-50 12,504 crossbars; VGG-16 67,576; ViT-Base 42,138.

Inter-tile partial-sum demand, Gbit/inference:

| T | ResNet-50 | VGG-16 | ViT-Base |
|---|---|---|---|
| 1 | 0.0222 | 0.1122 | 0.1151 |
| 2 | 0.0088 | 0.0546 | 0.0493 |
| 4 | 0.0037 | 0.0267 | 0.0238 |
| 8 | 0.0014 | 0.0110 | 0.0036 |
| 16 | 0.0005 | 0.0043 | 0.0018 |
| 32 | 0.0001 | 0.0011 | ~0 |
| 64 | ~0 | ~0 | ~0 |

Crossings — row-major: ResNet 1.78, VGG 1.96, ViT 1.83. Blocked (√T×√T):
3.55 / 3.93 / 3.67. All below the {4…64} sweep range.

The three *different* crossing points that `CROSSBAR-ADC-PACKING.md` §5 predicts
do not appear under row-major packing: the crossover is governed by `ceil(R/T)`
vs `R`, and `R ≫ T` for every volume-dominant layer, so it collapses to ~`1/T`
regardless of layer shape. VGG's deep-fan-in FC layers do have large `R`
(fc6: 196) but `P = 1`, so they carry negligible volume.

## 3. Packing axis is a first-order choice, not a footnote

Row-major vs blocked shifts the crossing by a factor of 2 and keeps inter-tile
psum traffic alive one binary step longer. §5 below shows this is in fact the
dominant modelling assumption in the whole calculation.

## 4. Verified against project data

The work-queue `[VERIFY]` item on hotspot share is **confirmed**. In
`traffics_dnn_6base/rn50_6b_ls0.006_flows.csv`, nodes 4 and 40 each take 18
incoming flows and 1,708,924 bytes of 8,837,248 total — **38.7% combined**.
The corrected 32–38% figure is right; the earlier ~72% was not.

## 5. ⚠ Divergence from the Stage-2 generator — invalidates §2

Checked after computing, against `traffics_dnn_6base/*_flows.csv`:

1. **Scope mismatch.** §2 models all 53 layers of full ResNet-50 and aggregates.
   The Stage-2 tables model a *single bottleneck block* (`resnet50_bottleneck3`);
   its `conv1/conv2/conv3` phases are the three convs inside that block, not
   ResNet's conv2_x stage.

2. **Packing-axis mismatch.** §2 assumes row-major packing, which maximises
   intra-tile reduction and drives inter-tile psum traffic toward zero by T=16
   (psum ≈ 0.5–4% of NoC traffic). The generator produces the opposite:

   | class | bytes | share |
   |---|---|---|
   | reduce (partial sums) | 7,225,344 | **81.8%** |
   | scatter (activations) | 1,411,200 | 16.0% |
   | add (shortcut) | 200,704 | 2.3% |

   conv2/reduce alone is 3.41 MB across 34 flows. The generator is not packing
   row-major.

**Therefore:** the §2 crossing points and the "workload-independent crossover"
claim are conditional on row-major packing and must not be quoted for this
project until recomputed against the real rule in `tools/stage2_core.py`.
An earlier draft of this note also speculated the conv2 hotspot might be
activation-driven — that is **wrong**; it is reduce-driven, empirically.

**What survives:** the model structure, the packing-axis sensitivity result, and
the method.

## 6. To finish Task 1 properly

- [ ] Read the packing rule out of `tools/stage2_core.py`; replace `split_rowmajor`
- [ ] Rescope to the bottleneck block the tables actually model
- [ ] Add `c` = 96 (ISAAC: 12 IMAs × 8 crossbars at 128×128) — `CROSSBAR-ADC-PACKING.md` §5
- [ ] Add 256×256 crossbar as a second curve family — §1 "what to do instead"
- [ ] Add fragmentation curves (whole-tile allocation waste) — §5 calls this the
      recommended lead justification for low `c`
- [ ] Add phase-utilisation and power-density curves — §4, §5
