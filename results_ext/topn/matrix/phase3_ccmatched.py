"""Phase 3: the CC-matched below-floor control arm ("bE").

Isolates the regime from the communication budget. The above-floor arm pays
CCx 1.43-1.50 and gains escape room as a side effect; this arm pays the SAME
budget below the floor and maximises E directly:

    objective : max E (escapable fraction at the PL-argmax link)
    subject to: CC <= 1.45 x CC(start),  PL <= 0.90 x PF   (clearly below floor)
    starts    : the same 8 interior min-CC placements per packing

Writes arms3_<pack>.csv, tables/<pack>_bE<i>_k<k>.txt and sinks_<pack>_bE<i>.
"""
import collections, csv, multiprocessing as mp, os, random, statistics as st, sys

H = '/home/nizar/noxim3d-dnn/results_stage3/mapping_pilot/pool1000/hill'
OUT = '/home/nizar/noxim3d-dnn/results_ext/topn/matrix'
TD = '/home/nizar/noxim3d-dnn/traffics_dnn_packing'
sys.path.insert(0, H); sys.path.insert(0, OUT)
import phase1_arms as PA

PACKS = [
    ('r1628', 'resnet50_bottleneck3_xb128_6x6x3_c16r2s8', 0.258178,
     [400, 700, 1000, 1400, 1700, 1800, 2100]),
    ('v1644', 'vgg16_block3_xb128_6x6x3_c16r4s4', 0.942699,
     [150, 250, 400, 430, 450, 480, 520]),
    ('esxd', 'vitsmall_encoder1_xb128_6x6x3_c16r1s16', 0.905396,
     [470, 550, 580, 600, 620, 650, 700]),
]
CC_BUDGET = 1.45
PL_CAP = 0.90
STEPS, KN = 300, 50
M = None
EA = None


def job(a):
    tag, i, p0, PF = a
    cc = lambda p: M.metrics(p)[2]
    cc0 = cc(p0)
    ok = lambda p: cc(p) <= CC_BUDGET * cc0 and PA.stats(p)[0] <= PL_CAP * PF
    rng = random.Random(hash((tag, i, 'bE')) & 0xffff)
    perm = dict(p0); cur = -EA.local(perm)[1]
    idle = [n for n in range(108) if n not in set(perm.values())]
    for _ in range(STEPS):
        found = None
        for _ in range(KN):
            p2 = dict(perm)
            if idle and rng.random() < 0.3:
                p2[rng.choice(M.USED)] = rng.choice(idle)
            else:
                x, y = rng.sample(M.USED, 2); p2[x], p2[y] = perm[y], perm[x]
            if not ok(p2):
                continue
            v = -EA.local(p2)[1]
            if v < cur - 1e-12 and (found is None or v < found[0]):
                found = (v, p2)
        if found is None:
            continue
        cur, perm = found
        idle = [n for n in range(108) if n not in set(perm.values())]
    s = PA.stats(perm)
    return dict(arm='bE', start=f'int{i}', E=round(EA.local(perm)[1], 4),
                E0=round(EA.local(p0)[1], 4), ES=round(s[1], 4),
                E50=round(s[2], 4), E40=round(s[3], 4),
                PL_PF=round(s[0] / PF, 4), CCx=round(cc(perm) / cc0, 4),
                perm=' '.join(str(perm[n]) for n in M.USED))


if __name__ == '__main__':
    import importlib
    for pk, stem, pf, ks in PACKS:
        os.environ['DNN_BASE_TABLE'] = f'{TD}/{stem}.txt'
        for m in ('metrics', 'escapable_analytic'):
            sys.modules.pop(m, None)
        import metrics as M_, escapable_analytic as EA_
        M, EA = M_, EA_; PA.M = M_
        globals()['M'], globals()['EA'] = M_, EA_
        starts = []
        for r in csv.reader(open(f'/home/nizar/noxim3d-dnn/results_ext/topn/int6/perms_{pk}.csv')):
            if r[0].startswith('int') and len(starts) < 8:
                starts.append((pk, int(r[0][3:]),
                               dict(zip(M.USED, map(int, r[3].split()))), pf))
        with mp.Pool(8) as pool:
            rows = pool.map(job, starts)
        with open(f'{OUT}/arms3_{pk}.csv', 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
        print(f"{pk}: bE  E {st.mean(r['E'] for r in rows):.3f} "
              f"[{min(r['E'] for r in rows):.2f}..{max(r['E'] for r in rows):.2f}]"
              f"  (start E {st.mean(r['E0'] for r in rows):.3f})"
              f"  CCx {st.mean(r['CCx'] for r in rows):.2f}"
              f"  PL/PF {st.mean(r['PL_PF'] for r in rows):.2f}", flush=True)
        n = 0
        for r in rows:
            perm = dict(zip(M.USED, map(int, r['perm'].split())))
            assert len(set(perm.values())) == len(M.USED)
            tag = f"{pk}_bE{r['start'][3:]}"
            for k in ks:
                with open(f'{OUT}/tables/{tag}_k{k:04d}.txt', 'w') as f:
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
        print(f"   wrote {n} tables + 8 sinkfiles", flush=True)
    print('PHASE3 DONE')
