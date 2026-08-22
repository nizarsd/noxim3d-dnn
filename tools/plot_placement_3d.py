#!/usr/bin/env python3
"""Visualise how stage2_dnn_full.py maps layer tiles onto the 7x7x3 mesh.

Reads the generated *_placement.csv and renders two views:
  A  allocation order -- the Z-fastest traversal the bump allocator walks
  B  three example layers highlighted against the rest of the mesh

Colour: panel A uses the sequential blue ramp (ordered magnitude = fill order);
panel B uses categorical slots 1-3, the three that validate all-pairs.
"""
import csv
import sys
from collections import OrderedDict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

SRC = sys.argv[1] if len(sys.argv) > 1 else \
    "traffics_dnn/resnet50_full_xb128_120pt_7x7x3_placement.csv"
DIMX, DIMY, DIMZ = 7, 7, 3

SURFACE, TEXT_1, TEXT_2 = "#fcfcfb", "#0b0b0b", "#52514e"
LINK = "#dcdbd6"                      # mesh links: hairline, one shade off surface
GREY = "#c9c8c3"
SEQ = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5",
       "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
CAT = ["#2a78d6", "#eb6834", "#1baf7a"]
RAMP = LinearSegmentedColormap.from_list("seq", SEQ)

plt.rcParams.update({"figure.facecolor": SURFACE, "savefig.facecolor": SURFACE,
                     "font.family": "DejaVu Sans", "font.size": 9,
                     "text.color": TEXT_1})


def load():
    rows = list(csv.DictReader(open(SRC)))
    layers = OrderedDict()
    for r in rows:
        layers.setdefault(r["layer"], []).append(
            (int(r["node"]), int(r["x"]), int(r["y"]), int(r["z"])))
    return rows, layers


def draw_links(ax):
    """Faint mesh edges, so the point cloud reads as a mesh."""
    for x in range(DIMX):
        for y in range(DIMY):
            for z in range(DIMZ):
                if x + 1 < DIMX:
                    ax.plot([x, x + 1], [y, y], [z, z], color=LINK, lw=0.5, zorder=1)
                if y + 1 < DIMY:
                    ax.plot([x, x], [y, y + 1], [z, z], color=LINK, lw=0.5, zorder=1)
                if z + 1 < DIMZ:
                    ax.plot([x, x], [y, y], [z, z + 1], color=LINK, lw=0.5, zorder=1)


def frame(ax, title):
    ax.set_xlabel("X", labelpad=-6, color=TEXT_2)
    ax.set_ylabel("Y", labelpad=-6, color=TEXT_2)
    ax.set_zlabel("Z", labelpad=-6, color=TEXT_2)
    ax.set_xticks(range(DIMX)); ax.set_yticks(range(DIMY)); ax.set_zticks(range(DIMZ))
    ax.tick_params(labelsize=7, colors=TEXT_2, pad=-2)
    ax.set_box_aspect((DIMX, DIMY, DIMZ * 1.6))
    ax.view_init(elev=22, azim=-58)
    for pane in (ax.xaxis, ax.yaxis, ax.zaxis):
        pane.pane.set_facecolor(SURFACE); pane.pane.set_edgecolor(LINK)
        pane._axinfo["grid"]["color"] = SURFACE
    ax.set_title(title, fontsize=10.5, color=TEXT_1, loc="left", pad=-2)


def main():
    rows, layers = load()
    fig = plt.figure(figsize=(13, 5.6))

    # ---- panel A: allocation order -----------------------------------------
    a = fig.add_subplot(121, projection="3d")
    draw_links(a)
    order = []
    for name, cells in layers.items():
        for c in cells:
            order.append(c)
    n = len(order)
    xs = [c[1] for c in order]; ys = [c[2] for c in order]; zs = [c[3] for c in order]
    a.scatter(xs, ys, zs, c=[RAMP(i / (n - 1)) for i in range(n)],
              s=55, depthshade=False, edgecolors=SURFACE, linewidths=0.8, zorder=3)
    # the walk itself: first 12 steps, to show z-fastest then x
    a.plot(xs[:9], ys[:9], zs[:9], color="#e34948", lw=1.2, alpha=0.85, zorder=4)
    a.text(xs[0]-0.3, ys[0]-0.9, zs[0], "walk starts here", fontsize=8, color="#e34948")
    frame(a, "A · allocation order — Z fastest, then X, then Y")
    sm = plt.cm.ScalarMappable(cmap=RAMP)
    cb = fig.colorbar(sm, ax=a, shrink=0.5, pad=0.02, aspect=18)
    cb.set_ticks([0, 1]); cb.set_ticklabels(["first", "last"])
    cb.ax.tick_params(labelsize=8, colors=TEXT_2); cb.outline.set_edgecolor(LINK)

    # ---- panel B: three layers highlighted ---------------------------------
    b = fig.add_subplot(122, projection="3d")
    draw_links(b)
    show = [nm for nm in ("stem", "s3b0_c2", "s4b0_c2") if nm in layers]
    hi = {nm: CAT[i] for i, nm in enumerate(show)}
    rest = [c for nm, cs in layers.items() if nm not in hi for c in cs]
    b.scatter([c[1] for c in rest], [c[2] for c in rest], [c[3] for c in rest],
              c=GREY, s=28, depthshade=False, edgecolors=SURFACE, linewidths=0.6,
              zorder=2, label="other layers")
    for nm in show:
        cs = layers[nm]
        # connect the layer's tiles in ALLOCATION order: the run is contiguous in
        # the walk even though it looks scattered in space -- that is the point.
        if len(cs) > 1:
            b.plot([c[1] for c in cs], [c[2] for c in cs], [c[3] for c in cs],
                   color=hi[nm], lw=1.6, alpha=0.75, zorder=3)
        b.scatter([c[1] for c in cs], [c[2] for c in cs], [c[3] for c in cs],
                  c=hi[nm], s=95, depthshade=False, edgecolors=SURFACE,
                  linewidths=1.0, zorder=4, label=f"{nm} ({len(cs)} tile"
                  f"{'s' if len(cs) > 1 else ''})")
    frame(b, "B · three layers — line = consecutive in the walk")
    b.legend(frameon=False, fontsize=8.5, loc="upper left",
             bbox_to_anchor=(-0.02, 0.92))

    fig.suptitle("Tile → node mapping on the 7×7×3 mesh — a bump allocator over a "
                 "Z-fastest walk, deliberately unoptimised",
                 fontsize=12, color=TEXT_1, x=0.008, ha="left", y=0.985)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig("fig3_placement_3d.png", dpi=200)
    print("wrote fig3_placement_3d.png")


if __name__ == "__main__":
    main()
