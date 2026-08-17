# Placement objective for DNN traffic tables

How to place tiles onto nodes when generating the **VGG-16** and **transformer**
workloads, derived from the ResNet-50 result in [FINDINGS.md](FINDINGS.md) §"The
mechanism: a funnel at the reduction sinks".

## Why placement is the lever

On the ResNet-50 block, swapping **two** node pairs — nothing else changed, same
traffic graph, rates and phase windows — moved DP from +5.0% (no effect) to
**−29.0% vs bufferlevel** (t = −3.51, n = 30), while making bufferlevel 18.7%
*slower*. Placement decides whether the congestion a workload creates is
**routable at all**. A mapping that leaves no routable congestion leaves nothing
for any selection policy — DP today, RL in Stage 7 — to act on.

## The objective

> **Minimise the peak routing-admitted arrival-face load over all (node, face)
> pairs, subject to a bound on mean hop count.**

Score it with [`oe_arrival_faces.py`](oe_arrival_faces.py):

```
python3 oe_arrival_faces.py TABLE.txt DIMX DIMY DIMZ --routing oe --top 8
```

It enumerates every admissible minimal path and records the **final hop**, so it
measures what the router will actually do.

**Do not use a geometric estimate** ("one face per displaced dimension"). On
ResNet node 4 it gave 0.118 flits/cyc against **0.274 measured by DPTRACE**;
the path-enumeration model gives 0.297, within 8%. The geometric metric scored a
worthless swap as an improvement — the resulting run measured +2.6%, t = 0.45.

## Rules, in order of measured impact

1. **Match fan-in to node degree.** Rank sinks by in-traffic; give the heaviest
   the nodes with most links. Interior = 6, face = 5, edge = 4. On the ResNet
   block this alone was worth −19.7% to DP.
2. **Surround the sink.** Six links are useless if every sender lies on one side.
   Place each accumulator near the **centroid of its own reduction group**.
   Target worst-face/mean-face → 1.00; measured 3.68× (edge) → 2.07–2.33×
   (interior).
3. **Check faces the *router* admits, not the geometry.** Node 52 had six
   geometric faces and OE allowed only four.
4. **Separate the hot sinks** from each other — the top two shared a link before
   the fix.
5. **Interior budget is the binding constraint.** Interior nodes number
   (X−2)(Y−2)(Z−2) — only **16** on 6×6×3. Z=3 has one interior plane; Z=4
   doubles it. Spend the budget on the top sinks by traffic share.
6. **A low-fan-in sink cannot be fixed by placement.** Three senders cannot fill
   six faces wherever you put them. Those need a wider phase window or a split
   reduction, not relocation.

## What this means for the two remaining workloads

`R` = reduction depth = fan-in per accumulator; `C` = accumulators per layer.

| workload | layer | matrix | **R (fan-in)** | **C (accs)** | tiles |
|---|---|---|---|---|---|
| ResNet-50 (measured) | conv2 | 2304×256 | 18 | 2 | 36 |
| **VGG-16 blk 3** | conv5 | 1152×256 | 9 | 2 | 18 |
| | conv6 | 2304×256 | **18** | 2 | 36 |
| | conv7 | 2304×256 | **18** | 2 | 36 |
| **Transformer** | q/k/v/o | 768×768 | 6 | 6 | 36 |
| | ff1 | 768×3072 | 6 | **24** | 144 |
| | ff2 | 3072×768 | **24** | 6 | 144 |

**VGG-16 is the harder placement problem.** Three consecutive layers each carry
an 18- or 9-deep reduction into only **2** accumulators — so six hot sinks, two
of them as concentrated as ResNet's worst, and they fire in **adjacent phases**
rather than one dominating. Expect the interior budget to bind: six sinks needing
interior nodes against 16 available on 6×6×3, and they must also be separated
from each other. Rules 1, 4 and 5 dominate. VGG block 3 is 90 tiles, so on 6×6×3
(108 nodes) there are only 18 spare — much tighter than ResNet's 16-of-108 with a
single dominant layer.

**The transformer is the easier one, except for `ff2`.** `q/k/v/o` and `ff1`
spread their reduction over 6 and 24 accumulators at fan-in 6 — inherently
spread, close to what a tree reduction would produce, and unlikely to funnel.
`ff2` is the exception and is **worse than anything in ResNet**: fan-in **24**
into 6 accumulators. Those six nodes are the whole placement problem; put them
interior, centroid-of-senders, mutually separated, and score with
`oe_arrival_faces.py` before running. Note the transformer block is 432 tiles, so
it does not fit 6×6×3 or 7×7×3 at 128×128 — resize the mesh or the crossbar
first, and re-derive the table with that in mind.

**Before any transformer run**, fix the missing residuals — `transformer_layers()`
in `stage2_dnn_full.py` omits 2 per block, 24 total. They are long-range flows and
their absence understates the workload's non-locality, which is precisely the
stimulus DP responds to.

## Alternative: remove the funnel instead of relocating it

Flat `R → 1` reduction becomes a tree, e.g. 18 → 6 → 2 → 1, dropping max fan-in
from 18 to 3. The hotspot stops existing rather than moving. Costs ~44% more
bytes (intermediate sums also travel) and adds sequential stages needing their own
phase sub-windows. Converter-side only, in `reduce_within()` — the simulator does
not change. This is what real accelerators do (ISAAC/Krishnan H-tree between CEs,
[RELATED_WORK.md](RELATED_WORK.md) §1) and it is the right fix for VGG's six
sinks, where placement alone will run out of interior nodes.

## Caveats

- The ResNet result is measured at `ls=0.026`, **past that mesh's knee** (delay
  rises 4.9× from 0.020). Locate each workload's own knee before quoting a
  DP-vs-BL percentage — see the FINDINGS.md warning about saturation artefacts.
- `oe_arrival_faces.py` ports `routingOddEven3D` and reuses the OEB port in
  `oeb_path_diversity.py`. Validated against one DPTRACE measurement (8%), not
  against a full hop trace. Cross-check before a paper number.
