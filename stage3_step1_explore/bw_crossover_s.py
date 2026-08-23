#!/usr/bin/env python3
"""Task 1, the OTHER slice: sweep c along the OUTPUT axis with r fixed at 1.

`bw_crossover2.py` sweeps c along the INPUT axis -- split_rowmajor never divides
C, so s=1 is hardcoded and c = r*1 = r along its whole x-axis.  That is the
packing which maximises intra-tile reduction, and it is NOT what the Stage-2
generator does.

tools/stage2_core.py packs the opposite way.  For the 6x6x3_base ResNet block,
conv2 has R_xb = ceil(3*3*256/128) = 18 and C_xb = ceil(256*8/128) = 16, giving
18*16 = 288 crossbars in 36 tiles -> c = 8 spent entirely on the output axis:
r = 1, s = 8.  Reduction depth stays ceil(R_xb/r) - 1 = 17, which is why
`reduce` is 81.8% of traffic in rn50_6b_ls0.006_flows.csv.

This script fixes r = 1 and sweeps c = s, i.e. the slice the project actually
occupies.  The headline is that inter-tile partial-sum demand is FLAT: with
r = 1 every row group sits in its own tile, so no reduction is ever internalised
and c buys nothing on the psum side.  What s does buy is scatter -- the input
activations are delivered once per tile-column instead of once per tile.

Payload widths follow bw_crossover.py (PSUM_BITS = 16) so the two figures stay
comparable.  NOTE: the generator uses INT32 psums (BYTES_PER_PSUM = 4 in
tools/stage2_core.py:50), so absolute psum values here are 2x low.  The shape of
every curve is unaffected.

Run:  python3 bw_crossover_s.py     (writes *_s.{csv,json,png} beside this file)
"""
import csv
import json
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


HERE = os.path.dirname(os.path.abspath(__file__))
ACT_BITS = 8                      # INT8 activations, per stage2_core.py
C_SWEEP = [1, 2, 4, 8, 16, 32, 64]

# r is held CONSTANT and the sweep spends the rest of c on s (s = c/r).  Pass r
# on the command line: `python3 bw_crossover_s.py 2`.  Default 1 = the packing
# the Stage-2 tables use.
R_FIX = int(sys.argv[1]) if len(sys.argv) > 1 else 1


def _load_v1():
    """Pull constants/workloads/geometry out of bw_crossover.py without running it.

    That file is not importable as shipped: it writes its CSV/JSON/PNG at module
    level to a hard-coded /home/claude/stage3/ path, so `import` raises
    FileNotFoundError here.  Exec only the imports, constant assignments and
    function definitions, dropping every other top-level statement.
    """
    import ast
    import types
    src = open(f"{HERE}/bw_crossover.py").read()
    tree = ast.parse(src)
    tree.body = [n for n in tree.body
                 if isinstance(n, (ast.Import, ast.ImportFrom, ast.Assign,
                                   ast.FunctionDef))]
    mod = types.ModuleType("bw_crossover_defs")
    exec(compile(tree, "bw_crossover.py", "exec"), mod.__dict__)
    return mod


_v1 = _load_v1()
N_BITS, PE_X, PE_Y = _v1.N_BITS, _v1.PE_X, _v1.PE_Y
PSUM_BITS, WORKLOADS, layer_geometry = _v1.PSUM_BITS, _v1.WORKLOADS, _v1.layer_geometry



def split_colmajor(R, C, P, s, r=1):
    """c = r*s spent on the OUTPUT axis (r fixed at 1 by default).

    tile grid is ceil(R/r) x ceil(C/s).  Partial sums travel up each column of
    tiles to the accumulator hosted on the r=0 tile, so depth = ceil(R/r) - 1
    and is independent of s.  Activations are broadcast once per tile-column.
    """
    tr, tc = math.ceil(R / r), math.ceil(C / s)
    inter_psum = (tr - 1) * C * P * PSUM_BITS      # crosses the NoC
    intra_psum = (R - tr) * C * P * PSUM_BITS      # absorbed on-tile (0 when r=1)
    scatter = tc * (R * PE_X) * P * ACT_BITS       # inputs delivered per column
    return intra_psum, inter_psum, scatter, tr * tc


def analyse(layers):
    out = {}
    for c in C_SWEEP:
        if c < R_FIX:
            continue                      # c must cover at least r crossbars
        ia = ie = sc = tiles = 0
        for _, k, ci, co, P in layers:
            R, C, _ = layer_geometry(k, ci, co)
            a, e, s_, t = split_colmajor(R, C, P, s=c // R_FIX, r=R_FIX)
            ia += a; ie += e; sc += s_; tiles += t
        out[c] = dict(intra_psum=ia, inter_psum=ie, scatter=sc,
                      inter_total=ie + sc, tiles=tiles)
    return out


def main():
    res = {w: analyse(L) for w, L in WORKLOADS.items()}

    with open(f"{HERE}/bw_crossover_s_r{R_FIX}.csv", "w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["workload", "c", "r", "s", "tiles", "inter_psum_Gbit",
                     "scatter_Gbit", "inter_total_Gbit", "psum_share"])
        for w, d in res.items():
            for c, v in d.items():
                tot = v["inter_total"]
                wr.writerow([w, c, R_FIX, c // R_FIX, v["tiles"],
                             round(v["inter_psum"] / 1e9, 6),
                             round(v["scatter"] / 1e9, 6),
                             round(tot / 1e9, 6),
                             round(v["inter_psum"] / tot, 4) if tot else 0])

    with open(f"{HERE}/bw_crossover_s_r{R_FIX}.json", "w") as fh:
        json.dump({w: {str(c): v for c, v in d.items()} for w, d in res.items()},
                  fh, indent=2)

    # one shared decade range across all three panels, so the flat psum line and
    # the falling scatter line are directly comparable between workloads
    vals = [v[k] / 1e9 for d in res.values() for v in d.values()
            for k in ("inter_psum", "scatter", "inter_total")]
    lo = 10 ** math.floor(math.log10(min(vals)))
    hi = 10 ** math.ceil(math.log10(max(vals)))

    # Same two series as bw_crossover2.py -- intra vs inter partial sums -- so the
    # two figures answer the same question.  LINEAR y: at r=1 the intra curve is
    # identically zero and a log axis cannot render it.
    # Single row: TOTAL NoC demand per inference and the two components that
    # make it up.  psum is flat in c (it depends on r alone); scatter falls; the
    # total therefore falls, but only because of scatter.
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.0), sharex=True, sharey=True)
    lo = 10 ** math.floor(math.log10(min(
        v["inter_psum"] for d in res.values() for v in d.values()) / 1e9))
    hi = 10 ** math.ceil(math.log10(max(
        v["inter_total"] for d in res.values() for v in d.values()) / 1e9))

    for ax, (w, d) in zip(axes, res.items()):
        cs = sorted(d)
        ax.plot(cs, [d[c]["inter_total"] / 1e9 for c in cs], "^-", color="#7d3c98",
                lw=2.6, ms=9, zorder=3, label="TOTAL NoC demand")
        ax.plot(cs, [d[c]["scatter"] / 1e9 for c in cs], "o--", color="#2874a6",
                lw=1.6, ms=6, label="  component: scatter / activations")
        ax.plot(cs, [d[c]["inter_psum"] / 1e9 for c in cs], "s--", color="#c0392b",
                lw=1.6, ms=6, label="  component: partial sums (flat in c)")
        ax.axvline(8, color="k", ls=":", lw=1.2)
        ax.set_xscale("log", base=2); ax.set_yscale("log")
        ax.set_ylim(lo, hi)
        ax.set_xticks(C_SWEEP); ax.set_xticklabels(C_SWEEP)
        t0 = d[cs[0]]["inter_total"] / 1e9
        t1 = d[cs[-1]]["inter_total"] / 1e9
        ax.set_title(f"{w}   total {t0:.3f} -> {t1:.3f} Gbit  ({t1/t0*100:.0f}%)")
        ax.set_xlabel(f"c   (s = c/{R_FIX};  r fixed at {R_FIX})")
        ax.grid(alpha=.3, which="both")
    axes[0].set_ylabel("total NoC demand per inference (Gbit)")
    axes[0].legend(fontsize=8.5, loc="lower left")
    fig.suptitle(
        f"TOTAL NoC demand per inference — c spent on the OUTPUT axis "
        f"(r fixed at {R_FIX}, s = c/{R_FIX}).\n"
        f"Total falls with c, but ALL of the fall is scatter: the partial-sum "
        f"component is flat, because psum depends on r alone.",
        fontsize=11)
    fig.tight_layout()
    fig.savefig(f"{HERE}/bw_crossover_s_r{R_FIX}.png", dpi=150)
    print(f"wrote bw_crossover_s_r{R_FIX}.{{csv,json,png}}")

    for w, d in res.items():
        cs = sorted(d)
        ie = [d[c]["inter_psum"] for c in cs]
        ia = [d[c]["intra_psum"] for c in cs]
        print(f"  {w:<10} r={R_FIX}  inter {ie[0]/1e9:.4f} Gbit "
              f"(max/min {max(ie)/min(ie):.3f})   "
              f"intra {ia[0]/1e9:.4f} Gbit   "
              f"scatter {d[cs[0]]['scatter']/1e9:.3f} -> {d[cs[-1]]['scatter']/1e9:.3f}")


if __name__ == "__main__":
    main()
