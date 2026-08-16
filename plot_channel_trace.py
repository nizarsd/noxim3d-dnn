#!/usr/bin/env python3
"""How DP's congestion estimators see one busy channel.

Reads DPTRACE csv (T,cycle,qlen,flits_total -- one line per cycle for a single
node/direction) and reconstructs, offline, what each estimator would have
reported.  One simulation run, any interval, any decay.

Usage: plot_channel_trace.py TRACE_4X [TRACE_1X] [node:dir]

The cinterval overlays are computed offline from the raw per-cycle trace, so
they cost nothing to change.  The dp_clock multiplier does NOT -- it changes
routing decisions and therefore the trajectory, so 1x and 4x are two separate
runs and panel D compares two realisations, not a per-cycle diff.

Panels
  A  full run under 4x: instantaneous queue vs the block average DP actually
     uses (4998), DNN phase boundaries marked -- does the estimator track the
     workload's phase structure at all
  B  one t_period zoomed: block averages at 4998 / 500 / 100 against the raw
     queue, so the dilution is visible rather than inferred
  C  the wait metric W = load/sent under those same intervals
  D  1x vs 4x dp_clock on the same channel and window -- whether converging
     the cost field 4x faster changes what the channel actually experiences

Colour: categorical slots 1-3 (validate all-pairs); raw trace in grey.
"""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SRC_4X = sys.argv[1] if len(sys.argv) > 1 else "results_trace/node49_dir4_ls022_seed2_4x.csv"
SRC_1X = sys.argv[2] if len(sys.argv) > 2 else None
NODE, DIR = (sys.argv[3] if len(sys.argv) > 3 else "49:4").split(":")

T_PERIOD = 38536
RESET = 1000                      # trace cycle c  ->  traffic gate sees c + RESET
PHASES = [("conv1", 0, 5138), ("conv2", 5138, 28259), ("conv3", 28259, 38535)]
MAXB = 16

# DP_COST_WAIT_MAX = 1000000 centi-cycles (NoximDefs.h) -> 10,000 cycles.
# Also the cost charged to a channel that sent nothing while holding flits.
WAIT_CLAMP = 10000.0
# 1029 is the run setting for the 4x arm (== dp_cycle under DP_CLOCK_MULT=4);
# 4998 is what the 1x arm uses; 100 is a fine reference.
INTERVALS = (4998, 1029, 100)
RUN_CI = 1029

SURFACE, TEXT_1, TEXT_2 = "#fcfcfb", "#0b0b0b", "#52514e"
GRID, RAW = "#e6e5e0", "#c9c8c3"
C1, C2, C3 = "#2a78d6", "#eb6834", "#1baf7a"

plt.rcParams.update({"figure.facecolor": SURFACE, "savefig.facecolor": SURFACE,
                     "font.family": "DejaVu Sans", "font.size": 9,
                     "text.color": TEXT_1, "axes.facecolor": SURFACE})


def load(path):
    opener = open
    if path.endswith(".gz"):
        import gzip
        opener = gzip.open
    t, q, f = [], [], []
    with opener(path, "rt") as fh:
        for line in fh:
            if not line.startswith("T,"):
                continue
            _, c, ql, ft = line.rstrip("\n").split(",")
            t.append(int(c)); q.append(int(ql)); f.append(int(ft))
    dep = [0] + [f[i] - f[i - 1] for i in range(1, len(f))]
    return t, q, dep


def block_avg(t, q, dep, interval):
    """What accumulate-and-reset reports: piecewise-constant, one value per window."""
    xs, occ, wait = [], [], []
    load = sent = n = 0
    for i in range(len(t)):
        load += q[i]; sent += dep[i]; n += 1
        if n == interval:
            xs.append(t[i])
            occ.append(100.0 * load / (n * MAXB))
            # sent==0 with flits held == blocked channel; DP charges the clamp.
            wait.append(load / sent if sent
                        else (float("nan") if load == 0 else WAIT_CLAMP))
            load = sent = n = 0
    return xs, occ, wait


def window(xs, ys, lo, hi):
    p = [(x, y) for x, y in zip(xs, ys) if lo <= x < hi and y == y]
    return [a for a, _ in p], [b for _, b in p]


def phase_spans(lo, hi):
    """Phase windows overlapping [lo,hi), in trace-cycle coordinates."""
    out = []
    k0 = (lo + RESET) // T_PERIOD
    for k in range(k0, (hi + RESET) // T_PERIOD + 2):
        for name, a, b in PHASES:
            s, e = k * T_PERIOD + a - RESET, k * T_PERIOD + b - RESET
            if e > lo and s < hi:
                out.append((name, max(s, lo), min(e, hi)))
    return out


def frame(ax, title, xlab=None):
    ax.set_title(title, fontsize=10.5, color=TEXT_1, loc="left", pad=6)
    ax.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color(GRID)
    ax.tick_params(colors=TEXT_2, labelsize=8)
    if xlab:
        ax.set_xlabel(xlab, color=TEXT_2, fontsize=9)


def main():
    t, q, dep = load(SRC_4X)
    ref = load(SRC_1X) if SRC_1X else None

    npanel = 4 if ref else 3
    fig, ax = plt.subplots(npanel, 1, figsize=(13, 3.7 * npanel))

    # ---- A: whole run --------------------------------------------------
    a = ax[0]
    a.fill_between(t, [100.0 * v / MAXB for v in q], color=RAW, lw=0,
                   label="instantaneous queue", rasterized=True)
    xs, occ, _ = block_avg(t, q, dep, RUN_CI)
    a.step(xs, occ, where="post", color=C1, lw=2,
           label=f"block average, cinterval {RUN_CI} — what DP actually uses")
    for name, s, e in phase_spans(t[0], t[-1]):
        if name == "conv2":
            a.axvspan(s, e, color=C2, alpha=0.07, lw=0)
    a.set_ylabel("occupancy (% of buffer)", color=TEXT_2, fontsize=9)
    a.set_xlim(t[0], t[-1]); a.set_ylim(0, 100)
    a.legend(frameon=False, fontsize=8.5, loc="upper right")
    frame(a, f"A · node {NODE} dir {DIR}, whole run at 4× dp_clock, cinterval "
             f"{RUN_CI} — shaded bands are conv2 phases")

    # ---- B: one period zoomed ------------------------------------------
    lo = 4 * T_PERIOD - RESET
    hi = min(lo + T_PERIOD, t[-1])
    sl = slice(lo, hi)
    b = ax[1]
    b.fill_between(t[sl], [100.0 * v / MAXB for v in q[sl]], color=RAW, lw=0,
                   label="instantaneous queue", rasterized=True)
    for iv, col, lw in zip(INTERVALS, (C1, C2, C3), (2.0, 1.6, 1.2)):
        xs, occ, _ = block_avg(t, q, dep, iv)
        wx, wy = window(xs, occ, lo, hi)
        if wx:
            b.step(wx, wy, where="post", color=col, lw=lw,
                   label=f"block average, cinterval {iv}")
    for name, s, e in phase_spans(lo, hi):
        b.axvline(s, color=TEXT_2, lw=0.7, ls=":", alpha=0.6)
        b.text(s + 300, 96, name, fontsize=8, color=TEXT_2)
    b.set_ylabel("occupancy (% of buffer)", color=TEXT_2, fontsize=9)
    b.set_xlim(lo, hi); b.set_ylim(0, 100)
    b.legend(frameon=False, fontsize=8.5, loc="upper right")
    frame(b, "B · one t_period zoomed — shorter cinterval recovers the bursts")

    # ---- C: wait metric ------------------------------------------------
    # Log axis: the real waits are O(1-100) but a blocked window is charged the
    # 10,000-cycle clamp, so on a linear axis the clamp spikes erase everything
    # that actually varies.  The clamp is a saturation flag, not a measurement.
    c = ax[2]
    clamped = {}
    for iv, col, lw in zip(INTERVALS, (C1, C2, C3), (2.0, 1.6, 1.2)):
        xs, _, wt = block_avg(t, q, dep, iv)
        wx, wy = window(xs, wt, lo, hi)
        if not wx:
            continue
        clamped[iv] = (sum(1 for v in wy if v >= WAIT_CLAMP), len(wy))
        c.step(wx, [max(v, 0.05) for v in wy], where="post", color=col, lw=lw,
               label=f"wait W = load/sent, cinterval {iv}")
    c.set_yscale("log")
    c.set_ylim(0.05, 30000)
    c.set_ylabel("wait (cycles per flit, log)", color=TEXT_2, fontsize=9)
    c.set_xlim(lo, hi)
    c.axhline(WAIT_CLAMP, color=TEXT_2, lw=0.8, ls="--", alpha=0.7)
    c.text(lo + 300, WAIT_CLAMP * 1.25,
           f"clamp = {WAIT_CLAMP:.0f} cycles  —  hit in "
           + ", ".join(f"{n}/{m} windows at ci {iv}"
                       for iv, (n, m) in clamped.items()),
           fontsize=8, color=TEXT_2)
    c.legend(frameon=False, fontsize=8.5, loc="lower right", ncol=3)
    frame(c, "C · the wait metric over the same window — shorter cinterval "
             "mostly buys more clamp hits, not more resolution",
          None if ref else "cycle")

    # ---- D: 1x vs 4x dp_clock ------------------------------------------
    if ref:
        rt, rq, rdep = ref
        d = ax[3]
        for (tt, qq, dd), col, lab, ci in (
                ((rt, rq, rdep), C2, "1× dp_clock, cinterval 4998", 4998),
                ((t, q, dep), C1, "4× dp_clock, cinterval 1029", 1029)):
            xs, occ, _ = block_avg(tt, qq, dd, ci)
            wx, wy = window(xs, occ, lo, hi)
            d.step(wx, wy, where="post", color=col, lw=1.6, label=lab)
        d.set_ylabel("occupancy (% of buffer)", color=TEXT_2, fontsize=9)
        d.set_xlim(lo, hi); d.set_ylim(0, 100)
        d.legend(frameon=False, fontsize=8.5, loc="upper right")
        frame(d, "D · the two arms as actually run — each at its own dp_cycle. "
                 "Two runs, not a per-cycle diff", "cycle")

    # Header offsets in inches, so they do not collide as npanel changes height.
    H = fig.get_size_inches()[1]
    fig.suptitle("What DP's congestion estimators see on one busy channel",
                 fontsize=13.5, color=TEXT_1, x=0.006, ha="left", y=1 - 0.30 / H)
    fig.text(0.006, 1 - 0.62 / H,
             f"7×7×3, ls=0.022, seed 2, -dpcost wait, node "
             f"{NODE} dir {DIR}, run cinterval {RUN_CI} (= dp_cycle at 4×). Other "
             f"intervals are recomputed offline; the dp_clock arms are separate runs.",
             fontsize=9.5, color=TEXT_2, ha="left")
    fig.tight_layout(rect=[0, 0, 1, 1 - 0.95 / H])
    fig.savefig("fig5_channel_trace_4x.png", dpi=170)
    print("wrote fig5_channel_trace_4x.png")

    # ---- numbers behind the panels -------------------------------------
    def stats(tag, tt, qq, dd):
        for iv in INTERVALS:
            xs, occ, wt = block_avg(tt, qq, dd, iv)
            live = [w for w in wt if w == w]
            zero = sum(1 for o in occ if o == 0.0)
            print(f"  {tag:>3}  ci {iv:>4}  n={len(occ):>4}  "
                  f"occ mean {sum(occ)/len(occ):6.2f}%  max {max(occ):6.2f}%  "
                  f"zero-windows {zero:>4}/{len(occ):<4}  "
                  f"wait mean {sum(live)/len(live):8.2f}  max {max(live):9.1f}")
    print("\nblock-average statistics over the whole trace:")
    if ref:
        stats("1×", *ref)
    stats("4×", t, q, dep)


if __name__ == "__main__":
    main()
