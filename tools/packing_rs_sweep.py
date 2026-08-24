#!/usr/bin/env python3
"""(c,r,s) sweep tables using the REAL generator flow builder.

Byte totals come from stage2_core.build_flows(), not a re-derivation, so the
(8,1,8) row must reproduce each shipped table's flows.csv exactly.  r>1 is
blocked by the `R >= base_R` assert, so Layer.__init__ is patched in-memory
here only -- the repo file is untouched.
"""
import collections
import importlib
import math
import os
import sys

sys.path.insert(0, "/home/nizar/noxim3d-dnn/tools")
os.chdir("/home/nizar/noxim3d-dnn")
import stage2_core as core

XB, NB = 128, 8


def layers_for(mod, grid):
    """Rebuild core.LAYER with an arbitrary tile grid, bypassing the asserts."""
    orig = core.Layer.__init__

    def patched(self, name, k, cin, cout, kind):
        self.name, self.k, self.cin, self.cout, self.kind = name, k, cin, cout, kind
        self.rows, self.cols = k * k * cin, cout
        self.base_R = math.ceil(self.rows / core.XB)
        self.base_C = math.ceil(self.cols / core.XB)
        self.R, self.C = grid[name]                     # no assert
        self.row_groups = core.split_ranges(self.rows, self.R)
        self.col_groups = core.split_ranges(self.cols, self.C)
        self.tiles = self.R * self.C
        self.macs = k * k * cin * cout * core.HW
        self.node = {}
    core.Layer.__init__ = patched
    core.LAYER = {n: core.Layer(n, k, ci, co, kd) for (n, k, ci, co, kd) in core.LAYERS}
    core.TRUNK = [core.LAYER[n] for (n, _, _, _, kd) in core.LAYERS if kd == "conv"]
    core.Layer.__init__ = orig
    nid = 0
    for L in core.LAYER.values():                        # any bijection; bytes are placement-free
        for i in range(L.tiles):
            L.node[(i // L.C, i % L.C)] = nid; nid += 1


def sweep(modname, mesh, tag, quiet=False):
    """Return (tag, crossbars_required, [row dicts]); also prints the md table."""
    m = importlib.import_module(modname); importlib.reload(m)
    os.environ["DNN_MESH"] = mesh
    importlib.reload(core); core.configure(m)
    shapes = [(n, k, ci, co) for (n, k, ci, co, _) in core.LAYERS]
    used = sum(math.ceil(k*k*ci/XB) * math.ceil(co*NB/XB) for _, k, ci, co in shapes)

    rows = []
    for c in (8, 16, 32):
        r = 1
        while r <= c:
            s = c // r
            grid, tiles = {}, 0
            for n, k, ci, co in shapes:
                Rx, Cx = math.ceil(k*k*ci/XB), math.ceil(co*NB/XB)
                R, C = math.ceil(Rx/r), max(1, math.ceil(Cx/s))
                grid[n] = (R, C); tiles += R*C
            layers_for(m, grid)
            core.build_phases()
            _, cls = core.build_flows()
            agg = collections.Counter()
            for _, d in cls.items():
                for kind, b in d.items(): agg[kind] += b
            sca = agg["scatter"] + agg.get("reduce+scatter", 0)
            red, add = agg["reduce"], agg.get("add", 0)
            alloc = tiles * c
            rows.append(dict(c=c, r=r, s=s, tiles=tiles, fits=tiles <= 108,
                             alloc=alloc, used=used, unused=alloc - used,
                             scatter=sca, reduce=red, add=add, total=sca + red + add))
            r *= 2

    if not quiet:
        print(f"\n### {tag}   crossbars required = {used}   mesh 6x6x3 = 108 nodes")
        print("| c | r | s | Tiles | Fit | Alloc. CBs | Used | Unused | Unused % "
              "| Scatter (B) | Reduce (B) | Add (B) | Total (B) | MiB/pass |")
        print("|---:|---:|---:|---:|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for d in rows:
            print(f"| {d['c']} | {d['r']} | {d['s']} | {d['tiles']} "
                  f"| {'Yes' if d['fits'] else 'No'} "
                  f"| {d['alloc']:,} | {d['used']:,} | {d['unused']:,} "
                  f"| {d['unused']/d['alloc']*100:.2f}% "
                  f"| {d['scatter']:,.0f} | {d['reduce']:,.0f} | {d['add']:,.0f} "
                  f"| {d['total']:,.0f} | {d['total']/1048576:.3f} |")
    return tag, used, rows


WORKLOADS = [("stage2_resnet",   "6x6x3_base", "ResNet-50 stage-3 bottleneck"),
             ("stage2_vgg",      "6x6x3",      "VGG-16 block 3"),
             ("stage2_vitsmall", "6x6x3",      "DeiT-S encoder block")]

if __name__ == "__main__":
    for _mod, _mesh, _tag in WORKLOADS:
        sweep(_mod, _mesh, _tag)
