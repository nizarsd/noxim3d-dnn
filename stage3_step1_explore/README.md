# Task 1 — intra vs inter-tile bandwidth crossover (arithmetic, no simulation)

Generated 23 Aug 2026. Suggested home in the repo: `tools/task1_bandwidth/`.

## Contents

| File | What it is |
|---|---|
| `bw_crossover.py` | v1 model. Layer shapes for ResNet-50 / VGG-16 / ViT-Base, crossbar geometry, row-major split. Importable — v2 pulls `WORKLOADS`, `layer_geometry`, constants from it. |
| `bw_crossover2.py` | v2. Adds T ∈ {1,2}, blocked-packing sensitivity, inter-layer activation reference line. Writes the CSV, JSON and PNG. Run this one. |
| `bw_crossover.csv` | Per workload × T: intra/inter demand under both packings, activation volume, psum share of NoC. |
| `bw_crossover.json` | Same data plus computed crossing points. |
| `bw_crossover.png` | Three-panel figure, log-log, shaded region = the queue's original {4..64} sweep range. |

Run: `python3 bw_crossover2.py` (needs numpy + matplotlib; writes outputs to the
paths hard-coded at the bottom of the script — edit those before running elsewhere).

## Model

128×128 crossbar, 8-bit weights → 16 usable weight columns, 16-bit partial sums,
tree reduction, `crossbars = ceil(k²·Cin/128) · ceil(Cout·8/128)`.

Per layer: `R = ceil(k²Cin/128)` row groups, `C = ceil(Cout·8/128)` column groups,
`P` output positions. At `T` crossbars/tile, tiles spanned per column group = `ceil(R/T)`:

- inter-tile psum bits = `(ceil(R/T) − 1) · C · P · 16`
- intra-tile psum bits = `(R − ceil(R/T)) · C · P · 16`

Reported as **demand**, not service — intra-tile contention and ADC serialisation
are unmodelled, per the declared limitation in `docs/CROSSBAR-ADC-PACKING.md` §5.

## ⚠ Known divergence from the Stage-2 generator — read before citing

These numbers do **not** describe the configuration your traffic tables simulate.
Two differences, found after the fact by checking `traffics_dnn_6base/*_flows.csv`:

1. **Scope.** This models all 53 layers of full ResNet-50 and aggregates. Your
   Stage-2 tables model a *single bottleneck block* (`resnet50_bottleneck3`),
   where `conv1/conv2/conv3` are the three convs inside that block — not ResNet's
   conv2_x stage.

2. **Packing axis.** This assumes **row-major** packing along the row-group axis,
   which maximises intra-tile reduction. Under that assumption inter-tile psum
   traffic falls to near zero by T=16, giving psum ≈ 0.5–4% of NoC traffic.
   Your generator produces the opposite: in `rn50_6b_ls0.006_flows.csv`,
   `reduce` (partial sums) is **81.8%** of 8.84 MB total, `scatter`
   (activations) 16.0%, `add` 2.3%. So the generator is not packing row-major.

**Consequently:** the crossing points reported here (T ≈ 1.8–2.0 row-major,
≈3.5–3.9 blocked) and the "workload-independent crossover" claim are conditional
on row-major packing and should not be quoted for this project until recomputed
against the real packing rule in `tools/stage2_core.py`.

**What survives:** the model structure, the blocked-vs-row-major sensitivity
(packing axis is a first-order choice, not a footnote), and the method for adding
the `c`=96 ISAAC point and a 256×256 second curve family that
`CROSSBAR-ADC-PACKING.md` §1 asks for — both still to be done.

## Separately verified from your data

The work-queue `[VERIFY]` item on hotspot share is **confirmed**: in
`rn50_6b_ls0.006_flows.csv`, nodes 4 and 40 each take 18 incoming flows and
1,708,924 bytes — **38.7% combined** of total traffic. The corrected 32–38%
figure is right; the earlier ~72% was not.

## To finish Task 1 properly

- [ ] Read the packing rule out of `tools/stage2_core.py`; replace `split_rowmajor`
- [ ] Rescope to the bottleneck block the tables actually model
- [ ] Add `c` = 96 (ISAAC: 12 IMAs × 8 crossbars at 128×128)
- [ ] Add 256×256 crossbar as a second curve family
- [ ] Add fragmentation curves (whole-tile allocation waste) — `CROSSBAR-ADC-PACKING.md`
      §5 calls this the recommended lead justification for low `c`
- [ ] Add phase-utilisation and power-density curves (§4, §5)
