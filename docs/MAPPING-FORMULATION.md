# Two-Stage Mapping — Problem Formulation

Formulation for Paper 1 (mapping / design-space exploration). Absorbs the former
`MAPPING.md` (placement objective, rules, per-workload structure). Companion to
[SESSION-NOTES.md](SESSION-NOTES.md) §5, which holds the work queue derived from this.

Status: formulation settled in discussion; **not yet implemented**.

---

## 1. The decomposition

Mapping a DNN onto a 3D NoC is **two decisions, not one**, and they are not
interchangeable:

| Stage | Decision | Determines | Cannot change |
|---|---|---|---|
| **A — Packing** | crossbars → tiles | the **traffic graph**: which flows exist, their volumes, their fan-in | — |
| **B — Placement** | tiles → mesh coordinates | **path diversity** and hop count | the traffic graph |

**Key asymmetry:** placement can only decide how well the network serves a given
traffic graph. It cannot alter that graph. Packing is what creates or destroys
the aggregation structure in the first place.

This separation is the paper's organising claim. Prior work (Krishnan et al.,
ISAAC) fixes packing by architectural convention and does not treat it as a
mapping variable at all.

---

## 2. Fixed architectural constants

Settled. Used by both stages.

| Parameter | Value | Source |
|---|---|---|
| Crossbar array | 128 × 128 cells, 1 bit/cell | current configuration |
| Weight precision | 8 bits | — |
| Usable weight columns | 128 / 8 = **16** | derived |
| Weight capacity per crossbar | 128 × 16 = **2048** | derived |
| Partial-sum width | **16 bits** | ISAAC convention; matched to 128-row accumulation |
| Intra-tile reduction | **tree** | ISAAC convention; affects latency/wiring, not volume |
| Mesh | **6 × 6 × 3** (108 nodes) | fixed across all workloads |

Crossbars required per layer:

```
crossbars = ceil( (k · k · Cin) / PE_x ) · ceil( (Cout · N_bits) / PE_y )
```

with `PE_x = PE_y = 128`, `N_bits = 8` (Krishnan JETC 2022, Eq. 2).

> The `N_bits` factor is easy to omit and caused an ~8× undercount earlier in the
> programme. It is the reason a 128-column array holds only 16 weights across.

**The mesh is fixed deliberately.** The NoC is the object of study; it cannot
also be a variable. Packing absorbs model-size differences between workloads so
that tile occupancy stays comparable across ResNet-50, VGG-16 and ViT-Base.

---

## 3. Stage A — Packing (crossbars → tiles)

### Decision variable

`c` = crossbars per tile, swept over {4, 8, 16, 32, 64}.

(Which crossbars share a tile is a second-order variable — grouping crossbars
that feed the same output channel flattens aggregation, grouping across output
channels preserves it. Held fixed initially.)

### The bandwidth trade-off

Each crossbar produces partial sums that must be reduced. Packing decides where
that reduction happens:

- **Intra-tile demand** rises with `c` — more partial sums reduced on the on-tile
  bus / H-tree.
- **Inter-tile demand** falls with `c` — fewer partial sums cross the network.

Both curves are computed as: (number of partial sums on that side) × 16 bits.

**The crossing point** — where the two curves meet — is where the two burdens
balance. Below it the network is the bottleneck; above it the tile fabric is.
It marks the natural centre of the design space.

### Procedure (arithmetic only, no simulation)

1. From layer shapes, compute crossbars per layer via the formula above.
2. For each `c` in the sweep, partition partial sums into intra-tile and
   inter-tile.
3. Multiply by the 16-bit payload → two bandwidth-demand curves.
4. Plot per workload; record the crossing point.

**Expect three different crossing points**, one per workload. Layer shape drives
the split: VGG's FC layers have far deeper per-output fan-in than ResNet
bottlenecks; ViT attention differs again. **Workload-dependent optimal packing is
itself a reportable finding**, not merely calibration.

### Do this before choosing which packings to simulate

If the curves cross at 12, then {4, 8, 16} brackets it well. If they cross at 40,
the current sweep range is in the wrong place entirely. This is cheap arithmetic
that determines the simulation budget.

### Lower bound on packing — a research constraint, not just area realism

Packing an aggregation tree entirely inside one tile **engineers away the
phenomenon under study**. The conv2 hotspot exists because 18 separate flows
converge on one tile:

| `c` | Converging flows at the hotspot | Status |
|---|---|---|
| 8 | 18 | current |
| 16 | ~9 | still a hotspot, still network traffic |
| 32 | ~4–5 | phenomenon largely internalised |

So `c` has a **lower bound set by preserving inter-tile aggregation**. 16 is
attractive: it retains the hotspot and lands exactly on Krishnan's published
configuration.

### Declared modelling limitation

**The simulator does not model intra-tile contention.** Denser packing does not
remove aggregation cost — it relocates it onto the on-tile bus / H-tree.

Mitigation: report **demand**, not service. The bandwidth curves are a
requirements statement, not a performance claim, so no second simulator is
needed. State this explicitly in the paper.

Note also that Krishnan's "no congestion observed" finding is plausibly the same
artifact — a consequence of 16-crossbar tiles internalising the aggregation.

---

## 4. Stage B — Placement (tiles → mesh)

### Why placement is the lever

On the ResNet-50 block, swapping **two** node pairs — nothing else changed, same
traffic graph, rates and phase windows — moved DP from +5.0% (no effect) to
**−29.0% vs bufferlevel** (t = −3.51, n = 30), while making bufferlevel 18.7%
*slower*. Edge tiles expose only 3–4 usable input ports instead of 6.

Placement decides whether the congestion a workload creates is **routable at all**.
A mapping that leaves no routable congestion leaves nothing for any selection
policy — DP today, RL in Stage 7 — to act on.

### Objective

> **Minimise the peak routing-admitted arrival-face load over all (node, face)
> pairs, subject to a bound on mean hop count.**

Score it with [`oe_arrival_faces.py`](../tools/oe_arrival_faces.py):

```
python3 tools/oe_arrival_faces.py TABLE.txt DIMX DIMY DIMZ --routing oeb --top 8
```

It enumerates every admissible minimal path and records the **final hop**, so it
measures what the router will actually do. `--routing oeb` is the default and is
the relaxed odd-even-balanced model as simulated; `oeb2` reproduces the historic
modified2 analysis.

**Do not use a geometric estimate** ("one face per displaced dimension"). On
ResNet node 4 it gave 0.118 flits/cyc against **0.274 measured by DPTRACE**;
the path-enumeration model gives 0.297, within 8%. The geometric metric scored a
worthless swap as an improvement — the resulting run measured +2.6%, t = 0.45.

Validated as monotone against measurement on four ResNet placements: peak
0.190 → −50.2% p99, 0.254 → −37.2%, 0.297 → +5.1%, 0.382 → +31.9%.

### Rules, in order of measured impact

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

**Which sinks to relocate is decided by traffic, not by count.** Because the
objective is a *max*, moving any sink that is not the argmax changes it by zero:
ResNet's 2 conv2 sinks carry 47% of reduce traffic and moving them took the peak
0.382 → 0.190, whereas VGG's conv5 pair sits at 0.216, below the conv6/conv7
argmax of 0.301, so relocating it contributes nothing. The rule that makes
workloads comparable: **keep relocating the current argmax until the peak is no
longer set by a relocatable sink** — terminating at 2 sinks for ResNet, 3 for the
transformer, 4 for VGG. Report Δf₁ and the fraction of reduce traffic covered,
never the raw count.

### Path-diversity metric — the enabling condition, not the objective

Computed **under the actual turn model**, not raw topology. Odd-even-balanced
legality branches on coordinate parity, so an interior 6-port node may have fewer
usable paths than its degree implies.

Per src→dst pair:

1. Enumerate **legal minimal paths** under the turn model.
2. Count them.
3. Weight by flow volume.
4. Sum over all pairs → one traffic-weighted diversity score per mapping.

Additionally, for hotspot sinks, count **distinct legal input ports at the
destination**.

**Static computation, no simulation** — cheap enough to sit inside an NSGA loop.

### Why this is the right metric

Under minimal-only routing, all legal paths to a destination have identical hop
count, so the per-hop term cancels in the DP argmin and congestion is the sole
discriminator. If the legal candidate set has size 1, congestion information is
irrelevant regardless of how well it is measured.

**Corollary:** diversity is the *enabling condition* for congestion-aware routing.
This is why the metric should arguably be defined as mean `|legal candidate set|`
weighted by flow volume — that is exactly the quantity the argmin operates over.

**But diversity is a diagnostic, not the objective.** Arrival-face load is what
was validated against measurement; diversity explains *why* it works. Diversity
elsewhere in the mesh cannot help a sink whose senders all lie to one side,
because under minimal routing the arrival face is fixed by sender position, not
chosen.

### Optimiser

NSGA-II, reusing the machinery from **j6** (Integration 2021) with a **new
objective pair**. Same optimiser lineage, different objectives — a defensible
extension rather than a re-application.

- `f₁` = peak arrival-face load, scored on the **busiest phase only** (equal to
  the max-over-phases and to the phase-blind score on all three current
  workloads, but the phase-aware form is the one that generalises)
- `f₂` = traffic-weighted mean hop count

### Per-workload reduction structure

`R` = reduction depth = fan-in per accumulator; `C` = accumulators per layer.

| workload | layer | matrix | **R (fan-in)** | **C (accs)** | tiles |
|---|---|---|---|---|---|
| ResNet-50 (measured) | conv2 | 2304×256 | 18 | 2 | 36 |
| **VGG-16 blk 3** | conv5 | 1152×256 | 9 | 2 | 18 |
| | conv6 | 2304×256 | **18** | 2 | 36 |
| | conv7 | 2304×256 | **18** | 2 | 36 |
| **Transformer** (128×128) | q/k/v/o | 768×768 | 6 | 6 | 36 |
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
`ff2` is the exception. The transformer block is 432 tiles at 128×128 and does not
fit 6×6×3; **resolved** ([STAGE3-MAPPING-FINDINGS.md](archive/STAGE3-MAPPING-FINDINGS.md),
workloads section) by absorbing the size gap into crossbar **size**, not
crossbars-per-tile — the transformer runs at **256×256, where one encoder block is
108 tiles and fills 6×6×3 exactly** (8 crossbars/tile kept). The R/C values above
are the 128×128 derivation; at 256×256 they halve, so `ff2` is a genuine
**R = 12 → C = 3** reduction. ResNet-50 and VGG-16 stay at 128×128 → 92 and 90 tiles.

Note the network reduction depth is `ceil(R_xb / r) − 1`, not `ceil(R_xb / r)` —
the accumulator is hosted *on* the `r = 0` tile, so one level of the reduction
never crosses the network.

### Alternative: remove the funnel instead of relocating it

Flat `R → 1` reduction becomes a tree, e.g. 18 → 6 → 2 → 1, dropping max fan-in
from 18 to 3. The hotspot stops existing rather than moving. Costs ~44% more
bytes (intermediate sums also travel) and adds sequential stages needing their own
phase sub-windows. Converter-side only, in `reduce_within()` — the simulator does
not change. This is what real accelerators do (ISAAC/Krishnan H-tree between CEs,
[RELATED_WORK.md](RELATED_WORK.md) §1) and it is the right fix for VGG's six
sinks, where placement alone will run out of interior nodes.

### Caveats

- The ResNet result is measured at `ls = 0.026`, **past that mesh's knee** (delay
  rises 4.9× from 0.020). Locate each workload's own knee before quoting a
  DP-vs-BL percentage — see the FINDINGS.md warning about saturation artefacts.
- `oe_arrival_faces.py` ports `routingOddEven3D` and reuses the OEB port in
  `oeb_path_diversity.py`. Validated against one DPTRACE measurement (8%), not
  against a full hop trace. Cross-check before a paper number.

---

## 5. The experiment this formulation exists to support

**Hypothesis:** congestion-awareness benefit grows monotonically with path
diversity.

- Independent variable: mapping (ordered by diversity score)
- Dependent variable: the **occupancy-cost minus no-cost** delay gap

Three mapping points:

1. Original **edge** placement — retained as a deliberate control; the contrast
   *is* the result
2. Minimal **interior** tweak — current
3. **NSGA** multi-objective mapping

Each run with occupancy cost and with no cost, **no-skip in both cases**.

A widening gap across the three points establishes diversity as the enabling
condition, and gives the mapping optimiser a **performance** justification rather
than only an area one. That is the spine of Paper 1.

A single anecdote (edge vs interior) is not a design-space claim — the packing
sweep must run alongside the placement work.

---

## 6. Open items

- [ ] Compute the three bandwidth crossing points (Task 1 in the work queue)
- [ ] Decide whether diversity is scored as legal-minimal-path count or as mean
      legal-candidate-set size
- [ ] Fix the crossbar-grouping rule within a tile (currently held constant)
- [ ] Confirm tile counts fit 108 nodes at the chosen `c` for all three workloads
- [ ] Check `MAX_STATIC_DIM` and `DPSIZE` headroom before any topology change
