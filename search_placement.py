#!/usr/bin/env python3
"""Search for a placement that separates HOP COUNT from PATH DIVERSITY.

The current and XY-diagonal placements change both at once (7x7x3: hops
3.33->4.96 while diversity 25.5%->67.2%), so the measured DP degradation cannot
be attributed to either.  This hill-climbs the tile->node permutation toward a
target (diversity, hops) pair, to build the missing cells:

  LOW-DIV / HIGH-HOP   -- diversity like current, hops like diagonal.
                          If DP still degrades here, HOPS are the cause.
  HIGH-DIV / LOW-HOP   -- diversity like diagonal, hops like current.
                          If DP degrades here, DIVERSITY is the cause.

Usage: python3 search_placement.py FLOWS.csv DIMX DIMY DIMZ TARGET_DIV TARGET_HOP OUT.json
"""
import csv
import json
import random
import sys

from oeb_path_diversity import Mesh

_cache = {}


def score(m, flows, perm):
    """(bytes-weighted % with >1 path, bytes-weighted mean hops)."""
    tot = div = wh = 0.0
    for s, d, b in flows:
        a, c = perm[s], perm[d]
        if a == c:
            continue
        key = (a, c)
        if key not in _cache:
            _cache[key] = (m.npaths(m.xyz(a), m.xyz(c)), m.hops(a, c))
        n, h = _cache[key]
        tot += b
        wh += h * b
        if n > 1:
            div += b
    return div / tot * 100, wh / tot


def search(flows_csv, dims, tgt_div, tgt_hop, iters=6000, seed=1):
    m = Mesh(*dims)
    R = list(csv.DictReader(open(flows_csv)))
    flows = [(int(r['src']), int(r['dst']), float(r['bytes'])) for r in R]
    used = sorted({f[0] for f in flows} | {f[1] for f in flows})
    N = dims[0] * dims[1] * dims[2]
    rng = random.Random(seed)

    # start from identity (the current placement) padded with the free nodes
    free = [n for n in range(N) if n not in set(used)]
    cur = {u: u for u in used}
    spare = list(free)

    def cost(p):
        dv, hp = score(m, flows, p)
        # hops weighted up: it is the harder target to hit
        return abs(dv - tgt_div) + 6.0 * abs(hp - tgt_hop), dv, hp

    best, bd, bh = cost(cur)
    for it in range(iters):
        p = dict(cur)
        if spare and rng.random() < 0.4:          # move a tile to a free node
            u = rng.choice(used); j = rng.randrange(len(spare))
            p[u], spare[j] = spare[j], p[u]
            c, dv, hp = cost(p)
            if c < best:
                best, bd, bh, cur = c, dv, hp, p
            else:
                spare[j] = p[u]                   # undo
        else:                                     # swap two tiles
            a, b = rng.sample(used, 2)
            p[a], p[b] = p[b], p[a]
            c, dv, hp = cost(p)
            if c < best:
                best, bd, bh, cur = c, dv, hp, p
        if it % 1500 == 0:
            print(f"    it {it:5d}  div {bd:5.1f}%  hop {bh:4.2f}  cost {best:.3f}")
    return cur, bd, bh


if __name__ == '__main__':
    fl, dx, dy, dz, td, th, out = sys.argv[1:8]
    dims = (int(dx), int(dy), int(dz))
    print(f"  target: diversity {td}%  hops {th}")
    perm, dv, hp = search(fl, dims, float(td), float(th))
    print(f"  ACHIEVED: diversity {dv:.1f}%   weighted hops {hp:.2f}")
    json.dump({str(k): v for k, v in perm.items()}, open(out, 'w'))
    print(f"  wrote {out}")
