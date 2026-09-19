"""F3 — escape room predicts DP's capacity gain only where ejection binds.

Three matched pairs (one workload at one density each, differing only in which
port sets the floor).  y = r(E, capacity gain) over that population's engineered
E x PL grid; light = ejection-bound, dark = injection-bound, same grammar as F1
and F2.  Point labels carry n.  -> paper1-ext/figs/f_e_binding.{pdf,png}
"""
import os, statistics as st, sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

sys.path.insert(0, '/home/nizar/noxim3d-dnn/results_ext/ebind')
import analyse as A

PAIRS = [('ResNet-50\nc=8', ('ResNet (8,1,8)', 'eject', ('kstar_c8r1s8.csv', 'ladder_c8r1s8.csv')),
          ('ResNet (8,2,4)', 'inject', None)),
         ('VGG-16\nc=8', ('VGG (8,2,4)', 'eject', ('e3_kstar_vgg824.csv', 'e3_ladder_vgg824.csv')),
          ('VGG (8,4,2)', 'inject', ('e3_kstar_vgg842.csv', 'e3_ladder_vgg842.csv'))),
         ('DeiT-S\nc=16', ('DeiT (16,1,16)', 'eject', None),
          ('DeiT (16,2,8)', 'inject', None))]
NEW = {'ResNet (8,2,4)': 'r824', 'DeiT (16,1,16)': 'd1616', 'DeiT (16,2,8)': 'd1628'}


def stats(lab, src):
    cur, E = (A.curves_old(*src) if src else A.curves_new(NEW[lab]))
    Ev, cap = [], []
    for name, (e, plpf, cc) in sorted(E.items()):
        cb, cd = cur.get((name, 'BL')), cur.get((name, 'DP'))
        if not cb or not cd:
            continue
        kb, kd = A.kstar(cb), A.kstar(cd)
        if kb and kd:
            Ev.append(e); cap.append(kd / kb)
    return A.pear(Ev, cap), len(Ev)


plt.rcParams.update({'pdf.fonttype': 42, 'ps.fonttype': 42, 'font.size': 8})
EJ, INJ = '#9DC3EA', '#1F62B4'
fig, ax = plt.subplots(figsize=(4.4, 2.9))
W = 0.34
for i, (pair, ej, inj) in enumerate(PAIRS):
    x0 = i * 1.4
    for (lab, bind, src), off, col in ((ej, -0.22, EJ), (inj, +0.22, INJ)):
        r, n = stats(lab, src)
        x = x0 + off
        ax.bar(x, r, W, color=col)
        ax.text(x, r + 0.025 if r > 0 else 0.025, f'{r:+.2f}', ha='center', fontsize=6.6)
        ax.text(x, -0.045, f'{"eject" if bind=="eject" else "inject"}\nn={n}',
                ha='center', va='top', fontsize=6.2,
                transform=ax.get_xaxis_transform())
ax.axhline(0, color='0.45', lw=0.9)
ax.set_ylim(-0.12, 0.78)
ax.set_yticks([0, 0.2, 0.4, 0.6])
ax.set_ylabel('r ( escape room E , DP capacity gain )', fontsize=7.5)
ax.set_xticks([i * 1.4 for i in range(3)])
ax.set_xticklabels([p for p, _, _ in PAIRS], fontsize=8)
ax.tick_params(axis='x', length=0, pad=26)
ax.set_xlim(-0.75, 3.55)
h = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (EJ, INJ)]
ax.legend(h, ['ejection-bound (PF = PEL)', 'injection-bound (PF = PIL)'],
          fontsize=6.6, frameon=False, loc='upper right', handlelength=1.2)
for s in ('top', 'right'):
    ax.spines[s].set_visible(False)
ax.set_position([0.16, 0.22, 0.81, 0.74])
for e in ('pdf', 'png'):
    fig.savefig(f'/home/nizar/noxim3d-dnn/paper1-ext/figs/f_e_binding.{e}',
                dpi=200, bbox_inches='tight')
for pair, ej, inj in PAIRS:
    a, na = stats(ej[0], ej[2]); b, nb = stats(inj[0], inj[2])
    print(f"{pair.replace(chr(10),' '):15s} eject {a:+.2f} (n={na})   inject {b:+.2f} (n={nb})")
print('wrote f_e_binding')
