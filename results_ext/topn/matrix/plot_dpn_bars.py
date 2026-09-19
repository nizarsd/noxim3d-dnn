"""DPN vs DP, aggregated per workload: 4 bars per workload
(DP,DPN below floor | DP,DPN above floor), light = below, dark = above,
blue = DP, orange = DPN; activity panel underneath. ->
paper1-ext/figs/f_dpn_bars.{pdf,png}"""
import collections, statistics as st
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

K = '/home/nizar/noxim3d-dnn/results_ext/topn/matrix'
I6 = '/home/nizar/noxim3d-dnn/results_ext/topn/int6'
spec = {}
for fn in (f'{K}/run_spec.txt', f'{K}/run_spec_patch.txt', f'{K}/run_spec_bE.txt',
           f'{K}/run_spec_aE.txt', f'{K}/run_spec_b2.txt', f'{K}/run_spec_minE.txt',
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
for _f in ('res_bE.txt', 'res_aE.txt', 'res_b2.txt', 'res_minE.txt', 'res_extra_af.txt'):
    load(f'{K}/{_f}')
load(f'{I6}/res_c16knee.txt')


def cm(t, pol):
    d = runs.get((t, pol), {})
    return st.mean(v[0] for v in d.values()) if d else None


WL = [('r1628', 'ResNet-50', 23), ('v1644', 'VGG-16', 25), ('esxd', 'DeiT-S', 25)]
DATA = {}
for pk, name, N in WL:
    for sub, codes in (('below', ('int', 'bE', 'b2', 'bN')),
                       ('above', ('af', 'aE', 'aN', 'x'))):
        tags = sorted({t for t, p in runs if p == 'hyb' and spec.get(t) == 'OK'
                       and any(t.startswith(f'{pk}_{c}') for c in codes)})
        gd, gh = [], []
        for t in tags:
            b, d, h = cm(t, 'bl'), cm(t, 'dp'), cm(t, 'hyb')
            if b and d and h:
                gd.append(b / d); gh.append(b / h)
        DATA[(name, sub)] = (gd, gh)

plt.rcParams.update({'pdf.fonttype': 42, 'ps.fonttype': 42, 'font.size': 8})
DP_B, DP_A = '#9DC3EA', '#1F62B4'      # DP: light (below) / dark (above)
DN_B, DN_A = '#FBCB9A', '#E06D00'      # DPN: light / dark
DP_M, DN_M = '#5E92CF', '#ED9C4D'      # mid hues: cost applies to both regimes
fig, (ax, ax2) = plt.subplots(2, 1, figsize=(5.0, 4.4), sharex=True,
                              gridspec_kw=dict(height_ratios=[1, 1],
                                               hspace=0.30))
W = 0.34; PC = 0.50          # pair centre offset; bars sit either side of it
OFF = [-PC - (W / 2 + 0.01), -PC + (W / 2 + 0.01),
       PC - (W / 2 + 0.01), PC + (W / 2 + 0.01)]
for i, (pk, name, N) in enumerate(WL):
    x0 = i * 2.0
    for j, (sub, pol, col) in enumerate(
            (('below', 0, DP_B), ('below', 1, DN_B),
             ('above', 0, DP_A), ('above', 1, DN_A))):
        gd, gh = DATA[(name, sub)]
        v = gd if pol == 0 else gh
        x = x0 + OFF[j]
        YCAP = 1.62
        ax.bar(x, st.mean(v), W, color=col)
        top = min(max(v), YCAP)
        ax.plot([x] * 2, [min(v), top], '-', color='0.3', lw=0.9)
        if max(v) > YCAP:
            ax.plot(x, YCAP, marker='^', ms=3.5, color='0.3')
            ax.text(x, YCAP + 0.085, f'max\n{max(v):.1f}', fontsize=5.4,
                    color='0.35', ha='center', va='bottom')
        ax.text(x, top + 0.035, f'{st.mean(v):.2f}', ha='center', fontsize=6)
    ax2.bar(x0 - (W / 2 + 0.03), 108, W, color=DP_M)
    ax2.bar(x0 + (W / 2 + 0.03), N, W, color=DN_M)
    ax2.text(x0 + (W / 2 + 0.03), N + 10, f'{N} ({N*100//108}%)',
             ha='center', fontsize=6, color=DN_M)
    # regime labels sit under the gain panel, over the group they describe
    ax.text(x0 - PC, -0.05, 'below floor', ha='center', va='top',
            fontsize=6.6, transform=ax.get_xaxis_transform())
    ax.text(x0 + PC, -0.05, 'above floor', ha='center', va='top',
            fontsize=6.6, transform=ax.get_xaxis_transform())
ax.axhline(1.0, color='0.5', lw=0.8)
ax.set_ylabel('gain over BL\n(mean delay ratio)', fontsize=7.5)
ax.set_ylim(0.7, 1.80)
ax.set_yticks([0.8, 1.0, 1.2, 1.4, 1.6])
h = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (DP_B, DN_B, DP_A, DN_A)]
ax.legend(h, ['DP below', 'DPN below', 'DP above', 'DPN above'],
          fontsize=6.4, frameon=False, loc='upper left', ncol=2,
          columnspacing=0.9, handlelength=1.1)
for s in ('top', 'right'):
    ax.spines[s].set_visible(False)
ax2.set_ylabel('destinations\nswept', fontsize=7)
ax2.set_yticks([0, 54, 108]); ax2.set_ylim(0, 122)
ax2.text(-0.92, 112, '108 = full DP', fontsize=6, color=DP_M)
ax2.set_xticks([i * 2.0 for i in range(3)])
ax2.set_xticklabels([name for _, name, _ in WL], fontsize=7.5)
ax2.tick_params(axis='x', which='major', length=0, pad=3)
for s in ('top', 'right'):
    ax2.spines[s].set_visible(False)
fig.align_ylabels()
# force identical plot-box heights for the two panels
ax.set_position([0.15, 0.545, 0.83, 0.40])
ax2.set_position([0.15, 0.075, 0.83, 0.40])
for e in ('pdf', 'png'):
    fig.savefig(f'/home/nizar/noxim3d-dnn/paper1-ext/figs/f_dpn_bars.{e}',
                dpi=200, bbox_inches='tight')
print('wrote f_dpn_bars')
