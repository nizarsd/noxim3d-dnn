"""Screen: level-form escape metrics E10..E90 (+ES) vs measured DP gain,
on the existing engineered c16 int-arm cells (res_c16knee.txt: per-placement
knee rung 4-6x own free-flow, 8 seeds, per packing).

E_L(x) = escapable fraction of the tier of links whose peak-interval load is
>= x * the peak link's load.  DP gain = mean-delay ratio BL/DP per placement
(and p99 ratio).  Within-packing Pearson + Spearman; n~10 per packing, min-CC
population (compressed gain range) -- a SCREEN, not a confirmation.
"""
import collections, csv, importlib, os, statistics as st, sys

sys.path.insert(0, '/home/nizar/noxim3d-dnn/results_stage3/mapping_pilot/pool1000/hill')
EPS = 1e-9
PACKS = [
    ('r1628', 'resnet50_bottleneck3_xb128_6x6x3_c16r2s8'),
    ('v1644', 'vgg16_block3_xb128_6x6x3_c16r4s4'),
    ('esxd',  'vitsmall_encoder1_xb128_6x6x3_c16r1s16'),
]
XS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.9]


def levels(perm, M):
    peak = {}; ctx = {}
    for live in M.INTERVALS:
        lk = collections.Counter(); ct = collections.defaultdict(list)
        for s, d, pir in live:
            a, c = perm[s], perm[d]; lam = pir * M.F
            for e, fr in M.edge_flow(a, c)[0]:
                lk[e] += lam * fr; ct[e].append((lam, fr))
        for e, l in lk.items():
            if l > peak.get(e, 0):
                peak[e] = l; ctx[e] = ct[e]
    links = sorted(peak.items(), key=lambda kv: -kv[1])
    pl = links[0][1]
    esc = {e: 1.0 - sum(lm for lm, fr in ctx[e] if fr > 1 - EPS) / l
           for e, l in links}
    out = {}
    for x in XS:
        tier = [(e, l) for e, l in links if l >= x * pl]
        w = sum(l for _, l in tier)
        out[f'E{int(x*100)}'] = sum(esc[e] * l for e, l in tier) / w
    ev = []
    for f in (0.05, 0.20):
        n = max(1, int(len(links) * f))
        w = sum(l for _, l in links[:n])
        ev.append(sum(esc[e] * l for e, l in links[:n]) / w)
    out['ES'] = ev[1] - ev[0]
    return out


# measured delays: tag_kXXXX pol seed mean p99
runs = collections.defaultdict(list)
for ln in open('/home/nizar/noxim3d-dnn/results_ext/topn/int6/res_c16knee.txt'):
    p = ln.split()
    if p[3] == 'NA':
        continue
    tag = p[0].rsplit('_k', 1)[0]
    runs[(tag, p[1])].append((float(p[3]), float(p[4])))


def z(v):
    m = st.mean(v); s = st.pstdev(v)
    return [(x - m) / s if s else 0.0 for x in v]


def pear(x, y):
    return st.mean(a * b for a, b in zip(z(x), z(y)))


def rank(v):
    o = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    for j, i in enumerate(o):
        r[i] = j
    return r


def spear(x, y):
    return pear(rank(x), rank(y))


NAMES = [f'E{int(x*100)}' for x in XS] + ['ES']
pooled = collections.defaultdict(lambda: ([], []))
for pack, stem in PACKS:
    os.environ['DNN_BASE_TABLE'] = f'/home/nizar/noxim3d-dnn/traffics_dnn_packing/{stem}.txt'
    if 'metrics' in sys.modules:
        M = importlib.reload(sys.modules['metrics'])
    else:
        import metrics as M
    mets = {}
    for r in csv.reader(open(f'/home/nizar/noxim3d-dnn/results_ext/topn/int6/perms_{pack}.csv')):
        if r[0].startswith('int'):
            perm = dict(zip(M.USED, map(int, r[3].split())))
            mets[f'{pack}_{r[0]}'] = levels(perm, M)
    tags = sorted(t for t in mets
                  if (t, 'bl') in runs and (t, 'dp') in runs)
    gm = [st.mean(a for a, _ in runs[(t, 'bl')]) /
          st.mean(a for a, _ in runs[(t, 'dp')]) for t in tags]
    gp = [st.mean(b for _, b in runs[(t, 'bl')]) /
          st.mean(b for _, b in runs[(t, 'dp')]) for t in tags]
    print(f"=== {pack}  n={len(tags)}  DP gain mean {min(gm):.3f}..{max(gm):.3f} "
          f"p99 {min(gp):.3f}..{max(gp):.3f} ===")
    for nm in NAMES:
        x = [mets[t][nm] for t in tags]
        if st.pstdev(x) < 1e-9:
            print(f"  {nm:4s} degenerate")
            continue
        print(f"  {nm:4s} [{min(x):.3f}..{max(x):.3f}]  "
              f"r_mean {pear(x, gm):+.3f} (rho {spear(x, gm):+.3f})   "
              f"r_p99 {pear(x, gp):+.3f} (rho {spear(x, gp):+.3f})")
        zx, zgm = z(x), z(gm)
        zgp = z(gp)
        for xi, gi, pi in zip(zx, zgm, zgp):
            pooled[nm][0].append((xi, gi)); pooled[nm][1].append((xi, pi))
print(f"\n=== pooled (z-scored within packing, n={len(pooled['ES'][0])}) ===")
for nm in NAMES:
    a, b = pooled[nm]
    if not a:
        continue
    rm = st.mean(x * y for x, y in a); rp = st.mean(x * y for x, y in b)
    print(f"  {nm:4s} r_mean {rm:+.3f}   r_p99 {rp:+.3f}")
