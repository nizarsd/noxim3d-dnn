#!/usr/bin/env python3
"""Per-PORT load for a traffic table: transit links as well as the ejection port.

A node's ejection port carries only traffic DESTINED for it, and that is fixed by
the flow graph -- remapping relabels which node is hot, not how hot it is.  But a
node also forwards traffic PASSING THROUGH it, and that loads its output links.
Transit load depends entirely on where the tiles sit, so it is the placement-
sensitive half of congestion and the half a mapping search can actually move.

Every port is capacity 1 flit/cycle.  A flow is spread evenly over all minimal
paths the OEB router admits, which is what an adaptive selection policy
approximates.  Loads are computed per elementary interval (windows overlap) and
the maximum is taken over all of them.

  python3 tools/table_link_load.py TABLE.txt [...] [--dims 6 6 3] [--top N]
"""
import collections
import functools
import sys

sys.path.insert(0, '/home/nizar/noxim3d-dnn/tools')
from oeb_path_diversity import STEP, UP, DN, route_relaxed as route

DX = DY = DZ = 6, 6, 3
F = 16


def xyz(n): return (n % DX, (n // DX) % DY, n // (DX * DY))
def nid(c): return c[0] + c[1] * DX + c[2] * DX * DY


def edge_flow(src, dst):
    """{(u,v): fraction of admissible minimal paths using directed edge u->v}."""
    s, d = xyz(src), xyz(dst)

    @functools.lru_cache(maxsize=None)
    def npaths(cur, sxy, din):
        if cur == d:
            return 1
        t = 0
        for k in route(cur, (sxy[0], sxy[1], s[2]), d, din):
            st = STEP[k]
            nxt = (cur[0] + st[0], cur[1] + st[1], cur[2] + st[2])
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
            nxt = (cur[0] + st[0], cur[1] + st[1], cur[2] + st[2])
            sx = (nxt[0], nxt[1]) if k in (UP, DN) else sxy
            sub = npaths(nxt, sx, k)
            if not sub:
                continue
            frac = w * sub / n_here
            out[(nid(cur), nid(nxt))] += frac
            walk(nxt, sx, k, frac)

    walk(s, (s[0], s[1]), -1, 1.0)
    return out


def read(path):
    rows, period = [], None
    for L in open(path):
        if L.startswith('%') or not L.strip():
            continue
        f = L.split()
        rows.append((int(f[0]), int(f[1]), float(f[2]), int(f[4]), int(f[5])))
        period = int(f[6])
    return rows, period


def analyse(rows, period, cache):
    cuts = sorted({0, period} | {r[3] for r in rows} | {r[4] for r in rows})
    best = dict(eject=(0.0, None), link=(0.0, None), inject=(0.0, None))
    for a, b in zip(cuts, cuts[1:]):
        live = [r for r in rows if r[3] <= a and r[4] >= b]
        if not live:
            continue
        ej = collections.Counter(); inj = collections.Counter()
        lk = collections.Counter()
        for s, d, pir, _, _ in live:
            lam = pir * F
            ej[d] += lam; inj[s] += lam
            if (s, d) not in cache:
                cache[(s, d)] = edge_flow(s, d)
            for e, fr in cache[(s, d)].items():
                lk[e] += lam * fr
        for key, ctr in (('eject', ej), ('inject', inj), ('link', lk)):
            if ctr:
                k, v = ctr.most_common(1)[0]
                if v > best[key][0]:
                    best[key] = (v, k, (a, b))
    return best


def main(paths, top):
    cache = {}
    print(f"{'table':46s} {'eject':>8} {'LINK':>8} {'inject':>8}  "
          f"{'bottleneck':>10}  hot link")
    for p in paths:
        rows, period = read(p)
        b = analyse(rows, period, cache)
        which = max(('eject', 'link', 'inject'), key=lambda k: b[k][0])
        e = b['link'][1]
        hl = f"{e[0]}->{e[1]} {xyz(e[0])}->{xyz(e[1])}" if e else '-'
        print(f"{p.rsplit('/',1)[-1][:46]:46s} {b['eject'][0]:>8.4f} {b['link'][0]:>8.4f} "
              f"{b['inject'][0]:>8.4f}  {which:>10}  {hl}")


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if '--dims' in sys.argv:
        i = sys.argv.index('--dims')
        DX, DY, DZ = (int(v) for v in sys.argv[i+1:i+4])
        args = [a for a in args if a not in sys.argv[i+1:i+4]]
    else:
        DX, DY, DZ = 6, 6, 3
    main(args, 8)
