"""Two-regime matrix panel: BL/DP and BL/DPN gain per placement, 7 arms x 3
workloads, one figure. Outputs figs/f_matrix_two_regime.{pdf,png}."""
import collections, statistics as st
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

K = '/home/nizar/noxim3d-dnn/results_ext/topn/matrix'
I6 = '/home/nizar/noxim3d-dnn/results_ext/topn/int6'

spec = {}
for fn in (f'{K}/run_spec.txt', f'{K}/run_spec_patch.txt'):
    for ln in open(fn):
        t, k, dep, flag = ln.split(); spec[t] = flag
for ln in open(f'{I6}/run_spec_c16.txt'):
    spec[ln.split()[0]] = 'OK'
runs = collections.defaultdict(dict)
patched = {ln.split()[0] for ln in open(f'{K}/run_spec_patch.txt')}


def load(fn, skip=set()):
    for ln in open(fn):
        p = ln.split()
        if p[3] == 'NA':
            continue
        t = p[0].rsplit('_k', 1)[0]
        if t not in skip:
            runs[(t, p[1])][int(p[2])] = float(p[3])


load(f'{K}/res_matrix.txt', patched)
load(f'{K}/res_matrix_patch.txt')
load(f'{I6}/res_c16knee.txt')

ARMS = [('int', 'minCC'), ('es', 'maxES'), ('e50', 'maxE50'), ('e40', 'maxE40'),
        ('ne40', 'minE40'), ('ne50', 'minE50'), ('af', 'above-\nfloor')]
PACKS = [('r1628', 'ResNet-50 (16,2,8)'), ('v1644', 'VGG-16 (16,4,4)'),
         ('esxd', 'DeiT-S (16,1,16)')]
C_DP, C_HYB = '#1170aa', '#fc7d0b'


def arm_code(t):
    b = t.split('_', 1)[1]
    for c, _ in [('ne40', 0), ('ne50', 0), ('e50', 0), ('e40', 0), ('es', 0),
                 ('af', 0), ('int', 0)]:
        if b.startswith(c):
            return c


fig, axes = plt.subplots(1, 3, figsize=(9.2, 2.9), sharey=True)
for ax, (pack, title) in zip(axes, PACKS):
    for xi, (code, label) in enumerate(ARMS):
        tags = sorted({t for t, _ in runs if t.startswith(pack)
                       and arm_code(t) == code and spec.get(t) == 'OK'})
        gd, gh = [], []
        for t in tags:
            bl = runs.get((t, 'bl'), {}); dp = runs.get((t, 'dp'), {})
            hy = runs.get((t, 'hyb'), {})
            c = set(bl) & set(dp)
            if len(c) >= 4:
                gd.append(st.mean(bl[s] for s in c) / st.mean(dp[s] for s in c))
            ch = set(bl) & set(hy)
            if len(ch) >= 4:
                gh.append(st.mean(bl[s] for s in ch) / st.mean(hy[s] for s in ch))
        if gd:
            ax.plot([xi - 0.14] * len(gd), gd, 'o', ms=3.2, mfc=C_DP,
                    mec='none', alpha=0.55, zorder=3)
            ax.plot([xi - 0.30, xi + 0.02], [st.mean(gd)] * 2, '-', lw=2.2,
                    color=C_DP, zorder=4)
        if gh:
            ax.plot([xi + 0.14] * len(gh), gh, '^', ms=3.4, mfc=C_HYB,
                    mec='none', alpha=0.65, zorder=3)
            ax.plot([xi - 0.02, xi + 0.30], [st.mean(gh)] * 2, '-', lw=2.2,
                    color=C_HYB, zorder=4)
    ax.axhline(1.0, color='0.45', lw=0.8, zorder=1)
    ax.axvline(5.55, color='0.55', lw=0.8, ls='--', zorder=1)
    ax.axvspan(5.55, 6.6, color='0.93', zorder=0)
    ax.set_xlim(-0.6, 6.6)
    ax.set_xticks(range(7))
    ax.set_xticklabels([l for _, l in ARMS], fontsize=6.6, rotation=38,
                       ha='right')
    ax.set_title(title, fontsize=8.5)
    ax.set_yscale('log')
    ax.set_yticks([0.8, 1.0, 1.25, 1.6, 2.0, 2.5])
    ax.set_yticklabels(['0.8', '1.0', '1.25', '1.6', '2.0', '2.5'], fontsize=7)
    ax.tick_params(length=2)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
axes[0].set_ylabel('gain over BL (mean delay ratio)', fontsize=7.8)
axes[0].text(5.95, 2.62, 'PL>PF', fontsize=6.6, ha='center', color='0.35')
axes[2].annotate('DPN at 22%\nof DP activity', xy=(6.15, 1.30),
                 xytext=(4.2, 2.05), fontsize=6.6, color=C_HYB,
                 arrowprops=dict(arrowstyle='-', color=C_HYB, lw=0.7))
h = [plt.Line2D([], [], marker='o', ls='-', color=C_DP, ms=4, label='DP'),
     plt.Line2D([], [], marker='^', ls='-', color=C_HYB, ms=4,
                label='DPN (top-N sinks)')]
axes[1].legend(handles=h, fontsize=6.8, frameon=False, loc='upper left',
               handlelength=1.4)
fig.tight_layout(pad=0.4)
for ext in ('pdf', 'png'):
    fig.savefig(f'/home/nizar/noxim3d-dnn/paper1-ext/figs/f_matrix_two_regime.{ext}',
                dpi=200, bbox_inches='tight')
print('wrote figs/f_matrix_two_regime.{pdf,png}')
