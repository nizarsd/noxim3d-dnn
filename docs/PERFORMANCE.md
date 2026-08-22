# Noxim3D — Correctness Fixes & Performance Work

Engineering record of the fixes and speedups applied to the simulator. Research
results (DP vs BL sweeps) live in [FINDINGS.md](FINDINGS.md).

---

## 1. Correctness: odd-even-balanced routing + DP legality

Committed in `a698e05` ("Noxim oddevenBalanced fix and simulator performance
improvements, sanity checked").

### Root cause — NaN results (a routing stall, not a warmup problem)

The old [`TRouter::routingOddEven1()`](../noxim3d_src/TRouter.cpp) had **inverted parity/turn
conditions**, incompatible with the intended odd-even restrictions. It could drive
the network into a persistent congestion/stall state in which almost no packets
were delivered. With a long warmup the network entered this state *before*
statistics collection began; if zero packets were received during the measured
interval, the average-delay and throughput calculations divided by zero →
**NaN**.

The long warmup did **not** cause the NaN — it only exposed the underlying routing
stall more clearly. (Relevant to sizing warmup: see the timing notes in
[FINDINGS.md](FINDINGS.md).)

### Router fix

- **`routingOddEven1()` replaced** with the corrected X-primary odd-even
  implementation by delegating to the standard function:
  `return routingOddEven(current, source, destination);`
- **`routingOddEvenBalanced()` made consistent across Z planes:**
  - Even Z plane → `routingOddEven1` → X-primary / column-wise
  - Odd Z plane  → `routingOddEven0` → Y-primary / row-wise

  The same mapping is used on the destination plane, during permitted downward
  in-plane movement, and during upward in-plane movement.

### DP model fix (must mirror the router)

The DP unit picks only from the router's legal candidate list, so it can never
violate OEB prohibitions — but its own legality
([`can_turnOddEvenBalanced`](../noxim3d_src/DPNode.cpp)) was corrected to match the new mapping:

- Even Z → `routingOddEven1_DPStrict()`; Odd Z → `routingOddEven0_DPStrict()`.
- Same-plane OEB calls swapped to the correct orientation.
- Downward movement on odd Z now uses `routingOddEven0_DPStrict()`.
- Upward movement on even Z now uses `routingOddEven1_DPStrict()`.
- The obsolete strict OE1 impl was replaced with
  `return routingOddEvenDPStrict(current, destination);` (corrected X-primary rules).

DP remains **intentionally stricter**: lacking packet-source info, it omits
source-dependent permissions (`cz == sz`, `c0 == s0`, `c1 == s1`). It also falls
back to `can_turnOddEven` when `mesh_dim_z == 1` to match the router's 2D
behaviour.

### Result

Five-seed **5×5×3, PIR 0.027**: OEB DP mean delay improved **168.46 → 143.14
cycles**, while bufferlevel was unchanged at **222.91 cycles**. DP-on-OEB now
produces legal, deadlock-free routes that track the router exactly, enabling the
DP-vs-BL study in [FINDINGS.md](FINDINGS.md).

---

## 2. Performance profiling (baseline)

Profiled with `gprof` (`-O2 -pg`), one representative run
(6×6×3, `-sel dp`, PIR 0.020 near the knee). Baseline ≈ **18 s / run**; a 42-run
sweep was **sequential** → ~13 min.

Top hotspots (self-time %):

| % | function | note |
|---|---|---|
| 13.2 | `TRouter::bufferMonitor` | ran NoP work every cycle for *all* strategies |
| 10.5 | `DPNode::can_turnOddEvenBalanced` | 124.8M calls — topology-static, recomputed every cycle |
| 10.2 / 10.0 | `rxProcess` / `txProcess` | core flit movement (irreducible) |
| 9.2 | `DPNode::dpProcess` | DP cost-field relaxation |
| 3.3 | `sc_signal<TNoP_data>::write` | 42M calls — **all** unused NoP output |
| 2.7 / 2.0 | `can_turn` / `isMinimalDirection` | DP legality dispatch |
| 2.0 | `vector::_M_realloc_insert` | routing helpers heap-allocate a vector per call |

Two clusters were pure waste for DP runs: the DP legality recomputation (~25%)
and the NoP output writes (~5%).

---

## 3. Optimization B — gate the NoP output

[`TRouter::bufferMonitor`](../noxim3d_src/TRouter.cpp) wrote `NoP_data_out` and computed
`getCurrentNoPData()` every cycle for every router, but that data is consumed
**only** by `selectionNoP()` (reachable only under `-sel nop`). The guard had
been commented out.

**Fix:** keep the `free_slots` writes unconditional (DP's congestion sampling and
bufferlevel both read `free_slots_neighbor`), but wrap the NoP block in
`if (selection_strategy == SEL_NOP)`.

**Safety verified:** `NoP_data_out` is read only by `selectionNoP` and the dead
`NoP_report()`; no `SC_METHOD` is sensitive to NoP signals, so gating cannot
perturb scheduling. Removes ~5% from DP/bufferlevel runs.

## 4. Optimization C — cache DP turn-legality

`can_turn(dir_in, dir_out, dst)` depends only on node coordinates, destination,
and the (fixed) routing algorithm — constant for a whole run — yet `dpProcess`
recomputed it 36×/node/cycle (124.8M calls), each doing coordinate math and a
heap `std::vector` allocation.

**Fix:** memoize per destination in [`DPNode`](../noxim3d_src/DPNode.h):
`bool legal_cache[DPSIZE][DIRECTIONS][DIRECTIONS]` + `legal_cached[DPSIZE]`,
built lazily on first use of each `dst_id` and looked up thereafter. `can_turn`
calls drop from ~124.8M to ~`nodes × dsts × 36` (built once).

## 5. Validation & results

- **Bit-identical output:** re-running 4×4×3 after B+C produced a `diff` of
  **zero** against the pre-optimization results (both the DP-vs-BL compare table
  and all 42 raw per-seed rows). B and C are behaviour-preserving by construction
  (pure memoization + gating unused output).
- **Re-profiled after B+C:** `can_turnOddEvenBalanced`, `can_turn`,
  `isMinimalDirection`, the `*_DPStrict` helpers, and the NoP `sc_signal` writes
  **all dropped out of the top of the profile**. Remaining time is core flit
  movement + `dpProcess` itself.
- **Wall clock:** 6×6×3 run ≈ **12 s** vs 13.5–18 s baseline. Noisy because the
  dev machine (i7-10510U, 4 cores / 8 threads, 15 W) throttles hard under load,
  but consistently faster, never slower.

## 6. Parallel sweep driver

[`noximrun_buffer_sweep_parallel.bash`](../noximrun_buffer_sweep_parallel.bash) — a
drop-in parallel version of the sweep script. Same env-var interface + DP-aware
timing; new `JOBS` knob (default = `nproc`). Each job writes its own row file
(no CSV race); rows are concatenated at the end. Runs are deterministic per seed,
so parallel output is **bit-identical** to sequential (validated on 4×4×3).

Speedup is capped by the 4-physical-core / thermally-throttled dev machine
(~1.6–2× observed), not by the script — it will scale further on a real
multi-core host.

## 7. Known limit — DPSIZE

`DPSIZE = 260` ([NoximDefs.h](../noxim3d_src/NoximDefs.h)) bounds the DP arrays (`cost_mem`,
`routing_directions`, `legal_cache`), all indexed by `dst_id`. **Meshes with
> 260 nodes overflow these arrays with no guard** (e.g. 8×8×7 = 448 nodes).
Raise `DPSIZE` and rebuild before running larger topologies.
