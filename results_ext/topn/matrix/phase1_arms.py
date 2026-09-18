"""Phase 1: engineer maxES / maxE50 / maxE40 arms for the c16 matrix.

Starts: the 8 int-arm (interior-pinned min-CC) placements per packing from
results_ext/topn/int6/perms_<tag>.csv.  Each climb maximises one objective
under the same constraints as the paper's ES generator (esxd_search.py):
CC <= CC(start) and PL <= PL(start).  Swap/relocate moves, STEPS x K budget.

Metrics (peak-interval link loads, matching esxd_search.py):
  ES  = E20 - E5 (count-fraction tiers of hottest links)
  E50 / E40 = escapable fraction of the tier of links with load >= 0.5/0.4 x
  the peak link's load; candidates with tier < 3 links are rejected (guard
  against the single-link degenerate tier found in phase 0).

Output: results_ext/topn/matrix/arms_<tag>.csv  (arm,start,ES,E50,E40,n50,
n40,PL_PF,CCx,perm) — every final placement carries ALL metrics so the race
analysis has the full cross-metric matrix.
"""
import collections, csv, multiprocessing as mp, os, random, statistics as st, sys

H = '/home/nizar/noxim3d-dnn/results_stage3/mapping_pilot/pool1000/hill'
OUT = '/home/nizar/noxim3d-dnn/results_ext/topn/matrix'
sys.path.insert(0, H)
EPS = 1e-9; STEPS, K = 300, 50
PACKS = [
    ('r1628', 'resnet50_bottleneck3_xb128_6x6x3_c16r2s8', 0.258178),
    ('v1644', 'vgg16_block3_xb128_6x6x3_c16r4s4', 0.942699),
    ('esxd',  'vitsmall_encoder1_xb128_6x6x3_c16r1s16', 0.905396),
]

M = None  # set per packing before forking the pool


def stats(perm):
    """(PL, ES, E50, E40, n50, n40) on peak-interval link loads."""
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
    ev = []
    for f in (0.05, 0.20):
        n = max(1, int(len(links) * f))
        w = sum(l for _, l in links[:n])
        ev.append(sum(esc[e] * l for e, l in links[:n]) / w)
    lv = []
    for x in (0.5, 0.4):
        tier = [(e, l) for e, l in links if l >= x * pl]
        w = sum(l for _, l in tier)
        lv.append((sum(esc[e] * l for e, l in tier) / w, len(tier)))
    return pl, ev[1] - ev[0], lv[0][0], lv[1][0], lv[0][1], lv[1][1]


def climb(seed, score, constraint, start):
    rng = random.Random(seed); used = M.USED
    perm = dict(start); cur = score(stats(perm))
    idle = [n for n in range(108) if n not in set(perm.values())]
    for _ in range(STEPS):
        found = None
        for _ in range(K):
            p2 = dict(perm)
            if idle and rng.random() < 0.3:
                p2[rng.choice(used)] = rng.choice(idle)
            else:
                a, b = rng.sample(used, 2); p2[a], p2[b] = perm[b], perm[a]
            if not constraint(p2):
                continue
            v = score(stats(p2))
            if v < cur - 1e-12 and (found is None or v < found[0]):
                found = (v, p2)
        if found is None:
            continue
        cur, perm = found[0], found[1]
        idle = [n for n in range(108) if n not in set(perm.values())]
    return perm


OBJ = {
    'maxES':  lambda s: -s[1],
    'maxE50': lambda s: (1e9 if s[4] < 3 else -s[2]),
    'maxE40': lambda s: (1e9 if s[5] < 3 else -s[3]),
}


def job(a):
    tag, i, p0 = a
    cc = lambda p: M.metrics(p)[2]
    cc0 = cc(p0); st0 = stats(p0); pl0 = st0[0]
    ok = lambda p: cc(p) <= cc0 and stats(p)[0] <= pl0
    rows = []
    for arm, sc in OBJ.items():
        p = climb(hash((tag, i, arm)) & 0xffff, sc, ok, p0)
        s = stats(p)
        rows.append(dict(arm=arm, start=f'int{i}', ES=round(s[1], 4),
                         E50=round(s[2], 4), E40=round(s[3], 4),
                         n50=s[4], n40=s[5],
                         PL_PF=round(s[0] / PF, 4), CCx=round(cc(p) / cc0, 4),
                         perm=' '.join(str(p[n]) for n in M.USED)))
    # the start itself, as the minCC row (CCx = 1 by construction)
    rows.append(dict(arm='minCC', start=f'int{i}', ES=round(st0[1], 4),
                     E50=round(st0[2], 4), E40=round(st0[3], 4),
                     n50=st0[4], n40=st0[5], PL_PF=round(pl0 / PF, 4),
                     CCx=1.0, perm=' '.join(str(p0[n]) for n in M.USED)))
    return rows


if __name__ == '__main__':
    for tag, stem, pf in PACKS:
        PF = pf
        os.environ['DNN_BASE_TABLE'] = \
            f'/home/nizar/noxim3d-dnn/traffics_dnn_packing/{stem}.txt'
        import importlib
        if 'metrics' in sys.modules:
            M = importlib.reload(sys.modules['metrics'])
        else:
            import metrics as M
        globals()['M'] = M
        starts = []
        for r in csv.reader(open(f'/home/nizar/noxim3d-dnn/results_ext/topn/int6/perms_{tag}.csv')):
            if r[0].startswith('int') and len(starts) < 8:
                i = int(r[0][3:])
                perm = dict(zip(M.USED, map(int, r[3].split())))
                starts.append((tag, i, perm))
        assert len(starts) == 8, (tag, len(starts))
        with mp.Pool(8) as pool:
            res = pool.map(job, starts)
        rows = [r for g in res for r in g]
        with open(f'{OUT}/arms_{tag}.csv', 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
        print(f'=== {tag} ===', flush=True)
        for arm in ('minCC', 'maxES', 'maxE50', 'maxE40'):
            g = [r for r in rows if r['arm'] == arm]
            print(f"  {arm:7s} ES {st.mean(r['ES'] for r in g):+.3f}"
                  f"  E50 {st.mean(r['E50'] for r in g):.3f}"
                  f"  E40 {st.mean(r['E40'] for r in g):.3f}"
                  f"  CCx {st.mean(r['CCx'] for r in g):.3f}"
                  f"  PL/PF {st.mean(r['PL_PF'] for r in g):.3f}", flush=True)
    print('PHASE1 DONE')
