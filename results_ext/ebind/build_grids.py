"""E x PL grids for the E-vs-binding test, above the floor.

Three new populations complete within-workload, within-density matched pairs
(ejection- vs injection-bound) for all three workloads:

  r824  ResNet-50 (8,2,4)    inject  PF 0.392   pairs with existing (8,1,8) eject
  d1616 DeiT-S   (16,1,16)   eject   PF 0.905   pairs with d1628
  d1628 DeiT-S   (16,2,8)    inject  PF 0.909   same c, same tiles, PF within 0.5%

Protocol (trimmed E1/E3): PL targets x E targets x reps; phase A climbs PL into
its band, phase B climbs E to target while holding the band. Hits/misses are
reported, never hidden. Writes grid_<tag>.csv and ladder tables.
"""
import collections, csv, math, multiprocessing as mp, os, random, statistics as st, sys

H = '/home/nizar/noxim3d-dnn/results_stage3/mapping_pilot/pool1000/hill'
OUT = '/home/nizar/noxim3d-dnn/results_ext/ebind'
TD = '/home/nizar/noxim3d-dnn/traffics_dnn_packing'
sys.path.insert(0, H)
os.makedirs(f'{OUT}/tables', exist_ok=True)

POPS = [
    # DeiT (16,2,8): injection-bound twin of d1616 — same c, same 66 tiles,
    # PF 0.909 vs 0.905 (0.4% apart). The tightest matched pair in the design.
    ('d1628', 'vitsmall_encoder1_xb128_6x6x3_c16r2s8',     0.909019, 'inject',
     [1.10, 1.25], [0.05, 0.55], [150, 250, 350, 450, 550, 650, 760]),
]
REPS = 4
PL_TOL, E_TOL = 0.03, 0.12
STEPS, KN, TRIES = 300, 40, 5
M = None; EA = None; PF = None


def stats_pl(perm):
    """peak-interval PL (same definition as phase1_arms.stats)."""
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


def climb(seed, score, ok, start, steps=STEPS):
    rng = random.Random(seed); perm = dict(start); cur = score(perm)
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
    pl_t, e_t, rep = a
    tgt = pl_t * PF
    inband = lambda q: abs(stats_pl(q) - tgt) <= PL_TOL * tgt
    best = None
    for attempt in range(TRIES):
        rng = random.Random(hash((pl_t, e_t, rep, attempt)) & 0xffff)
        p = dict(zip(M.USED, rng.sample(range(108), len(M.USED))))
        p = climb(hash((pl_t, rep, attempt, 'A')) & 0xffff,
                  lambda q: abs(stats_pl(q) - tgt), lambda q: True, p)
        if not inband(p):
            continue
        p = climb(hash((pl_t, e_t, rep, attempt, 'B')) & 0xffff,
                  lambda q: abs(EA.local(q)[1] - e_t), inband, p)
        err = abs(EA.local(p)[1] - e_t)
        if best is None or err < best[0]:
            best = (err, dict(p))
        if err <= E_TOL:
            break
    if best is None:
        p = dict(zip(M.USED, random.Random(rep).sample(range(108), len(M.USED))))
    else:
        p = best[1]
    hit_pl = inband(p)
    pl = stats_pl(p); E = EA.local(p)[1]
    return dict(pl_t=pl_t, e_t=e_t, rep=rep, PL=round(pl, 6),
                PL_PF=round(pl / PF, 4), E=round(E, 4),
                CC=round(M.metrics(p)[2], 1),
                hit_pl=int(hit_pl), hit_E=int(abs(E - e_t) <= E_TOL),
                perm=' '.join(str(p[n]) for n in M.USED))


if __name__ == '__main__':
    import importlib
    for tag, stem, pf, bind, PLS, ES, KS in POPS:
        os.environ['DNN_BASE_TABLE'] = f'{TD}/{stem}.txt'
        for m in ('metrics', 'escapable_analytic'):
            sys.modules.pop(m, None)
        import metrics as M_, escapable_analytic as EA_
        M, EA, PF = M_, EA_, pf
        globals().update(M=M_, EA=EA_, PF=pf)
        args = [(pl, e, r) for pl in PLS for e in ES for r in range(REPS)]
        with mp.Pool(12) as pool:
            rows = pool.map(job, args)
        with open(f'{OUT}/grid_{tag}.csv', 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
        ok = [r for r in rows if r['hit_pl'] and r['hit_E']]
        print(f"{tag} ({bind}): {len(ok)}/{len(rows)} cells hit both targets", flush=True)
        for e in ES:
            g = [r for r in ok if r['e_t'] == e]
            if g:
                print(f"   E_target {e:.2f}: n={len(g)}  E {st.mean(r['E'] for r in g):.2f}"
                      f"  PL/PF {st.mean(r['PL_PF'] for r in g):.2f}"
                      f"  CC {st.mean(r['CC'] for r in g):,.0f}", flush=True)
        n = 0
        for r in ok:
            perm = dict(zip(M.USED, map(int, r['perm'].split())))
            name = f"{tag}_pl{int(r['pl_t']*100)}e{int(r['e_t']*100)}r{r['rep']}"
            for k in KS:
                with open(f'{OUT}/tables/{name}_k{k:04d}.txt', 'w') as f:
                    for s, d, pir, on, off in M.ROWS:
                        v = pir * k / 1000.0
                        f.write(f"{perm[s]:5d} {perm[d]:5d} {v:.10f} {v:.10f} "
                                f"{on:>8} {off:>8} {M.PERIOD:>8}\n")
                n += 1
        print(f"   wrote {n} tables", flush=True)
    print('GRIDS DONE')
