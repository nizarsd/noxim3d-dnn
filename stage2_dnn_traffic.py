#!/usr/bin/env python3
"""
Stage 2 traffic-table converter -- ResNet-50 stage-3 bottleneck block.

Emits a Noxim traffic table ("src dst pir por t_on t_off t_period") for a single
ResNet-50 bottleneck block mapped onto a 3D mesh under a size-driven IMC crossbar
model.  See STAGE2.md (authoritative) -- this implements SS7.1-7.5 with the SS9
resolved decisions.

MODEL SUMMARY
-------------
  * Partitioning: weights are STATIONARY in IMC crossbars.  A layer's weight
    matrix is (k*k*Cin) x Cout; it is split into an R x C grid of XB x XB tiles,
    one crossbar per node.
       R = ceil(rows/XB)  -> "reduction depth": each row-group holds a slice of
                             the input dimension, so it produces only a PARTIAL
                             sum which must be added across the column.
       C = ceil(cols/XB)  -> "fan-out width": each column-group computes different
                             output channels from the SAME input, so the input
                             must be replicated to all of them.
    These two splits -- not the layer dependency graph -- generate the traffic.

  * Multicast: source replication only (STAGE2.md SS9.4).  One unicast row per
    destination, same src, same t_on/t_off window.  No simulator change.

  * Packet size: global via `-size 16 16`, NOT per row (STAGE2.md SS9.1).
    Per-flow volume is encoded in `pir` (packet COUNT), never in size.

  * Timing: layer duration proportional to MACs (crossbars within a layer run in
    parallel, so tile count is the wrong proxy; and H*W alone ignores that a 3x3
    conv does 9x the work per position of a 1x1).  Strictly sequential firing
    conv1 -> conv2 -> conv3, no pipelining.  The projection shortcut is the one
    parallel branch and spans the whole block pass.

    !! This is a FIRST-ORDER TIMING ESTIMATE, not a validated performance model.
       It has no notion of crossbar latency, ADC conversion cost, memory
       bandwidth, or pipeline fill.  It fixes the RELATIVE ordering and rough
       proportions of the phases; the absolute scale is a free knob
       (CYCLES_PER_MAC).  Do not quote it as a performance result.

  * The whole representation is a piecewise-constant, MEMORYLESS approximation of
    the DNN trace: Noxim injects Bernoulli trials at rate `pir` inside each
    window, so a burst becomes an elevated-rate Poisson stream, and flows fire on
    a static clock with no causal dependency (L+1 does not wait for L).
    See STAGE2.md SS4-SS5 for why this is acceptable for a congestion metric.

python3 stdlib only.  Shapes are hardcoded -- change the CONFIG block to retarget.
"""

import csv
import math
import os
from collections import defaultdict


def _env(name, default, cast=str):
    """Config value, overridable from the environment.

    Lets noximrun_dnn_traffic.bash regenerate the table per load-scale point
    without editing this file.  Everything still has a working default, so
    `python3 stage2_dnn_traffic.py` on its own does the right thing.
    """
    v = os.environ.get(name)
    return default if v is None or v == "" else cast(v)


# =============================================================================
# CONFIG -- retarget the converter by editing this block only
# =============================================================================

MODEL_TAG = "resnet50_bottleneck3"

# --- hardware -----------------------------------------------------------------
XB = 128                    # IMC crossbar dimension (XB x XB), 1 crossbar/node
DIMX, DIMY, DIMZ = 6, 6, 3  # mesh -> 108 nodes (STAGE2.md SS9.3, revised)

# --- workload -----------------------------------------------------------------
FMAP_H, FMAP_W = 14, 14     # feature map of ResNet-50 stage 3, stride 1

# (name, k, Cin, Cout, kind)  -- weight matrix is (k*k*Cin) x Cout
#   kind: "conv"     = part of the sequential trunk, fires in its own phase
#         "shortcut" = parallel projection branch, spans the whole block pass
LAYERS = [
    ("conv1",    1,  512,  256, "conv"),
    ("conv2",    3,  256,  256, "conv"),
    ("conv3",    1,  256, 1024, "conv"),
    ("shortcut", 1,  512, 1024, "shortcut"),
]

# Spare-node absorption (STAGE2.md SS9.3): the block needs 92 tiles, the mesh has
# 108 nodes.  Rather than leave 16 idle, layers are given a FINER split than XB
# strictly requires -- crossbars end up partly filled, which deepens reduction /
# widens fan-out instead of inventing traffic that isn't there.
#
# Constraint: a group may only get SMALLER, never larger than XB.  So
#   R >= ceil(rows/XB)  and  C >= ceil(cols/XB).
# The chosen grids also make the placement boxes tile 6x6x3 exactly.
GRID_OVERRIDE = {
    "conv1":    (6, 2),   # base (4, 2)  =  8 -> 12
    "conv2":    (18, 2),  # base (18, 2) = 36 -> 36  (unchanged)
    "conv3":    (3, 8),   # base (2, 8)  = 16 -> 24
    "shortcut": (4, 9),   # base (4, 8)  = 32 -> 36
}                         #                 92 -> 108

# Placement (STAGE2.md SS9.2): blocked/clustered 3D sub-volume per layer, via
# coord2Id.  NOT sequential ids -- id+1 walks along X and only reaches the Z
# neighbour after DIMX*DIMY steps, so a sequential layout would barely use TSVs
# and the 3D findings (Z-series, vertical turn exclusivity) would stay dormant.
# These four boxes tile 6x6x3 exactly with no gaps and no overlap.
#   name: (x0, y0, z0, sx, sy, sz)
BOXES = {
    "conv1":    (0, 0, 0, 2, 2, 3),   # 12
    "conv2":    (2, 0, 0, 4, 3, 3),   # 36
    "conv3":    (0, 2, 0, 2, 4, 3),   # 24
    "shortcut": (2, 3, 0, 4, 3, 3),   # 36
}
# NOTE: deliberately UNOPTIMISED.  Congestion-aware placement is excluded on
# purpose (STAGE2.md SS9.2) -- it would confound "does DNN traffic behave
# differently" with "does smart mapping help".

# --- data sizes ---------------------------------------------------------------
BYTES_PER_ACT = 1           # INT8 activations
BYTES_PER_PSUM = 4          # INT32 partial sums -- 4x the activation width, which
                            # is why reduce traffic dominates volume even when
                            # flow counts are comparable
FLIT_BYTES = 4
PACKET_FLITS = 16           # must match the simulator's `-size 16 16`
PACKET_BYTES = FLIT_BYTES * PACKET_FLITS

# --- timing / load ------------------------------------------------------------
# Stretches or compresses the whole timeline.  Must be large enough that (a) each
# phase comfortably exceeds DP_CYCLE = 2*nodes*(diameter+3) so the DP cost field
# can converge inside a phase, and (b) no source's cumulative pir exceeds 1.
# Both constraints want a LARGER value; validate() reports the binding one.
#
# But a LARGER value also means a longer t_period, and the sweep scripts measure
# over SIM = SIM_DP_CYCLES * DP_CYCLE -- so too long a period leaves only a
# fraction of a block pass inside the measurement window.  1.3e-4 puts the
# shortest phase (conv1) just above DP_CYCLE while keeping t_period short enough
# that SIM_DP_CYCLES=80 covers ~10 block passes.  See the timing report printed
# by main().
CYCLES_PER_MAC = _env("DNN_CYCLES_PER_MAC", 1.3e-4, float)

SIM_DP_CYCLES = _env("SIM_DP_CYCLES", 80, int)      # mirrors the sweep-script env vars;
WARMUP_DP_CYCLES = _env("WARMUP_DP_CYCLES", 3, int)  # used only to report coverage

# Global pir multiplier -> sweep the DP-vs-BL knee exactly as in the Stage-1 PIR
# sweeps (STAGE2.md SS7.4).  The DNN sets the SHAPE (spatial pattern + phases),
# this sets the LEVEL.
#
# NOTE the direction: at LOAD_SCALE=1.0 the raw DNN volume gives per-node
# injection rates of 0.05-0.55 depending on phase, against a Stage-1 knee for
# 6x6x3 of PIR ~= 0.020.  Scale 1.0 is therefore deep in saturation, and the
# useful sweep runs DOWNWARD, not upward.  0.05 puts the busiest phase (conv1)
# near the Stage-1 knee.
LOAD_SCALE = _env("DNN_LOAD_SCALE", 0.05, float)

OUTDIR = _env("DNN_TABLE_DIR", "traffics_dnn")
# Filename stem.  The sweep script overrides this per load-scale point so the
# generated tables do not collide (parallel jobs each read their own file).
TABLE_STEM = _env("DNN_TABLE_STEM", "")


# =============================================================================
# Derived geometry
# =============================================================================

NODES = DIMX * DIMY * DIMZ
DIAMETER = (DIMX - 1) + (DIMY - 1) + (DIMZ - 1)
DP_CYCLE = 2 * NODES * (DIAMETER + 3)      # NoximDefs.h / FINDINGS.md method
HW = FMAP_H * FMAP_W


def coord2id(x, y, z):
    """Mirror of coord2Id in NoximDefs.h."""
    return x + y * DIMX + z * DIMX * DIMY


def split_ranges(total, n):
    """Split [0,total) into n contiguous groups, largest-first sizing."""
    g = math.ceil(total / n)
    out = []
    for i in range(n):
        lo, hi = i * g, min((i + 1) * g, total)
        assert lo < hi, f"empty group {i} splitting {total} into {n}"
        out.append((lo, hi))
    assert out[-1][1] == total
    return out


def overlap(a, b):
    """Size of the intersection of two [lo,hi) ranges."""
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))


class Layer:
    def __init__(self, name, k, cin, cout, kind):
        self.name, self.k, self.cin, self.cout, self.kind = name, k, cin, cout, kind
        self.rows = k * k * cin
        self.cols = cout
        self.base_R = math.ceil(self.rows / XB)
        self.base_C = math.ceil(self.cols / XB)
        self.R, self.C = GRID_OVERRIDE[name]

        # a finer split is legal (partly-filled crossbar); a coarser one is not
        assert self.R >= self.base_R, f"{name}: R={self.R} < ceil(rows/XB)={self.base_R}"
        assert self.C >= self.base_C, f"{name}: C={self.C} < ceil(cols/XB)={self.base_C}"

        self.row_groups = split_ranges(self.rows, self.R)
        self.col_groups = split_ranges(self.cols, self.C)
        assert max(hi - lo for lo, hi in self.row_groups) <= XB
        assert max(hi - lo for lo, hi in self.col_groups) <= XB

        self.tiles = self.R * self.C
        self.macs = k * k * cin * cout * HW
        self.node = {}          # (r, c) -> node id

    def in_ch_range(self, r):
        """Input-CHANNEL range covered by row-group r.

        im2col row order is (channel-major, kernel position minor), so
        channel = row // (k*k).  A row-group boundary can land mid-channel, so
        this widens to the enclosing channel range -- overlaps are computed in
        channels, which keeps the producer/consumer mapping correct even when
        the two layers use different R/C splits.
        """
        lo, hi = self.row_groups[r]
        kk = self.k * self.k
        return (lo // kk, math.ceil(hi / kk))

    def out_ch_range(self, c):
        return self.col_groups[c]

    def acc(self, c):
        """Accumulator node for column-group c: the r=0 tile of that column."""
        return self.node[(0, c)]


LAYER = {name: Layer(name, k, cin, cout, kind)
         for (name, k, cin, cout, kind) in LAYERS}
TRUNK = [LAYER[n] for (n, _, _, _, kind) in LAYERS if kind == "conv"]
SHORTCUT = LAYER["shortcut"]


# =============================================================================
# Placement
# =============================================================================

def place():
    """Assign each layer's (r,c) tiles to node ids inside its 3D box.

    Cell order within a box is z-fastest, then x, then y.  Consecutive tile
    indices therefore land on VERTICAL neighbours, so intra-layer exchange
    actually crosses TSVs -- the thing sequential-id placement would lose.
    """
    used = {}
    for L in LAYER.values():
        x0, y0, z0, sx, sy, sz = BOXES[L.name]
        cells = sx * sy * sz
        assert cells == L.tiles, f"{L.name}: box holds {cells}, layer needs {L.tiles}"
        for i in range(L.tiles):
            dz = i % sz
            dx = (i // sz) % sx
            dy = i // (sz * sx)
            nid = coord2id(x0 + dx, y0 + dy, z0 + dz)
            assert nid not in used, f"node {nid} claimed by {used.get(nid)} and {L.name}"
            used[nid] = L.name
            L.node[(i // L.C, i % L.C)] = nid
    return used


# =============================================================================
# Phases
# =============================================================================

def build_phases():
    """Strictly sequential trunk phases sized in proportion to MACs.

    The traffic-table gate is STRICT on both ends (TGlobalTrafficTable.cpp:116):
        r = ccycle % t_period;  on iff t_on < r < t_off
    and the loader asserts t_off > t_on and t_period > t_off
    (TGlobalTrafficTable.cpp:82,86).  So the last phase must end strictly before
    t_period, and one cycle is lost at every boundary (r == boundary is off for
    both the phase that ends and the phase that starts).  Negligible at these
    window lengths, but it is why window_len below subtracts 1.
    """
    durations = [max(1, int(L.macs * CYCLES_PER_MAC)) for L in TRUNK]
    bounds, t = [], 0
    for L, d in zip(TRUNK, durations):
        bounds.append((L.name, t, t + d))
        t += d
    total = t

    phases = {name: (on, off) for (name, on, off) in bounds}
    # The projection shortcut is the one parallel branch: it reads the same block
    # input conv1 reads, and its result is not needed until the residual add at
    # the very end of conv3.  Nothing forces it to complete early, so it spans
    # the full block pass -- which also lifts mesh occupancy during conv2 and
    # gives it room for its 102.8M MACs (4x conv1's).
    phases["shortcut"] = (0, total)
    t_period = total + 1                     # loader requires t_period > t_off
    return phases, t_period, durations


# =============================================================================
# Flows
# =============================================================================
# Volumes are accumulated in INTEGER BYTES keyed by (src, dst, phase) and only
# converted to packets once, at the end.  Aggregating in bytes rather than in
# packets (or floats) is what keeps the emitted table and the volume matrix
# exactly consistent -- there is no float accumulation anywhere in the path.

def build_flows():
    vol = defaultdict(int)                       # (src, dst, phase) -> bytes
    cls = defaultdict(lambda: defaultdict(int))  # (src, dst, phase) -> class -> bytes

    def add(src, dst, phase, nbytes, kind):
        if src == dst or nbytes <= 0:
            return                               # no self-traffic
        vol[(src, dst, phase)] += nbytes
        cls[(src, dst, phase)][kind] += nbytes

    # --- block input holders -------------------------------------------------
    # The block's input tensor has to live somewhere.  It is taken as resident on
    # conv1's column-0 tiles, partitioned by conv1's row-groups.  Both conv1's
    # own fan-out and the shortcut's scatter read from these same holders --
    # which is exactly what the residual topology says: the two branches consume
    # the same tensor.
    c1 = LAYER["conv1"]
    holders = [(c1.node[(r, 0)], c1.in_ch_range(r)) for r in range(c1.R)]

    def scatter_from(producers, L, phase):
        """Deliver producer output channels to every tile of L that needs them.

        This single routine covers BOTH the inter-layer handoff and the
        consumer's intra-layer fan-out: a producer group feeding row-group r must
        send to all C tiles of that row, so the fan-out falls out of the loop as
        one unicast row per destination -- source replication, per STAGE2.md SS9.4.
        Matching is done on channel ranges, so producer and consumer may use
        different R/C splits.
        """
        for r in range(L.R):
            need = L.in_ch_range(r)
            for (pnode, prange) in producers:
                n = overlap(need, prange)
                if n == 0:
                    continue
                for c in range(L.C):
                    add(pnode, L.node[(r, c)], phase, n * HW * BYTES_PER_ACT,
                        "scatter")

    def reduce_within(L, phase):
        """Every (r,c) ships its partial sum up to the column accumulator (0,c).

        Flat all-to-one: the accumulator takes R-1 simultaneous incoming flows of
        INT32 partials.  For conv2 that is 17 senders into a single node -- the
        sharpest hotspot in the block, and the structure DP's multi-hop cost
        field should handle better than BL's one-hop view.  A tree/chain
        reduction would spread it; flat is the simpler baseline and is the knob
        that controls whether the block has a hotspot at all.
        """
        for c in range(L.C):
            lo, hi = L.out_ch_range(c)
            nbytes = (hi - lo) * HW * BYTES_PER_PSUM
            for r in range(1, L.R):
                add(L.node[(r, c)], L.acc(c), phase, nbytes, "reduce")

    # --- trunk: conv1 -> conv2 -> conv3 --------------------------------------
    for i, L in enumerate(TRUNK):
        phase = L.name
        if i == 0:
            scatter_from(holders, L, phase)          # block input -> conv1
        reduce_within(L, phase)
        if i + 1 < len(TRUNK):
            nxt = TRUNK[i + 1]
            producers = [(L.acc(c), L.out_ch_range(c)) for c in range(L.C)]
            # handoff sits in the PRODUCER's window: the layer computes and ships
            # its output within its own phase
            scatter_from(producers, nxt, phase)

    # --- shortcut: block input -> projection tiles -> reduce -> the add ------
    S = SHORTCUT
    scatter_from(holders, S, "shortcut")
    reduce_within(S, "shortcut")

    # The residual add happens at conv3's accumulators, which already hold the
    # trunk output.  This is the one non-local flow: it jumps from the projection
    # box to conv3's box, crossing the mesh, and is the only thing making the
    # pattern non-linear.
    c3 = TRUNK[-1]
    for cs in range(S.C):
        for c3c in range(c3.C):
            n = overlap(S.out_ch_range(cs), c3.out_ch_range(c3c))
            if n:
                add(S.acc(cs), c3.acc(c3c), "shortcut",
                    n * HW * BYTES_PER_ACT, "add")

    return vol, cls


# =============================================================================
# Rows
# =============================================================================

def build_rows(vol, cls, phases, t_period):
    rows = []
    for (src, dst, phase), nbytes in sorted(vol.items()):
        t_on, t_off = phases[phase]
        window = t_off - t_on - 1                # strict gate on both ends
        assert window > 0
        packets = math.ceil(nbytes / PACKET_BYTES)
        pir = LOAD_SCALE * packets / window
        kinds = "+".join(sorted(cls[(src, dst, phase)]))
        rows.append(dict(src=src, dst=dst, pir=pir, por=pir,
                         t_on=t_on, t_off=t_off, t_period=t_period,
                         phase=phase, kind=kinds,
                         bytes=nbytes, packets=packets, window=window))
    return rows


def validate(rows, placed, phases, t_period, durations):
    errs, warns = [], []

    # -- loader contract (TGlobalTrafficTable.cpp) ----------------------------
    for r in rows:
        if not (0 <= r["src"] < NODES and 0 <= r["dst"] < NODES):
            errs.append(f"node id out of range: {r['src']}->{r['dst']}")
        if r["src"] == r["dst"]:
            errs.append(f"self traffic at {r['src']}")
        if not (0 <= r["pir"] <= 1):
            errs.append(f"pir out of [0,1]: {r['pir']:.4f} {r['src']}->{r['dst']}")
        # a flow whose pir rounds to 0 at the emitted precision is silently
        # dropped by the simulator -- the row loads, but never fires
        if float(f"{r['pir']:.10f}") == 0.0:
            errs.append(f"pir {r['pir']:.3e} underflows to 0 at %.10f "
                        f"({r['src']}->{r['dst']}) -- LOAD_SCALE too small")
        if not r["t_off"] > r["t_on"]:
            errs.append("assert t_off > t_on would fire")
        if not r["t_period"] > r["t_off"]:
            errs.append("assert t_period > t_off would fire")

    # -- cumulative pir per source, per phase --------------------------------
    # getCumulativePirPor sums pir over every row whose src matches and whose
    # window is open; the PE compares a uniform draw against that sum, so it must
    # not exceed 1 or the flow mix is silently clipped.
    cum = defaultdict(float)
    for r in rows:
        cum[(r["src"], r["phase"])] += r["pir"]
    worst = max(cum.items(), key=lambda kv: kv[1]) if cum else ((None, None), 0.0)

    # shortcut overlaps every trunk phase, so those sources stack
    stacked = defaultdict(float)
    for (src, phase), v in cum.items():
        if phase == "shortcut":
            for tl in TRUNK:
                stacked[(src, tl.name)] += v
        else:
            stacked[(src, phase)] += v
    worst_stacked = max(stacked.items(), key=lambda kv: kv[1])
    if worst_stacked[1] > 1.0:
        errs.append(
            f"cumulative pir {worst_stacked[1]:.3f} > 1 at node {worst_stacked[0][0]} "
            f"in phase {worst_stacked[0][1]} -- raise CYCLES_PER_MAC or lower LOAD_SCALE")

    # -- DP convergence vs phase length --------------------------------------
    for L, d in zip(TRUNK, durations):
        if d < DP_CYCLE:
            warns.append(f"phase {L.name} is {d} cycles < DP_CYCLE {DP_CYCLE} "
                         f"-- DP cannot converge inside this phase")

    # -- placement ------------------------------------------------------------
    if len(placed) != NODES:
        warns.append(f"{NODES - len(placed)} nodes unused")

    return errs, warns, worst, worst_stacked


# =============================================================================
# Output
# =============================================================================

def write_all(rows, placed, phases, t_period, durations):
    os.makedirs(OUTDIR, exist_ok=True)
    mesh = f"{DIMX}x{DIMY}x{DIMZ}"
    stem = TABLE_STEM or f"{MODEL_TAG}_xb{XB}_{mesh}"
    base = os.path.join(OUTDIR, stem)

    # --- the traffic table ---------------------------------------------------
    with open(base + ".txt", "w") as f:
        f.write(f"% {MODEL_TAG}  crossbar {XB}x{XB}  mesh {mesh} ({NODES} nodes)\n")
        f.write(f"% generated by stage2_dnn_traffic.py -- see STAGE2.md\n")
        f.write(f"% run with:  -size {PACKET_FLITS} {PACKET_FLITS} "
                f"-dimx {DIMX} -dimy {DIMY} -dimz {DIMZ} -traffic table {base}.txt\n")
        f.write(f"% sweep with: WARMUP_DP_CYCLES={WARMUP_DP_CYCLES} "
                f"SIM_DP_CYCLES={SIM_DP_CYCLES}  "
                f"(DP_CYCLE={DP_CYCLE}, SIM={SIM_DP_CYCLES*DP_CYCLE}, "
                f"{SIM_DP_CYCLES*DP_CYCLE/t_period:.1f} block passes measured)\n")
        f.write(f"% LOAD_SCALE={LOAD_SCALE}  CYCLES_PER_MAC={CYCLES_PER_MAC}"
                f"  t_period={t_period}\n")
        f.write("% phases:")
        for name, (on, off) in phases.items():
            f.write(f"  {name}=[{on},{off})")
        f.write("\n")
        f.write("% src dst pir por t_on t_off t_period\n")
        # %.10f, not %.8f: a low LOAD_SCALE sweep point drives the smallest pir
        # toward 1e-8, where 8 decimals would round it to zero and silently drop
        # the flow.  The loader parses with %f into a 32-bit float (~7 significant
        # figures), so 10 decimals is past what the simulator can retain -- the
        # cost is file size only.  validate() asserts nothing underflows.
        for r in rows:
            f.write(f"{r['src']:5d} {r['dst']:5d} {r['pir']:.10f} {r['por']:.10f} "
                    f"{r['t_on']:8d} {r['t_off']:8d} {r['t_period']:8d}\n")

    # --- src x dst volume matrix (for hand-verification) ---------------------
    mat = [[0] * NODES for _ in range(NODES)]
    for r in rows:
        mat[r["src"]][r["dst"]] += r["bytes"]
    with open(base + "_volume.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["src\\dst"] + list(range(NODES)))
        for s in range(NODES):
            w.writerow([s] + mat[s])

    # --- per-flow detail -----------------------------------------------------
    with open(base + "_flows.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["src", "dst", "phase", "class", "bytes", "packets",
                    "window", "pir", "t_on", "t_off", "t_period"])
        for r in rows:
            # same precision as the table, so the two files stay comparable
            w.writerow([r["src"], r["dst"], r["phase"], r["kind"], r["bytes"],
                        r["packets"], r["window"], f"{r['pir']:.10f}",
                        r["t_on"], r["t_off"], r["t_period"]])

    # --- placement -----------------------------------------------------------
    with open(base + "_placement.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["node", "x", "y", "z", "layer", "r", "c", "role"])
        rev = {}
        for L in LAYER.values():
            for (r, c), nid in L.node.items():
                rev[nid] = (L.name, r, c, "accumulator" if r == 0 else "tile")
        for nid in range(NODES):
            x = nid % DIMX
            y = (nid // DIMX) % DIMY
            z = nid // (DIMX * DIMY)
            name, r, c, role = rev.get(nid, ("-", "", "", "idle"))
            w.writerow([nid, x, y, z, name, r, c, role])

    return base


# =============================================================================

def main():
    placed = place()
    phases, t_period, durations = build_phases()
    vol, cls = build_flows()
    rows = build_rows(vol, cls, phases, t_period)
    errs, warns, worst, worst_stacked = validate(
        rows, placed, phases, t_period, durations)
    base = write_all(rows, placed, phases, t_period, durations)

    total_tiles = sum(L.tiles for L in LAYER.values())
    total_macs = sum(L.macs for L in TRUNK)

    print(f"mesh {DIMX}x{DIMY}x{DIMZ} = {NODES} nodes   "
          f"diameter {DIAMETER}   DP_CYCLE {DP_CYCLE}")
    print(f"crossbar {XB}x{XB}   tiles {total_tiles}   nodes used {len(placed)}\n")

    print(f"{'layer':10s} {'matrix':>12s} {'base':>8s} {'grid':>8s} "
          f"{'tiles':>6s} {'depth':>6s} {'width':>6s} {'MACs':>12s} {'phase':>16s}")
    for L in LAYER.values():
        on, off = phases[L.name]
        print(f"{L.name:10s} {f'{L.rows}x{L.cols}':>12s} "
              f"{f'{L.base_R}x{L.base_C}':>8s} {f'{L.R}x{L.C}':>8s} "
              f"{L.tiles:6d} {L.R:6d} {L.C:6d} {L.macs:12,d} "
              f"{f'[{on},{off})':>16s}")

    print(f"\nt_period {t_period}   trunk MACs {total_macs:,}")
    for L, d in zip(TRUNK, durations):
        print(f"  {L.name:10s} {d:8d} cycles  ({100*L.macs/total_macs:5.1f}% of MACs)"
              f"  {d/DP_CYCLE:5.2f} x DP_CYCLE")
    sim = SIM_DP_CYCLES * DP_CYCLE
    warm = WARMUP_DP_CYCLES * DP_CYCLE
    print(f"  sweep WARMUP {warm} SIM {sim}"
          f"  -> {sim/t_period:.1f} block passes measured"
          f"  (warmup covers {warm/t_period:.2f})")

    by_class = defaultdict(int)
    by_phase = defaultdict(int)
    for r in rows:
        by_class[r["kind"]] += r["bytes"]
        by_phase[r["phase"]] += r["bytes"]
    print(f"\nrows {len(rows)}   total volume {sum(r['bytes'] for r in rows):,} bytes"
          f"   {sum(r['packets'] for r in rows):,} packets")
    for k, v in sorted(by_class.items(), key=lambda kv: -kv[1]):
        print(f"  class {k:16s} {v:12,d} bytes")
    for k, v in sorted(by_phase.items(), key=lambda kv: -kv[1]):
        print(f"  phase {k:16s} {v:12,d} bytes")

    print(f"\nmax cumulative pir (per phase)   {worst[1]:.4f} at node {worst[0][0]}"
          f" phase {worst[0][1]}")
    print(f"max cumulative pir (with overlap) {worst_stacked[1]:.4f} at node "
          f"{worst_stacked[0][0]} phase {worst_stacked[0][1]}")

    for w in warns:
        print(f"WARN  {w}")
    for e in errs:
        print(f"ERROR {e}")
    print(f"\nwrote {base}.txt (+ _volume/_flows/_placement.csv)")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
