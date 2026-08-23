#!/usr/bin/env python3
"""
Stage 3 / Task 1 (v2) - intra vs inter-tile partial-sum bandwidth demand.

Adds three things v1 lacked:
  1. T = 1, 2 (the crossing sits BELOW the queue's {4..64} range)
  2. packing-policy sensitivity: row-major (best case for intra reduction)
     vs blocked (sqrt(T) x sqrt(T) of row x column groups) - a tile that
     spends half its capacity on column groups cannot reduce across them.
  3. inter-layer ACTIVATION traffic as a reference line: it is independent
     of packing, so once psum inter-tile traffic drops below it, packing
     stops being the lever that controls NoC load.

DEMAND, not service. The simulator does not model intra-tile contention.
"""
import math, csv, json
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from bw_crossover import WORKLOADS, PE_X, PE_Y, N_BITS, PSUM_BITS, layer_geometry

ACT_BITS = 8                       # activation precision on the wire
TILE_SIZES = [1, 2, 4, 8, 16, 32, 64]

def split_rowmajor(R, C, P, T):
    tiles = math.ceil(R / T)
    return (R - tiles)*C*P*PSUM_BITS, (tiles - 1)*C*P*PSUM_BITS

def split_blocked(R, C, P, T):
    """Tile holds tr row-groups x tc column-groups, tr*tc = T, tr = min(R, 2^floor(log2T/2))."""
    tr = max(1, int(2 ** (math.log2(T)//2)))
    tr = min(tr, max(1, R))
    tiles = math.ceil(R / tr)
    return (R - tiles)*C*P*PSUM_BITS, (tiles - 1)*C*P*PSUM_BITS

def activation_bits(layers):
    """Output activations forwarded to the next layer's tiles."""
    tot = 0
    for _, k, ci, co, P in layers:
        tot += co * P * ACT_BITS
    return tot

def crossing(xs, a, b):
    for i in range(len(xs)-1):
        d0, d1 = a[i]-b[i], a[i+1]-b[i+1]
        if d0 == 0: return float(xs[i])
        if d0*d1 < 0:
            f = -d0/(d1-d0)
            return 2**(math.log2(xs[i]) + f*(math.log2(xs[i+1])-math.log2(xs[i])))
    return None

summary, rows = {}, []
for name, layers in WORKLOADS.items():
    xb = sum(layer_geometry(k, ci, co)[2] for _, k, ci, co, _ in layers)
    act = activation_bits(layers)
    cur = {}
    for tag, fn in (("row", split_rowmajor), ("blk", split_blocked)):
        ia, ie = [], []
        for T in TILE_SIZES:
            a = e = 0
            for _, k, ci, co, P in layers:
                R, C, _ = layer_geometry(k, ci, co)
                da, de = fn(R, C, P, T); a += da; e += de
            ia.append(a/1e9); ie.append(e/1e9)
        cur[tag] = (ia, ie)
    summary[name] = {"crossbars": xb, "act_Gb": act/1e9,
        "x_row": crossing(TILE_SIZES, *cur["row"]),
        "x_blk": crossing(TILE_SIZES, *cur["blk"]),
        "psum_eq_act_row": crossing(TILE_SIZES, cur["row"][1], [act/1e9]*len(TILE_SIZES)),
        "curves": {t: {"intra": cur[t][0], "inter": cur[t][1]} for t in cur}}
    for i, T in enumerate(TILE_SIZES):
        rows.append({"workload": name, "crossbars_per_tile": T, "tiles": math.ceil(xb/T),
            "intra_row_Gb": round(cur["row"][0][i],4), "inter_row_Gb": round(cur["row"][1][i],4),
            "intra_blk_Gb": round(cur["blk"][0][i],4), "inter_blk_Gb": round(cur["blk"][1][i],4),
            "activation_Gb": round(act/1e9,4),
            "noc_total_row_Gb": round(cur["row"][1][i]+act/1e9,4),
            "psum_share_of_noc_row": round(cur["row"][1][i]/(cur["row"][1][i]+act/1e9),4)})

with open("/home/claude/stage3/bw_crossover.csv","w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
with open("/home/claude/stage3/bw_crossover.json","w") as f: json.dump(summary,f,indent=2)

fig, axes = plt.subplots(1,3,figsize=(13.5,4.4))
for ax,(name,layers) in zip(axes, WORKLOADS.items()):
    s=summary[name]; c=s["curves"]
    ax.plot(TILE_SIZES,c["row"]["intra"],"o-",color="#2f6f9f",label="intra-tile (row-major)")
    ax.plot(TILE_SIZES,c["row"]["inter"],"s-",color="#c1553b",label="inter-tile psum (row-major)")
    ax.plot(TILE_SIZES,c["blk"]["inter"],"s--",color="#e08a70",lw=1.2,label="inter-tile psum (blocked)")
    ax.axhline(s["act_Gb"],color="#4a8a5c",ls="-.",lw=1.3,label="inter-layer activations")
    if s["x_row"]:
        ax.axvline(s["x_row"],ls="--",lw=1,color="#666")
        ax.annotate(f"x-over {s['x_row']:.1f}",(s["x_row"],ax.get_ylim()[0]),fontsize=8,
                    rotation=90,va="bottom",ha="right",color="#444")
    ax.axvspan(4,64,color="#000",alpha=.03)
    ax.set_xscale("log",base=2); ax.set_yscale("log")
    ax.set_xticks(TILE_SIZES); ax.set_xticklabels(TILE_SIZES)
    ax.set_title(f"{name} ({s['crossbars']:,} crossbars)",fontsize=10)
    ax.set_xlabel("crossbars per tile"); ax.grid(alpha=.3,which="both",lw=.4)
axes[0].set_ylabel("demand per inference (Gbit)")
axes[0].legend(fontsize=7,loc="lower left")
fig.suptitle("Partial-sum vs activation bandwidth demand (128×128 xbar, 8-bit W, 16-bit psum). Shaded = queue's original sweep range.",fontsize=10)
fig.tight_layout(); fig.savefig("/home/claude/stage3/bw_crossover.png",dpi=160)

for name in WORKLOADS:
    s=summary[name]; c=s["curves"]
    print(f"\n{name}: {s['crossbars']:,} xbars | activation traffic {s['act_Gb']:.4f} Gb "
          f"| intra/inter x-over row={s['x_row']} blk={s['x_blk']} "
          f"| psum==act at T={s['psum_eq_act_row']}")
    print(f"  {'T':>3} {'tiles':>6} {'intra':>8} {'inter':>8} {'inter_blk':>10} {'psum% of NoC':>13}")
    for i,T in enumerate(TILE_SIZES):
        ie=c["row"]["inter"][i]
        print(f"  {T:>3} {math.ceil(s['crossbars']/T):>6} {c['row']['intra'][i]:>8.4f} "
              f"{ie:>8.4f} {c['blk']['inter'][i]:>10.4f} {100*ie/(ie+s['act_Gb']):>12.1f}%")
