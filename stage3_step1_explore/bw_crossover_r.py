#!/usr/bin/env python3
"""The original c=r figure, split into its REDUCE and SCATTER components.

`bw_crossover2.py` plots intra- vs inter-tile PARTIAL SUMS only, so the activation
traffic never appears.  This keeps its packing convention -- s fixed (default 1),
so c = r*s and growing c grows r -- but plots the two NoC traffic classes the
Stage-2 generator actually emits:

  reduce  = partial sums, tile (r,c) -> column accumulator.  (ceil(R/r) - 1)
            senders per column, 4 bytes/element (INT32).  CONVERGES on one node.
  scatter = input activations, producer -> every tile that needs them.  Delivered
            once per tile-column, 1 byte/element (INT8).  FANS OUT.

On this axis reduce falls with c (deeper grouping internalises the reduction) and
scatter is flat (s is pinned, so the number of tile-columns never changes).  That
is the exact mirror of bw_crossover_s.py, where reduce is flat and scatter falls.

Run:  python3 bw_crossover_r.py [s]      default s = 1
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
ACT_BITS = 8                  # INT8 activations   (stage2_core.py BYTES_PER_ACT=1)
PSUM_BITS = 32                # INT32 partial sums (stage2_core.py BYTES_PER_PSUM=4)
C_SWEEP = [1, 2, 4, 8, 16, 32, 64]
S_FIX = int(sys.argv[1]) if len(sys.argv) > 1 else 1


def _load_v1():
    """Constants + workloads from bw_crossover.py without running its writes."""
    import ast
    import types
    tree = ast.parse(open(f"{HERE}/bw_crossover.py").read())
    tree.body = [n for n in tree.body
                 if isinstance(n, (ast.Import, ast.ImportFrom, ast.Assign,
                                   ast.FunctionDef))]
    mod = types.ModuleType("bw_crossover_defs")
    exec(compile(tree, "bw_crossover.py", "exec"), mod.__dict__)
    return mod


_v1 = _load_v1()
PE_X, N_BITS, WORKLOADS = _v1.PE_X, _v1.N_BITS, _v1.WORKLOADS


def analyse(layers):
    out = {}
    for c in C_SWEEP:
        if c < S_FIX:
            continue
        r = c // S_FIX
        red = sca = tiles = 0
        for _, k, ci, co, P in layers:
            R = math.ceil(k * k * ci / PE_X)
            C = math.ceil(co * N_BITS / PE_X)
            tr, tc = math.ceil(R / r), math.ceil(C / S_FIX)
            tiles += tr * tc
            red += (tr - 1) * C * P * PSUM_BITS
            sca += tc * (k * k * ci) * P * ACT_BITS
        out[c] = dict(reduce=red, scatter=sca, total=red + sca, tiles=tiles, r=r)
    return out


def main():
    res = {w: analyse(L) for w, L in WORKLOADS.items()}

    with open(f"{HERE}/bw_crossover_r_s{S_FIX}.csv", "w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["workload", "c", "r", "s", "tiles", "reduce_Gbit",
                     "scatter_Gbit", "total_Gbit", "reduce_share"])
        for w, d in res.items():
            for c, v in d.items():
                wr.writerow([w, c, v["r"], S_FIX, v["tiles"],
                             round(v["reduce"] / 1e9, 6),
                             round(v["scatter"] / 1e9, 6),
                             round(v["total"] / 1e9, 6),
                             round(v["reduce"] / v["total"], 4)])
    with open(f"{HERE}/bw_crossover_r_s{S_FIX}.json", "w") as fh:
        json.dump({w: {str(c): v for c, v in d.items()} for w, d in res.items()},
                  fh, indent=2)

    vals = [v[k] / 1e9 for d in res.values() for v in d.values()
            for k in ("reduce", "scatter", "total") if v[k] > 0]
    lo = 10 ** math.floor(math.log10(min(vals)))
    hi = 10 ** math.ceil(math.log10(max(vals)))

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.0), sharex=True, sharey=True)
    for ax, (w, d) in zip(axes, res.items()):
        cs = sorted(d)
        # total is drawn as a wide pale halo: scatter lies almost exactly on it
        # (reduce is <3% of the total everywhere), so a same-width line would
        # hide scatter completely.
        ax.plot(cs, [d[c]["total"] / 1e9 for c in cs], "-", color="#7d3c98",
                lw=7, alpha=.30, solid_capstyle="round", zorder=1,
                label="TOTAL NoC demand")
        ax.plot(cs, [d[c]["scatter"] / 1e9 for c in cs], "o-", color="#2874a6",
                lw=2, ms=7, zorder=3, label="scatter — activations (flat in c)")
        ax.plot(cs, [d[c]["reduce"] / 1e9 for c in cs], "s--", color="#c0392b",
                lw=2, ms=7, zorder=3, label="reduce — partial sums (falls with c)")
        ax.axvline(8, color="k", ls=":", lw=1.2)
        ax.set_xscale("log", base=2); ax.set_yscale("log")
        ax.set_ylim(lo, hi)
        ax.set_xticks(C_SWEEP); ax.set_xticklabels(C_SWEEP)
        sh0 = d[cs[0]]["reduce"] / d[cs[0]]["total"] * 100
        sh1 = d[cs[-1]]["reduce"] / d[cs[-1]]["total"] * 100
        ax.set_title(f"{w}   reduce share {sh0:.0f}% -> {sh1:.1f}%")
        ax.set_xlabel(f"c   (r = c/{S_FIX};  s fixed at {S_FIX})")
        ax.grid(alpha=.3, which="both")
    axes[0].set_ylabel("NoC demand per inference (Gbit)")
    axes[0].legend(fontsize=8.5, loc="lower left")
    fig.suptitle(
        f"The c=r figure split into its two NoC traffic classes "
        f"(s fixed at {S_FIX}, r = c/{S_FIX}).\n"
        f"reduce falls with c — deeper row grouping internalises the reduction. "
        f"scatter is flat — s is pinned, so the tile-column count never changes.",
        fontsize=11)
    fig.tight_layout()
    fig.savefig(f"{HERE}/bw_crossover_r_s{S_FIX}.png", dpi=150)
    print(f"wrote bw_crossover_r_s{S_FIX}.{{csv,json,png}}")
    for w, d in res.items():
        cs = sorted(d)
        print(f"  {w:<10} reduce {d[cs[0]]['reduce']/1e9:.4f} -> "
              f"{d[cs[-1]]['reduce']/1e9:.4f}   scatter flat at "
              f"{d[cs[0]]['scatter']/1e9:.3f}   tiles {d[cs[0]]['tiles']} -> "
              f"{d[cs[-1]]['tiles']}")


if __name__ == "__main__":
    main()
