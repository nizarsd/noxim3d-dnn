#!/usr/bin/env python3
"""
Stage 2 traffic-table converter -- WHOLE NETWORKS on a fixed 7x7x3 mesh.

Generalises stage2_dnn_traffic.py (single ResNet-50 bottleneck block, 1 crossbar
per node) to complete networks under the SS9.3a/b/c tile model.  The single-block
converter and its traffics_dnn/resnet50_bottleneck3_* artefacts remain valid and
are untouched -- they are the high-fidelity spatial reference (zero tile
quantisation), this is the temporally rich case.

WHAT IS NEW RELATIVE TO THE BLOCK CONVERTER
-------------------------------------------
  * Per-workload hardware: crossbar size, crossbars-per-tile and N_bits are
    WORKLOAD parameters, not globals (STAGE2.md SS9.3c).  The NoC is identical in
    every case -- only partitioning granularity varies, and the simulator does not
    model tile internals.

  * Weight precision.  Krishnan JETC Eq.2, with N_bits on the COLUMN term:
        crossbars = ceil((k*k*Cin) / PE_x) * ceil((Cout * N_bits) / PE_y)
    8-bit weights on 1-bit cells need 8 physical columns per logical column.

  * A TILE HOLDS MANY CROSSBARS.  The crossbar grid R x C is covered by tiles of
    tr x tc crossbars (tr*tc <= XB_PER_TILE).  Only INTER-TILE edges are NoC
    traffic; intra-tile partial sums are bus/H-tree work (SS9.3a) and are free.
    Tiling policy: FILL THE REDUCTION AXIS FIRST (tr as large as possible).
    Physically motivated -- it keeps the dense psum traffic inside the tile --
    and it is the only policy of the three tried that fits 7x7x3.
    Consequence: a layer whose whole grid fits one tile emits NO intra-layer
    traffic.  That is the truth of the architecture at this density, not a bug;
    25 of ResNet-50's 54 layers are in that class.

  * Identity shortcuts carry NO crossbars but DO carry traffic (block input ->
    add point).  These are the long-range non-local flows.

CARRIED OVER UNCHANGED from the block converter
------------------------------------------------
  Blocked/clustered placement via coord2Id; row split = partial-sum reduction and
  column split = input fan-out (both axes); fan-out as SOURCE REPLICATION (one
  unicast row per dst, same src, same window -- SS9.4, no simulator change);
  MAC-proportional layer durations with strict sequential firing; global
  LOAD_SCALE on pir; integer-byte volume accumulation so the table and the volume
  matrix agree exactly; packet size global via `-size 16 16`, never per row.

  !! TIMING IS A FIRST-ORDER ESTIMATE, not a validated performance model.  It has
     no crossbar latency, ADC cost, memory bandwidth or pipeline fill.  It fixes
     the RELATIVE ordering and rough proportions of phases; absolute scale is a
     free knob (CYCLES_PER_MAC).  Do not quote it as a performance result.

python3 stdlib only.  Usage:  python3 stage2_dnn_full.py [--workload NAME]
"""

import argparse
import csv
import math
import os
from collections import defaultdict


def _env(name, default, cast=str):
    v = os.environ.get(name)
    return default if v is None or v == "" else cast(v)


# =============================================================================
# MESH -- fixed for every workload (STAGE2.md SS9.3c)
# =============================================================================

DIMX, DIMY, DIMZ = 7, 7, 3
NODES = DIMX * DIMY * DIMZ                  # 147
DIAMETER = (DIMX - 1) + (DIMY - 1) + (DIMZ - 1)
DP_CYCLE = 2 * NODES * (DIAMETER + 3)       # NoximDefs.h / FINDINGS.md method

# --- data sizes ---------------------------------------------------------------
BYTES_PER_ACT = 1           # INT8 activations
BYTES_PER_PSUM = 4          # INT32 partial sums -- 4x the activation width, which
                            # is why reduce traffic dominates volume
FLIT_BYTES = 4
PACKET_FLITS = 16           # must match the simulator's `-size 16 16`
PACKET_BYTES = FLIT_BYTES * PACKET_FLITS

# --- timing / load ------------------------------------------------------------
CYCLES_PER_MAC = _env("DNN_CYCLES_PER_MAC", 1.3e-4, float)
SIM_DP_CYCLES = _env("SIM_DP_CYCLES", 80, int)
WARMUP_DP_CYCLES = _env("WARMUP_DP_CYCLES", 3, int)
LOAD_SCALE = _env("DNN_LOAD_SCALE", 0.05, float)
OUTDIR = _env("DNN_TABLE_DIR", "traffics_dnn")
TABLE_STEM = _env("DNN_TABLE_STEM", "")

# Krishnan Eq.3 sanity bound: flag if the swept load implies an absurd frame rate.
FPS_WARN = 1e5
# Accelerator clock assumed only for the implied-FPS report (Eq.3), nothing else.
FREQ_HZ = _env("DNN_FREQ_HZ", 1e9, float)

# Phase-duration floor in cycles; see build_phases().  Default DP_CYCLE so every
# phase reaches DP's converged regime.  0 disables the floor.
MIN_PHASE = _env("DNN_MIN_PHASE", DP_CYCLE, int)


# =============================================================================
# LAYER TABLES -- one per model, hardcoded (python3 stdlib only, no PyTorch)
# =============================================================================
# Each entry: (name, k, Cin, Cout, out_H, out_W, kind, group)
#   kind:  "conv"     sequential trunk layer, fires in its own phase
#          "proj"     projection shortcut -- HAS crossbars, parallel branch
#          "identity" identity shortcut   -- NO crossbars, traffic only
#   group: block id, used to scope shortcut windows and residual adds

def resnet50_layers():
    """ResNet-50: stem, stages [3,4,6,3] widths 64/128/256/512, expansion 4, FC.

    Projection shortcut on the FIRST block of each stage (dimensions change),
    identity on the rest.  Feature maps: 112 (stem), 56, 28, 14, 7.
    Stride-2 lives on the 3x3 conv of the first block of stages 2-4.
    """
    L = [("stem", 7, 3, 64, 112, 112, "conv", "stem")]
    cin, hw = 64, 56                       # after maxpool
    for s, (n, w) in enumerate(zip([3, 4, 6, 3], [64, 128, 256, 512]), 1):
        out = w * 4
        for b in range(n):
            g = f"s{s}b{b}"
            # first block of stages 2..4 halves the map on its 3x3
            hw_out = hw // 2 if (b == 0 and s > 1) else hw
            L += [(f"{g}_c1", 1, cin, w,   hw,     hw,     "conv", g),
                  (f"{g}_c2", 3, w,   w,   hw_out, hw_out, "conv", g),
                  (f"{g}_c3", 1, w,   out, hw_out, hw_out, "conv", g)]
            if b == 0:
                L.append((f"{g}_sc", 1, cin, out, hw_out, hw_out, "proj", g))
            else:
                L.append((f"{g}_sc", 1, cin, out, hw_out, hw_out, "identity", g))
            cin, hw = out, hw_out
    L.append(("fc", 1, 2048, 1000, 1, 1, "conv", "fc"))
    return L


def transformer_layers(nblk=12, d=768, ff=3072, seq=197):
    """12 encoder blocks (BERT/ViT-Base).  seq = token count = the 'feature map'.

    !! INCOMPLETE -- NO RESIDUAL CONNECTIONS.  A real encoder block has a residual
       around the attention sublayer and another around the FFN sublayer: 2 per
       block, 24 across 12 blocks.  They are omitted here, so this table models a
       pure sequential chain.

       Consequence: the transformer's non-locality is UNDERSTATED.  Those residuals
       are long-range flows, the direct analogue of ResNet-50's 12 identity
       shortcuts (which measure mean hop 3.78 vs 3.53 for every other flow in its
       table).  DP beats bufferlevel precisely by seeing congestion several hops
       out, so judging this workload as written would hand DP a weaker stimulus
       than the architecture actually presents.

       FIX BEFORE RUNNING ANY TRANSFORMER SIMULATION: add the 24 residuals the same
       way ResNet's identity shortcuts are done -- kind="identity", zero crossbars,
       traffic only, window spanning the sublayer they bypass.
    """
    L = []
    for b in range(nblk):
        g = f"b{b}"
        for nm in ("q", "k", "v", "o"):
            L.append((f"{g}_{nm}", 1, d, d, seq, 1, "conv", g))
        L.append((f"{g}_ff1", 1, d, ff, seq, 1, "conv", g))
        L.append((f"{g}_ff2", 1, ff, d, seq, 1, "conv", g))
    return L


def vgg16_layers():
    cfg = [(3, 64, 224), (64, 64, 224), (64, 128, 112), (128, 128, 112),
           (128, 256, 56), (256, 256, 56), (256, 256, 56),
           (256, 512, 28), (512, 512, 28), (512, 512, 28),
           (512, 512, 14), (512, 512, 14), (512, 512, 14)]
    L = [(f"conv{i}", 3, a, b, h, h, "conv", f"c{i}")
         for i, (a, b, h) in enumerate(cfg, 1)]
    L += [("fc6", 1, 25088, 4096, 1, 1, "conv", "fc"),
          ("fc7", 1, 4096, 4096, 1, 1, "conv", "fc"),
          ("fc8", 1, 4096, 1000, 1, 1, "conv", "fc")]
    return L


# =============================================================================
# WORKLOADS (STAGE2.md SS9.3c, tile counts revised to per-layer allocation)
# =============================================================================
# expect_xb / expect_tiles are ASSERTED so a bad edit fails loudly.

WORKLOADS = {
    "resnet50_full": dict(
        tag="resnet50_full", PE_X=128, PE_Y=128, N_BITS=8, XB_PER_TILE=120,
        layers=resnet50_layers, expect_xb=12504, expect_tiles=147),
    "transformer_12blk": dict(
        tag="transformer_12blk", PE_X=256, PE_Y=256, N_BITS=8, XB_PER_TILE=96,
        layers=transformer_layers, expect_xb=10368, expect_tiles=None),
    "vgg16_full": dict(
        tag="vgg16_full", PE_X=256, PE_Y=256, N_BITS=8, XB_PER_TILE=128,
        layers=vgg16_layers, expect_xb=16912, expect_tiles=None),
}


# =============================================================================
# Geometry helpers
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
    """One DNN layer: crossbar grid -> tile grid -> node ids.

    Two grids matter and must not be confused:
      R  x C   crossbars  -- the physical partition (Krishnan Eq.2)
      Rt x Ct  TILES      -- what the NoC actually sees; one node per tile
    Traffic is generated on the TILE grid.  A tile covering tr x tc crossbars
    absorbs those partial sums internally (SS9.3a: bus/H-tree, not NoC).
    """

    def __init__(self, spec, hw):
        (self.name, self.k, self.cin, self.cout,
         self.oh, self.ow, self.kind, self.group) = spec
        self.hw = hw                                  # hardware dict
        PE_X, PE_Y, NB, PT = hw["PE_X"], hw["PE_Y"], hw["N_BITS"], hw["XB_PER_TILE"]

        self.rows = self.k * self.k * self.cin        # im2col rows
        self.pcols = self.cout * NB                   # PHYSICAL columns (bit-sliced)
        self.macs = self.k * self.k * self.cin * self.cout * self.oh * self.ow

        if self.kind == "identity":
            # weight-free: no crossbars, no tiles, traffic only
            self.R = self.C = self.Rt = self.Ct = 0
            self.crossbars = self.tiles = 0
            self.row_groups = self.col_groups = []
            self.node = {}
            return

        self.R = math.ceil(self.rows / PE_X)
        self.C = math.ceil(self.pcols / PE_Y)
        self.crossbars = self.R * self.C

        # --- tiling: fill the reduction axis first ---------------------------
        self.tr = min(self.R, PT)
        self.tc = max(1, PT // self.tr)
        self.Rt = math.ceil(self.R / self.tr)
        self.Ct = math.ceil(self.C / self.tc)
        self.tiles = self.Rt * self.Ct

        # Bit-planes of one output channel must not straddle a column group, or
        # the shift-and-add would become inter-tile traffic this model omits.
        assert PE_Y % NB == 0, f"PE_Y {PE_Y} not a multiple of N_bits {NB}"

        self.row_groups = split_ranges(self.rows, self.Rt)
        self.col_groups = split_ranges(self.pcols, self.Ct)
        self.node = {}                                # (rt, ct) -> node id

    # -- channel mapping -------------------------------------------------------
    def in_ch_range(self, rt):
        """Input-CHANNEL range of row-tile rt.

        im2col row order is channel-major, kernel-position minor, so
        channel = row // (k*k).  Widened to the enclosing channel range so
        producer/consumer matching stays correct across different splits.
        """
        lo, hi = self.row_groups[rt]
        kk = self.k * self.k
        return (lo // kk, math.ceil(hi / kk))

    def out_ch_range(self, ct):
        """Output-CHANNEL range of column-tile ct (physical cols / N_bits)."""
        lo, hi = self.col_groups[ct]
        nb = self.hw["N_BITS"]
        return (lo // nb, math.ceil(hi / nb))

    def acc(self, ct):
        """Accumulator node of column-tile ct: its rt=0 tile."""
        return self.node[(0, ct)]

    def accs(self):
        return [(self.acc(ct), self.out_ch_range(ct)) for ct in range(self.Ct)]

    def act_bytes(self, nchan):
        return nchan * self.oh * self.ow * BYTES_PER_ACT


# =============================================================================
# Placement -- clustered, TSV-crossing, deliberately unoptimised
# =============================================================================

def place(layers):
    """Give each weighted layer a CONTIGUOUS run of nodes in z-fastest order.

    Cell order is z fastest, then x, then y -- so consecutive tiles of a layer
    land on VERTICAL neighbours and intra-layer exchange actually crosses TSVs.
    Sequential ids would walk X and reach the Z neighbour only after DIMX*DIMY
    steps, leaving the 3D findings dormant (STAGE2.md SS9.2).

    With 54 layers averaging under 3 tiles each, per-layer rectangular boxes are
    not packable; a contiguous run in this order is the clustering that survives.

    NOTE: deliberately UNOPTIMISED.  Congestion-aware placement is excluded on
    purpose -- it would confound "does DNN traffic behave differently" with
    "does smart mapping help".
    """
    order = []
    for y in range(DIMY):
        for x in range(DIMX):
            for z in range(DIMZ):
                order.append(coord2id(x, y, z))

    used, i = {}, 0
    for L in layers:
        if L.tiles == 0:
            continue
        assert i + L.tiles <= NODES, (
            f"out of nodes at {L.name}: need {L.tiles}, {NODES - i} left "
            f"(total tiles exceed the {NODES}-node mesh)")
        for t in range(L.tiles):
            nid = order[i + t]
            assert nid not in used, f"node {nid} claimed twice"
            used[nid] = L.name
            L.node[(t // L.Ct, t % L.Ct)] = nid
        i += L.tiles
    return used, i


# =============================================================================
# Phases -- strictly sequential, MAC-proportional
# =============================================================================

def build_phases(layers):
    """One phase per weighted trunk layer, duration proportional to MACs.

    Crossbars within a layer run in parallel, so tile count is the wrong proxy;
    H*W alone ignores that a 3x3 does 9x the work per position of a 1x1.

    The traffic-table gate is STRICT on both ends (TGlobalTrafficTable.cpp:116):
        r = ccycle % t_period;  on iff t_on < r < t_off
    and the loader asserts t_off > t_on and t_period > t_off, so the last phase
    must end strictly before t_period and one cycle is lost per boundary.
    """
    trunk = [L for L in layers if L.kind == "conv"]

    # Phase-duration FLOOR (time compression).  A whole network's layers span ~58x
    # in MACs, so pure MAC-proportional timing forces a choice between a t_period
    # the run cannot cover and phases too short for DP to converge in.  Flooring
    # only the short phases keeps the big ones MAC-proportional -- strictly better
    # than a power law, which has to inflate everything to lift the shortest.
    #
    # MIN_PHASE = DP_CYCLE puts every phase in DP's CONVERGED regime.  Set it to 0
    # to measure DP's transient instead (the regime the Stage 6 phase-indexed
    # baseline targets).  Note the floor cannot take t_period below
    # len(trunk) * MIN_PHASE.
    #
    # Compression also RAISES offered load: pir = LOAD_SCALE * packets / window,
    # so a shorter window injects the same packets faster.  Re-find the knee after
    # changing this.
    durations = [max(1, int(L.macs * CYCLES_PER_MAC)) for L in trunk]
    if MIN_PHASE > 0:
        durations = [max(MIN_PHASE, d) for d in durations]

    phases, t = {}, 0
    for L, d in zip(trunk, durations):
        phases[L.name] = (t, t + d)
        t += d
    total = t

    # A shortcut (projection or identity) spans its whole block: it reads the
    # block input that conv1 reads, and its result is not needed until the
    # residual add at the end of conv3.
    for L in layers:
        if L.kind in ("proj", "identity"):
            mem = [x.name for x in trunk if x.group == L.group]
            if mem:
                phases[L.name] = (phases[mem[0]][0], phases[mem[-1]][1])
            else:
                phases[L.name] = (0, total)
    return phases, total + 1, durations, trunk


# =============================================================================
# Flows -- integer bytes keyed by (src, dst, phase); packets computed once
# =============================================================================

def build_flows(layers, phases):
    vol = defaultdict(int)
    cls = defaultdict(lambda: defaultdict(int))

    def add(src, dst, phase, nbytes, kind):
        if src == dst or nbytes <= 0:
            return
        vol[(src, dst, phase)] += nbytes
        cls[(src, dst, phase)][kind] += nbytes

    def scatter_from(producers, L, phase):
        """Deliver producer output channels to every tile of L that needs them.

        Covers BOTH the inter-layer handoff and the consumer's intra-layer
        fan-out: a producer feeding row-tile rt must send to all Ct tiles of that
        row, so fan-out falls out as one unicast row per destination -- source
        replication (SS9.4).  Matched on channel ranges, so producer and consumer
        may use different splits.
        """
        if L.tiles == 0:
            return
        for rt in range(L.Rt):
            need = L.in_ch_range(rt)
            for pnode, prange in producers:
                n = overlap(need, prange)
                if n == 0:
                    continue
                for ct in range(L.Ct):
                    add(pnode, L.node[(rt, ct)], phase, L.act_bytes(n), "scatter")

    def reduce_within(L, phase):
        """Every (rt,ct) ships its partial sum to the column accumulator (0,ct).

        Flat all-to-one: the accumulator takes Rt-1 simultaneous incoming INT32
        flows -- the sharpest hotspot in the layer, and the structure DP's
        multi-hop cost field should handle better than BL's one-hop view.
        Nothing is emitted when Rt == 1: those partial sums are intra-tile.
        """
        if L.tiles == 0:
            return
        for ct in range(L.Ct):
            lo, hi = L.out_ch_range(ct)
            nbytes = (hi - lo) * L.oh * L.ow * BYTES_PER_PSUM
            for rt in range(1, L.Rt):
                add(L.node[(rt, ct)], L.acc(ct), phase, nbytes, "reduce")

    by_name = {L.name: L for L in layers}
    trunk = [L for L in layers if L.kind == "conv"]

    # --- the network's input has to live somewhere ---------------------------
    # Taken as resident on the first trunk layer's column-0 tiles, partitioned by
    # its row-tiles -- the same convention the block converter uses.
    first = trunk[0]
    src_of = [(first.node[(rt, 0)], first.in_ch_range(rt)) for rt in range(first.Rt)]

    # --- trunk chain ---------------------------------------------------------
    prev_out = src_of
    for i, L in enumerate(trunk):
        ph = L.name
        scatter_from(prev_out, L, ph)
        reduce_within(L, ph)
        prev_out = L.accs()

        # residual add at the end of a block: shortcut -> this layer's accs
        sc = by_name.get(f"{L.group}_sc")
        if sc is not None and L.name.endswith("_c3"):
            members = [x for x in trunk if x.group == L.group]
            blk_in = block_input(members, trunk, src_of)
            if sc.kind == "proj":
                # projection owns crossbars: scatter -> reduce -> add
                scatter_from(blk_in, sc, sc.name)
                reduce_within(sc, sc.name)
                donors = sc.accs()
            else:
                # identity: NO crossbars, but the traffic is real and long-range
                donors = blk_in
            for dnode, drange in donors:
                for ct in range(L.Ct):
                    n = overlap(drange, L.out_ch_range(ct))
                    if n:
                        add(dnode, L.acc(ct), sc.name, L.act_bytes(n), "add")

    return vol, cls


def block_input(members, trunk, src_of):
    """Producers feeding a block: the accumulators of the layer before its c1."""
    first_of_block = members[0]
    idx = trunk.index(first_of_block)
    if idx == 0:
        return src_of
    return trunk[idx - 1].accs()


# =============================================================================
# Rows
# =============================================================================

def build_rows(vol, cls, phases, t_period):
    rows = []
    for (src, dst, phase), nbytes in sorted(vol.items()):
        t_on, t_off = phases[phase]
        window = t_off - t_on - 1                  # strict gate on both ends
        assert window > 0, f"phase {phase} has no open window"
        packets = math.ceil(nbytes / PACKET_BYTES)
        pir = LOAD_SCALE * packets / window
        rows.append(dict(src=src, dst=dst, pir=pir, por=pir,
                         t_on=t_on, t_off=t_off, t_period=t_period,
                         phase=phase, kind="+".join(sorted(cls[(src, dst, phase)])),
                         bytes=nbytes, packets=packets, window=window))
    return rows


# =============================================================================
# Validation
# =============================================================================

def validate(rows, placed, phases, durations, trunk, layers, hw):
    errs, warns = [], []

    # -- loader contract (TGlobalTrafficTable.cpp) ----------------------------
    for r in rows:
        if not (0 <= r["src"] < NODES and 0 <= r["dst"] < NODES):
            errs.append(f"node id out of range: {r['src']}->{r['dst']}")
        if r["src"] == r["dst"]:
            errs.append(f"self traffic at {r['src']}")
        if not (0 <= r["pir"] <= 1):
            errs.append(f"pir out of [0,1]: {r['pir']:.4f} {r['src']}->{r['dst']}")
        # a flow whose pir rounds to 0 at the emitted precision loads but never fires
        if float(f"{r['pir']:.10f}") == 0.0:
            errs.append(f"pir {r['pir']:.3e} underflows to 0 at %.10f "
                        f"({r['src']}->{r['dst']}) -- LOAD_SCALE too small")
        if not r["t_off"] > r["t_on"]:
            errs.append("assert t_off > t_on would fire")
        if not r["t_period"] > r["t_off"]:
            errs.append("assert t_period > t_off would fire")

    # -- cumulative pir per source, per OVERLAPPING window ---------------------
    # getCumulativePirPor sums pir over every row whose src matches and whose
    # window is open; the PE compares one uniform draw against that sum, so it
    # must not exceed 1 or the flow mix is silently clipped.  Shortcut windows
    # span their whole block, so they stack on top of the trunk phases.
    win = {name: phases[name] for name in phases}
    cum = defaultdict(float)
    for r in rows:
        cum[(r["src"], r["phase"])] += r["pir"]

    stacked = defaultdict(float)
    for (src, phase), v in cum.items():
        on, off = win[phase]
        for L in trunk:                       # attribute to every trunk phase it covers
            t_on, t_off = win[L.name]
            if on < t_off and t_on < off:     # windows intersect
                stacked[(src, L.name)] += v
    worst = max(stacked.items(), key=lambda kv: kv[1]) if stacked else ((None, None), 0.0)
    if worst[1] > 1.0:
        errs.append(f"cumulative pir {worst[1]:.3f} > 1 at node {worst[0][0]} in phase "
                    f"{worst[0][1]} -- raise CYCLES_PER_MAC or lower LOAD_SCALE")

    # -- DP convergence vs phase length ---------------------------------------
    short = [(L.name, d) for L, d in zip(trunk, durations) if d < DP_CYCLE]
    if short:
        warns.append(f"{len(short)} of {len(trunk)} phases are shorter than DP_CYCLE "
                     f"({DP_CYCLE}) -- DP cannot converge inside them "
                     f"(shortest: {min(short, key=lambda x: x[1])})")

    # -- placement -------------------------------------------------------------
    if len(placed) != NODES:
        warns.append(f"{NODES - len(placed)} of {NODES} nodes unused")

    # -- silent layers ---------------------------------------------------------
    silent = [L.name for L in layers if L.tiles == 1]
    if silent:
        warns.append(f"{len(silent)} layers occupy a single tile and emit no "
                     f"intra-layer traffic (expected at this tile density)")
    return errs, warns, worst


def check_consistency(rows):
    """HANDOVER.md open item 2: flows and volume matrix must agree EXACTLY.

    The superseded converter had a 0.0016-packet mismatch that was never traced.
    Both views are derived from the same integer-byte rows here, so this asserts
    the derivation rather than hoping.  Integer arithmetic throughout -- no float
    accumulation anywhere in the path.
    """
    mat = defaultdict(int)
    for r in rows:
        mat[(r["src"], r["dst"])] += r["bytes"]
    flows_total = sum(r["bytes"] for r in rows)
    matrix_total = sum(mat.values())
    assert flows_total == matrix_total, (
        f"flows/volume mismatch: {flows_total} vs {matrix_total} bytes")

    pkt_flows = sum(r["packets"] for r in rows)
    per_pair = defaultdict(int)
    for r in rows:
        per_pair[(r["src"], r["dst"])] += r["packets"]
    assert pkt_flows == sum(per_pair.values()), "packet totals disagree"
    return flows_total, pkt_flows


def implied_fps(t_period):
    """Frames/s implied by the swept load.

    One t_period is one inference pass, so at LOAD_SCALE = 1 the mesh carries a
    full inference every t_period cycles.  LOAD_SCALE scales the injected packet
    count linearly, so the implied frame rate scales with it:

        FPS = LOAD_SCALE * freq / t_period

    Krishnan Eq.3 expresses the same relation the other way round (injection rate
    as a function of FPS, tile counts, bus width and frequency).  It is quoted in
    STAGE2.md SS9.3a as the source, but RELATED_WORK.md -- where SS9.3a says the
    verification lives -- does not exist in the repo, so Eq.3 has NOT been
    cross-checked here.  This form follows directly from the model's own timeline
    and needs no external constant beyond the clock.
    """
    return LOAD_SCALE * FREQ_HZ / t_period


# =============================================================================
# Output
# =============================================================================

def stage_summary(layers, hw):
    """Per-stage crossbar/tile breakdown so the total can be hand-checked."""
    agg = defaultdict(lambda: [0, 0, 0])       # stage -> [layers, crossbars, tiles]
    for L in layers:
        st = L.group.split("b")[0] if L.group.startswith("s") else L.group
        a = agg[st]
        a[0] += 1
        a[1] += L.crossbars
        a[2] += L.tiles
    return agg


def write_all(rows, layers, placed, phases, t_period, durations, trunk, hw, wl):
    os.makedirs(OUTDIR, exist_ok=True)
    mesh = f"{DIMX}x{DIMY}x{DIMZ}"
    stem = TABLE_STEM or (f"{wl['tag']}_xb{hw['PE_X']}_{hw['XB_PER_TILE']}pt_{mesh}")
    base = os.path.join(OUTDIR, stem)
    total_tiles = sum(L.tiles for L in layers)
    fps = implied_fps(t_period)

    with open(base + ".txt", "w") as f:
        f.write(f"% {wl['tag']}  crossbar {hw['PE_X']}x{hw['PE_Y']}  "
                f"{hw['XB_PER_TILE']} xb/tile  N_bits={hw['N_BITS']}  "
                f"mesh {mesh} ({NODES} nodes)\n")
        f.write(f"% generated by stage2_dnn_full.py -- see STAGE2.md SS9.3a-c\n")
        f.write(f"% crossbars={sum(L.crossbars for L in layers)}  tiles={total_tiles}"
                f"  occupancy={total_tiles/NODES:.0%}\n")
        f.write(f"% run with:  -size {PACKET_FLITS} {PACKET_FLITS} "
                f"-dimx {DIMX} -dimy {DIMY} -dimz {DIMZ} -traffic table {base}.txt\n")
        f.write(f"% sweep with: WARMUP_DP_CYCLES={WARMUP_DP_CYCLES} "
                f"SIM_DP_CYCLES={SIM_DP_CYCLES}  (DP_CYCLE={DP_CYCLE}, "
                f"SIM={SIM_DP_CYCLES*DP_CYCLE}, "
                f"{SIM_DP_CYCLES*DP_CYCLE/t_period:.1f} inference passes measured)\n")
        f.write(f"% LOAD_SCALE={LOAD_SCALE}  CYCLES_PER_MAC={CYCLES_PER_MAC}"
                f"  t_period={t_period}  implied_FPS={fps:.3g}\n")
        f.write(f"% phases: {len(trunk)} trunk + "
                f"{len(layers)-len(trunk)} shortcut windows\n")
        f.write("% src dst pir por t_on t_off t_period\n")
        # %.10f, not %.8f: a low LOAD_SCALE point drives the smallest pir toward
        # 1e-8, where 8 decimals would round it to zero and silently drop the flow.
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

    # --- per-flow detail ------------------------------------------------------
    with open(base + "_flows.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["src", "dst", "phase", "class", "bytes", "packets",
                    "window", "pir", "t_on", "t_off", "t_period"])
        for r in rows:
            w.writerow([r["src"], r["dst"], r["phase"], r["kind"], r["bytes"],
                        r["packets"], r["window"], f"{r['pir']:.10f}",
                        r["t_on"], r["t_off"], r["t_period"]])

    # --- placement ------------------------------------------------------------
    with open(base + "_placement.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["node", "x", "y", "z", "layer", "kind", "rt", "ct",
                    "R", "C", "Rt", "Ct", "crossbars", "tiles"])
        for L in layers:
            for (rt, ct), nid in sorted(L.node.items()):
                z = nid // (DIMX * DIMY)
                y = (nid % (DIMX * DIMY)) // DIMX
                x = nid % DIMX
                w.writerow([nid, x, y, z, L.name, L.kind, rt, ct,
                            L.R, L.C, L.Rt, L.Ct, L.crossbars, L.tiles])
    return base, total_tiles, fps


# =============================================================================
# main
# =============================================================================

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workload", default="resnet50_full", choices=sorted(WORKLOADS))
    ap.add_argument("--no-assert", action="store_true",
                    help="skip the expected crossbar/tile asserts (for exploration)")
    args = ap.parse_args()

    wl = WORKLOADS[args.workload]
    hw = {k: wl[k] for k in ("PE_X", "PE_Y", "N_BITS", "XB_PER_TILE")}

    layers = [Layer(spec, hw) for spec in wl["layers"]()]
    tot_xb = sum(L.crossbars for L in layers)
    tot_tiles = sum(L.tiles for L in layers)

    if not args.no_assert:
        assert tot_xb == wl["expect_xb"], (
            f"crossbars {tot_xb} != expected {wl['expect_xb']}")
        if wl["expect_tiles"] is not None:
            assert tot_tiles == wl["expect_tiles"], (
                f"tiles {tot_tiles} != expected {wl['expect_tiles']}")
        assert tot_tiles <= NODES, f"{tot_tiles} tiles exceed {NODES} nodes"

    placed, used_n = place(layers)
    phases, t_period, durations, trunk = build_phases(layers)
    vol, cls = build_flows(layers, phases)
    rows = build_rows(vol, cls, phases, t_period)
    tot_bytes, tot_pkts = check_consistency(rows)
    errs, warns, worst = validate(rows, placed, phases, durations, trunk, layers, hw)
    base, _, fps = write_all(rows, layers, placed, phases, t_period,
                             durations, trunk, hw, wl)

    # --- report ---------------------------------------------------------------
    print(f"workload {wl['tag']}  {hw['PE_X']}x{hw['PE_Y']} xb  "
          f"{hw['XB_PER_TILE']} xb/tile  N_bits={hw['N_BITS']}")
    print(f"mesh {DIMX}x{DIMY}x{DIMZ} = {NODES} nodes   "
          f"crossbars {tot_xb}   tiles {tot_tiles} ({tot_tiles/NODES:.0%} occupancy)")
    print()
    print("per-stage tile summary (hand-check the total):")
    print(f"  {'stage':8s} {'layers':>6} {'crossbars':>10} {'tiles':>6}")
    agg = stage_summary(layers, hw)
    for st in sorted(agg, key=lambda s: (s != "stem", s == "fc", s)):
        n, x, t = agg[st]
        print(f"  {st:8s} {n:>6} {x:>10} {t:>6}")
    print(f"  {'TOTAL':8s} {len(layers):>6} {tot_xb:>10} {tot_tiles:>6}")
    print()
    single = sum(1 for L in layers if L.tiles == 1)
    ident = sum(1 for L in layers if L.kind == "identity")
    print(f"flows {len(rows)} rows   {tot_bytes:,} bytes   {tot_pkts:,} packets")
    print(f"phases {len(trunk)} trunk, t_period {t_period} cycles, "
          f"DP_CYCLE {DP_CYCLE}")
    print(f"layers on a single tile (no intra-layer traffic): {single}/{len(layers)}")
    print(f"identity shortcuts (zero tiles, traffic only): {ident}")
    print(f"worst cumulative pir {worst[1]:.4f} at node {worst[0][0]} "
          f"phase {worst[0][1]}")
    print(f"LOAD_SCALE {LOAD_SCALE}  ->  implied {fps:,.0f} FPS "
          f"@ {FREQ_HZ/1e9:g} GHz")
    if fps > FPS_WARN:
        print(f"  !! implied FPS exceeds {FPS_WARN:,.0f} -- the swept load is far "
              f"above any real inference rate; treat as a stress point, not a "
              f"deployment scenario")
    print()
    for w_ in warns:
        print(f"WARN  {w_}")
    for e in errs:
        print(f"ERROR {e}")
    print(f"\nwrote {base}.txt (+ _volume/_flows/_placement.csv)")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
