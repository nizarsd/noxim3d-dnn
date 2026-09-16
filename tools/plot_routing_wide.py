#!/usr/bin/env python3
"""Full-width version of the routing panel of Fig. 6 (fig:layers_p99).

Per regime (row) x workload (column): the BL/DP gain of every knee-window
placement x load cell, drawn as a box over cells within a load band, with the
band's ratio of pooled means as a marker and the panel's pooled DP and oracle
lines.  Same populations, knee rule and aggregation as plot_layer_bars.py
(results_stage3/mapping_pilot/pool1000/hill/); nothing is hardcoded, every
number is read from the result ladders and the pooled per-regime figures are
gated against the paper's before anything is drawn.

  cell      one placement at one rung, seeds averaged (3, or 5 for res_ladder)
  knee rule a rung is kept while the set's mean BL delay < 30x the set's
            free-flow delay (its lowest rung)
  load band the set's mean BL delay at the rung over its free-flow: <5x, 5-15x,
            15-30x (the same quantity the knee rule uses)
  ratio     BL / DP of the metric (p99 by default); > 1 means DP is better
  pooled    mean over cells of BL / mean over cells of DP (the paper's number)
  oracle    mean BL / mean over cells of min(BL, DP)

DeiT-S below the floor is the (16,1,16) ES-arm population: drawn, not pooled
into the regime line (decision 2026-09-09).

usage: plot_routing_wide.py [--metric p99|mean] [--force]
writes figs/f_routing_wide[_mean].{pdf,png}
"""
import collections, os, statistics as st, sys
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

H = '/home/nizar/noxim3d-dnn/results_stage3/mapping_pilot/pool1000/hill'
FIG = '/home/nizar/noxim3d-dnn/figs'
METRIC = sys.argv[sys.argv.index('--metric') + 1] if '--metric' in sys.argv else 'p99'
FORCE = '--force' in sys.argv
TOPUP = '--topup' in sys.argv          # add results_ext top-up cells (DeiT deep bands)
RE = '/home/nizar/noxim3d-dnn/results_ext/trace_runs'
MI = {'mean': 0, 'p99': 1}[METRIC]
plt.rcParams.update({'pdf.fonttype': 42, 'ps.fonttype': 42, 'font.size': 7})

WL = ['ResNet-50', 'DeiT-S', 'VGG-16']
SETS = {
    'above': {'ResNet-50': ['res_ladder'],
              'DeiT-S':    ['res_e7', 'res_e3_vit_grid'],
              'VGG-16':    ['res_e3_vgg_grid', 'res_e3_vgg824_grid', 'res_e3_vgg842_grid']},
    'below': {'ResNet-50': ['res_bf', 'res_f1'],
              'DeiT-S':    ['res_esxd'],
              'VGG-16':    ['res_f2']},
}
NOT_POOLED = {('below', 'DeiT-S')}
# top-up sets: mixed-policy res files from results_ext; ff comes from the parent
# canonical set so the band axis is unchanged.  Cells are EXCLUDED from the gate
# and from the panel pooled/oracle lines (canonical populations only).
TOPUP_SETS = {('above','DeiT-S'): [(f'{RE}/res_topup_e7.txt','res_e7'),
                                   (f'{RE}/res_topup_e3_vit.txt','res_e3_vit_grid')],
              ('below','DeiT-S'): [(f'{RE}/res_topup_esxd.txt','res_esxd')]}
BANDS = [(0, 5, '<5×'), (5, 15, '5–15×'), (15, 30, '15–30×')]
PAPER = {'p99':  {'above': 2.39, 'below': 1.23, 'orc_above': 2.5, 'orc_below': 7.7},
         'mean': {'above': 1.85, 'below': 1.15, 'orc_above': 1.1, 'orc_below': 3.8}}

BASE_C, TREAT_C, INK, MUTED, GRID = '#9AA3AE', '#2A78D6', '#33373D', '#6B7280', '#E4E6EA'


def load(f):
    """{(tag, k_int): [(mean, p99), ...]} over seeds."""
    d = collections.defaultdict(list)
    for ln in open(f):
        p = ln.split()
        if len(p) < 5 or p[3] == 'NA':
            continue
        tag, k = p[0].rsplit('_k', 1)
        d[(tag, int(k))].append((float(p[3]), float(p[4])))
    return d


def m(d, tag, k, i):
    return st.mean(v[i] for v in d[(tag, k)])


def cells(pre):
    """Knee-window cells of one result set: dict per (placement, rung)."""
    BL, DP = load(f'{H}/{pre}_bl.txt'), load(f'{H}/{pre}_dp.txt')
    tags = sorted({t for (t, _) in BL})
    ks = sorted(set.intersection(*[{k for (t2, k) in BL if t2 == t} for t in tags]))
    ff = st.mean(m(BL, t, ks[0], 0) for t in tags)
    out = []
    for k in ks:
        load_ratio = st.mean(m(BL, t, k, 0) for t in tags) / ff
        if load_ratio >= 30:
            continue
        for t in tags:
            if (t, k) in BL and (t, k) in DP:
                out.append(dict(set=pre, tag=t, k=k / 1000, load=load_ratio,
                                bl=(m(BL, t, k, 0), m(BL, t, k, 1)),
                                dp=(m(DP, t, k, 0), m(DP, t, k, 1))))
    return out


def cells_topup(path, parent):
    """Cells of a mixed-policy top-up res file, banded by the PARENT set's ff."""
    if not os.path.exists(path):
        return []
    BLp = load(f'{H}/{parent}_bl.txt')
    tp = sorted({t for (t, _) in BLp})
    kp = sorted(set.intersection(*[{k for (t2, k) in BLp if t2 == t} for t in tp]))
    ff = st.mean(m(BLp, t, kp[0], 0) for t in tp)
    d = {'bufferlevel': collections.defaultdict(list), 'dp': collections.defaultdict(list)}
    for ln in open(path):
        pr = ln.split()
        if len(pr) < 6 or pr[3] == 'NA':
            continue
        tag, k = pr[0].rsplit('_k', 1)
        d[pr[1]][(tag, int(k))].append((float(pr[3]), float(pr[4])))
    BL, DP = d['bufferlevel'], d['dp']
    tags = sorted({t for (t, _) in BL})
    out = []
    for k in sorted({kk for (_, kk) in BL}):
        have = [t for t in tags if (t, k) in BL and (t, k) in DP]
        if not have:
            continue
        load_ratio = st.mean(m(BL, t, k, 0) for t in have) / ff
        if load_ratio >= 30:
            continue
        for t in have:
            out.append(dict(set=f'topup:{parent}', tag=t, k=k / 1000, load=load_ratio,
                            bl=(m(BL, t, k, 0), m(BL, t, k, 1)),
                            dp=(m(DP, t, k, 0), m(DP, t, k, 1))))
    return out


def pooled(cs, i):
    b = st.mean(c['bl'][i] for c in cs); d = st.mean(c['dp'][i] for c in cs)
    o = st.mean(min(c['bl'][i], c['dp'][i]) for c in cs)
    return b / d, b / o


# ---- load everything ----------------------------------------------------------------
DATA = {}                                   # (regime, wl) -> list of cells
for reg in SETS:
    for wl in WL:
        cs = []
        for pre in SETS[reg][wl]:
            if not (os.path.exists(f'{H}/{pre}_bl.txt') and os.path.exists(f'{H}/{pre}_dp.txt')):
                sys.exit(f'missing result set {pre}')
            cs += cells(pre)
        DATA[(reg, wl)] = cs
TOPUP_DATA = {}
if TOPUP:
    for key, lst in TOPUP_SETS.items():
        TOPUP_DATA[key] = [c for path, parent in lst for c in cells_topup(path, parent)]
        if TOPUP_DATA[key]:
            print(f'topup {key}: +{len(TOPUP_DATA[key])} cells, bands '
                  f'{sorted(set(round(c["load"]) for c in TOPUP_DATA[key]))}x')

# ---- gate: the pooled per-regime numbers must reproduce the paper -------------------
print('gate: pooled per regime (canonical cells only)')
ok = True
for i, name in ((1, 'p99'), (0, 'mean')):
    for reg in ('above', 'below'):
        pool = [c for wl in WL for c in DATA[(reg, wl)] if (reg, wl) not in NOT_POOLED]
        r, orc = pooled(pool, i)
        orc_pct = (orc / r - 1) * 100
        want_r, want_o = PAPER[name][reg], PAPER[name]['orc_' + reg]
        flag = '' if abs(r - want_r) <= 0.011 and abs(orc_pct - want_o) <= 0.16 else '  <-- MISMATCH'
        ok &= flag == ''
        print(f'  {name:4s} {reg:5s} n={len(pool):3d}  BL/DP {r:.3f} (paper {want_r})  '
              f'oracle over DP +{orc_pct:.1f}% (paper +{want_o}){flag}')
if not ok and not FORCE:
    sys.exit('gate failed: population differs from the paper; fix or pass --force')

# ---- table ----------------------------------------------------------------------------
print(f'\nper band, metric = {METRIC}')
print(f"{'regime':6s} {'workload':9s} {'band':7s} {'n':>4s} {'pooled':>7s} {'median':>7s} "
      f"{'min':>6s} {'max':>6s} {'DP loses':>9s}")
ROWS = {}
for reg in ('below', 'above'):
    for wl in WL:
        cs = DATA[(reg, wl)] + (TOPUP_DATA.get((reg, wl), []) if TOPUP else [])
        for lo, hi, lab in BANDS:
            b = [c for c in cs if lo <= c['load'] < hi]
            if not b:
                ROWS[(reg, wl, lab)] = None; continue
            rr = [c['bl'][MI] / c['dp'][MI] for c in b]
            pr, _ = pooled(b, MI)
            ROWS[(reg, wl, lab)] = dict(n=len(b), ratios=rr, pooled=pr, lose=sum(r < 1 for r in rr))
            print(f'{reg:6s} {wl:9s} {lab:7s} {len(b):4d} {pr:7.2f} {st.median(rr):7.2f} '
                  f'{min(rr):6.2f} {max(rr):6.2f} {sum(r < 1 for r in rr):5d}/{len(b)}')
        can = DATA[(reg, wl)]
        r, orc = pooled(can, MI)
        print(f'{reg:6s} {wl:9s} {"all":7s} {len(can):4d} {r:7.2f}   oracle {orc:.2f}x  (canonical only'
              + (f'; +{len(cs)-len(can)} topup cells in bands' if len(cs) > len(can) else '')
              + (', ES arm drawn not pooled)' if (reg, wl) in NOT_POOLED else ')'))

# ---- figure ---------------------------------------------------------------------------
fig, axes = plt.subplots(2, 3, figsize=(7.16, 3.7), sharey='row')
for ri, reg in enumerate(('below', 'above')):
    for ci, wl in enumerate(WL):
        ax = axes[ri][ci]
        cs = DATA[(reg, wl)]
        cs_bands = cs + (TOPUP_DATA.get((reg, wl), []) if TOPUP else [])
        np_ = (reg, wl) in NOT_POOLED
        fill = BASE_C if np_ else TREAT_C
        data, pos, labs = [], [], []
        for bi, (lo, hi, lab) in enumerate(BANDS):
            row = ROWS[(reg, wl, lab)]
            if row is None:
                ax.annotate('no cells', (bi, 0), xycoords=('data', 'axes fraction'), xytext=(0, 2),
                            textcoords='offset points', ha='center', va='bottom', fontsize=5.5, color=MUTED, style='italic')
                continue
            data.append(row['ratios']); pos.append(bi); labs.append(lab)
        bp = ax.boxplot(data, positions=pos, widths=0.52, patch_artist=True, showfliers=True,
                        whis=(5, 95), zorder=3,
                        boxprops=dict(facecolor=fill, alpha=0.35, edgecolor=fill, lw=0.8),
                        medianprops=dict(color=INK, lw=1.0),
                        whiskerprops=dict(color=fill, lw=0.8), capprops=dict(color=fill, lw=0.8),
                        flierprops=dict(marker='o', ms=2, mfc=fill, mec='none', alpha=0.6))
        for p, lab in zip(pos, labs):
            row = ROWS[(reg, wl, lab)]
            ax.plot(p, row['pooled'], marker='D', ms=4, color=INK, zorder=5)
            ax.annotate(f"n={row['n']}", (p, 0), xycoords=('data', 'axes fraction'),
                        xytext=(0, 2), textcoords='offset points', ha='center', va='bottom',
                        fontsize=5.5, color=MUTED)
        r, orc = pooled(cs, MI)
        ax.axhline(r, color=INK, lw=1.0, ls=(0, (0.7, 1.1)), zorder=4)
        ax.axhline(orc, color=MUTED, lw=0.9, ls=(0, (3, 1.5)), zorder=4)
        ax.text(0.98, 0.97, f'DP {r:.2f}×', transform=ax.transAxes, ha='right', va='top', fontsize=6.2, color=INK, fontweight='bold')
        ax.text(0.98, 0.86, f'oracle {orc:.2f}×', transform=ax.transAxes, ha='right', va='top', fontsize=6, color=MUTED)
        ax.axhline(1.0, color=MUTED, lw=0.6, zorder=1)
        ax.set_yscale('log')
        ax.set_xticks(range(len(BANDS))); ax.set_xticklabels([b[2] for b in BANDS], fontsize=6)
        ax.set_xlim(-0.6, 2.6)
        ax.tick_params(axis='y', labelsize=6, length=2, pad=1.5); ax.tick_params(axis='x', length=2, pad=1.5)
        ax.grid(axis='y', color=GRID, lw=0.6); ax.set_axisbelow(True)
        for sp in ('top', 'right'):
            ax.spines[sp].set_visible(False)
        if ri == 0:
            ax.set_title(wl, fontsize=7.5, fontweight='bold', color='#4B5563', pad=3)
        if ci == 0:
            ax.set_ylabel(f'{reg} floor\nBL / DP {METRIC}', fontsize=6.5, color=INK)
        if np_:
            ax.text(0.02, 0.97, 'ES arm, not pooled', transform=ax.transAxes, ha='left', va='top',
                    fontsize=5.5, color=MUTED, style='italic')
for ax in axes[1]:
    ax.set_xlabel('load band: BL mean delay / free-flow', fontsize=6.5, color=INK)
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter
for row in axes:
    row[0].yaxis.set_major_locator(LogLocator(base=2, subs=(1.0,)))
    row[0].yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v:g}×'))
    row[0].yaxis.set_minor_formatter(NullFormatter())
fig.legend([Patch(facecolor=TREAT_C, alpha=0.35, edgecolor=TREAT_C), Line2D([], [], marker='D', ms=4, color=INK, ls='none'),
            Line2D([], [], color=INK, lw=1.0, ls=(0, (0.7, 1.1))), Line2D([], [], color=MUTED, lw=0.9, ls=(0, (3, 1.5)))],
           ['per-cell ratios (box: IQR, whiskers 5–95%)', 'band pooled', 'panel pooled DP', 'panel oracle'],
           fontsize=6, frameon=False, loc='lower center', bbox_to_anchor=(0.5, -0.01), ncol=4,
           handlelength=1.4, handletextpad=0.5, columnspacing=1.4)
fig.tight_layout(pad=0.3, h_pad=0.8, w_pad=0.6, rect=(0, 0.05, 1, 1))
OUT = 'f_routing_wide' + ('' if METRIC == 'p99' else '_mean')
for ext in ('png', 'pdf'):
    fig.savefig(f'{FIG}/{OUT}.{ext}', dpi=300, bbox_inches='tight', pad_inches=0.02)
print(f'\nwrote figs/{OUT}.{{png,pdf}}')
