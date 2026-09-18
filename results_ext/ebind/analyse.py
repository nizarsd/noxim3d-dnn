"""E-vs-binding analysis for the two new grids, plus the existing five.

Scores every population three ways so the conclusion cannot be an artifact of
the outcome variable:
  1. capacity gain  k*_DP / k*_BL          (anchor-free)
  2. delay BL/DP at k*_DP                  (the design point: best achievable)
  3. delay BL/DP at 5x own free-flow       (the c16 matrix convention)
and reports, per population, the low-E vs high-E contrast and r(E, gain).
"""
import collections, csv, math, os, statistics as st

H = '/home/nizar/noxim3d-dnn/results_stage3/mapping_pilot/pool1000/hill'
K = '/home/nizar/noxim3d-dnn/results_ext/ebind'

NEW = [('d1616', 'DeiT (16,1,16)', 'eject'), ('r824', 'ResNet (8,2,4)', 'inject')]
OLD = [('kstar_c8r1s8.csv', 'ladder_c8r1s8.csv', 'ResNet (8,1,8)', 'eject'),
       ('e3_kstar_vgg824.csv', 'e3_ladder_vgg824.csv', 'VGG (8,2,4)', 'eject'),
       ('e3_kstar_vgg842.csv', 'e3_ladder_vgg842.csv', 'VGG (8,4,2)', 'inject'),
       ('e3_kstar_vgg.csv', 'e3_ladder_vgg.csv', 'VGG (32,8,4)', 'inject'),
       ('e3_kstar_vit.csv', 'e3_ladder_vit.csv', 'DeiT (8,1,8)', 'inject')]


def interp(c, k, i=0):
    ks = sorted(c)
    if k <= ks[0]:
        return c[ks[0]][i]
    if k >= ks[-1]:
        return c[ks[-1]][i]
    for a, b in zip(ks, ks[1:]):
        if a <= k <= b:
            y0, y1 = math.log(c[a][i]), math.log(c[b][i])
            t = (math.log(k) - math.log(a)) / (math.log(b) - math.log(a))
            return math.exp(y0 + t * (y1 - y0))


def kstar(c, mult=2.0, i=0):
    ks = sorted(c); ff = c[ks[0]][i]; tgt = mult * ff; prev = None
    for k in ks:
        if c[k][i] >= tgt:
            if prev is None:
                return ks[0]
            y0, y1 = math.log(c[prev][i]), math.log(c[k][i])
            t = (math.log(tgt) - y0) / (y1 - y0)
            return prev + t * (k - prev)
        prev = k
    return None


def z(v):
    m = st.mean(v); s = st.pstdev(v)
    return [(x - m) / s if s else 0.0 for x in v]


def pear(x, y):
    return st.mean(a * b for a, b in zip(z(x), z(y)))


def rank(v):
    o = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0] * len(v)
    for j, i in enumerate(o):
        r[i] = j
    return r


def curves_new(tag):
    cur = collections.defaultdict(dict)
    for ln in open(f'{K}/res_ebind.txt'):
        p = ln.split()
        if len(p) < 5 or p[3] == 'NA' or not p[0].startswith(tag):
            continue
        name, k = p[0].rsplit('_k', 1)
        cur[(name, p[1].upper())].setdefault(int(k) / 1000.0, []).append((float(p[3]), float(p[4])))
    out = collections.defaultdict(dict)
    for (name, pol), d in cur.items():
        out[(name, pol)] = {k: (st.mean(v[0] for v in vs), st.mean(v[1] for v in vs))
                            for k, vs in d.items()}
    E = {}
    for r in csv.DictReader(open(f'{K}/grid_{tag}.csv')):
        if r['hit_pl'] == '1' and r['hit_E'] == '1':
            E[f"{tag}_pl{int(float(r['pl_t'])*100)}e{int(float(r['e_t'])*100)}r{r['rep']}"] = \
                (float(r['E']), float(r['PL_PF']), float(r['CC']))
    return out, E


def curves_old(ks_f, lad_f):
    cur = collections.defaultdict(dict)
    for r in csv.DictReader(open(f'{H}/{lad_f}')):
        cur[(r['tag'], r['policy'])][float(r['k'])] = (float(r['delay']), float(r['p99']))
    E = {}
    for r in csv.DictReader(open(f'{H}/{ks_f}')):
        if r.get('kstar_DP') and r.get('kstar_BL'):
            E[r['tag']] = (float(r['E']), float(r['PL_PF']), float(r['CC']))
    return cur, E


def score(cur, E, lab, bind, rows_out):
    recs = []
    for name, (e, plpf, cc) in sorted(E.items()):
        cb, cd = cur.get((name, 'BL')), cur.get((name, 'DP'))
        if not cb or not cd or len(cb) < 3 or len(cd) < 3:
            continue
        kb, kd = kstar(cb), kstar(cd)
        if not kb or not kd:
            continue
        ff = cb[min(cb)][0]
        k5 = None
        ks = sorted(cb); prev = None
        for k in ks:
            if cb[k][0] >= 5 * ff:
                k5 = k if prev is None else prev + (k - prev) * 0.5
                break
            prev = k
        cap = kd / kb
        d_kd = interp(cb, kd) / interp(cd, kd)
        d_5 = interp(cb, k5) / interp(cd, k5) if k5 else None
        recs.append((e, cap, d_kd, d_5, cc, plpf))
    if len(recs) < 4:
        print(f"{lab:16s} {bind:6s}  n={len(recs)} — too few"); return
    Ev = [r[0] for r in recs]
    med = sorted(Ev)[len(Ev) // 2]
    def split(idx):
        lo = [r[idx] for r in recs if r[0] <= med and r[idx]]
        hi = [r[idx] for r in recs if r[0] > med and r[idx]]
        return (st.mean(lo), st.mean(hi), st.mean(hi) - st.mean(lo)) if lo and hi else (0, 0, 0)
    cap = [r[1] for r in recs]
    dkd = [r[2] for r in recs]
    d5 = [r[3] for r in recs if r[3]]
    E5 = [r[0] for r in recs if r[3]]
    c_lo, c_hi, c_d = split(1)
    print(f"{lab:16s} {bind:6s} {len(recs):3d} | E {min(Ev):.2f}-{max(Ev):.2f} "
          f"CC±{100*(max(r[4] for r in recs)/min(r[4] for r in recs)-1):4.0f}% | "
          f"cap {c_lo:.3f}->{c_hi:.3f} ({c_d:+.3f}) r={pear(Ev,cap):+.2f} rho={pear(rank(Ev),rank(cap)):+.2f} | "
          f"d@k*DP r={pear(Ev,dkd):+.2f} | "
          f"d@5x r={(pear(E5,d5) if len(d5)>3 else float('nan')):+.2f}")
    rows_out.append((lab, bind, len(recs), c_d, pear(Ev, cap), pear(Ev, dkd)))


if __name__ == '__main__':
    print("E vs DP gain, per population — above the floor\n")
    print(f"{'population':16s} {'bind':6s} {'n':>3s} | {'E span / CC spread':22s} | "
          f"{'capacity low-E -> high-E':40s} | {'delay@k*DP':10s} | {'delay@5x':8s}")
    rows = []
    for tag, lab, bind in NEW:
        if os.path.exists(f'{K}/res_ebind.txt'):
            cur, E = curves_new(tag)
            score(cur, E, lab + ' NEW', bind, rows)
    for ks_f, lad_f, lab, bind in OLD:
        if os.path.exists(f'{H}/{lad_f}'):
            cur, E = curves_old(ks_f, lad_f)
            score(cur, E, lab, bind, rows)
    print("\nBY BINDING CLASS (capacity contrast, low-E -> high-E):")
    for cls in ('eject', 'inject'):
        g = [r for r in rows if r[1] == cls]
        if g:
            print(f"  {cls:6s} n_pop={len(g)}  mean delta {st.mean(r[3] for r in g):+.3f}  "
                  f"mean r {st.mean(r[4] for r in g):+.3f}   "
                  f"[{', '.join(f'{r[0].split()[0]}{r[3]:+.2f}' for r in g)}]")
