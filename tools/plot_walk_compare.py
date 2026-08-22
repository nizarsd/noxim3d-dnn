#!/usr/bin/env python3
"""Current (Z-fastest) vs XY-diagonal tile placement, per layer, on 7x7x3.

The point of the figure is the REDUCTION AXIS.  Under the current bump-allocator
walk a layer's partial-sum reduction lands along a single mesh axis, and
modified2 odd-even-balanced admits exactly one path for an axis-aligned flow --
so DP has nothing to select between for 41% of all traffic bytes.  The diagonal
walk breaks that alignment.

Colour encodes the WALK (categorical slots 1-2, which clear the all-pairs
floors); layer identity is carried by the column title, so no two categorical
hues ever appear in the same panel.

Reads the generated placement + flows CSVs; writes fig4_walk_compare.png.
"""
import csv
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from oeb_path_diversity import Mesh                      # noqa: E402

DX, DY, DZ = 7, 7, 3
MESH = Mesh(DX, DY, DZ)
npaths = lambda a, b: (MESH.npaths(a, b), None)   # (paths, _) shape kept below
xyz, nid = MESH.xyz, MESH.nid

PL = "traffics_dnn/resnet50_bottleneck3_xb128_7x7x3_placement.csv"
FL = "traffics_dnn/resnet50_bottleneck3_xb128_7x7x3_flows.csv"
LAYERS = ["conv1", "conv2", "conv3", "shortcut"]

SURFACE, TEXT_1, TEXT_2 = "#fcfcfb", "#0b0b0b", "#52514e"
LINK, GREY = "#dcdbd6", "#c9c8c3"
CUR, DIAG = "#2a78d6", "#eb6834"          # categorical slots 1, 2

plt.rcParams.update({"figure.facecolor": SURFACE, "savefig.facecolor": SURFACE,
                     "font.family": "DejaVu Sans", "font.size": 9,
                     "text.color": TEXT_1})


def diagonal_walk():
    """Offset each mesh row's x by its y, Z still innermost."""
    return MESH.diagonal_walk()


def load():
    place = [r for r in csv.DictReader(open(PL)) if r["layer"] not in ("-", "")]
    flows = list(csv.DictReader(open(FL)))
    # allocation order of the current walk: y outer, x mid, z inner
    seq = sorted(place, key=lambda r: (int(r["y"]), int(r["x"]), int(r["z"])))
    cur_nodes = [int(r["node"]) for r in seq]
    remap = {old: new for old, new in zip(cur_nodes, diagonal_walk())}
    layer_of = {int(r["node"]): r["layer"] for r in place}
    return place, flows, remap, layer_of


def diversity(flows, remap, layer, use_diag):
    """Share of this layer's bytes whose flow admits more than one path."""
    tot = div = 0.0
    for r in flows:
        if r["phase"] != layer:
            continue
        s, d = int(r["src"]), int(r["dst"])
        if use_diag:
            s, d = remap[s], remap[d]
        if s == d:
            continue
        b = float(r["bytes"])
        tot += b
        if npaths(xyz(s), xyz(d))[0] > 1:
            div += b
    return div / tot * 100 if tot else 0.0


def draw_links(ax):
    for x in range(DX):
        for y in range(DY):
            for z in range(DZ):
                if x + 1 < DX: ax.plot([x, x+1], [y, y], [z, z], color=LINK, lw=0.4, zorder=1)
                if y + 1 < DY: ax.plot([x, x], [y, y+1], [z, z], color=LINK, lw=0.4, zorder=1)
                if z + 1 < DZ: ax.plot([x, x], [y, y], [z, z+1], color=LINK, lw=0.4, zorder=1)


def frame(ax):
    ax.set_xticks(range(DX)); ax.set_yticks(range(DY)); ax.set_zticks(range(DZ))
    ax.set_xticklabels([]); ax.set_yticklabels([]); ax.set_zticklabels([])
    ax.set_xlabel("X", labelpad=-12, color=TEXT_2, fontsize=8)
    ax.set_ylabel("Y", labelpad=-12, color=TEXT_2, fontsize=8)
    ax.set_zlabel("Z", labelpad=-12, color=TEXT_2, fontsize=8)
    ax.tick_params(length=0)
    ax.set_box_aspect((DX, DY, DZ * 1.7))
    ax.view_init(elev=24, azim=-60)
    for pane in (ax.xaxis, ax.yaxis, ax.zaxis):
        pane.pane.set_facecolor(SURFACE); pane.pane.set_edgecolor(LINK)
        pane._axinfo["grid"]["color"] = SURFACE


def panel(ax, layer, place, flows, remap, use_diag, colour):
    draw_links(ax)
    nodes = [int(r["node"]) for r in place if r["layer"] == layer]
    if use_diag:
        nodes = [remap[n] for n in nodes]
    rest = [n for n in range(DX*DY*DZ) if n not in set(nodes)]
    R = [xyz(n) for n in rest]
    ax.scatter([p[0] for p in R], [p[1] for p in R], [p[2] for p in R],
               c=GREY, s=9, depthshade=False, edgecolors="none", zorder=2)

    # the reduction flows -- the traffic whose path diversity is at stake
    for r in flows:
        if r["phase"] != layer or r["class"] != "reduce":
            continue
        s, d = int(r["src"]), int(r["dst"])
        if use_diag:
            s, d = remap[s], remap[d]
        a, b = xyz(s), xyz(d)
        ax.plot([a[0], b[0]], [a[1], b[1]], [a[2], b[2]],
                color=colour, lw=1.0, alpha=0.5, zorder=3)

    T = [xyz(n) for n in nodes]
    ax.scatter([p[0] for p in T], [p[1] for p in T], [p[2] for p in T],
               c=colour, s=42, depthshade=False, edgecolors=SURFACE,
               linewidths=0.7, zorder=4)
    frame(ax)


def main():
    place, flows, remap, _ = load()
    fig = plt.figure(figsize=(15.5, 8.0))

    for col, layer in enumerate(LAYERS):
        ntiles = sum(1 for r in place if r["layer"] == layer)
        for row, (use_diag, colour, name) in enumerate(
                ((False, CUR, "current"), (True, DIAG, "XY-diagonal"))):
            ax = fig.add_subplot(2, 4, row * 4 + col + 1, projection="3d")
            panel(ax, layer, place, flows, remap, use_diag, colour)
            pct = diversity(flows, remap, layer, use_diag)
            ax.set_title(f"{pct:.0f}% of bytes have >1 path",
                         fontsize=9.5, color=colour, loc="left", pad=-4)
            if col == 0:
                ax.text2D(-0.07, 0.42, name, transform=ax.transAxes,
                          fontsize=11.5, color=colour, rotation=90,
                          va="center", ha="center")

    fig.suptitle("Tile placement and the reduction axis — why the current walk "
                 "starves DP of routing choice",
                 fontsize=14, color=TEXT_1, x=0.008, ha="left", y=0.985)
    fig.text(0.008, 0.950,
             "7×7×3 mesh, ResNet-50 bottleneck block. Lines are partial-sum "
             "reduction flows — 82% of all traffic bytes.",
             fontsize=10, color=TEXT_2, ha="left")
    fig.text(0.008, 0.925,
             "Under modified2 odd-even-balanced an axis-aligned flow admits "
             "exactly one path, so DP and bufferlevel are provably identical on it.",
             fontsize=10, color=TEXT_2, ha="left")
    # column headers as figure text on their own row, so they cannot collide
    # with the 3D axes' generous bounding boxes
    L, Rt = 0.030, 0.995
    for col, layer in enumerate(LAYERS):
        ntiles = sum(1 for r in place if r["layer"] == layer)
        fig.text(L + col * (Rt - L) / 4 + 0.030, 0.876,
                 f"{layer}  ·  {ntiles} tiles", fontsize=12.5, color=TEXT_1)

    fig.subplots_adjust(left=L, right=Rt, top=0.855, bottom=0.005,
                        wspace=0.02, hspace=0.20)
    fig.savefig("fig4_walk_compare.png", dpi=190)
    print("wrote fig4_walk_compare.png")


if __name__ == "__main__":
    main()
