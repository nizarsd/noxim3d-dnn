#!/usr/bin/env python3
"""Plot the Stage 2 DNN traffic load sweep (DP vs bufferlevel, 6x6x3).

Reads results_dnn_scale_sweep/summary.csv and writes two figures:
  fig1_load_response.png  -- delay and throughput vs load scale (operating regime)
  fig2_dp_vs_bl.png       -- DP-vs-BL deltas with significance

Palette: slots 1-2 of the validated categorical reference palette, light mode.
"""
import csv, math, statistics as st
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SRC = "results_dnn_scale_sweep/summary.csv"

# --- design tokens (light mode) ---------------------------------------------
SURFACE = "#fcfcfb"
TEXT_1 = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e6e5e1"
BL_C = "#2a78d6"   # categorical slot 1 (blue)  -- bufferlevel
DP_C = "#eb6834"   # categorical slot 2 (orange) -- DP
POS_C = "#2a78d6"  # diverging pole: DP better
NEG_C = "#e34948"  # diverging pole: DP worse
MID_C = "#f0efec"  # diverging neutral midpoint

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "font.family": "DejaVu Sans", "font.size": 9,
    "text.color": TEXT_1, "axes.labelcolor": TEXT_2, "axes.edgecolor": GRID,
    "xtick.color": TEXT_2, "ytick.color": TEXT_2,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "grid.linestyle": "-", "axes.axisbelow": True,
})


def load():
    per = defaultdict(list)
    for r in csv.DictReader(open(SRC)):
        per[(r["selection"], float(r["load_scale"]))].append(r)
    return per


def mean(v):
    return sum(v) / len(v)


def welch_t(a, b):
    va, vb, na, nb = st.variance(a), st.variance(b), len(a), len(b)
    se = math.sqrt(va / na + vb / nb)
    return (mean(a) - mean(b)) / se if se else float("inf")


def series(per, sel, field, scales):
    return [mean([float(r[field]) for r in per[(sel, s)]]) for s in scales]


def seeds(per, sel, field, scales):
    return [[float(r[field]) for r in per[(sel, s)]] for s in scales]


def tidy(ax):
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_linewidth(0.8)
        ax.spines[side].set_color(GRID)


def fig1(per, scales):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.3))

    # --- panel A: delay -----------------------------------------------------
    for sel, c, lab in (("bufferlevel", BL_C, "bufferlevel"), ("dp", DP_C, "DP")):
        m = series(per, sel, "avg_delay", scales)
        a1.plot(scales, m, "-o", color=c, lw=2, ms=6, mec=SURFACE, mew=1.5,
                label=lab, zorder=3)
        for x, pts in zip(scales, seeds(per, sel, "avg_delay", scales)):
            a1.plot([x] * len(pts), pts, "o", color=c, ms=3.5, alpha=0.45,
                    mec="none", zorder=2)
    a1.axvspan(0.02, 0.03, color=BL_C, alpha=0.06, zorder=0, lw=0)
    a1.text(0.0245, 55, "knee", ha="center", fontsize=8.5, color=TEXT_2, style="italic")
    a1.set_xscale("log"); a1.set_yscale("log")
    a1.set_xlabel("load scale"); a1.set_ylabel("mean packet delay (cycles)")
    a1.set_title("Delay climbs 1000x across the sweep", fontsize=10.5,
                 color=TEXT_1, loc="left", pad=10)
    a1.text(0.055, 0.30, "the two policies overlap at every load",
            transform=a1.transAxes, fontsize=8.5, color=TEXT_2, style="italic")
    a1.legend(frameon=False, loc="lower right", fontsize=9)

    # --- panel B: throughput ------------------------------------------------
    base = series(per, "bufferlevel", "avg_throughput", scales)[0]
    ideal = [base * (s / scales[0]) for s in scales]
    a2.plot(scales, ideal, "--", color="#a9a8a3", lw=1.5, zorder=1,
            label="ideal (linear in load)")
    for sel, c, lab in (("bufferlevel", BL_C, "bufferlevel"), ("dp", DP_C, "DP")):
        m = series(per, sel, "avg_throughput", scales)
        a2.plot(scales, m, "-o", color=c, lw=2, ms=6, mec=SURFACE, mew=1.5,
                label=lab, zorder=3)
        for x, pts in zip(scales, seeds(per, sel, "avg_throughput", scales)):
            a2.plot([x] * len(pts), pts, "o", color=c, ms=3.5, alpha=0.45,
                    mec="none", zorder=2)
    a2.annotate("saturation ceiling", xy=(0.20, 0.00724),
                xytext=(0.062, 0.0126), fontsize=8.5, color=TEXT_2,
                ha="center",
                arrowprops=dict(arrowstyle="-", color="#a9a8a3", lw=0.9))
    a2.set_xscale("log"); a2.set_yscale("log")
    a2.set_xlabel("load scale"); a2.set_ylabel("throughput (flits/cycle/IP)")
    a2.set_title("Throughput saturates from ls≈0.03", fontsize=10.5,
                 color=TEXT_1, loc="left", pad=10)
    a2.legend(frameon=False, loc="upper left", fontsize=9)

    for ax in (a1, a2):
        ax.set_xticks(scales)
        ax.set_xticklabels([f"{s:g}" for s in scales])
        ax.minorticks_off()
        tidy(ax)

    fig.suptitle("ResNet-50 bottleneck on 6×6×3 — only ls=0.01 is a "
                 "lightly-loaded point", fontsize=12, color=TEXT_1, x=0.008,
                 ha="left", y=0.99)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig("fig1_load_response.png", dpi=200)
    print("wrote fig1_load_response.png")


def fig2(per, scales):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.3))
    idx = range(len(scales))

    panels = [
        (a1, "avg_delay", True, "delay reduction (%)",
         "DP delay advantage — none of it significant"),
        (a2, "avg_throughput", False, "throughput gain (%)",
         "DP throughput gain — real at saturation"),
    ]
    for ax, field, lower_better, ylab, title in panels:
        vals, sigs = [], []
        for s in scales:
            bl = [float(r[field]) for r in per[("bufferlevel", s)]]
            dp = [float(r[field]) for r in per[("dp", s)]]
            if lower_better:
                vals.append((mean(bl) - mean(dp)) / mean(bl) * 100)
                t = welch_t(bl, dp)
            else:
                vals.append((mean(dp) - mean(bl)) / mean(bl) * 100)
                t = welch_t(dp, bl)
            sigs.append(abs(t) >= 2.8)
        for i, (v, sig) in enumerate(zip(vals, sigs)):
            c = POS_C if v >= 0 else NEG_C
            ax.bar(i, v, width=0.62, color=c, alpha=1.0 if sig else 0.32,
                   edgecolor=SURFACE, linewidth=2, zorder=3)
            off = 0.9 if v >= 0 else -0.9
            ax.text(i, v + off, "p<0.01" if sig else "ns", ha="center",
                    va="bottom" if v >= 0 else "top", fontsize=8,
                    color=TEXT_1 if sig else TEXT_2,
                    fontweight="bold" if sig else "normal")
        ax.axhline(0, color=TEXT_2, lw=0.9, zorder=4)
        ax.set_xticks(list(idx))
        ax.set_xticklabels([f"{s:g}" for s in scales])
        ax.set_xlabel("load scale"); ax.set_ylabel(ylab)
        ax.set_title(title, fontsize=10.5, color=TEXT_1, loc="left", pad=10)
        lo, hi = min(vals + [0]), max(vals + [0])
        pad = (hi - lo) * 0.26 + 1
        ax.set_ylim(lo - pad, hi + pad)
        tidy(ax)

    fig.text(0.008, 0.035, "positive = DP better · solid bars are significant "
             "(Welch t, n=3)", fontsize=8.5, color=TEXT_2, style="italic")
    fig.text(0.008, 0.005, "at ls=0.2 DP carried 6.8% more traffic, so it sits "
             "further up the same delay curve — a different operating point, "
             "not a regression", fontsize=8.5, color=TEXT_2)
    fig.suptitle("DP vs bufferlevel — the delay story is noise, the "
                 "throughput story is not", fontsize=12, color=TEXT_1,
                 x=0.008, ha="left", y=0.99)
    fig.tight_layout(rect=[0, 0.065, 1, 0.94])
    fig.savefig("fig2_dp_vs_bl.png", dpi=200)
    print("wrote fig2_dp_vs_bl.png")


if __name__ == "__main__":
    per = load()
    scales = sorted({k[1] for k in per})
    fig1(per, scales)
    fig2(per, scales)
