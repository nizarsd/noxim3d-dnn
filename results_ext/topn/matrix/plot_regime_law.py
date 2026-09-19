"""Exhibit 2 — the regime law: below the port floor no engineered mapping
creates selection-policy value; above it, value appears.

One dot per placement (DP gain over BL at its own knee rung, 8 seeds).
Below-floor dots pool the six engineered arms (minCC, maxES, maxE50, maxE40,
minE40, minE50) — the point is that none of them lifts the cloud off 1.0.
-> paper1-ext/figs/f_regime_law.{pdf,png}
"""
import collections, random, statistics as st
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

K = '/home/nizar/noxim3d-dnn/results_ext/topn/matrix'
I6 = '/home/nizar/noxim3d-dnn/results_ext/topn/int6'
spec = {}
for fn in (f'{K}/run_spec.txt', f'{K}/run_spec_patch.txt', f'{K}/run_spec_bE.txt',
           f'{K}/run_spec_b2.txt', f'{K}/run_spec_minE.txt',
           f'{K}/run_spec_extra_af.txt'):
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
            runs[(t, p[1])][int(p[2])] = (float(p[3]), float(p[4]))


load(f'{K}/res_matrix.txt', patched)
load(f'{K}/res_matrix_patch.txt')
load(f'{K}/res_bE.txt')
load(f'{K}/res_b2.txt')
load(f'{K}/res_minE.txt')
load(f'{K}/res_extra_af.txt')
load(f'{I6}/res_c16knee.txt')


def cm(t, pol):
    d = runs.get((t, pol), {})
    return st.mean(v[0] for v in d.values()) if d else None


WL = [('r1628', 'ResNet-50'), ('v1644', 'VGG-16'), ('esxd', 'DeiT-S')]
groups = {}
for pk, name in WL:
    for sub, code in (('below', 'bN'), ('bE', 'b2'), ('above', 'af')):
        vals = []
        for t in sorted({t for t, p in runs if p == 'dp' and spec.get(t) == 'OK'
                         and (t.startswith(pk + '_') or t.startswith(pk + 'x'))}):
            body = t.split('_', 1)[1] if '_' in t else t[len(pk):]
            if code == 'af':
                if not (body.startswith('af') or t.startswith(pk + 'x')):
                    continue
            elif not body.startswith(code):
                continue
            b, d = cm(t, 'bl'), cm(t, 'dp')
            if b and d:
                vals.append(b / d)
        groups[(name, sub)] = vals

plt.rcParams.update({'pdf.fonttype': 42, 'ps.fonttype': 42, 'font.size': 8})
C_B, C_M, C_A = '#C9DEF2', '#7FB2E0', '#1F62B4'
LBL = {'below': 'below\nE=0', 'bE': 'below\nE=1', 'above': 'above\nE=.1-.6'}
fig, ax = plt.subplots(figsize=(5.4, 3.0))
W = 0.36; PC = 0.46
for i, (pk, name) in enumerate(WL):
    x0 = i * 2.05
    for sub, col, sign in (('below', C_B, -1), ('bE', C_M, 0), ('above', C_A, +1)):
        v = groups[(name, sub)]
        x = x0 + sign * PC
        YCAP = 1.62
        top = min(max(v), YCAP)
        ax.bar(x, st.mean(v), W, color=col)
        ax.plot([x] * 2, [min(v), top], '-', color='0.3', lw=0.9)
        if max(v) > YCAP:
            ax.plot(x, YCAP, marker='^', ms=3.5, color='0.3')
            ax.text(x + 0.22, YCAP + 0.02, f'max {max(v):.1f}', fontsize=5.4,
                    color='0.35', ha='left')
        ax.text(x, (st.mean(v) + 0.03) if max(v) > YCAP else (top + 0.035),
                f'{st.mean(v):.2f}', ha='center', fontsize=6.4)
        ax.text(x, -0.04, LBL[sub], ha='center', va='top', fontsize=6.2,
                transform=ax.get_xaxis_transform())
ax.axhline(1.0, color='0.45', lw=0.9)
ax.text(0.5, 0.965, 'all arms at the same communication budget (CCx $\\approx$ 1.5)',
        transform=ax.transAxes, ha='center', fontsize=6.4, color='0.35')
ax.set_ylim(0.7, 1.80)
ax.set_yticks([0.8, 1.0, 1.2, 1.4, 1.6])
ax.set_xticks([i * 2.05 for i in range(3)])
ax.set_xticklabels([n for _, n in WL], fontsize=8)
ax.tick_params(axis='x', length=0, pad=24)
ax.set_xlim(-0.95, 5.05)
ax.set_ylabel('DP gain over BL\n(mean delay ratio)', fontsize=7.5)
for s in ('top', 'right'):
    ax.spines[s].set_visible(False)
ax.set_position([0.14, 0.20, 0.83, 0.76])
for e in ('pdf', 'png'):
    fig.savefig(f'/home/nizar/noxim3d-dnn/paper1-ext/figs/f_regime_law.{e}',
                dpi=200, bbox_inches='tight')
for k_, v in groups.items():
    print(f'{k_[0]:10s} {k_[1]:5s} n={len(v):2d} mean {st.mean(v):.3f} '
          f'[{min(v):.2f}..{max(v):.2f}]')
