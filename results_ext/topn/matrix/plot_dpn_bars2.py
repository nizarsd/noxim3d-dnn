"""F1 v2 — DP vs DPN with the coverage escalation shown.

Per workload: below floor (DP, DPN@90) and above floor (DP, DPN@90, DPN@95),
with a cost panel underneath giving destinations swept per rotation
(108 / N@90 / N@95).  Above-floor bars use the cells that have both coverages
(6/8/6) so the three bars in that group are the same placements.
"""
import collections, statistics as st
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

K = '/home/nizar/noxim3d-dnn/results_ext/topn/matrix'
I6 = '/home/nizar/noxim3d-dnn/results_ext/topn/int6'
spec = {}
for fn in ('run_spec.txt', 'run_spec_patch.txt', 'run_spec_bE.txt',
           'run_spec_aE.txt', 'run_spec_b2.txt', 'run_spec_minE.txt'):
    try:
        for ln in open(f'{K}/{fn}'):
            t, k, dep, flag = ln.split(); spec[t] = flag
    except FileNotFoundError:
        pass
for ln in open(f'{I6}/run_spec_c16.txt'):
    spec[ln.split()[0]] = 'OK'
runs = collections.defaultdict(dict)
patched = {ln.split()[0] for ln in open(f'{K}/run_spec_patch.txt')}


def load(fn, skip=set()):
    try:
        F = open(fn)
    except FileNotFoundError:
        return
    for ln in F:
        p = ln.split()
        if p[3] == 'NA':
            continue
        t = p[0].rsplit('_k', 1)[0]
        if t not in skip:
            runs[(t, p[1])][int(p[2])] = (float(p[3]), float(p[4]))


load(f'{K}/res_matrix.txt', patched)
load(f'{K}/res_matrix_patch.txt')
for _f in ('res_bE.txt', 'res_aE.txt', 'res_b2.txt', 'res_minE.txt', 'res_af_n95.txt'):
    load(f'{K}/{_f}')
load(f'{I6}/res_c16knee.txt')


def cm(t, pol):
    d = runs.get((t, pol), {})
    return st.mean(v[0] for v in d.values()) if d else None


WL = [('r1628', 'ResNet-50', 23, 27), ('v1644', 'VGG-16', 25, 38),
      ('esxd', 'DeiT-S', 25, 45)]
BELOW = ('int', 'bE', 'b2', 'bN')
DATA = {}
for pk, name, n90, n95 in WL:
    tags = sorted({t for t, p in runs if p == 'hyb' and spec.get(t) == 'OK'
                   and any(t.startswith(f'{pk}_{c}') for c in BELOW)})
    gd, gh = [], []
    for t in tags:
        b, d, h = cm(t, 'bl'), cm(t, 'dp'), cm(t, 'hyb')
        if b and d and h:
            gd.append(b / d); gh.append(b / h)
    DATA[(name, 'below')] = (gd, gh, None)
    tags = sorted({t for t, p in runs if p == 'hyb95' and spec.get(t) == 'OK'
                   and t.startswith(f'{pk}_af')})
    gd, gh, g9 = [], [], []
    for t in tags:
        b, d, h, h9 = cm(t, 'bl'), cm(t, 'dp'), cm(t, 'hyb'), cm(t, 'hyb95')
        if b and d and h and h9:
            gd.append(b / d); gh.append(b / h); g9.append(b / h9)
    DATA[(name, 'above')] = (gd, gh, g9)

plt.rcParams.update({'pdf.fonttype': 42, 'ps.fonttype': 42, 'font.size': 8})
DP_B, DP_A = '#9DC3EA', '#1F62B4'
DN_B, DN_A = '#FBCB9A', '#E06D00'
DN_A2 = '#8C4400'
fig, (ax, ax2) = plt.subplots(2, 1, figsize=(6.0, 4.4), sharex=True,
                              gridspec_kw=dict(hspace=0.30))
W = 0.26
YCAP = 1.62
for i, (pk, name, n90, n95) in enumerate(WL):
    x0 = i * 2.4
    groups = [('below', [(-0.95, DP_B, 0), (-0.66, DN_B, 1)]),
              ('above', [(0.25, DP_A, 0), (0.54, DN_A, 1), (0.83, DN_A2, 2)])]
    for reg, bars in groups:
        gd, gh, g9 = DATA[(name, reg)]
        series = [gd, gh, g9]
        for off, col, idx in bars:
            v = series[idx]
            if not v:
                continue
            x = x0 + off
            top = min(max(v), YCAP)
            ax.bar(x, st.mean(v), W, color=col)
            ax.plot([x] * 2, [min(v), top], '-', color='0.3', lw=0.9)
            if max(v) > YCAP:
                ax.plot(x, YCAP, marker='^', ms=3.5, color='0.3')
            ax.text(x, (st.mean(v) + 0.03) if max(v) > YCAP else top + 0.035,
                    f'{st.mean(v):.2f}', ha='center', fontsize=6.2)
    ax.text(x0 - 0.80, -0.05, f'below floor\nn={len(DATA[(name,"below")][0])}',
            ha='center', va='top', fontsize=6.3, transform=ax.get_xaxis_transform())
    ax.text(x0 + 0.54, -0.05, f'above floor\nn={len(DATA[(name,"above")][0])}',
            ha='center', va='top', fontsize=6.3, transform=ax.get_xaxis_transform())
    # cost panel
    ax2.bar(x0 - 0.66, 108, W, color=DP_A)
    ax2.bar(x0 - 0.37, n90, W, color=DN_A)
    ax2.bar(x0 - 0.08, n95, W, color=DN_A2)
    ax2.text(x0 - 0.37, n90 + 4, f'{n90}', ha='center', fontsize=6.2, color=DN_A)
    ax2.text(x0 - 0.08, n95 + 4, f'{n95}', ha='center', fontsize=6.4,
             color=DN_A2, fontweight='bold')
ax.axhline(1.0, color='0.5', lw=0.8)
ax.set_ylabel('gain over BL\n(mean delay ratio)', fontsize=7.5)
ax.set_ylim(0.85, 1.75)
ax.set_yticks([0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6])
h = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (DP_B, DN_B, DP_A, DN_A, DN_A2)]
ax.legend(h, ['DP, below floor', 'DPN N@90, below', 'DP, above floor',
              'DPN N@90, above', 'DPN N@95, above'],
          fontsize=6.3, frameon=False, loc='upper left', ncol=2,
          columnspacing=0.9, handlelength=1.1)
for s in ('top', 'right'):
    ax.spines[s].set_visible(False)
ax2.set_ylabel('destinations swept\nper rotation', fontsize=7.5)
ax2.set_yticks([0, 27, 54, 108]); ax2.set_ylim(0, 128)
ax2.text(-1.35, 112, '108 = full DP', fontsize=6.3, color=DP_A)
ax2.set_xticks([i * 2.4 for i in range(3)])
ax2.set_xticklabels([n for _, n, _, _ in WL], fontsize=8.5)
ax2.set_xlim(-1.5, 6.0)
ax2.tick_params(axis='x', length=0, pad=4)
for s in ('top', 'right'):
    ax2.spines[s].set_visible(False)
ax2.text(3.0, 118, 'N@90 is nearly uniform (23/25/25); N@95 is not (27/38/45)',
         fontsize=6.3, color='0.35', ha='center')
fig.align_ylabels()
ax.set_position([0.13, 0.46, 0.85, 0.50])
ax2.set_position([0.13, 0.09, 0.85, 0.26])
for e in ('pdf', 'png'):
    fig.savefig(f'/home/nizar/noxim3d-dnn/paper1-ext/figs/f_dpn_bars2.{e}',
                dpi=200, bbox_inches='tight')
for pk, name, n90, n95 in WL:
    for reg in ('below', 'above'):
        gd, gh, g9 = DATA[(name, reg)]
        s9 = f"  DPN95 {st.mean(g9):.3f}" if g9 else ""
        print(f"{name:10s} {reg:6s} n={len(gd):2d}  DP {st.mean(gd):.3f}  "
              f"DPN90 {st.mean(gh):.3f}{s9}")
print('wrote f_dpn_bars2')
