"""Below-floor min-E / max-E arms for ResNet-50 (8,1,8) — the ejection-bound
packing whose above-floor grid already exists (E1).

Completes the same-packing regime pair for ResNet at an ejection-bound point,
so F2 can be shown with all three workloads ejection-bound.

Protocol matches the c16 arms: 8 min-CC starts, CC pinned at ~1.5x the start's
CC (the budget the above-floor placements pay), PL <= 0.90 x PF, then E driven
to its extremes. Knee rung per placement, BL/DP/DPN, 8 seeds.
"""
import collections, csv, multiprocessing as mp, os, random, statistics as st, sys

H = '/home/nizar/noxim3d-dnn/results_stage3/mapping_pilot/pool1000/hill'
OUT = '/home/nizar/noxim3d-dnn/results_ext/ebind'
TD = '/home/nizar/noxim3d-dnn/traffics_dnn_packing'
sys.path.insert(0, H)
os.environ['DNN_BASE_TABLE'] = f'{TD}/resnet50_bottleneck3_xb128_6x6x3_c8r1s8.txt'
import metrics as M, escapable_analytic as EA

PF = 0.480000
PL_CAP, CC_TARGET, CC_TOL = 0.90, 1.50, 0.05
STEPS, KN, TRIES = 250, 40, 4
KS = [300, 500, 700, 950, 1300, 1700, 2200]


def PL(perm):
    peak = {}
    for live in M.INTERVALS:
        lk = collections.Counter()
        for s, d, pir in live:
            a, c = perm[s], perm[d]; lam = pir * M.F
            for e, fr in M.edge_flow(a, c)[0]:
                lk[e] += lam * fr
        for e, l in lk.items():
            if l > peak.get(e, 0):
                peak[e] = l
    return max(peak.values())


def climb(rng, score, ok, start, steps=STEPS):
    perm = dict(start); cur = score(perm)
    idle = [n for n in range(108) if n not in set(perm.values())]
    for _ in range(steps):
        found = None
        for _ in range(KN):
            p2 = dict(perm)
            if idle and rng.random() < 0.3:
                p2[rng.choice(M.USED)] = rng.choice(idle)
            else:
                a, b = rng.sample(M.USED, 2); p2[a], p2[b] = perm[b], perm[a]
            if not ok(p2):
                continue
            v = score(p2)
            if v < cur - 1e-12 and (found is None or v < found[0]):
                found = (v, p2)
        if found is None:
            continue
        cur, perm = found
        idle = [n for n in range(108) if n not in set(perm.values())]
    return perm


def job(a):
    i, direction = a
    rng = random.Random(4000 + i * 7 + (1 if direction == 'max' else 0))
    # min-CC start
    p0 = dict(zip(M.USED, rng.sample(range(108), len(M.USED))))
    p0 = climb(rng, lambda q: M.metrics(q)[2], lambda q: True, p0)
    cc0 = M.metrics(p0)[2]; tgt = CC_TARGET * cc0
    below = lambda q: PL(q) <= PL_CAP * PF
    p = climb(rng, lambda q: abs(M.metrics(q)[2] - tgt), below, p0)
    band = lambda q: abs(M.metrics(q)[2] - tgt) <= CC_TOL * cc0 and below(q)
    if band(p):
        sgn = -1 if direction == 'max' else 1
        p = climb(rng, lambda q: sgn * EA.local(q)[1], band, p)
    return dict(arm=f'{direction}E', idx=i, E=round(EA.local(p)[1], 4),
                CCx=round(M.metrics(p)[2] / cc0, 4), PL_PF=round(PL(p) / PF, 4),
                hit=int(band(p)), perm=' '.join(str(p[n]) for n in M.USED))


if __name__ == '__main__':
    args = [(i, d) for i in range(8) for d in ('min', 'max')]
    with mp.Pool(12) as pool:
        rows = pool.map(job, args)
    with open(f'{OUT}/arms_r818_below.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    for d in ('min', 'max'):
        g = [r for r in rows if r['arm'] == f'{d}E' and r['hit']]
        if g:
            print(f"{d}E: {len(g)}/8 hit  E {st.mean(r['E'] for r in g):.3f} "
                  f"[{min(r['E'] for r in g):.2f}..{max(r['E'] for r in g):.2f}]  "
                  f"CCx {st.mean(r['CCx'] for r in g):.2f}  "
                  f"PL/PF {st.mean(r['PL_PF'] for r in g):.2f}", flush=True)
    n = 0
    os.makedirs(f'{OUT}/tables_r818', exist_ok=True)
    for r in rows:
        if not r['hit']:
            continue
        perm = dict(zip(M.USED, map(int, r['perm'].split())))
        tag = f"r818b{'N' if r['arm']=='minE' else 'X'}{r['idx']}"
        for k in KS:
            with open(f"{OUT}/tables_r818/{tag}_k{k:04d}.txt", 'w') as f:
                for s, d, pir, on, off in M.ROWS:
                    v = pir * k / 1000.0
                    f.write(f"{perm[s]:5d} {perm[d]:5d} {v:.10f} {v:.10f} "
                            f"{on:>8} {off:>8} {M.PERIOD:>8}\n")
            n += 1
        vol = collections.Counter()
        for s, d, pir, on, off in M.ROWS:
            vol[perm[d]] += pir * (off - on)
        with open(f'{OUT}/sinks_{tag}', 'w') as f:
            for d2, _ in vol.most_common():
                f.write(f'{d2}\n')
    print(f'wrote {n} tables')
    print('R818 BELOW BUILD DONE')
