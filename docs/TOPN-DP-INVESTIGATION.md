# Top-N-sinks DP — Turn 1 investigation

Per [TOPN-DP-PROMPT.md](TOPN-DP-PROMPT.md). All facts verified in source or measured
this session (2026-09-16); measurement artifacts under `results_ext/`. The same design
is specced as task 3 of [EXTENSION-PATHWAYS.md](EXTENSION-PATHWAYS.md) ("sink-list
hybrid"), converged on independently before this prompt was read; differences are
flagged in §9.

## 1. DP relaxation structure — clean restriction

Destinations are processed strictly one at a time: `dst_id = (phase / dp_dwell()) %
dp_no_dst()` ([DPNode.cpp:24](../noxim3d_src/DPNode.cpp)). Within a window the
relaxation touches only `cost_mem[dst_id][*]`, `legal_cache[dst_id][*][*]` and the
anchor test `local_id == dst_id` ([DPNode.cpp:49-127](../noxim3d_src/DPNode.cpp)).
The only cross-destination state is `frozen_local_cost[]`, the congestion sample
re-latched at every window start ([DPNode.cpp:49-52](../noxim3d_src/DPNode.cpp)) —
shared input, not shared computation. The untagged DP links are coherent because all
nodes hold the same `dst_id` ([DPNode.cpp:80-81](../noxim3d_src/DPNode.cpp)); any
subset sweep preserves this as long as every node derives the same list. **A
destination subset is a clean restriction.**

## 2. DP cycle scaling — linear in destination count

`dp_pass() = dp_dwell() × dp_no_dst()` with `dp_dwell() = ceil(diameter /
DP_CLOCK_MULT) + 3` ([NoximDefs.h:252-256](../noxim3d_src/NoximDefs.h)); settle
defaults to 0 in all Stage-3 runs, so cycle = pass = 6 × 108 = 648 at 6×6×3. The
cycle is **linear in the number of destinations swept**: N sinks → N × 6 cycles
(15 → 90, 24 → 144). DPSIZE (260) only sizes arrays. Supporting measurement: the
knee-load coherence time of hot-link occupancy is 50–160 cycles
(`results_ext/` ACF analysis), so N ≤ ~25 puts the refresh inside the window that
648 misses — the freshness motivation is measured, not assumed.

## 3. Table layout — no remap needed

Router side: `routing_directions[DPSIZE][DIRECTIONS]`
([TRouter.h:193](../noxim3d_src/TRouter.h)), written per live destination at the
window end ([TRouter.cpp:379-385](../noxim3d_src/TRouter.cpp)), read by full `dst_id`
([TRouter.cpp:586](../noxim3d_src/TRouter.cpp)). DP side: `cost_mem[DPSIZE][6]`,
`legal_cache[DPSIZE][6][6]` ([DPNode.h:26-32](../noxim3d_src/DPNode.h)). Keeping full-
size arrays indexed by real node id and simply never visiting unlisted rows requires
**nothing** — no sparse index, no remap. Unvisited rows stay at their reset values
(−2 / BIG_VALUE), which the selection loop already skips as non-matching. (True
hardware would shrink the arrays; the simulator need not model that.)

## 4. Per-packet policy switch — one line, same turn model

Selection is dispatched once per packet in `selectionFunction`; DP's selector walks
the ranked row and intersects with the routing function's admissible set, with a
fallback at [TRouter.cpp:595](../noxim3d_src/TRouter.cpp). Minimal change: at the
top of `selectionDP`, if the packet's `dst_id` is not in the sink set, `return
selectionBufferLevel(directions);`. BL's inputs (`free_slots_neighbor`) are advertised
unconditionally ([TRouter.cpp:340-344](../noxim3d_src/TRouter.cpp)), so they are live
under `-sel dp`. **Deadlock freedom is unaffected**: both selectors choose only among
`directions`, the admissible set the routing function computed under the one turn
model; selection never adds a turn ([TRouter.cpp:577-596](../noxim3d_src/TRouter.cpp)).

## 5. Sink identification — one-liner from the run table

Volume rank per destination = Σ over its inflow rows of pir × (t_off − t_on), read
from the run's own traffic table (the generated tables already carry mesh node ids —
`gen_tables_generic.py` writes `perm[s], perm[d]`, so no placement translation is
needed at run time). Computed this session in `results_ext/phase_score/` (script
inline; promote to `tools/rank_sinks.py` in Turn 2). No pre-existing ranking script
was found; the §28 ejection-normalisation and hot-tier lists rank links/ports, not
sinks, and were not reused.

## 6. Hot-tier sizes (measured 2026-09-16)

Bytes-coverage N per table (N@80% / N@95%, of total sinks):

| table | sinks | N@80% | N@95% |
|---|---|---|---|
| ResNet (8,2,4) — prompt ref | 91 | ~40 | 57 |
| VGG (8,4,2) — prompt ref | 104 | ~42 | 86 |
| DeiT-S (16,1,16) — prompt ref | 64 | 14 | 45 |
| ResNet (8,1,8) | 89 | 15 | 42 |
| ResNet (16,2,8) min-PF | 45 | 17 | 27 |
| VGG (32,8,4) min-PF | 31 | 13 | 26 |

Two of the prompt's three reference points (ResNet (8,2,4), VGG (8,4,2)) are the
FLAT, injection-bound tables — and also the ones where the traced runs show near-zero
hot-link queues and DP ≈ BL (gain 1.00 / 1.06). The concentrated tables are the
ejection-bound ones and every global min-PF pick. Sweep range from the data:
N ∈ {1, 2, 4, 8, 15, N@80%, N@95%, all}.

## 7. Double-buffering — not needed; the premise is wrong

There is no torn read to fix. `routing_directionsUpdater` is an `SC_METHOD` on the
NoC clock ([TRouter.h:128-130](../noxim3d_src/TRouter.h)); DP publishes at
`phase % dwell == dwell−2` ([DPNode.cpp:116](../noxim3d_src/DPNode.cpp)) and the
router latches one NoC cycle later at `dwell−1`
([TRouter.cpp:378](../noxim3d_src/TRouter.cpp)); `dp_dir` is stable across that
boundary and the six-entry row write completes atomically within the method. A
shorter cycle changes write frequency, not this ordering. `dir_tbl[2]` + active
index is unnecessary; Turn 2 is NOT gated on it. (Same conclusion recorded in
EXTENSION-PATHWAYS.md §3.1.)

## 8. Regression targets

- **transpose1 bit-identical**: the Stage-1 gate (CLAUDE.md validation rule;
  FINDINGS.md Stage-1 section). Flag absent must be bit-identical at HEAD.
- **Full-DP and BL references at the knee** for the three prompt points exist twice:
  the canonical hill results (`res_f1`, `res_f2`, `res_esxd` in
  `results_stage3/mapping_pilot/pool1000/hill/`, read-only) and this session's
  bit-comparable reruns with traces (`results_ext/trace_runs/res_{f1,f2,esxd}.txt`),
  8/8/16 placements × knee rungs × **3 seeds**, deterministic per seed.
- **Gap to the prompt**: no n = 30 references exist for these points; the study
  standard is 3 seeds (paired, deterministic). Turn 2 should either run at 3 seeds
  against the existing references or first extend the references to n = 30
  (~an extra 2×128×27 runs). Flagged as the one open protocol decision.

## 9. Deltas from the prompt (for reconciliation)

- Flag: EXTENSION-PATHWAYS task 3 specs `-dpsinks N` with the list ranked at startup
  from the traffic table; the prompt specs `-dptopn <N> <sinkfile>`. The sinkfile
  form is better for auditability — adopt it, generated by `tools/rank_sinks.py`.
- Semantics agree after 2026-09-16 correction: flag absent = current behaviour
  (bit-identical gate); N = 0 = pure BL via fallback; N = all ≈ full DP. Note
  N = all is NOT bit-identical to `-sel dp` unless the sinkfile order reproduces
  0..107: the sweep order changes which window serves which destination, shifting
  RNG-free but time-dependent field ages. Expect statistical, not bit, identity —
  the prompt already allows this (Turn 2 §2, "report the delta and its cause").
- Registered readings to carry over from EXTENSION-PATHWAYS task 3: recover the
  destination-gated oracle headroom where it is large (+7.0% ResNet (8,2,4),
  +4.7% DeiT-S), hold always-DP where it already wins (ResNet (8,1,8) guard), and
  the coherence-window rationale for why freshness should pay at small N.

## Verdict

**READY** for Turn 2 (different session, per the prompt), with one protocol decision
open: 3-seed against existing references vs extending references to n = 30.
