#!/usr/bin/env python3
"""Emit a full traffic table set for every FEASIBLE (c,r,s) packing point.

Feasible = the packing needs <= NODES tiles, so a placement exists at all.
For each such point this writes the usual four files via stage2_core.write_all():

    <stem>.txt              simulator traffic table
    <stem>_flows.csv        per (src,dst,phase) bytes / packets / pir
    <stem>_volume.csv       NODES x NODES byte matrix
    <stem>_placement.csv    node -> (x,y,z, layer, row group, col group, role)

plus INDEX.csv summarising every point and flagging the minima.

WHY THIS EXISTS
    The shipped converter can only emit the ONE packing its hand-authored
    `boxes` were sized for: stage2_core.place() asserts `cells == L.tiles`, and
    every other (c,r,s) changes L.tiles.  Mapping exploration needs the flow
    graph at other packings, so placement here is done by an explicit placer
    instead -- see place_linear().

    Two blockers are worked around, both in memory only; no repo file changes:
      * Layer.__init__ asserts R >= ceil(rows/XB), which forbids r > 1
        (patched by packing_rs_sweep.layers_for)
      * place() asserts the box holds exactly L.tiles (bypassed by writing
        L.node directly)

THE PLACEMENT IS A SEED, NOT AN OPTIMUM
    place_linear() lays each layer out contiguously in node-id order, in LAYERS
    (dependency) order.  It is legal and deterministic, and that is all it is
    claimed to be.  It is NOT the tuned box placement the shipped tables use, so
    delays from these tables are NOT comparable to published Stage 3 numbers --
    they are a baseline for a mapper to improve on.  Swap place_linear() for a
    search to explore.

    python3 tools/packing_rs_placements.py [outdir]
"""
import csv
import math
import os
import sys

sys.path.insert(0, "/home/nizar/noxim3d-dnn/tools")
import packing_rs_sweep as sw
import stage2_core as core

OUTDIR = sys.argv[1] if len(sys.argv) > 1 else "traffics_dnn_packing"
XB, NB = sw.XB, sw.NB

# Operating point per workload -- MUST match the shipped tables in
# traffics_dnn_current/, or pir and the phase windows land somewhere the Stage 3
# runs never used.  These are NOT the module defaults: every shipped table was
# generated with env overrides, so relying on stage2_<model>.CYCLES_PER_MAC gives
# VGG 4x and DeiT-S 0.5x the correct t_period.  Read back from the table headers.
OPPOINT = {
    "stage2_resnet":   dict(cpm="0.0002",  load_scale="0.026"),
    "stage2_vgg":      dict(cpm="2.5e-05", load_scale="0.05"),
    "stage2_vitsmall": dict(cpm="0.0002",  load_scale="0.05"),
}


def place_linear():
    """Contiguous node-id fill, layers in LAYERS order.  Returns {node: layer}.

    Within a layer, tile (row_group, col_group) lands at base + rg*C + cg, so the
    C accumulators (row group 0) occupy the layer's first C nodes.  Node ids run
    x fastest, then y, then z (stage2_core.coord2id), so a layer's block is a
    contiguous mesh run that may wrap across rows and planes.
    """
    placed, nid = {}, 0
    for L in core.LAYER.values():
        for i in range(L.tiles):
            assert nid < core.NODES, f"{L.name}: out of nodes at tile {i}"
            L.node[(i // L.C, i % L.C)] = nid
            placed[nid] = L.name
            nid += 1
    return placed


def grid_for(shapes, r, s):
    """Per-layer (R, C) tile grid for an (r, s) packing, and the tile total."""
    grid, tiles = {}, 0
    for n, k, ci, co in shapes:
        Rx, Cx = math.ceil(k * k * ci / XB), math.ceil(co * NB / XB)
        R, C = math.ceil(Rx / r), max(1, math.ceil(Cx / s))
        grid[n] = (R, C)
        tiles += R * C
    return grid, tiles


def emit(modname, mesh, tag, index):
    import importlib
    m = importlib.import_module(modname); importlib.reload(m)
    os.environ["DNN_MESH"] = mesh
    os.environ["DNN_CYCLES_PER_MAC"] = OPPOINT[modname]["cpm"]
    os.environ["DNN_LOAD_SCALE"] = OPPOINT[modname]["load_scale"]
    importlib.reload(core); core.configure(m)
    shapes = [(n, k, ci, co) for (n, k, ci, co, _) in core.LAYERS]

    _, _, rows = sw.sweep(modname, mesh, tag, quiet=True)
    # sw.sweep() reloads core, which re-reads the env -- but configure() only
    # takes CYCLES_PER_MAC from the model when the env var is unset, so re-apply.
    importlib.reload(core); core.configure(m)
    assert f"{core.CYCLES_PER_MAC}" == OPPOINT[modname]["cpm"].lstrip("0") or \
           float(core.CYCLES_PER_MAC) == float(OPPOINT[modname]["cpm"]), \
        f"{tag}: CYCLES_PER_MAC={core.CYCLES_PER_MAC} != {OPPOINT[modname]['cpm']}"
    assert float(core.LOAD_SCALE) == float(OPPOINT[modname]["load_scale"])
    fitting = [d for d in rows if d["fits"]]
    gmin = min(fitting, key=lambda d: d["total"])
    cmin = {c: min((d for d in fitting if d["c"] == c), key=lambda d: d["total"])
            for c in sorted({d["c"] for d in fitting})}

    print(f"\n### {tag}   {len(fitting)}/{len(rows)} feasible")
    for d in fitting:
        c, r, s = d["c"], d["r"], d["s"]
        grid, tiles = grid_for(shapes, r, s)
        sw.layers_for(m, grid)              # rebuild LAYER at this grid
        placed = place_linear()             # explicit, swappable seed placement

        phases, t_period, durations = core.build_phases()
        vol, cls = core.build_flows()
        trows = core.build_rows(vol, cls, phases, t_period)
        errs, warns, worst, worst_stacked = core.validate(
            trows, placed, phases, t_period, durations)

        core.OUTDIR = OUTDIR
        core.TABLE_STEM = (f"{core.MODEL_TAG}_xb{XB}_"
                           f"{core.DIMX}x{core.DIMY}x{core.DIMZ}_c{c}r{r}s{s}")
        base = core.write_all(trows, placed, phases, t_period, durations)

        note = []
        if (c, r, s) == (8, 1, 8): note.append("current")
        if d is gmin: note.append("GLOBAL MIN")
        elif d in cmin.values(): note.append(f"min@c={c}")
        index.append(dict(
            workload=tag, c=c, r=r, s=s, tiles=tiles,
            nodes_idle=core.NODES - len(placed),
            scatter=d["scatter"], reduce=d["reduce"], add=d["add"],
            total_bytes=d["total"], mib=round(d["total"] / 1048576, 3),
            flows=len(trows), t_period=t_period,
            worst_stacked_pir=round(worst_stacked[1], 4),
            sim_ready="yes" if not errs else "NO",
            errors="; ".join(errs)[:300], warnings="; ".join(warns)[:300],
            note=" ".join(note), stem=os.path.basename(base)))
        flag = "OK " if not errs else "ERR"
        print(f"  {flag} c={c:2d} r={r:2d} s={s:2d}  tiles={tiles:3d}  "
              f"idle={core.NODES-len(placed):3d}  flows={len(trows):4d}  "
              f"stacked_pir={worst_stacked[1]:.3f}  {d['total']/1048576:8.3f} MiB"
              f"  {' '.join(note)}")
        if errs:
            print(f"      {errs[0]}")


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    index = []
    for modname, mesh, tag in sw.WORKLOADS:
        emit(modname, mesh, tag, index)
    path = os.path.join(OUTDIR, "INDEX.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(index[0].keys()))
        w.writeheader()
        w.writerows(index)
    ok = sum(1 for d in index if d["sim_ready"] == "yes")
    print(f"\nwrote {len(index)} packing points ({ok} simulator-ready) "
          f"to {OUTDIR}/, index at {path}")


if __name__ == "__main__":
    main()
