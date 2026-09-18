"""Coherent Fig-6 rebuild at c=16: p99 gain per layer and workload, every panel
from the same density (packings: min-PF picks; placements/routing: the matrix).

  panel 1 packing  min-BW orientation (baseline) vs min-PF, BL, 3 placements x
          3 seeds, at the paper rung (two rungs past the min-BW knee; ResNet
          keeps the paper's k=1.00, DeiT k=0.40; VGG c16 rung auto-picked).
  panel 2 mapping  minCC start (baseline) vs maxES climb, PAIRED by start, BL,
          each placement at its own knee rung, 8 pairs per workload.
  panel 3 routing  BL (baseline) vs DP and vs DPN, pooled p99 over cells;
          sub-groups below floor (minCC arm) and above floor (aboveF arm).

usage: plot_layer_bars_ext.py [--metric mean]
"""
import collections, os, statistics as st, sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

H = '/home/nizar/noxim3d-dnn/results_stage3/mapping_pilot/pool1000/hill'
K = '/home/nizar/noxim3d-dnn/results_ext/topn/matrix'
I6 = '/home/nizar/noxim3d-dnn/results_ext/topn/int6'
F6 = '/home/nizar/noxim3d-dnn/results_ext/fig6ext'
FIG = '/home/nizar/noxim3d-dnn/paper1-ext/figs'
P99 = 0 if '--metric' in sys.argv and sys.argv[sys.argv.index('--metric')+1] == 'mean' else 1
plt.rcParams.update({'pdf.fonttype': 42, 'ps.fonttype': 42, 'font.size': 7})
BASE_C, TREAT_C, HYB_C, INK = '#9AA3AE', '#2A78D6', '#fc7d0b', '#33373D'
WL = ['ResNet-50', 'VGG-16', 'DeiT-S']
PACKMAP = {'ResNet-50': 'r1628', 'VGG-16': 'v1644', 'DeiT-S': 'esxd'}


def load(f):
    d = collections.defaultdict(list)
    for ln in open(f):
        p = ln.split()
        if len(p) < 5 or p[3] == 'NA':
            continue
        tag, k = p[0].rsplit('_k', 1)
        d[(tag, int(k))].append((float(p[3]), float(p[4])))
    return d


def m(d, tag, k, i=P99):
    return st.mean(v[i] for v in d[(tag, k)])


# ---------- panel 1: packing ----------
PACK = {'ResNet-50': (f'{H}/res_test1_bl.txt', 1000),
        'DeiT-S': (f'{H}/res_ladder_deit16_bl.txt', 400),
        'VGG-16': (f'{F6}/res_ladder_vgg16_bl.txt', None)}
pack_rows = []
for wl in WL:
    f, kk = PACK[wl]
    if not os.path.exists(f) or os.path.getsize(f) == 0:
        pack_rows.append((wl, None, None, None)); continue
    L = load(f)
    base = sorted({t for t, _ in L if t.startswith('basePO')})
    flow = sorted({t for t, _ in L if t.startswith('flowPO')})
    if not base or not flow:
        pack_rows.append((wl, None, None, None)); continue
    if kk is None:                      # auto: two rungs past min-BW knee
        ks = sorted({k for _, k in L
                     if all((t, k) in L for t in base + flow)})
        if not ks:
            pack_rows.append((wl, None, None, None)); continue
        ff = st.mean(m(L, t, ks[0], 0) for t in base)
        knee = next((k for k in ks
                     if st.mean(m(L, t, k, 0) for t in base) > 2 * ff), ks[-1])
        kk = ks[min(ks.index(knee) + 2, len(ks) - 1)]
        print(f'{wl}: auto rung k={kk/1000:.2f} (min-BW knee {knee/1000:.2f})')
    b = st.mean(m(L, t, kk) for t in base)
    tr = st.mean(m(L, t, kk) for t in flow)
    pack_rows.append((wl, b, tr, b / tr))

# ---------- matrix loaders (panels 2 & 3) ----------
spec = {}
for fn in (f'{K}/run_spec.txt', f'{K}/run_spec_patch.txt'):
    for ln in open(fn):
        t, k, dep, flag = ln.split(); spec[t] = flag
for ln in open(f'{I6}/run_spec_c16.txt'):
    spec[ln.split()[0]] = 'OK'
runs = collections.defaultdict(dict)
patched = {ln.split()[0] for ln in open(f'{K}/run_spec_patch.txt')}


def load2(fn, skip=set()):
    for ln in open(fn):
        p = ln.split()
        if p[3] == 'NA':
            continue
        t = p[0].rsplit('_k', 1)[0]
        if t not in skip:
            runs[(t, p[1])][int(p[2])] = (float(p[3]), float(p[4]))


load2(f'{K}/res_matrix.txt', patched)
load2(f'{K}/res_matrix_patch.txt')
load2(f'{I6}/res_c16knee.txt')


def cellmean(t, pol, i=P99):
    d = runs.get((t, pol), {})
    return st.mean(v[i] for v in d.values()) if d else None


map_rows = []
for wl in WL:
    pk = PACKMAP[wl]
    ratios = []
    for i in range(11):
        a, b = f'{pk}_int{i}', f'{pk}_es{i}'
        if spec.get(a) == 'OK' and spec.get(b) == 'OK':
            x, y = cellmean(a, 'bl'), cellmean(b, 'bl')
            if x and y:
                ratios.append(x / y)
    map_rows.append((wl, len(ratios), st.mean(ratios)))

rout_rows = []                    # (wl, sub, n, BL, DP, DPN)
for wl in WL:
    pk = PACKMAP[wl]
    for sub, code in (('below', 'int'), ('above', 'af')):
        tags = [t for (t, pol) in runs if pol == 'bl' and t.startswith(f'{pk}_{code}')
                and spec.get(t) == 'OK']
        tags = sorted(set(tags))
        bl = st.mean(cellmean(t, 'bl') for t in tags)
        dp = st.mean(cellmean(t, 'dp') for t in tags)
        hy = [cellmean(t, 'hyb') for t in tags if cellmean(t, 'hyb')]
        rout_rows.append((wl, sub, len(tags), bl, dp,
                          st.mean(hy) if hy else None))

# ---------- print table ----------
lab = 'p99' if P99 else 'mean'
print(f'\n== packing ({lab}) =='); [print(f'  {w}: {r and round(r,2)}') for w, _, _, r in pack_rows]
print(f'== mapping (paired minCC/maxES, {lab}) ==')
for w, n, r in map_rows: print(f'  {w}: {r:.3f} (n={n})')
print(f'== routing ({lab}) ==')
for w, sub, n, bl, dp, hy in rout_rows:
    print(f'  {w:9s} {sub:5s} n={n}  BL/DP {bl/dp:.3f}  BL/DPN {bl/hy if hy else float("nan"):.3f}')

# ---------- figure ----------
fig, axes = plt.subplots(3, 1, figsize=(3.45, 4.4),
                         gridspec_kw=dict(height_ratios=[1, 1, 1.7]))
def hbar(ax, y, ratio, color, label):
    ax.barh(y, 1.0, height=0.32, color=BASE_C, alpha=0.45)
    ax.barh(y - 0.36, 1.0 / ratio, height=0.32, color=color)
    ax.text(1.0 / ratio + 0.02, y - 0.36, f'{ratio:.2f}×', va='center',
            fontsize=6.5, color=INK)

for ax, title in zip(axes, ['packing: min-PF vs min-BW orientation (BL)',
                            'mapping: maxES vs minCC start (BL, paired)',
                            'routing: DP and DPN vs BL']):
    ax.set_title(title, fontsize=7, loc='left')
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)

ax = axes[0]
for i, (wl, b, tr, r) in enumerate(pack_rows):
    if r:
        hbar(ax, 2 - i, r, TREAT_C, wl)
ax.set_yticks([2, 1, 0]); ax.set_yticklabels(WL, fontsize=6.5)
ax.set_xscale('log'); ax.set_xlim(0.008, 1.4)

ax = axes[1]
for i, (wl, n, r) in enumerate(map_rows):
    hbar(ax, 2 - i, r, TREAT_C, wl)
ax.set_yticks([2, 1, 0]); ax.set_yticklabels(WL, fontsize=6.5)
ax.set_xlim(0, 1.4)

ax = axes[2]
yy = 5.6
ylabels, ypos = [], []
for wl in WL:
    for sub in ('above', 'below'):
        row = next(r for r in rout_rows if r[0] == wl and r[1] == sub)
        _, _, n, bl, dp, hy = row
        ax.barh(yy, 1.0, height=0.22, color=BASE_C, alpha=0.45)
        ax.barh(yy - 0.24, dp and 1.0 / (bl / dp), height=0.22, color=TREAT_C)
        ax.text(1.0 / (bl / dp) + 0.02, yy - 0.24, f'{bl/dp:.2f}×',
                va='center', fontsize=6, color=INK)
        if hy:
            ax.barh(yy - 0.48, 1.0 / (bl / hy), height=0.22, color=HYB_C)
            ax.text(1.0 / (bl / hy) + 0.02, yy - 0.48, f'{bl/hy:.2f}×',
                    va='center', fontsize=6, color=HYB_C)
        ylabels.append(f'{wl}\n{sub}'); ypos.append(yy - 0.24)
        yy -= 1.05
ax.set_yticks(ypos); ax.set_yticklabels(ylabels, fontsize=6)
ax.set_xlim(0, 1.5)
h = [plt.Rectangle((0, 0), 1, 1, color=BASE_C, alpha=0.45),
     plt.Rectangle((0, 0), 1, 1, color=TREAT_C),
     plt.Rectangle((0, 0), 1, 1, color=HYB_C)]
axes[2].legend(h, ['baseline (=1)', 'DP / treatment', 'DPN (22% activity)'],
               fontsize=6, frameon=False, loc='lower right')
fig.tight_layout(pad=0.5)
os.makedirs(FIG, exist_ok=True)
for ext in ('pdf', 'png'):
    fig.savefig(f'{FIG}/f_layer_bars_ext.{ext}', dpi=200, bbox_inches='tight')
print(f'\nwrote {FIG}/f_layer_bars_ext.pdf/.png')
