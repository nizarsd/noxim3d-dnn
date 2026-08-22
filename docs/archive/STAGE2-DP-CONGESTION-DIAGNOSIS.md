# Stage 2 — DP Congestion Signal Diagnosis and Fix Plan

Date: 16 August 2026
Context: DP vs bufferlevel (BL) on ResNet-derived DNN traffic, 7×7×3 mesh (147 nodes)

---

## 1. Observation

DP shows **no meaningful advantage over bufferlevel** on ResNet DNN traffic with
blocked/clustered 3D placement, despite the load-scale sweep reaching saturation
(average delay reaches saturation levels at high load scales).

This contrasts sharply with Stage 1 synthetic-traffic results (+82.4% peak DP
benefit on 7×7×3 under `transpose1`).

## 2. Spatial hypothesis — REJECTED

Initial hypothesis: blocked placement makes traffic mostly short-hop/local,
removing the multi-hop path diversity DP needs.

Test: re-ran with **diagonal placement (X then Y then Z)**, which maximises path
diversity for the given traffic at the cost of extra hops.

Result: **no change**. Since maximising path diversity moved nothing, the
bottleneck is **not spatial**.

## 3. Root cause — congestion signal diluted to zero

Code investigation established:

- The current DP congestion term is **per-channel average buffer occupancy**
  (not per-node).
- It is averaged over the `CINTERVAL` window, which is tied to `DP_CYCLE`.
- On 7×7×3: `nodes=147`, `diameter=14`, `DP_DWELL=17`,
  `DP_CYCLE = 2 · 147 · 17 = 4998` cycles.
- DNN burst durations are a small fraction of ~5000 cycles, so the average
  **dilutes to nearly zero most of the time**.

Consequence: the DP cost field collapses to **pure hop count**, and route choice
falls through to the selection strategy's arbitrary tie-breaking.

**Congestion is effectively not being measured for this metric.**

## 4. Confirming three-way comparison

| Congestion metric in DP cost | Outcome |
|---|---|
| Average channel occupancy | no meaningful DP benefit |
| Average waiting cycles per buffer (occupancy × cycles, normalised by flits transmitted) | non-zero values, more discrepancy between buffers, but still no benefit |
| **None** — equal cost, first-free-port priority fallback | **best results** |

Interpretation: the congestion estimates are **noisy and stale**, therefore
actively misleading. The first-free-port fallback reacts instantly with zero lag.
The problem is the **signal-to-lag ratio**, not the DP concept.

## 5. Fix plan

### Lever 1 (primary — attacks the root cause)

Replace accumulate-and-reset with a **decaying (exponentially weighted) average**
per channel:

1. Sample congestion frequently — target ~10 samples per DP cycle.
2. On each sample: `stored = decay · stored + new_sample` (no reset).
3. DP reads the current `stored` value at relaxation time.

Key insight established during discussion: **increasing sampling frequency alone
does not help** — DP still reads only one value per DP cycle, and that snapshot
can land on an idle moment. The value must *remember*. Decay is the actual fix.

Settings at the current (1×) DP clock:

- `CINTERVAL` ≈ 500 cycles (10 samples per 4998-cycle DP cycle)
- decay ≈ 0.9 (effective memory ≈ interval / (1 − decay))

Cost: ~2 lines in the sampling path, one member variable for the stored value,
one for the decay factor. No structural change to DP.

### Lever 2 (secondary — reduces reaction lag)

Speed up the DP clock and shrink the dwell (already noted as unimplemented in
`CLAUDE.md`).

- **4×** chosen as defensible: DP does simple integer min-plus relaxation, so
  ~4 GHz against a 1 GHz router clock is arguable given 2–3 GHz commodity parts.
  10× (i.e. 10 GHz) was rejected as indefensible.
- At 4×: DP cycle ≈ 1250 network cycles.
- Rescale `CINTERVAL` ≈ 125 (10 samples), decay ≈ 0.5
  (effective memory ≈ 250 cycles, appropriate for a waiting-time metric where a
  packet clears in tens of cycles with buffer = 16).
- ~10 samples per DP cycle is the practical floor; at 20 samples the interval
  (~60 cycles) approaches noise for a waiting-time metric.

**Ordering:** Lever 1 first — it attacks the actual defect. Lever 2 only shortens
lag, and multiplies a signal that is not yet there. Do them one at a time so
causal attribution is clean.

### Lever 3 — MOOT

Bounding the congestion contribution below the per-hop cost (100) so it can only
break ties: **not applicable**. Under minimal-only routing (odd-even /
odd-even-balanced), every legal candidate has identical hop count, so congestion
is always the deciding term. Nothing to bound. Only relevant if non-minimal paths
are allowed.

## 6. Open items to verify

1. **Calibrate against workload, not queueing theory.** The sampling-interval and
   decay-factor numbers above are derived from queueing timescales (packet
   service time, buffer depth) and are **placeholders**. They must be recalibrated
   against the **actual ResNet layer durations** produced by the converter. If
   layer active windows are only a few hundred cycles, short memory is right; if
   they run tens of thousands of cycles, a longer memory and coarser interval are
   affordable.

2. **Verify the DP-cost read path in the code.** Unconfirmed whether DP writes a
   routing-directions table that the router consults, or whether the router reads
   DP costs **directly at decision time** and decides on the fly. Current belief
   is the latter (DP computes costs only). This matters: if the router reads costs
   directly, the two-clock-domain question is trivial — no handshake, no
   double-buffering; the cost array is simply fresher. If a directions table
   exists, a shadow copy with a pointer swap at end-of-dwell would be needed to
   avoid reading a torn table.

3. Plot the DP cost field over time to confirm the dilution-to-zero diagnosis
   graphically rather than by inference.

## 7. Framing note (baseline legitimacy)

The current DP configuration is the published/validated one and works on
synthetic traffic (Stage 1). Its failure on DNN traffic is therefore a **finding**,
not a misconfiguration, and DP-as-is remains a legitimate baseline.

Lever 1 should still be run — not to "fix the baseline", but to establish how much
of the gap is closable by better *measurement* versus how much genuinely requires
*prediction*. That split is the evidence gate for any temporal/predictive
contribution later (Stage 6 → Stage 7).

## 8. Reference numbers (7×7×3)

| Quantity | Value |
|---|---|
| Nodes | 147 |
| Diameter | 14 |
| `DP_DWELL` | 17 |
| `DP_CYCLE` (1×) | 4998 |
| `DP_CYCLE` (4×) | ~1250 |
| `CINTERVAL` for 10 samples (1×) | ~500 |
| `CINTERVAL` for 10 samples (4×) | ~125 |
