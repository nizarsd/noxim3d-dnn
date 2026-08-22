# Crossbar Size, ADCs, and Packing Density — Constraints & Trade-offs

Reference for the tile-architecture decisions underlying Stage A (packing) of the
two-stage mapping. Companion to `MAPPING-FORMULATION.md`.

Status: analysis settled in discussion. Numbers marked **[ASSUMED]** are design
choices, not derivations — they must be stated explicitly in the paper.

---

## 0. Summary of decisions

| Parameter | Value | Basis |
|---|---|---|
| Crossbar array | **128 × 128 cells**, 1 bit/cell | fixed; not a swept variable |
| Weight precision | 8 bits, bit-sliced across 8 columns | → 16 usable weight columns |
| ADC resolution | **8 bits** | **derived** (see §2.1) |
| ADC organisation | **shared, column-multiplexed** | universal in real silicon (§2.3) |
| Sharing ratio `S` | **[ASSUMED]** 16:1 → 8 ADCs/crossbar | ISAAC-consistent operating point |
| Partial-sum width | **16 bits** | **derived** (see §2.2) |
| Intra-tile reduction | tree, depth log₂(`c`) | ISAAC convention |
| Tile area | **scales with `c`** | stated assumption; see §4 |
| Crossbars/tile `c` | swept {4, 8, 16, 32, 64, 96} arithmetic; {8, 16, 32} simulated | §5 |

---

## 1. Crossbar size — fixed at 128×128, not explored

### Why it is not a sweep axis

1. **It acts on the same axis as packing.** Both larger crossbars and denser
   tiles reduce inter-tile aggregation traffic. Sweeping both makes attribution
   impossible, and packing is the variable the paper is built on.

2. **It is entangled with mesh fit.** Both terms of the crossbar formula have
   `128` in the denominator, so 256×256 cuts crossbar count **~4×**. On a fixed
   6×6×3 mesh you must either let tile count collapse to a quarter (occupancy no
   longer comparable across workloads) or cut `c` by 4 to compensate (which just
   moves the packing variable). Not separable.

3. **It drags partial-sum width along.** 16 bits is matched to 128-row
   accumulation. At 256 rows, full-precision accumulation exceeds it — requiring
   wider payloads or explicit truncation, which changes the units on *both*
   bandwidth curves. Two coupled variables masquerading as one.

4. **It shrinks the phenomenon under study.** 256 rows halve the reduction
   traffic converging on the conv2 hotspot — the same direction as denser
   packing. The arm would spend simulation budget weakening the effect.

5. **Only two credible points exist.** 128 and 256 are the published anchors;
   512 is not defensible for analog IMC (ADC precision, IR drop, sneak paths).
   Two points do not support a design-space claim.

### What to do instead

Include **256×256 as a second curve family in the Task 1 arithmetic** — zero
simulation cost. Report crossing points and MACs-per-conversion for both. This
answers "why 128?" pre-emptively and lists crossbar size as a stated future axis
rather than a silent omission.

### The distinction worth one sentence in the paper

- **Crossbar size** changes how many partial sums *exist* — a 256-row array
  accepts twice the fan-in along `Cin`, so partial sums genuinely halve.
  Accumulation happens **in the analog domain, inside the array**, eliminating an
  ADC conversion per output.
- **Packing density** does not reduce the count at all — it relocates the
  reduction from network to on-tile fabric.

Same direction on the bandwidth curve, different mechanism. Only one is a genuine
efficiency win.

### Justification to state

Fixed at 128×128 because it is matched to the 16-bit partial-sum width, is the
more conservative analog-IMC assumption, and preserves the inter-tile aggregation
the study depends on.

---

## 2. ADCs

### 2.1 Resolution is derived, not chosen

The array computes in analog: input voltages on rows, cell conductances multiply,
Kirchhoff's current law sums products down each column. The result is an **analog
current** — the ADC converts it into a number.

With 1-bit cells and bit-serial (binary) inputs, 128 rows produce a sum in
**0–128**, requiring log₂(128) + 1 = **8 bits** to represent losslessly.

**Consequence: >8-bit ADCs are waste on a 128-row array.** Beyond 8 bits the
converter resolves analog noise, not signal, while ADC area and energy scale
roughly 2× per additional bit. Practical designs often go *below* 8 deliberately,
accepting quantisation error to save area — so 8 is the lossless **upper bound**,
not a floor.

> Qualifier: this holds for binary inputs. Multi-bit input drive (e.g. 2-bit
> activations as multiple voltage levels) widens the sum range and would need
> more bits. Not assumed here.

### 2.2 Partial-sum width is also derived

Each conversion yields 8 bits for **one weight bit-slice**. The 8 bit-slices are
then combined by digital shift-and-add across weight bit positions → **~16 bits**.

So the 16-bit partial sum is not a borrowed convention — it falls out of 8-bit
conversions on a 128-row array with 8-bit weights. It should be presented as
derived.

### 2.3 Sharing is universal in real silicon

ADCs are **not** placed per column. An ADC is orders of magnitude larger than the
column pitch of a memristive array — 128 of them physically do not fit. Column
multiplexing is a layout necessity before it is an efficiency decision.

Fabricated RRAM/ReRAM macros (ISSCC/VLSI-class prototypes) typically share one
ADC across **8–32 columns**, or use a single SAR ADC per subarray behind a column
mux. Alternative readout schemes exist (1-bit sense amplifiers, time-domain,
charge-domain), but the sharing principle holds regardless of converter type.

**ISAAC assumes shared ADCs with column multiplexing**, and its 8-bit ADC is
explicitly the area/energy bottleneck the whole architecture is designed around —
its eDRAM buffering and pipelining exist to keep those converters busy.

### 2.4 Resolution and sharing ratio are independent

A frequent conflation. They are separate knobs:

- **Resolution** (8 bits) ← set by accumulation range.
- **Sharing ratio `S`** (columns per ADC) ← an area/throughput design choice.

ADCs per 128-column crossbar = `128 / S`:

| `S` | ADCs per crossbar |
|---|---|
| 8 | 16 |
| 16 | 8 |
| 32 | 4 |
| 128 | 1 |

Nothing in the bit width determines the count.

### 2.5 ADC amortisation

ADCs dominate area (~50–60% of tile) and a comparable share of power, while the
analog array itself is nearly free. Each conversion produces one value, so the
design goal is **maximising useful MACs per conversion**.

- **Amortising over rows:** a 128-row array gives 128 MACs per conversion; 256
  rows gives 256, halving ADC cost per MAC. Accumulation in analog costs no
  conversion; accumulation *across* crossbars costs one conversion each plus a
  digital add.
- **Amortising by sharing:** fewer converters multiplexed across more columns
  reduces area but serialises conversion.

**Why this matters to the argument:** it gives the packing lower bound an
independent architectural justification. Splitting a layer across many crossbars
is what forces extra conversions — so the inter-tile aggregation traffic being
modelled is a **real cost signal**, not an artifact of a deliberately weak
configuration. This pre-empts the obvious reviewer objection ("you chose a bad
packing to manufacture congestion").

---

## 3. Sharing overhead — the throughput cost

Conversion cycles per crossbar pass scale **linearly with `S`**:

```
conversions per pass = S × N_bits = S × 8
```

| `S` | ADCs/crossbar | Conversions per pass (8 bit-slices) |
|---|---|---|
| 8 | 16 | 64 |
| 16 | 8 | 128 |
| 32 | 4 | 256 |

So 32:1 takes 4× longer than 8:1 for 4× less ADC area. A direct area↔throughput
trade.

### Two consequences

1. **Conversion time is the tile's real clock.** It dominates array settling, so
   `S` effectively sets layer compute time.

2. **This feeds `t_period` in the traffic table.** If `t_period` is currently
   derived purely from MAC counts, it is *implicitly* assuming a fixed sharing
   ratio. → **Open item:** confirm whether the cycles-per-MAC constant should be
   tied to `S`.

### Interaction with packing

Under shared ADCs, doubling `c` roughly doubles the wait for conversion if
converters are shared *across* crossbars within a tile. Whether they are is a
further design choice:

- **Per-crossbar ADC banks:** area scales linearly with `c`; per-crossbar
  throughput unaffected.
- **Tile-level ADC sharing:** area scales sub-linearly; conversions serialise
  across crossbars.

**[ASSUMED]** per-crossbar banks (simpler, and keeps `c` a clean area variable).
State explicitly — without it, `c` has no area interpretation.

---

## 4. Thermal impact — weakened by area scaling, but not zero

### The argument, and why it partly collapses

If the mesh **fixed the die floorplan** — 108 tiles at a given footprint — then
packing more crossbars per tile would raise power per unit area: same total MACs,
concentrated into fewer active tiles. Total energy falls, power *density* rises.
3D sharpens this because the middle Z layer has the worst heat path (j1/j3
territory directly).

**But tile area is assumed to scale with `c`.** Under that assumption, same MACs
over proportionally more area ⇒ W/mm² is roughly invariant. The die grows; the
density does not. **The primary thermal argument does not hold.**

### The residual effect runs the wrong way

If ADC area scales **sub-linearly** with `c` (tile-level sharing), then denser
tiles are proportionally more array and less periphery — arguably *higher* power
density, not lower. This must be checked before leaning on thermal at all.

### What survives

- Thermal remains a legitimate **secondary** remark, connecting Paper 1 to the
  strongest publication lineage (j1, j3, j6, j7) without requiring a thermal
  simulator.
- It must **not** be the primary defence of a low `c`: thermal is not modelled,
  so justifying the operating point on an unmodelled axis invites "then show me
  the thermal result." It also blurs into Idea 3, a separate proposal.

### The cheap version that keeps it usable

Same trick as the bandwidth curves — report **demand, not service**. Add a
**power-density curve** to the Task 1 figure: ADC count × conversion energy +
array energy, over assumed tile area. No HotSpot, no thermal simulation.

Present it as an **outcome** of the area-scaling assumption, not as a premise.

### The reframing this unlocks (if it survives the scaling check)

Denser packing looks free in a pure-traffic model. It is not: it buys network
quiet at the cost of thermal headroom. Sparse packing then becomes the
thermally-motivated choice, and its price is network congestion — which is
exactly what the mapping and routing work addresses.

That inverts the reviewer objection from *"you chose a weak packing to manufacture
congestion"* to *"sparse packing is thermally necessary, and here is how to make
it affordable."*

---

## 5. Intra-tile bandwidth and the packing bounds

### The trade-off

Packing decides **where** partial-sum reduction happens, not whether it happens:

- **Intra-tile demand rises** with `c` — more partial sums reduced on the on-tile
  bus / H-tree.
- **Inter-tile demand falls** with `c` — fewer partial sums cross the network.

Both computed as (partial sums on that side) × 16 bits. **The crossing point**
marks where the two burdens balance: below it the network is the bottleneck,
above it the tile fabric is. It defines the centre of the design space.

**Sequencing:** compute the curves *before* choosing which packings to simulate.
If they cross at 12, {4, 8, 16} brackets it well; if at 40, the sweep range is
wrong. Cheap arithmetic that sets the simulation budget.

**Expect three different crossing points**, one per workload — layer shape drives
the split (VGG's FC layers have far deeper per-output fan-in than ResNet
bottlenecks; ViT attention differs again). Workload-dependent optimal packing is
itself a reportable finding.

### Lower bound on `c` — a research constraint

Packing an aggregation tree entirely inside one tile **engineers away the
phenomenon under study**. The conv2 hotspot exists because 18 flows converge on
one tile:

| `c` | Converging flows at hotspot | Status |
|---|---|---|
| 8 | 18 | current |
| 16 | ~9 | still a hotspot, still network traffic |
| 32 | ~4–5 | largely internalised |

### Additional motivations for low `c` — strongest first

1. **Mapping fragmentation (strongest; arithmetic, workload-dependent).** Tiles
   are allocated in whole units. A layer needing 9 crossbars fills two 8-crossbar
   tiles at 56%, one 16 at 56%, one 32 at 28%. ResNet-50 is mostly small 1×1
   bottleneck convs, so fragmentation bites hard as `c` rises; VGG's FC layers
   fill any tile; ViT differs again. **Three fragmentation curves**, same figure
   family, zero simulation cost — and it argues for small tiles on *efficiency*
   grounds rather than research convenience. **Recommended as the lead
   justification.**

2. **Phase utilisation.** Layers fire sequentially; a tile sized for the largest
   layer idles through small ones. The fraction of array active per phase falls
   with `c`. Computable from the same layer shapes.

3. **Intra-tile aggregation latency.** Tree depth log₂(`c`) — 3 levels at `c`=8,
   6 at `c`=64 — plus longer wires and a wider on-tile bus. Not modelled, but a
   stated reason not to pack arbitrarily.

4. **ADC serialisation.** Only applies under tile-level ADC sharing (see §3).

5. **Defect granularity.** One bad crossbar retires a whole tile; coarser tiles
   mean coarser sparing and worse effective yield. Adjacent to c7, but weak in a
   simulation paper.

### Upper bound — where `c` stops being realistic

Against the published anchors, **8 is the least anchored point, not 64**:

| `c` | Standing |
|---|---|
| 4, 8 | Below both anchors. Also poor ADC amortisation — mostly periphery, arguably inefficient designs, not merely conservative. |
| 16 | Matches Krishnan's crossbars-per-tile (at 256×256, so not directly comparable). |
| 32 | Interpolates. No direct anchor. |
| 64 | ≈ Krishnan in **cell** terms (4 CEs × 4 PEs × 256² = 64 × 128²). Well supported. |
| 96 | **ISAAC exactly**: 12 IMAs × 8 crossbars, at 128×128 — the matching array size. |

**The reviewer objection this exposes:** *"you observe network congestion at a
packing density below every published design."* The answer must be the sweep
itself — show where the crossing point falls, show the hotspot surviving at 16,
and let 8 be one point on a curve rather than the configuration everything rests
on.

### Recommended split

| `c` | Arithmetic | Simulation |
|---|---|---|
| 4 | ✓ | — |
| 8 | ✓ | ✓ (existing data) |
| 16 | ✓ | ✓ |
| 32 | ✓ | ✓ |
| 64 | ✓ | — |
| 96 | ✓ | — |

Six arithmetic points including **both** published anchors literally; three
simulated. `c` = 64 is excluded from simulation because the hotspot is largely
internalised by 32 — the arithmetic already reports that endpoint, and simulating
a network with no hotspot confirms nothing. `c` = 8 is retained because the data
exists and excluding it would look like dropping an inconvenient point.

**Do not fix the simulated set until the Task 1 curves land** — if crossings fall
at 40 for VGG or 12 for ViT, the bracket is wrong for those workloads.

### Declared modelling limitation

**The simulator models neither intra-tile contention nor ADC serialisation.**
Denser packing therefore looks free in the results when it is not — the
aggregation cost is relocated onto the on-tile bus/H-tree, not removed.

Mitigation: report **demand**, not service. The curves are a requirements
statement, not a performance claim — no second simulator needed. One sentence
covers both omissions.

Note that Krishnan's "no congestion observed" finding is plausibly the same
artifact — a consequence of 16-crossbar tiles internalising the aggregation.

---

## 6. Open items

- [ ] Confirm ISAAC's 96/tile figure against the paper before it anchors the argument
- [ ] Decide sharing ratio `S`: fix at 16:1 or leave "shared, ISAAC-consistent"
- [ ] Decide ADC organisation: per-crossbar banks (assumed) vs tile-level sharing
- [ ] Check whether ADC area scales sub-linearly with `c` — decides whether the
      residual thermal effect runs the wrong way (§4)
- [ ] Confirm whether `t_period` in the traffic table should tie its
      cycles-per-MAC constant to `S` (§3)
- [ ] Compute fragmentation and phase-utilisation curves alongside the bandwidth
      curves — same layer shapes, no extra data required
- [ ] Verify the ~4–5 converging flows at `c`=32 estimate against actual layer shapes
