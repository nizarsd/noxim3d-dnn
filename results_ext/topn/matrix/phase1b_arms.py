"""Phase 1b: minE40 / minE50 / aboveF arms (additions to phase1_arms.py).

minE40/minE50: minimise the level metric from the same int starts, same
CC<=start and PL<=start constraints, tier>=3 guard (a low-E tier must stay a
multi-link tier).  aboveF: climb PL to 1.10 x PF +/- 2% (constraint dropped by
construction), CC minimised secondarily once inside the band.
"""
import collections, csv, importlib, multiprocessing as mp, os, random, statistics as st, sys

H = '/home/nizar/noxim3d-dnn/results_stage3/mapping_pilot/pool1000/hill'
OUT = '/home/nizar/noxim3d-dnn/results_ext/topn/matrix'
sys.path.insert(0, H); sys.path.insert(0, OUT)
import phase1_arms as PA

OBJ2 = {
    'minE40': lambda s: (1e9 if s[5] < 3 else s[3]),
    'minE50': lambda s: (1e9 if s[4] < 3 else s[2]),
}
TARGET = 1.10; TOL = 0.02


def job(a):
    tag, i, p0, PF = a
    M = PA.M
    cc = lambda p: M.metrics(p)[2]
    cc0 = cc(p0); st0 = PA.stats(p0); pl0 = st0[0]
    ok = lambda p: cc(p) <= cc0 and PA.stats(p)[0] <= pl0
    rows = []
    for arm, sc in OBJ2.items():
        p = PA.climb(hash((tag, i, arm)) & 0xffff, sc, ok, p0)
        s = PA.stats(p)
        rows.append(dict(arm=arm, start=f'int{i}', ES=round(s[1], 4),
                         E50=round(s[2], 4), E40=round(s[3], 4),
                         n50=s[4], n40=s[5], PL_PF=round(s[0]/PF, 4),
                         CCx=round(cc(p)/cc0, 4),
                         perm=' '.join(str(p[n]) for n in M.USED)))
    # aboveF: two-stage — climb PL into the band, then min CC inside it
    band = lambda pl: abs(pl - TARGET*PF) <= TOL*PF
    p = PA.climb(hash((tag, i, 'aF')) & 0xffff,
                 lambda s: abs(s[0] - TARGET*PF), lambda q: True, p0)
    if band(PA.stats(p)[0]):
        rng = random.Random(hash((tag, i, 'aF2')) & 0xffff)
        cur = cc(p); used = M.USED
        idle = [n for n in range(108) if n not in set(p.values())]
        for _ in range(150):
            found = None
            for _ in range(40):
                p2 = dict(p)
                if idle and rng.random() < 0.3:
                    p2[rng.choice(used)] = rng.choice(idle)
                else:
                    a2, b2 = rng.sample(used, 2)
                    p2[a2], p2[b2] = p[b2], p[a2]
                if not band(PA.stats(p2)[0]):
                    continue
                v = cc(p2)
                if v < cur - 1e-12 and (found is None or v < found[0]):
                    found = (v, p2)
            if found is None:
                break
            cur, p = found
            idle = [n for n in range(108) if n not in set(p.values())]
    s = PA.stats(p)
    rows.append(dict(arm='aboveF', start=f'int{i}', ES=round(s[1], 4),
                     E50=round(s[2], 4), E40=round(s[3], 4),
                     n50=s[4], n40=s[5], PL_PF=round(s[0]/PF, 4),
                     CCx=round(cc(p)/cc0, 4),
                     perm=' '.join(str(p[n]) for n in M.USED)))
    return rows


if __name__ == '__main__':
    for tag, stem, pf in PA.PACKS:
        os.environ['DNN_BASE_TABLE'] = \
            f'/home/nizar/noxim3d-dnn/traffics_dnn_packing/{stem}.txt'
        if 'metrics' in sys.modules:
            M = importlib.reload(sys.modules['metrics'])
        else:
            import metrics as M
        PA.M = M
        starts = []
        for r in csv.reader(open(f'/home/nizar/noxim3d-dnn/results_ext/topn/int6/perms_{tag}.csv')):
            if r[0].startswith('int') and len(starts) < 8:
                starts.append((tag, int(r[0][3:]),
                               dict(zip(M.USED, map(int, r[3].split()))), pf))
        with mp.Pool(8) as pool:
            res = pool.map(job, starts)
        rows = [r for g in res for r in g]
        with open(f'{OUT}/arms2_{tag}.csv', 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
        print(f'=== {tag} ===', flush=True)
        for arm in ('minE40', 'minE50', 'aboveF'):
            g = [r for r in rows if r['arm'] == arm]
            print(f"  {arm:7s} ES {st.mean(r['ES'] for r in g):+.3f}"
                  f"  E50 {st.mean(r['E50'] for r in g):.3f}"
                  f"  E40 {st.mean(r['E40'] for r in g):.3f}"
                  f"  CCx {st.mean(r['CCx'] for r in g):.3f}"
                  f"  PL/PF {st.mean(r['PL_PF'] for r in g):.3f}"
                  f"  [{min(r['PL_PF'] for r in g):.3f}..{max(r['PL_PF'] for r in g):.3f}]",
                  flush=True)
    print('PHASE1B DONE')
