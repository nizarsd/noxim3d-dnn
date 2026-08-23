#!/usr/bin/env python3
"""
Stage 3 / Task 1 - intra-tile vs inter-tile partial-sum bandwidth demand.

Model (ISAAC convention, settled constants):
  crossbar        : 128 x 128 cells, 1 bit/cell
  weight precision: 8 bits  -> 16 usable weight columns -> 2048 weights/crossbar
  partial sum     : 16 bits
  crossbars/layer : ceil(k*k*Cin / PE_X) * ceil(Cout*N_BITS / PE_Y)

Reduction structure:
  R = ceil(k*k*Cin / 128)   row groups  -> R partials must be summed per output group
  C = ceil(Cout*8  / 128)   column groups (16 output channels each)
  With T crossbars/tile packed along the row-group axis:
     tiles spanned per column group = ceil(R/T)
     inter-tile partial-sum hops    = ceil(R/T) - 1
     intra-tile reductions          = R - ceil(R/T)
  Volume scales by the number of output positions P (H_out*W_out for conv,
  token count for ViT), and by 16 bits per partial sum.

Reported quantity is DEMAND (bits moved per inference), not service.
The simulator does not model intra-tile contention; denser packing relocates
aggregation cost onto the on-tile H-tree rather than removing it.
"""

import math, csv, json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PE_X = 128          # crossbar rows
PE_Y = 128          # crossbar columns (cells)
N_BITS = 8          # weight precision
PSUM_BITS = 16      # partial-sum payload width

# ---------------------------------------------------------------- workloads
# (name, k, Cin, Cout, P)  P = output positions (H_out*W_out, or tokens)
def resnet50():
    L = [("conv1", 7, 3, 64, 112*112)]
    # (stage, out_hw, Cin_first, width, Cout, blocks)
    stages = [(56, 64, 64, 256, 3), (28, 256, 128, 512, 4),
              (14, 512, 256, 1024, 6), (7, 1024, 512, 2048, 3)]
    for si, (hw, cin0, w, cout, nb) in enumerate(stages):
        for b in range(nb):
            cin = cin0 if b == 0 else cout
            L.append((f"s{si+2}b{b}_1x1a", 1, cin, w, hw*hw))
            L.append((f"s{si+2}b{b}_3x3",  3, w,   w, hw*hw))
            L.append((f"s{si+2}b{b}_1x1b", 1, w, cout, hw*hw))
            if b == 0:
                L.append((f"s{si+2}b{b}_down", 1, cin, cout, hw*hw))
    L.append(("fc", 1, 2048, 1000, 1))
    return L

def vgg16():
    cfg = [(3,64,224),(64,64,224),(64,128,112),(128,128,112),
           (128,256,56),(256,256,56),(256,256,56),
           (256,512,28),(512,512,28),(512,512,28),
           (512,512,14),(512,512,14),(512,512,14)]
    L = [(f"conv{i+1}", 3, ci, co, hw*hw) for i,(ci,co,hw) in enumerate(cfg)]
    L += [("fc6", 1, 25088, 4096, 1), ("fc7", 1, 4096, 4096, 1),
          ("fc8", 1, 4096, 1000, 1)]
    return L

def vit_base():
    D, H, TOK, LYR = 768, 3072, 197, 12
    L = []
    L.append(("patch_embed", 1, 3*16*16, D, 196))
    for i in range(LYR):
        L.append((f"blk{i}_qkv",  1, D, 3*D, TOK))
        L.append((f"blk{i}_proj", 1, D, D,   TOK))
        L.append((f"blk{i}_fc1",  1, D, H,   TOK))
        L.append((f"blk{i}_fc2",  1, H, D,   TOK))
    L.append(("head", 1, D, 1000, 1))
    return L

WORKLOADS = {"ResNet-50": resnet50(), "VGG-16": vgg16(), "ViT-Base": vit_base()}
TILE_SIZES = [4, 8, 16, 32, 64]

# ---------------------------------------------------------------- model
def layer_geometry(k, cin, cout):
    R = math.ceil(k*k*cin / PE_X)
    C = math.ceil(cout*N_BITS / PE_Y)
    return R, C, R*C

def split(R, C, P, T):
    tiles = math.ceil(R / T)
    inter = (tiles - 1) * C * P * PSUM_BITS
    intra = (R - tiles) * C * P * PSUM_BITS
    return intra, inter

def analyse(layers):
    xb_total = sum(layer_geometry(k, ci, co)[2] for _, k, ci, co, _ in layers)
    out = {}
    for T in TILE_SIZES:
        ia = ie = 0
        for _, k, ci, co, P in layers:
            R, C, _ = layer_geometry(k, ci, co)
            a, e = split(R, C, P, T)
            ia += a; ie += e
        out[T] = (ia, ie)
    return xb_total, out

def crossing(res):
    """Linear interpolation in log2(T) of the intra/inter crossover."""
    ts = TILE_SIZES
    for i in range(len(ts)-1):
        d0 = res[ts[i]][0] - res[ts[i]][1]
        d1 = res[ts[i+1]][0] - res[ts[i+1]][1]
        if d0 == 0: return float(ts[i])
        if d0 * d1 < 0:
            f = -d0 / (d1 - d0)
            return 2 ** (math.log2(ts[i]) + f*(math.log2(ts[i+1])-math.log2(ts[i])))
    return None

# ---------------------------------------------------------------- run
summary, rows = {}, []
for name, layers in WORKLOADS.items():
    xb, res = analyse(layers)
    x = crossing(res)
    summary[name] = {"crossbars": xb, "crossing": x,
                     "curves": {T: {"intra_Gb": res[T][0]/1e9,
                                    "inter_Gb": res[T][1]/1e9} for T in TILE_SIZES}}
    for T in TILE_SIZES:
        rows.append({"workload": name, "crossbars_total": xb, "crossbars_per_tile": T,
                     "tiles": math.ceil(xb/T),
                     "intra_tile_Gbit": round(res[T][0]/1e9, 4),
                     "inter_tile_Gbit": round(res[T][1]/1e9, 4),
                     "inter_share": round(res[T][1]/max(1,(res[T][0]+res[T][1])), 4)})

with open("/home/claude/stage3/bw_crossover.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
with open("/home/claude/stage3/bw_crossover.json", "w") as f:
    json.dump(summary, f, indent=2)

# ---------------------------------------------------------------- plot
fig, axes = plt.subplots(1, 3, figsize=(13, 4.2), sharey=False)
for ax, (name, layers) in zip(axes, WORKLOADS.items()):
    s = summary[name]
    intra = [s["curves"][T]["intra_Gb"] for T in TILE_SIZES]
    inter = [s["curves"][T]["inter_Gb"] for T in TILE_SIZES]
    ax.plot(TILE_SIZES, intra, "o-", color="#2f6f9f", label="intra-tile")
    ax.plot(TILE_SIZES, inter, "s-", color="#c1553b", label="inter-tile (NoC)")
    ax.set_xscale("log", base=2); ax.set_yscale("log")
    ax.set_xticks(TILE_SIZES); ax.set_xticklabels(TILE_SIZES)
    if s["crossing"]:
        ax.axvline(s["crossing"], ls="--", lw=1, color="#666")
        ax.annotate(f"x-over ≈ {s['crossing']:.1f}", (s["crossing"], min(intra+inter)*1.3),
                    fontsize=8, rotation=90, va="bottom", ha="right", color="#444")
    ax.axvline(16, ls=":", lw=1, color="#999")
    ax.set_title(f"{name}  ({s['crossbars']:,} crossbars)", fontsize=10)
    ax.set_xlabel("crossbars per tile"); ax.grid(alpha=.3, which="both", lw=.4)
axes[0].set_ylabel("partial-sum demand per inference (Gbit)")
axes[0].legend(fontsize=8)
fig.suptitle("Intra-tile vs inter-tile partial-sum bandwidth demand (128×128 xbar, 8-bit W, 16-bit psum)",
             fontsize=11)
fig.tight_layout()
fig.savefig("/home/claude/stage3/bw_crossover.png", dpi=160)

for name in WORKLOADS:
    s = summary[name]
    print(f"\n{name}: {s['crossbars']:,} crossbars, crossing "
          f"{'≈ %.1f' % s['crossing'] if s['crossing'] else 'none in range'}")
    print(f"  {'T':>4} {'tiles':>7} {'intra Gb':>10} {'inter Gb':>10} {'inter %':>8}")
    for T in TILE_SIZES:
        c = s["curves"][T]
        sh = 100*c["inter_Gb"]/max(1e-12, c["intra_Gb"]+c["inter_Gb"])
        print(f"  {T:>4} {math.ceil(s['crossbars']/T):>7} {c['intra_Gb']:>10.3f} "
              f"{c['inter_Gb']:>10.3f} {sh:>7.1f}%")
