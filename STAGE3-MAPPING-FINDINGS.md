# Stage 3 — Mapping Hotspot Finding, DP Recovery, and Design-Space Plan

Date: 17 August 2026
Supersedes nothing; extends `STAGE2-DP-CONGESTION-DIAGNOSIS.md`.
Mesh changed from 7×7×3 → **6×6×3** (fits the ResNet-50 tile count being simulated).

---

## 1. What was actually implemented

**Lever 2 only** (from the Stage 2 diagnosis doc), not Lever 1:

- DP clock set to **4× the NoC clock**.
- `CINTERVAL` reduced to match the (now shorter) DP cycle — ~600-ish cycles at
  6×6×3.
- **No decaying/EWMA average implemented yet.** Sampling is still
  accumulate-and-reset.

**Result of Lever 2 alone: no significant change.** DP still lost to, or roughly
tied, bufferlevel.

Separately, before the remapping work below, shorter `CINTERVAL` than the DP cycle
appeared to pay off — **but this was a false positive and has been retracted.**
At `ci` 200/250 with **n=3** DP looked 8.8–8.9% better; at **n=12 the same point
reversed to +15.5%** (DP slower). The three seeds happened to be hard ones for
bufferlevel: BL averaged 184.28 on {2,5,10} against 157.52 over twelve seeds.

**The mechanism it suggested does not exist.** `DPNode.cpp:49` latches congestion
**once per `dp_cycle`** (`if (phase == 0)`) and reuses that single snapshot to build
all `num_dst` destination fields. `CINTERVAL` only sets the averaging window of
whatever value happens to be sitting there at the latch instant — it does **not**
change how often DP reads. Shortening it therefore gives *identical staleness with
more noise*, which is also why `-dpcost none` beats both real cost metrics.

So there is no "recency beats completeness" result. Recency cannot be bought with
`CINTERVAL` at all; it requires changing **where DP reads** (see §4.2).

---

## 2. The real blocker — aggregation hotspot at the mesh edge

Investigation (with Claude Code) found:

- The **conv2 aggregation collapses onto 2 nodes/tiles**, each receiving
  **18 incoming flows**.
- Those two nodes were placed **on the mesh edge** — (4,0,0) and (4,0,1) — so they
  did not expose all six ports: only **4 and 5** usable input directions, two of
  which received nothing at all (y=0 and z=0 mean no senders lie on those sides).
- These two sinks take **15.2% of total in-traffic each = 30.4% combined.**
  (For scale: top 4 receivers 55.4%, top 10 69.5%, all 20 accumulators 88.0%.)

### Why this invalidated the DP-vs-BL comparison

**It is not an ejection-port limit.** Offered load into each sink is 0.480
flits/cycle — **48% of a port** — and no node anywhere exceeds 100%. The bottleneck
is the **input link on one face**: `DPTRACE` measured the busiest arrival link into
node 4 full **73.5% of cycles** (mean queue 12.61/16) while an interior control link
never queued a single flit (0.00 occupancy).

The contention is on the *final hop into the node*, and the problem is that its
distribution is **forced, not chosen**. Node 4 admits 4 arrival faces, but they carry
0.297 vs 0.028 flits/cycle — a 10× imbalance — because it sits at x=4 with four
columns of senders to its west and one to its east, and minimal routing never moves
away from the destination. A selection policy can pick the face; it cannot change
which side the senders are on.

That distinction is load-bearing: **if this were an ejection-port limit, relocating
the node would change nothing.** It is precisely because the limit is on arrival
*distribution* that the fix in §3 works.

This is a **mapping failure, not a DP failure.**

---

## 3. The fix and the result

**Fix:** relocate the aggregator tiles to **interior** mesh positions where all
six ports are usable by the incoming flows.

**Result: DP improves over BL by ~25–28% near the knee.**

| Seeds | BL delay | DP delay | DP vs BL | paired t |
|---|---|---|---|---|
| 12 | 177.03 | 146.25 | −17.4% | −1.11 |
| 22 | 188.39 | 140.02 | −25.7% | −2.73 |
| **30** | **191.93** | **136.35** | **−29.0%** | **−3.51** |

Effect *and* significance grew monotonically with seeds (p ≈ 0.0015 at n=30, 23/30
seeds) — the signature of a real effect, and the opposite of the retracted
`CINTERVAL` result in §1, whose mean collapsed as seeds were added. On the edge
placement DP is +5.0%, t=0.65 — nothing.

**Double dissociation.** The same two-pair swap makes DP **19.7% faster**
(t = −3.05) and bufferlevel **18.7% slower** (t = +2.54). Edge placement pens
unroutable congestion in a corner where it obstructs nobody; interior placement makes
the same congestion routable and in everyone's way. DP exploits it, bufferlevel
cannot. Throughput is invariant throughout (0.01704–0.01714), so the entire effect is
delay.

- Measured at **one load scale, past the knee** — `ls=0.026`, where delay has already
  risen 4.9× from 0.020. FINDINGS.md warns that percentages taken in saturation can
  reflect which policy degrades faster rather than which routes better, so **repeat at
  0.020 before quoting −29%**.
- **Maximum delay moves the same way as the mean** on the interior placement
  (DP 5,723 vs BL 9,709). Two caveats: no significance test was run on the tail, and
  on the *edge* placement DP's tail is **worse** (6,840 vs 6,013) — so the tail
  advantage is specific to interior placement, not a general DP property. Tail latency
  matters for inference deadlines, so report both, with the test.

### Interpretation (the paper-relevant claim)

DP's benefit is **conditional on the mapping granting it degrees of freedom**.
Edge-pinned hotspot sinks remove the path diversity DP exploits on the final
hops; interior placement restores it. Same traffic, same routing, ~28% swing from
placement alone.

This is a **mapping × routing interaction**, and it belongs to contribution axis
one (mapping / packing), not to the routing work.

---

## 4. Immediate next steps

### 4.1 Full load sweep (not one point)

The 25–28% is a single load scale. Sweep the full load-scale range to produce the
DP-benefit curve: locate the peak, and check for a past-knee reversal. 6×6×3 is
**even × even**, so Stage 1 predicts a reversal shortly past the knee — confirm
or refute.

### 4.2 Lever 1 calibration sweep — then LOCK

Lever 1 (decaying average) is **still not implemented**.

**Revised premise (see §1).** Sweeping `CINTERVAL` alone cannot work: DP latches
congestion once per `dp_cycle` regardless of the interval, so all four points in a
`{1, 1/2, 1/4, 1/8} × DP cycle` sweep have the *same* staleness and differ only in
sample noise. The `CINTERVAL` sweep was already run at 100/150/200/250/300/648 on
6×6×3 and found nothing once seeded properly. **Do not re-run it as-is.**

To make recency reachable, one of these has to change first:

1. **Latch per dwell, not per pass** — `phase == 0` → `phase % dp_dwell() == 0` in
   `DPNode.cpp`. One line; gives `num_dst` samples per sweep instead of 1.
2. **EWMA in the router** — `stored = decay·stored + sample` so the single latched
   value carries history instead of being an isolated window.

Then the calibration sweep is worth running, over **decay ∈ {off, 0.7, 0.9} × latch
∈ {per-pass, per-dwell}** — 6 configurations. Pick the best, **document it as a
calibrated parameter, and freeze it**. This is a configuration choice justified once
— *not* a contribution. Gate either change on a Stage 1 `transpose1` regression
before trusting it on DNN traffic (CLAUDE.md working agreement).

**Confound warning:** the optimal setting is probably *not* fully decoupled
from the mapping (it depends on burst duration and hotspot concentration, both of
which the mapping changes). Handle it this way:

1. Calibrate on **one representative mapping**.
2. Freeze `CINTERVAL` and decay.
3. **Spot-check at the two extremes** of the mapping sweep.
4. If the ranking holds → fine, proceed. If it does not → **that interaction is
   itself a reportable finding**.

Do **not** re-tune DP per mapping — results become incomparable and a reviewer
will call it overfitting.

### 4.3 Keep the edge-placed version as a deliberate control

Do not discard the bad mapping. The edge-vs-interior contrast **is** the result.

---

## 5. Turn-model note (correction to record)

The mutual exclusivity between **planar and Z turns** in the modified
odd-even-balanced variant is a **performance choice, not a deadlock requirement**.
Both variants are verified deadlock-free.

**Why it was adopted:** on `transpose` synthetic traffic, allowing free Z turns
caused packets to climb to the destination Z plane early, concentrating traffic
in that plane and saturating it *faster* than plain odd-even.

**Why it needs re-testing:** that justification is **workload-specific**. It was
tuned on transpose, where destinations are spread across the mesh. DNN traffic has
**concentrated hotspot sinks**, so the early-Z-climbing failure mode may simply
not apply. Cheap experiment: run both variants on DNN traffic with interior-placed
aggregators.

Either outcome is reportable — it is a finding about how a routing constraint
interacts with hotspot-concentrated traffic, **not** a turn-model contribution.
The turn model is machinery for deadlock freedom; state which one was used and
why, and move on.

---

## 6. Paper split (decided)

**Paper 1 — mapping / design-space exploration.** Two staged mappings:
DNN → crossbars → tiles, then tiles → 3D NoC. The aggregator result is the
motivating demonstration.

**Paper 2 — routing/selection.** RL agents vs DP; local-vs-global,
temporal-vs-spatial. Deferred. Paper 1 gives it a validated baseline and a
known-good mapping, so it only has to prove one thing.

### Constraints that make Paper 1 a design-space paper rather than a tuning exercise

1. **Preserve DNN traffic characteristics.** Aggregation must remain *network*
   traffic. Packing an aggregation tree inside a single tile flattens the traffic
   and engineers away the phenomenon under study. → **crossbars-per-tile has a
   lower bound set by preserving inter-tile aggregation**, not only by area
   realism.

2. **Mapping is a multi-objective problem:** maximise path diversity to hotspot
   sinks, while bounding the extra hop count that diversity costs. Reuses the j6
   NSGA multi-objective mapping machinery on a **new objective pair** — same
   optimiser lineage, genuinely new objectives.

3. **A single anecdote is not a design-space claim.** The crossbars-per-tile sweep
   must run alongside the placement work so the claim is systematic.

---

## 7. Path-diversity objective — how to compute it

Compute diversity **under the actual turn model**, not on the raw topology. An
interior node with six ports may still have fewer usable paths than its degree
suggests, because odd-even-balanced turn legality branches on coordinate parity.

For each src→dst pair in the traffic table:

1. Enumerate the **legal minimal paths** permitted by the turn model; count them.
2. Weight each pair's count by its **flow volume** from the traffic table, so
   heavy flows dominate.
3. Sum → one traffic-weighted diversity number per mapping.

Additionally, for hotspot sinks specifically: count the **distinct legal input
ports at the destination**, and the *load* on each. That is precisely what the
aggregator finding exposed.

This is a **static computation — no simulation needed** — so it is cheap enough to
sit inside an NSGA evaluation loop.

**Both already exist — do not rebuild them** (added 17 Aug 2026, see
[MAPPING.md](MAPPING.md)):

- [`oeb_path_diversity.py`](oeb_path_diversity.py) — traffic-weighted count of legal
  minimal paths per src→dst under OEB `modified2`; also reports mean/weighted hops.
- [`oe_arrival_faces.py`](oe_arrival_faces.py) — enumerates admissible minimal paths
  and records the **final hop**, giving arrival-face load per sink under OE or OEB.
  Prints the objective directly: *peak arrival-face load over all (node, face) pairs*.

**Score on routing-admitted faces, never on geometry.** The cheap geometric proxy
("one face per displaced dimension") predicted 0.118 flits/cycle on node 4's hot face
against **0.274 measured** by DPTRACE; path enumeration gives 0.297, within 8%. The
difference is not academic: the geometric metric ranked the conv1 relocation
(nodes 64/28 → 52/45) as an improvement, while path enumeration predicted no gain
because OE admits only 4 of node 52's 6 geometric faces. The measured outcome was
**+2.6%, t = 0.45 — nothing**, matching the path-enumeration prediction.

---

## 8. Workloads and NoC configuration (decided)

**Three workloads, not one.** ResNet-50 alone is too thin: the aggregator finding
is specifically about *convolutional aggregation topology*, and a reviewer will
ask whether it generalises.

| Workload | Why |
|---|---|
| ResNet-50 | primary; conv aggregation + skip/projection structure |
| VGG-16 | cheap contrast; huge FC layers → different hotspot structure |
| ViT-Base (transformer) | attention is dense many-to-many → strongest congestion stimulus |

**The mesh stays FIXED at 6×6×3 across all three.** The NoC is the object of
study, so it cannot also be a variable.

**Absorb the size differences with crossbar SIZE, not crossbars-per-tile.** Using
density conflicts with §6.1, which sets a *lower* bound on crossbars-per-tile to keep
aggregation on the network. Single-block tile counts (tiles = R·C):

| workload | XB 128 | XB 256 | on 108 nodes |
|---|---|---|---|
| ResNet-50 bottleneck | **92** | 23 | 85% at XB 128 |
| VGG-16 block 3 | **90** | 23 | 83% at XB 128 |
| Transformer encoder block | 432 | **108** | **100% at XB 256** |

ResNet and VGG match closely at 128×128 (92 vs 90 tiles). The transformer is 4× too
large there — absorbing that via density would mean ~32 crossbars/tile against 8 for
the others, which flattens exactly the inter-tile aggregation under study and destroys
density comparability. At **256×256 the transformer block is 108 tiles — it fills
6×6×3 exactly**, keeps 8 crossbars/tile, and `ff2` stays a genuine reduction at
R=12 into C=3. So: fixed mesh, fixed density, **crossbar size stated per workload**.

A Z-sweep (NoC dimensionality at fixed node count) remains a valid separate
contribution axis — but run it as its own axis, **not mixed into the workload
comparison**.

---

## 9. Open items

- [ ] Full load sweep at 6×6×3 with interior aggregators (peak + past-knee behaviour).
      **Start at `ls=0.020`** — the −29% is measured past the knee (§3)
- [ ] Implement Lever 1 — needs a **latch-point change** (per-dwell) or a router-side
      EWMA; `CINTERVAL` alone cannot deliver recency (§1, §4.2)
- [ ] Run the decay × latch-point calibration sweep (6 configs), then **lock**.
      The `CINTERVAL`-only sweep is done and negative — do not repeat it
- [ ] Spot-check locked DP params at both extremes of the mapping sweep
- [ ] Re-test planar/Z turn exclusivity on DNN traffic with interior aggregators
- [ ] Verify DP-cost read path (directions table vs read-at-decision-time) — carried
      over from `STAGE2-DP-CONGESTION-DIAGNOSIS.md`, still unconfirmed
- [ ] Calibrate sampling/decay numbers against **actual layer durations** from the
      converter, not queueing theory — carried over, still open
- [ ] Confirm `MAX_STATIC_DIM` and `DPSIZE` headroom before any larger topology
      (6×6×3 = 108 nodes, within `DPSIZE=260`; a Z-sweep may not be)
- [ ] Score the VGG and transformer mappings with `oe_arrival_faces.py` *before*
      simulating. VGG blk3 has **six** hot sinks (R=9/18 into C=2, three consecutive
      phases) against only 16 interior nodes on 6×6×3, so the interior budget binds;
      the transformer is inherently spread except `ff2`. See [MAPPING.md](MAPPING.md)
- [ ] Add the 24 missing transformer residuals (`transformer_layers()` in
      `stage2_dnn_full.py`) before any transformer run — they are the long-range flows
      DP responds to, so omitting them understates the workload

---

## 10. Corrections log (17 Aug 2026)

Reconciled against the measured data; original claims retained above only where they
survived.

| § | was | now |
|---|---|---|
| 1 | short `CINTERVAL` "did pay off", recency > completeness | false positive at n=3, reversed at n=12; DP latches once per `dp_cycle` so `CINTERVAL` cannot buy recency |
| 2 | two sinks = ~72% of traffic | **30.4%** (72% ≈ the top-*10* figure) |
| 2 | 3–4 usable input directions | **4 and 5** |
| 2 | ejection-port limit, "exactly one path" | input-link limit at 48% of port capacity; 4 admissible faces with 10× forced imbalance |
| 3 | ~25% / ~28% | −25.7% (t=−2.73) / −29.0% (t=−3.51); added the n=12 point and the double dissociation |
| 3 | max delay "significantly lower" | lower on interior, **higher on edge**, no test run |
| 4.2 | 2-D `CINTERVAL` × decay sweep | latch-point × decay sweep; `CINTERVAL`-only is done and negative |
| 7 | describes the diversity computation | already implemented; use routing-admitted faces, not geometry |
| 8 | crossbars-per-tile absorbs size | **crossbar size** absorbs it; transformer = 108 tiles at 256×256 |

§5 (turn-model note) left as written: OE, OEB and the OEB variants are all
deadlock-free per the IET paper — treat that as settled, not open.
