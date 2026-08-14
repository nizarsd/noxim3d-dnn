# Noxim3D — Stage 2: DNN Traffic Characterization & Representation Decision

Design/decision doc for Stage 2. **No code yet** — this fixes the modeling choices
before the converter is written. Companion to [FINDINGS.md](FINDINGS.md) (Stage 1
DP-vs-BL results) and [PERFORMANCE.md](PERFORMANCE.md).

**Bottom line up front:** represent DNN traffic as **DNN-derived statistical table
rows with phase windows** (option **a**, extended to use `t_on/t_off/t_period`),
*not* a new packet-replay mode (option b). Target a **Transformer encoder block**
as the primary characterization subject, with a small CNN as a contrast/sanity case.
Rationale below.

---

## 1. Scope

"Traffic characterization" = turn a DNN's inference (or training-step) communication
into something Noxim can inject, and decide *how faithfully* to encode it. Three
sub-problems, only the third of which is decided here:

1. **Profile** — per-layer tensor volumes + the layer→layer dependency graph
   (PyTorch forward/backward hooks; deterministic, exact bytes per edge).
2. **Map** — assign layers/tiles to X×Y×Z mesh node IDs. The load-bearing modeling
   choice; deferred to the converter design, but constrained by `DPSIZE = 260` nodes.
3. **Represent** — encode the mapped traffic in a form the simulator consumes.
   **This doc decides #3** and recommends the subject model for #1.

---

## 2. The constraint envelope: what Noxim actually consumes

From the injection path ([`TProcessingElement::canShot`](TProcessingElement.cpp:134)
→ [`TGlobalTrafficTable::getCumulativePirPor`](TGlobalTrafficTable.cpp:101)):

- **Injection is statistical, memoryless.** Each node, each cycle, draws
  `rand()/RAND_MAX < threshold`. `threshold` is the *cumulative PIR* over all table
  rows for which the node is the source and the current cycle is inside the flow's
  active window. A hit picks the destination by the cumulative-probability ladder.
  Inter-arrival is geometric → Poisson-like. **There is no notion of "send this exact
  tensor now" — only "inject toward dst at average rate pir".**
- **A table row is already phase-capable.** Row format
  `src dst pir por t_on t_off t_period`; the gate is
  `r = ccycle % t_period; on iff t_on < r < t_off`
  ([TGlobalTrafficTable.cpp:115](TGlobalTrafficTable.cpp:115)). So a flow can be
  windowed and periodic. **The existing `traffics/*.txt` don't use this** — they set
  `t_on=0, t_off=10000, t_period=10001` (always-on). Phase structure is available and
  currently unexploited. (The [CLAUDE.md](CLAUDE.md) "whole-run only" caveat applies
  to `TRAFFIC_RANDOM`, not to the table.)
- **Packet size is decoupled from the flow.** `packet.make(..., getRandomSize())` —
  size is a uniform draw between `min/max_packet_size`, *not* derived from the tensor
  being modeled. Tensor volume must therefore be encoded as **rate**, not as size,
  unless the converter also emits/controls size.
- **Open-loop.** Injection never reacts to congestion (only to the static `t_*`
  windows and PE throttling). No node ever *waits for data to arrive* before sending.

So the expressive vocabulary is: **{per-(src,dst) average rate} × {piecewise-constant
periodic on/off windows} × {random packet size}, injected as independent Bernoulli
trials.**

---

## 3. Characterization: what DNN traffic looks like

**Spatial (who talks to whom).** Entirely determined by the layer→node mapping. Two
regimes:
- *One layer per node* → a near-linear dependency chain (node i → i+1). Sparse,
  almost no path contention. Uninteresting for a congestion study.
- *Tiled / model-parallel* (a layer spread over many nodes) → the inter-layer
  transfer becomes a structured **many-to-many** exchange (scatter/reduce of a matmul).
  This is where NoC congestion, hotspots, and path diversity actually appear — i.e.
  exactly the regime in which Stage 1 found DP's advantage (diameter- and
  parity-governed, [FINDINGS.md](FINDINGS.md)).
  - **CNN**: activation halos + channel-reduction → mostly structured/neighbor +
    reduction traffic. Congestion only shows up under tiling.
  - **Transformer block**: QKV projections, the attention matrix (all-to-all across
    the sequence/head tiling), and the output projection give genuinely dense
    many-to-many exchange — the richest congestion stimulus of the common models.

**Temporal (when).** DNN communication is **strongly phased and bursty**:
- A tiled layer computes, then transmits its whole output in a **burst**, then a
  dependency barrier, then the next layer. Bursts are *deterministic and correlated*
  (a tensor moves as a contiguous block), not memoryless.
- Across a batch/pipeline, several layers can be active at once (pipeline parallelism)
  — softening the strict barrier into overlapping phase windows.
- Net: highly **non-stationary**, with sharp on/off structure at layer granularity.

---

## 4. Expressiveness gap — table vs DNN

| DNN traffic property | Statistical table (a) | Faithful for our question? |
|---|---|---|
| src×dst volume matrix (spatial hotspots) | ✅ one row per non-zero edge, `pir ∝ volume` | **Yes** — the spatial congestion structure is preserved exactly |
| Load level / where the knee sits | ✅ scale all `pir` by a global factor → sweepable like the Stage-1 PIR sweeps | **Yes**, and *better* — keeps the reproducible sweep methodology |
| Phase / layer sequencing | ⚠️ approximable via `t_on/t_off/t_period` windows (coarse, piecewise-constant) | **Mostly** — captures "flow X hot during phase P", not exact edges |
| Burst *shape* (contiguous block vs elevated-probability window) | ❌ Bernoulli smears a burst into a Poisson stream at elevated rate | **Lossy** — but see §5: this loss is largely irrelevant to a congestion metric |
| Causal dependency (L+1 waits for L) | ❌ flows fire independently on a static clock | **Lossy for both a and b** — see §5 |
| Exact packet ordering / per-packet timing | ❌ | Not needed for aggregate delay/throughput |
| Tensor→packet size | ⚠️ random size unless converter controls it | Fixable in the converter (encode volume as rate; optionally fix size) |

---

## 5. The decisive argument: replay fidelity is illusory under congestion

Option (b) — a packet-replay `TRAFFIC_*` mode reading pre-recorded
`(node, t, dst, size)` events — *looks* more faithful, but the fidelity it adds is
mostly **not usable for this study**:

- The recorded timestamps come from *one particular execution* on *some* hardware.
  Replaying them **open-loop** fires events at those fixed times regardless of the
  simulated network's congestion. Under load, the simulated NoC's real timeline
  diverges from the recorded one, so the "faithful" timestamps are already wrong — you
  get a deterministic-but-arbitrary schedule, not the true reactive DNN behavior.
- True fidelity would require **dependency-gated replay** (node emits L+1's tensor
  only after L's data *arrives in simulation*) — i.e. a closed-loop execution model.
  That is a much larger change (event dependency graph, per-node barriers, credit of
  arrivals back to the traffic generator) and a different research contribution than
  "DP vs BL selection." Neither (a) nor naive (b) captures it.
- Replay would also **break the Stage-1 timing discipline.** The DP-aware
  `WARMUP/SIM/CINTERVAL` are derived from mesh geometry as a *steady-state* measurement
  window ([FINDINGS.md](FINDINGS.md) §method). A finite trace has no steady state and
  no natural warmup; every result would need a new, trace-specific justification, and
  cross-mesh comparison (the whole Stage-1 axis) gets muddier.

Since the research metric is **aggregate delay/throughput of DP vs BL near the
congestion knee**, what must be faithful is the **spatial congestion structure and the
load level** — both of which the table reproduces exactly — plus *coarse* phase
structure, which the windows approximate. Burst micro-shape and exact timing wash out
in the aggregate. So (b) pays real engineering + methodological cost for fidelity the
metric can't see.

---

## 6. Options & cost

| | (a) DNN-derived statistical table + windows | (b) packet-replay mode |
|---|---|---|
| Simulator change | **none** (converter is external Python) | new `TRAFFIC_*`, event reader, size handling, timing redesign |
| Reproducible load sweep | ✅ scale `pir` (reuses Stage-1 harness) | ✗ trace is a fixed operating point |
| Fits DP-aware timing | ✅ steady-state, as-is | ✗ needs per-trace warmup story |
| Spatial hotspots | ✅ exact | ✅ exact |
| Phase structure | ⚠️ coarse (windows) | ✅ fine (but open-loop, see §5) |
| Causal dependency | ✗ | ✗ (unless closed-loop — big lift) |
| Risk to Stage-1 comparability | low | high |

---

## 7. Recommendation

**Adopt option (a): a DNN-derived statistical traffic table that uses the
`t_on/t_off/t_period` windows.** Concretely, the (future) converter should:

1. Profile the model → per-edge tensor bytes + a coarse phase index per edge.
2. Map layers/tiles → node IDs (≤ 260 nodes).
3. Emit one row per non-zero `(src,dst)` edge with `pir ∝ bytes / phase_duration`,
   and `t_on/t_off/t_period` set from the edge's active phase window.
4. Expose a **global load scale** so the DP-vs-BL knee can be swept exactly as in
   Stage 1 — the DNN sets the *shape* (spatial pattern + phases), the scale sets the
   *level*.
5. Document it explicitly as a **piecewise-constant, memoryless approximation** of the
   DNN trace (this doc is that disclosure).

Keep option (b) as **future work**, and note that its only scientifically meaningful
form is *dependency-gated closed-loop replay* with an end-to-end **makespan/latency**
metric — a distinct study from the current selection-policy comparison.

**Recommended subject model: a Transformer encoder block** (small BERT/ViT block) as
primary — its attention gives the dense many-to-many exchange that produces the
congestion depth and path diversity the Stage-1 mechanism (diameter × parity) is about,
so it's the model most likely to *exercise* the DP-vs-BL difference. Add a **small CNN**
(a few conv layers, tiled) as a contrast case — sparser, more structured traffic — to
show whether the parity/diameter story generalizes across traffic shapes. Skip full
networks initially; a single representative block already produces a clean, mappable
src×dst matrix and keeps the node count under `DPSIZE`.

---

## 8. Choosing the routing algorithm for DNN traffic — read before deciding ⚠

A routing-variant side study ([FINDINGS.md](FINDINGS.md) → "Routing-variant study")
found that OEB **turn exclusivity trades off directly against DP's benefit**, and this
governs which routing to run under ResNet50 / VGG16 / the transformer (BERT-base) traffic:

- Lowest-coupling routing (**modified2**, both branches exclusive) has the **best absolute
  latency/throughput** but the **worst DP-vs-BL gap** — it strips path diversity, so DP goes
  *negative*. The fastest routing is the **worst substrate for the DP study**.
- Higher path diversity (baseline, or more-adaptive routings) gives DP more to exploit but
  lower saturation throughput.

**So decide the target metric FIRST:** absolute latency/throughput (favours modified2) vs the
DP-vs-BL advantage that is the Stage-1 story (favours diversity). Do **not** assume the fastest
routing is the right one. Also: modified2's funnel-then-shaft restriction may hurt **bursty /
phased** DNN traffic (the very structure Stage 2 introduces) and Z-heavy or hotspot-concentrating
patterns. Only measured on transpose1 4×4×3 so far — **sweep each DNN pattern × mesh to its own
knee**, reporting absolute delay *and* DP-vs-BL, before committing.

## 9. Resolved decisions (Aug 2026 session)

### 9.1 Packet size — CLOSED, no simulator change

`-size N N` (e.g. `-size 16 16`) yields an exactly fixed packet size: `getRandomSize()`
→ `randInt(min,max)` returns `min` when `min == max` (verified empirically, 1M draws),
and it passes both `CmdLineParser` validators. Size is **global per run**, not per-row,
so per-flow volume differences are encoded in **`pir` (packet count)**, not size. Lost:
message granularity only (a 64-flit message becomes four 16-flit packets), not volume.
Hardware-realistic — real NoCs use fixed flit width and fixed/near-fixed packet formats;
variable-size *messages* are segmented into fixed-size packets at the NI. Precedent:
Krishnan et al. (ACM JETC 2021) use non-uniform per-pair injection rates with this model.

### 9.2 Mapping policy — DECIDED

**Partitioning: size-driven IMC crossbar model.** Tiles per weight matrix =
`ceil(rows/xb) * ceil(cols/xb)` for an `xb × xb` crossbar; a conv layer's weight matrix
is `(k·k·Cin) × Cout`. *Not* one-layer-per-node — that yields a sparse linear chain with
no path contention (§3), so DP has nothing to exploit and the Stage-1 mechanism never
activates. Citeable: Krishnan et al. (ACM JETC 2021), SIAM (ACM TECS 2021).
**Stated assumption:** 1 crossbar per node. Real IMC designs often pack several
crossbars per tile; 1:1 is the conservative end and is a modelling knob.

**Placement: blocked/clustered in 3D.** Allocate each layer a compact 3D sub-volume
(box) via `coord2Id` (`id = x + y·DIMX + z·DIMX·DIMY`), advancing the box origin per
layer. *Not* sequential IDs: `id+1` walks along X and only reaches the Z neighbour after
`DIMX·DIMY` steps, so intra-layer many-to-many exchange would barely use TSVs and the 3D
findings (Z-series, vertical turn exclusivity) would stay dormant. A 3D box keeps a
layer's tiles within 1–2 hops in all three dimensions.

**Congestion-aware placement deliberately excluded** — that is j6 territory and would
confound "does DNN traffic behave differently" with "does smart mapping help". Blocked
placement is a *deliberately unoptimised* baseline and must be stated as such.

### 9.3 Tile counts (1 crossbar/node) — full networks are infeasible

| model | 128×128 xb | 256×256 xb |
|---|---|---|
| VGG-16 full | 8454 | 2121 |
| ResNet-50 full | 1406 | 379 |
| Transformer, 12 blocks | 5184 | 1296 |
| ResNet-50 **one bottleneck block** | **92** | 23 |
| Transformer **one encoder block** | 432 | **108** |

> **Correction (Aug 2026):** this row previously read **60 / 15**, which counted only
> conv1–conv3 and **omitted the projection shortcut**. The stage-3 bottleneck is a
> *projection* block (512→1024, dimensions change), so its 1×1 shortcut is a real
> weighted layer and must occupy crossbars — an identity (weight-free) shortcut only
> exists in blocks whose dimensions already match. Corrected to **92 / 23**. This
> invalidated the old "→ 5×5×3, spare 15" fit; see the revised decided start below.
> The transformer figures (432 / 108) were re-derived and are correct.
> `VGG-16 full` and `ResNet-50 full` have **not** been re-audited for the same
> projection-shortcut omission — ResNet-50 full has 4 more projection blocks, so 1406
> is likely an undercount. Immaterial to the decision (both are far over `DPSIZE`).

**ResNet-50 stage-3 bottleneck, per layer @128×128** (weight matrix = `(k·k·Cin) × Cout`;
`tiles = ceil(rows/128) · ceil(cols/128)`):

| layer | k | Cin→Cout | weight matrix | reduction depth | fan-out width | tiles |
|---|---|---|---|---|---|---|
| conv1 | 1 | 512→256 | 512×256 | 4 | 2 | 8 |
| conv2 | 3 | 256→256 | 2304×256 | **18** | 2 | 36 |
| conv3 | 1 | 256→1024 | 256×1024 | 2 | **8** | 16 |
| shortcut (projection) | 1 | 512→1024 | 512×1024 | 4 | **8** | 32 |
| | | | | | | **92** |

The two splits are independent axes and every tile participates in both: `ceil(rows/xb)`
is the **reduction depth** (each row-group holds a slice of the input dimension, so it
produces only a *partial* sum that must be added across the column) and `ceil(cols/xb)`
is the **fan-out width** (each column-group computes different output channels from the
*same* input, so the input must be replicated to all of them). This — not the layer
dependency graph — is what generates the intra-layer traffic.

All full networks exceed `DPSIZE = 260` — confirms §7's "use a representative block".
Convenient fits: transformer encoder block @256×256 = 108 → **6×6×3** exactly;
ResNet bottleneck block @128×128 = 92 → **6×6×3** (108 nodes, 16 spare absorbed by
giving layers extra tiles).

**Decided start:** ResNet-50 single bottleneck block, 128×128 crossbar, on **6×6×3**
(a mesh already swept in Stage 1, so DNN-vs-synthetic comparison stays direct). Converter
to be **hardcoded for this block first** (~50 lines, no PyTorch hooks) to get a runnable
table fastest, then generalised. Order after: transformer encoder block (§7's recommended
primary — richest congestion stimulus), then a VGG block as cheap contrast.

Bonus of the correction: ResNet-bottleneck @128×128 (92) and transformer-encoder @256×256
(108) now both land on **6×6×3**, so the two subjects are directly comparable on one mesh
with no geometry confound. A VGG-16 block 3 (three 3×3 convs; 18+36+36 = **90** tiles
@128×128) also fits the same mesh — sparser, width-2-everywhere, pure deep reduction.

### 9.3a Weight precision and crossbars-per-tile — reinterpretation, no rework

Two refinements to the formula above, verified against Krishnan et al. (ACM JETC 2022)
Eq. 2 (see [RELATED_WORK.md](RELATED_WORK.md)). Neither invalidates the generated tables.

**(i) The column term carries a weight-precision factor:**

```
crossbars = ceil((k·k·Cin) / PE_x) · ceil((Cout · N_bits) / PE_y)
```

8-bit weights on 1-bit cells need 8 physical columns per logical column. The counts in
§9.3 implicitly assume `N_bits = 1`. With `N_bits = 8`, the stage-3 bottleneck @128×128 is
**736 crossbars**, not 92 (conv1 64, conv2 288, conv3 128, shortcut 256).

**(ii) A tile holds many crossbars, not one.** No real IMC design puts an NoC router on a
single crossbar: router area/energy is comparable to the macro it serves, and
intra-partition partial-sum traffic is dense and short-range — bus/H-tree work, not NoC.
Krishnan explicitly justifies the hierarchy ("for low data volume, the NoC-based
interconnect provides marginal performance gain while increasing energy consumption").
Published values: **Krishnan 16 crossbars/tile** (256×256; 4 CEs × 4 PEs), **ISAAC 96
crossbars/tile** (128×128; 12 IMAs × 8 crossbars, shared ADCs).

**Why no rework is needed:** `736 / 92 = 8` exactly. The existing 92-tile partition is
identical to **8-bit weights at 8 crossbars per tile**. The generated traffic tables,
placement and flows are unchanged — only the physical labelling changes, from
"1-bit weights, 1 crossbar/tile" (unrealistic) to "8-bit weights, 8 crossbars/tile"
(a defensible point between Krishnan's 16 and a 1:1 flat array). State the assumption in
these terms in write-up.

**Design tension to record:** more crossbars per router → fewer tiles → smaller mesh →
*less* NoC traffic to study. 8/tile keeps a usable mesh; 16/tile (Krishnan) would halve it.

**Consequence for full networks — the "infeasible" claim is too strong.** At Krishnan's
own parameters (256×256, `N_bits = 8`, 16 crossbars/tile), whole ResNet-50 is **3190
crossbars → 200 tiles**, which fits `DPSIZE = 260` (7×7×4 = 196, 8×8×3 = 192). Whole
VGG-16 at 256×256, 96/tile is **177 tiles**. So a whole network costs little more mesh
than one block (200 vs 92) while providing many more phases and real long-range skip
connections — relevant if the single block proves too thin temporally (only 3 phases,
conv2 dominant). Not a change of plan; recorded as the natural next configuration.

### 9.4 Multicast / broadcast — source replication, no simulator change

Multicast and broadcast are modelled as **source replication, entirely within the traffic
table**: one unicast row per destination, all sharing the same `src` and the same
`t_on/t_off/t_period` window. **Requires no Noxim modification** — it is pure converter-side
table construction.

Defensible because **Garnet (gem5) does exactly this**: it has no router-level multicast
and breaks multicast messages into multiple unicasts at the network interface (per gem5
docs). The field-standard detailed NoC model has the same limitation and the same
workaround, so this is precedent, not a hack. noxim3d is unicast-only by the same measure
(`TFlit` carries a single `dst_id`; `route()` returns one output port; DP cost-to-go is
per single dst).

**Two limitations to state explicitly in write-up:**
1. Source replication loads the network *more* than true tree-based multicast would —
   which is precisely the inefficiency j5/c5 (surface-wave multicast) measured.
2. `getCumulativePirPor` picks **one dst per src per cycle** by weighted draw, so
   guaranteed simultaneous fan-out is impossible. Volumes average out correctly over a
   window — acceptable for CNN skip-connection fan-out, not for a hard synchronised burst.

## 10. Remaining open items

- **Converter (Stage 2 code)** implementing §7.1–7.5 for the ResNet bottleneck block
  (§9.3), then generalised.
- **Validation** — inject a known toy DNN, confirm the resulting table's steady-state
  hotspot map matches the profiled volume matrix, then run one DP-vs-BL sweep to see
  whether the knee/parity behavior from synthetic traffic ([FINDINGS.md](FINDINGS.md))
  persists under DNN-shaped traffic.
- **Routing choice for DNN traffic** (§8) — still open. Target metric provisionally
  "absolute latency/throughput", but deferred until Stage 2 results exist. Must sweep each
  DNN pattern × mesh to its **own** knee and report absolute delay **and** DP-vs-BL before
  committing.
