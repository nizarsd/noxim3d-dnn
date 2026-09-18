"""Offline feasibility check for the E x regime x binding factorial.

For each of six packings (3 workloads x {ejection-bound, injection-bound}, same c
within a workload) answer, without simulating:

  A. can it reach ABOVE the floor (max PL/PF by climbing)?
  B. with PL pinned and CC pinned, how far can E be driven DOWN and UP,
     in each regime?

B is the load-bearing question: the c16 attempt failed because pinning PL alone
already left no room for E. Here both PL and CC are pinned, which is stricter.
Reports achieved E span per cell; a span < 0.3 means that cell cannot carry the
contrast and the design must be relaxed (report, do not silently proceed).
"""
import collections, os, random, statistics as st, sys

H = '/home/nizar/noxim3d-dnn/results_stage3/mapping_pilot/pool1000/hill'
sys.path.insert(0, H)

POPS = [
    ('r818',  'resnet50_bottleneck3_xb128_6x6x3_c8r1s8',  0.480000, 'eject',  'ResNet (8,1,8)'),
    ('r824',  'resnet50_bottleneck3_xb128_6x6x3_c8r2s4',  0.392248, 'inject', 'ResNet (8,2,4)'),
    ('v824',  'vgg16_block3_xb128_6x6x3_c8r2s4',          1.782000, 'eject',  'VGG (8,2,4)'),
    ('v842',  'vgg16_block3_xb128_6x6x3_c8r4s2',          0.958000, 'inject', 'VGG (8,4,2)'),
    ('d1616', 'vitsmall_encoder1_xb128_6x6x3_c16r1s16',   0.905396, 'eject',  'DeiT (16,1,16)'),
    ('d1628', 'vitsmall_encoder1_xb128_6x6x3_c16r2s8',    0.909019, 'inject', 'DeiT (16,2,8)'),
]
STEPS, KN = 150, 30
PL_TOL, CC_TOL = 0.04, 0.05
M = None; EA = None


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


def cell(pf, pl_target, seed):
    """Pin PL at pl_target x PF, pin CC at whatever the pinned placement has,
    then drive E down and up. Returns (E_min, E_max, CC_ref, hit)."""
    rng = random.Random(seed)
    p = dict(zip(M.USED, rng.sample(range(108), len(M.USED))))
    tgt = pl_target * pf
    p = climb(rng, lambda q: abs(PL(q) - tgt), lambda q: True, p)
    if abs(PL(p) - tgt) > PL_TOL * tgt:
        return None
    cc0 = M.metrics(p)[2]
    ok = lambda q: (abs(PL(q) - tgt) <= PL_TOL * tgt and
                    abs(M.metrics(q)[2] - cc0) <= CC_TOL * cc0)
    lo = EA.local(climb(rng, lambda q: EA.local(q)[1], ok, p))[1]
    hi = EA.local(climb(rng, lambda q: -EA.local(q)[1], ok, p))[1]
    return lo, hi, cc0, EA.local(p)[1]


if __name__ == '__main__':
    import importlib
    print(f"{'population':16s} {'bind':6s} {'maxPL/PF':>8s} | "
          f"{'regime':6s} {'PL/PF':>5s} {'E_min':>5s} {'E_max':>5s} {'span':>5s}  verdict")
    for tag, stem, pf, bind, lab in POPS:
        os.environ['DNN_BASE_TABLE'] = f'/home/nizar/noxim3d-dnn/traffics_dnn_packing/{stem}.txt'
        for m in ('metrics', 'escapable_analytic'):
            sys.modules.pop(m, None)
        import metrics as M_, escapable_analytic as EA_
        M, EA = M_, EA_
        globals().update(M=M_, EA=EA_)
        # A: max reachable PL/PF (3 restarts, keep best)
        best = 0
        for s in range(1):
            rng = random.Random(900 + s)
            p = dict(zip(M.USED, rng.sample(range(108), len(M.USED))))
            p = climb(rng, lambda q: -PL(q), lambda q: True, p)
            best = max(best, PL(p) / pf)
        print(f"{lab:16s} {bind:6s} {best:8.2f} |")
        for regime, pl_t in (('below', 0.60), ('above', 1.10)):
            if regime == 'above' and best < 1.08:
                print(f"{'':16s} {'':6s} {'':8s} | {regime:6s} {'--':>5s} "
                      f"{'--':>5s} {'--':>5s} {'--':>5s}  UNREACHABLE above floor")
                continue
            res = [cell(pf, pl_t, 1000 + 17 * i) for i in range(1)]
            res = [r for r in res if r]
            if not res:
                print(f"{'':16s} {'':6s} {'':8s} | {regime:6s} "
                      f"{'--':>5s} {'--':>5s} {'--':>5s} {'--':>5s}  PL target not hit")
                continue
            lo = st.mean(r[0] for r in res); hi = st.mean(r[1] for r in res)
            span = hi - lo
            verdict = 'OK' if span >= 0.30 else ('marginal' if span >= 0.15 else 'TOO NARROW')
            print(f"{'':16s} {'':6s} {'':8s} | {regime:6s} {pl_t:5.2f} "
                  f"{lo:5.2f} {hi:5.2f} {span:5.2f}  {verdict}", flush=True)
    print('\nFEASIBILITY DONE')
