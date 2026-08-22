#!/usr/bin/env python3
"""
Stage 2 traffic-table core engine -- model-agnostic.

Extracted from stage2_dnn_traffic.py (the frozen ResNet converter) so that the
transformer and VGG converters share its EXACT conventions -- crossbar/grid tiling,
box placement, scatter/reduce mechanics, MAC-proportional phases, and the
pir/window row formula -- by construction rather than by copy-paste discipline.

A thin model module supplies only its shape/placement/residual config and calls
`run(model)`:

    MODEL_TAG   str
    XB          int                    crossbar dimension (XB x XB)
    FMAP_H, FMAP_W  int                "feature map"; HW = FMAP_H*FMAP_W multiplies
                                       every activation/psum volume (seq,1 for a
                                       transformer)
    LAYERS      [(name,k,Cin,Cout,kind)]   kind: "conv" trunk | "shortcut" proj branch
    CONFIGS     {mesh: {dims,(grid),(boxes)}}   per-mesh grid + placement boxes
    RESIDUALS   [{name,type,from,add_at,span[,layer]}]   see build_flows

The single ResNet projection shortcut generalises to a RESIDUALS list carrying two
residual types:
  - "proj":     a weighted branch (its own tiles): scatter -> reduce -> add
  - "identity": weight-free bypass (no tiles): donor accs -> add, traffic only

`stage2_resnet.py` reproduces stage2_dnn_traffic.py's output byte-for-byte (data
rows + CSVs), which is the regression gate for this extraction.

python3 stdlib only.
"""

import csv
import math
import os
import sys
from collections import defaultdict


def _env(name, default, cast=str):
    v = os.environ.get(name)
    return default if v is None or v == "" else cast(v)


# =============================================================================
# Shared conventions -- identical across all workloads (the reason for a core)
# =============================================================================

BYTES_PER_ACT = 1           # INT8 activations
BYTES_PER_PSUM = 4          # INT32 partial sums -- 4x activation width
FLIT_BYTES = 4
PACKET_FLITS = 16           # must match the simulator's `-size 16 16`
PACKET_BYTES = FLIT_BYTES * PACKET_FLITS

CYCLES_PER_MAC = _env("DNN_CYCLES_PER_MAC", 6.5e-5, float)
SIM_DP_CYCLES = _env("SIM_DP_CYCLES", 80, int)
WARMUP_DP_CYCLES = _env("WARMUP_DP_CYCLES", 3, int)
LOAD_SCALE = _env("DNN_LOAD_SCALE", 0.05, float)
OUTDIR = _env("DNN_TABLE_DIR", "traffics_dnn")
TABLE_STEM = _env("DNN_TABLE_STEM", "")
MESH = _env("DNN_MESH", "6x6x3")

# Filled in by configure(model):
MODEL_TAG = XB = FMAP_H = FMAP_W = HW = None
DIMX = DIMY = DIMZ = NODES = DIAMETER = DP_CYCLE = None
GRID_OVERRIDE = BOXES = None
LAYERS = LAYER = TRUNK = RESIDUALS = DEPS = None


# =============================================================================
# Geometry
# =============================================================================

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
        """Input-CHANNEL range covered by row-group r (channel = row // (k*k))."""
        lo, hi = self.row_groups[r]
        kk = self.k * self.k
        return (lo // kk, math.ceil(hi / kk))

    def out_ch_range(self, c):
        return self.col_groups[c]

    def acc(self, c):
        """Accumulator node for column-group c: the r=0 tile of that column."""
        return self.node[(0, c)]

    def accs(self):
        return [(self.acc(c), self.out_ch_range(c)) for c in range(self.C)]


# =============================================================================
# Configuration -- bind a model module into the module globals
# =============================================================================

def configure(model):
    global MODEL_TAG, XB, FMAP_H, FMAP_W, HW
    global DIMX, DIMY, DIMZ, NODES, DIAMETER, DP_CYCLE
    global GRID_OVERRIDE, BOXES, LAYERS, LAYER, TRUNK, RESIDUALS, DEPS, CYCLES_PER_MAC

    if os.environ.get("DNN_CYCLES_PER_MAC") in (None, "") and hasattr(model, "CYCLES_PER_MAC"):
        CYCLES_PER_MAC = model.CYCLES_PER_MAC
    MODEL_TAG = model.MODEL_TAG
    XB = model.XB
    FMAP_H, FMAP_W = model.FMAP_H, model.FMAP_W
    HW = FMAP_H * FMAP_W
    LAYERS = model.LAYERS
    RESIDUALS = getattr(model, "RESIDUALS", [])
    # {layer: [producer, ...]}, producer = a trunk layer name or "block_input".
    # Absent => strict chain in LAYERS order (ResNet/VGG, unchanged).
    DEPS = getattr(model, "DEPS", None)

    assert MESH in model.CONFIGS, f"DNN_MESH={MESH} not in {sorted(model.CONFIGS)}"
    cfg = model.CONFIGS[MESH]
    DIMX, DIMY, DIMZ = cfg["dims"]
    GRID_OVERRIDE = cfg["grid"]
    BOXES = cfg["boxes"]

    NODES = DIMX * DIMY * DIMZ
    DIAMETER = (DIMX - 1) + (DIMY - 1) + (DIMZ - 1)
    DP_CYCLE = NODES * (math.ceil(DIAMETER/4) + 3)      # NoximDefs.h / FINDINGS.md method

    LAYER = {name: Layer(name, k, cin, cout, kind)
             for (name, k, cin, cout, kind) in LAYERS}
    TRUNK = [LAYER[n] for (n, _, _, _, kind) in LAYERS if kind == "conv"]


# =============================================================================
# Placement -- clustered box per layer, z-fastest so intra-layer crosses TSVs
# =============================================================================

def place():
    used = {}
    for L in LAYER.values():
        if L.tiles == 0:
            continue
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
# Phases -- strictly sequential trunk phases sized in proportion to MACs
# =============================================================================

def build_phases():
    # Trunk levels: layers whose dependencies are all met run concurrently in one
    # window.  Each keeps its OWN t_off (it injects over its own compute time);
    # the level advances by its slowest member (barrier semantics).  Without DEPS
    # every level holds one layer, i.e. the original strict chain.
    if DEPS is None:
        levels = [[L] for L in TRUNK]
    else:
        lv = {}
        for L in TRUNK:                      # LAYERS order must be topological
            preds = [p for p in DEPS[L.name] if p != "block_input"]
            lv[L.name] = 1 + max((lv[p] for p in preds), default=-1)
        levels = [[L for L in TRUNK if lv[L.name] == i]
                  for i in range(max(lv.values()) + 1)]

    dur, bounds, t = {}, [], 0
    for grp in levels:
        ds = {L.name: max(1, int(L.macs * CYCLES_PER_MAC)) for L in grp}
        for L in grp:
            bounds.append((L.name, t, t + ds[L.name]))
            dur[L.name] = ds[L.name]
        t += max(ds.values())
    total = t
    durations = [dur[L.name] for L in TRUNK]      # keeps zip(TRUNK, durations)
    phases = {name: (on, off) for (name, on, off) in bounds}

    # A residual runs in parallel with the sublayers it bypasses: its window
    # spans from the first to the last trunk layer of its span.  ResNet's single
    # shortcut spans the whole block -> (0, total), unchanged.
    for res in RESIDUALS:
        first, last = res["span"]
        phases[res["name"]] = (phases[first][0], phases[last][1])

    t_period = total + 1                     # loader requires t_period > t_off
    return phases, t_period, durations


# =============================================================================
# Flows -- integer bytes keyed by (src, dst, phase); packets computed once
# =============================================================================

def build_flows():
    vol = defaultdict(int)
    cls = defaultdict(lambda: defaultdict(int))

    def add(src, dst, phase, nbytes, kind):
        if src == dst or nbytes <= 0:
            return
        vol[(src, dst, phase)] += nbytes
        cls[(src, dst, phase)][kind] += nbytes

    # The block's input tensor lives on the first trunk layer's column-0 tiles,
    # partitioned by its row-groups.  Both that layer's fan-out and any residual
    # bypass read from these same holders.
    first = TRUNK[0]
    holders = [(first.node[(r, 0)], first.in_ch_range(r)) for r in range(first.R)]

    def scatter_from(producers, L, phase):
        """Deliver producer output channels to every tile of L that needs them."""
        for r in range(L.R):
            need = L.in_ch_range(r)
            for (pnode, prange) in producers:
                n = overlap(need, prange)
                if n == 0:
                    continue
                for c in range(L.C):
                    add(pnode, L.node[(r, c)], phase, n * HW * BYTES_PER_ACT, "scatter")

    def reduce_within(L, phase):
        """Every (r,c) ships its partial sum up to the column accumulator (0,c)."""
        for c in range(L.C):
            lo, hi = L.out_ch_range(c)
            nbytes = (hi - lo) * HW * BYTES_PER_PSUM
            for r in range(1, L.R):
                add(L.node[(r, c)], L.acc(c), phase, nbytes, "reduce")

    def donors_of(spec):
        """Producers a residual reads from: block input, or a named layer's accs."""
        if spec == "block_input":
            return holders
        return LAYER[spec].accs()

    # --- trunk DAG -----------------------------------------------------------
    for i, L in enumerate(TRUNK):
        srcs = (["block_input"] if i == 0 else [TRUNK[i - 1].name]) \
            if DEPS is None else DEPS[L.name]
        for spec in srcs:
            # a handoff rides the PRODUCER's window; block input rides the
            # consumer's own window
            scatter_from(donors_of(spec), L,
                         L.name if spec == "block_input" else spec)
        reduce_within(L, L.name)

    # --- residual adds -------------------------------------------------------
    for res in RESIDUALS:
        ph = res["name"]
        if res["type"] == "proj":
            S = LAYER[res["layer"]]
            scatter_from(donors_of(res["from"]), S, ph)
            reduce_within(S, ph)
            donors = S.accs()
        elif res["type"] == "identity":
            donors = donors_of(res["from"])          # weight-free bypass, no tiles
        else:
            raise ValueError(f"unknown residual type {res['type']}")

        sink = LAYER[res["add_at"]]
        for (dnode, drange) in donors:
            for c in range(sink.C):
                n = overlap(drange, sink.out_ch_range(c))
                if n:
                    add(dnode, sink.acc(c), ph, n * HW * BYTES_PER_ACT, "add")

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

    for r in rows:
        if not (0 <= r["src"] < NODES and 0 <= r["dst"] < NODES):
            errs.append(f"node id out of range: {r['src']}->{r['dst']}")
        if r["src"] == r["dst"]:
            errs.append(f"self traffic at {r['src']}")
        if not (0 <= r["pir"] <= 1):
            errs.append(f"pir out of [0,1]: {r['pir']:.4f} {r['src']}->{r['dst']}")
        if float(f"{r['pir']:.10f}") == 0.0:
            errs.append(f"pir {r['pir']:.3e} underflows to 0 at %.10f "
                        f"({r['src']}->{r['dst']}) -- LOAD_SCALE too small")
        if not r["t_off"] > r["t_on"]:
            errs.append("assert t_off > t_on would fire")
        if not r["t_period"] > r["t_off"]:
            errs.append("assert t_period > t_off would fire")

    # -- cumulative pir per source, per phase --------------------------------
    cum = defaultdict(float)
    for r in rows:
        cum[(r["src"], r["phase"])] += r["pir"]
    worst = max(cum.items(), key=lambda kv: kv[1]) if cum else ((None, None), 0.0)

    # Anything whose window overlaps a trunk phase stacks against it -- residuals
    # as before, and now also trunk layers that run concurrently (a DEPS DAG).
    stacked = defaultdict(float)
    for (src, phase), v in cum.items():
        p_on, p_off = phases[phase]
        for tl in TRUNK:
            t_on, t_off = phases[tl.name]
            if t_on < p_off and p_on < t_off:
                stacked[(src, tl.name)] += v
    worst_stacked = max(stacked.items(), key=lambda kv: kv[1]) if stacked else \
        ((None, None), 0.0)
    if worst_stacked[1] > 1.0:
        errs.append(
            f"cumulative pir {worst_stacked[1]:.3f} > 1 at node {worst_stacked[0][0]} "
            f"in phase {worst_stacked[0][1]} -- raise CYCLES_PER_MAC or lower LOAD_SCALE")

    for L, d in zip(TRUNK, durations):
        if d < DP_CYCLE:
            warns.append(f"phase {L.name} is {d} cycles < DP_CYCLE {DP_CYCLE} "
                         f"-- DP cannot converge inside this phase")

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

    with open(base + ".txt", "w") as f:
        f.write(f"% {MODEL_TAG}  crossbar {XB}x{XB}  mesh {mesh} ({NODES} nodes)\n")
        f.write(f"% generated by stage2_core.py -- see STAGE2.md\n")
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
        for r in rows:
            f.write(f"{r['src']:5d} {r['dst']:5d} {r['pir']:.10f} {r['por']:.10f} "
                    f"{r['t_on']:8d} {r['t_off']:8d} {r['t_period']:8d}\n")

    mat = [[0] * NODES for _ in range(NODES)]
    for r in rows:
        mat[r["src"]][r["dst"]] += r["bytes"]
    with open(base + "_volume.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["src\\dst"] + list(range(NODES)))
        for s in range(NODES):
            w.writerow([s] + mat[s])

    with open(base + "_flows.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["src", "dst", "phase", "class", "bytes", "packets",
                    "window", "pir", "t_on", "t_off", "t_period"])
        for r in rows:
            w.writerow([r["src"], r["dst"], r["phase"], r["kind"], r["bytes"],
                        r["packets"], r["window"], f"{r['pir']:.10f}",
                        r["t_on"], r["t_off"], r["t_period"]])

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

def run(model):
    configure(model)
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
    for r in rows:
        by_class[r["kind"]] += r["bytes"]
    print(f"\nrows {len(rows)}   total volume {sum(r['bytes'] for r in rows):,} bytes"
          f"   {sum(r['packets'] for r in rows):,} packets")
    ident = sum(1 for res in RESIDUALS if res["type"] == "identity")
    if ident:
        print(f"identity residuals (zero tiles, traffic only): {ident}")
    for k, v in sorted(by_class.items(), key=lambda kv: -kv[1]):
        print(f"  class {k:16s} {v:12,d} bytes")

    for w in warns:
        print(f"WARN  {w}", file=sys.stderr)
    if errs:
        for e in errs:
            print(f"ERROR {e}", file=sys.stderr)
        sys.exit(1)
    return base
