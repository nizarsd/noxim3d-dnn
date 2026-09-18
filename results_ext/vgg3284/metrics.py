"""Offline placement metrics for ResNet-50 (8,2,4) on 6x6x3 -- PL, PR, CC, PV.

Same definitions as results_stage3/mapping_pilot/pool1000/gen_pool.py (PL/PR/CC)
and adddiv.py (PV), re-expressed once so the hill-climb and the pool agree.
Verified against pool.csv row-for-row before use.
"""
import collections, csv, functools, math, sys

sys.path.insert(0, '/home/nizar/noxim3d-dnn/tools')
from oeb_path_diversity import STEP, UP, DN, route_relaxed as route

DX, DY, DZ = 6, 6, 3
F = 16
import os
BASE = os.environ.get('DNN_BASE_TABLE',
        '/home/nizar/noxim3d-dnn/traffics_dnn_packing/'
        'resnet50_bottleneck3_xb128_6x6x3_c8r2s4.txt')


def xyz(n): return (n % DX, (n // DX) % DY, n // (DX * DY))
def nid(c): return c[0] + c[1] * DX + c[2] * DX * DY
def hops(a, b):
    p, q = xyz(a), xyz(b)
    return abs(p[0]-q[0]) + abs(p[1]-q[1]) + abs(p[2]-q[2])


def read(path):
    rows, period = [], None
    for L in open(path):
        if L.startswith('%') or not L.strip():
            continue
        f = L.split()
        rows.append((int(f[0]), int(f[1]), float(f[2]), int(f[4]), int(f[5])))
        period = int(f[6])
    return rows, period


@functools.lru_cache(maxsize=None)
def edge_flow(src, dst):
    """({(u,v): fraction of admissible minimal paths on u->v}, n_paths)."""
    s, d = xyz(src), xyz(dst)

    @functools.lru_cache(maxsize=None)
    def npaths(cur, sxy, din):
        if cur == d:
            return 1
        t = 0
        for k in route(cur, (sxy[0], sxy[1], s[2]), d, din):
            st = STEP[k]
            nxt = (cur[0]+st[0], cur[1]+st[1], cur[2]+st[2])
            t += npaths(nxt, (nxt[0], nxt[1]) if k in (UP, DN) else sxy, k)
        return t

    out = collections.Counter()

    def walk(cur, sxy, din, w):
        if cur == d:
            return
        n_here = npaths(cur, sxy, din)
        if not n_here:
            return
        for k in route(cur, (sxy[0], sxy[1], s[2]), d, din):
            st = STEP[k]
            nxt = (cur[0]+st[0], cur[1]+st[1], cur[2]+st[2])
            sx = (nxt[0], nxt[1]) if k in (UP, DN) else sxy
            sub = npaths(nxt, sx, k)
            if not sub:
                continue
            frac = w * sub / n_here
            out[(nid(cur), nid(nxt))] += frac
            walk(nxt, sx, k, frac)

    walk(s, (s[0], s[1]), -1, 1.0)
    n = npaths(s, (s[0], s[1]), -1)
    return (tuple(out.items()), n)


ROWS, PERIOD = read(BASE)
USED = sorted({r[0] for r in ROWS} | {r[1] for r in ROWS})
CUTS = sorted({0, PERIOD} | {r[3] for r in ROWS} | {r[4] for r in ROWS})
# elementary intervals -> the flows live throughout them
INTERVALS = []
for a, b in zip(CUTS, CUTS[1:]):
    live = [(s, d, pir) for s, d, pir, on, off in ROWS if on <= a and off >= b]
    if live:
        INTERVALS.append(live)
# PV weights: bytes = pir * window length, placement independent
PVW = [(s, d, pir * (off - on)) for s, d, pir, on, off in ROWS]
PVTOT = sum(w for _, _, w in PVW)


def metrics(perm):
    """(PL, PR, CC, PV) for a {logical node -> physical node} mapping.

    CC is phase-weighted flit-hops per period (fixed 2026-08-29; the previous
    form used pir*F*hops, i.e. every flow weighted as always-on, which ranked
    placements differently -- r=0.80, Spearman 0.77 against this one).
    """
    link = router = 0.0
    for live in INTERVALS:
        lk = collections.Counter(); nd = collections.Counter()
        for s, d, pir in live:
            a, c = perm[s], perm[d]
            lam = pir * F
            nd[a] += lam; nd[c] += lam           # inject at a, eject at c
            ef, _ = edge_flow(a, c)
            for (u, v), fr in ef:
                x = lam * fr
                lk[(u, v)] += x
                if u != a:
                    nd[u] += x                    # transit
        if lk:
            link = max(link, max(lk.values()))
        if nd:
            router = max(router, max(nd.values()))
    # phase-weighted: flit-hops per PERIOD (dynamic link energy).  The old
    # form omitted (off-on) and so weighted every flow as always-on.
    cc = sum(pir * (off - on) * F * hops(perm[s], perm[d])
             for s, d, pir, on, off in ROWS)
    pv = 0.0
    for s, d, w in PVW:
        a, c = perm[s], perm[d]
        if a == c:
            continue
        n = edge_flow(a, c)[1]
        if n > 0:
            pv += w * math.log2(n)
    return link, router, cc, pv / PVTOT


def perm_of(rec):
    return dict(zip(USED, [int(x) for x in rec['perm'].split()]))


def pool(path=None):
    if path is None:
        path = os.environ.get('DNN_POOL_CSV',
            '/home/nizar/noxim3d-dnn/results_stage3/mapping_pilot/pool1000/pool.csv')
    return list(csv.DictReader(open(path)))
