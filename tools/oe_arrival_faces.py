#!/usr/bin/env python3
"""Score a traffic table's PLACEMENT by the load on each node's arrival faces.

The Stage 2 mechanism result (FINDINGS.md) is that DP's benefit is decided by
whether a hot sink's fan-in can be spread across its input faces.  Under minimal
routing the arrival face is fixed by where the sender is, not chosen -- so a
sink whose senders all lie to one side has congestion no selection policy can
relieve, however much path diversity exists elsewhere in the mesh.

This scores that directly.  For every (src,dst) it enumerates all minimal paths
the router admits and records the FINAL hop, giving the routing-admitted arrival
load per face.  Do NOT substitute the cheap geometric estimate ("one face per
displaced dimension"): on node 4 of the 6x6x3 ResNet block the geometric number
was 0.118 flits/cyc against 0.274 measured by DPTRACE, while this model gives
0.297 -- 8% of measurement.  The geometric metric ranked a useless swap as an
improvement; this one predicted the null before the runs finished.

  OBJECTIVE for a placement search:  minimise the PEAK arrival-face load over
  all (node, face) pairs, subject to a bound on mean hop count.

Face labels are the direction of the packet's last hop, so E=... means "arrived
on an eastward hop", i.e. entered through the node's WEST side.

Usage:
  python3 oe_arrival_faces.py TABLE.txt [DIMX DIMY DIMZ] [--routing oe|oeb|oeb2] [--top N]

  oe    plain odd-even 3D            (-routing oddeven)
  oeb   odd-even-balanced, RELAXED   (-routing oddevenbalanced AS SIMULATED) -- default
  oeb2  odd-even-balanced, modified2 (historic; planar/vertical mutually exclusive)
"""
import collections
import sys

from oeb_path_diversity import STEP, UP, DN, oddEven, oddEven0
from oeb_path_diversity import route as route_oeb2          # modified2 (historic)
from oeb_path_diversity import route_relaxed as route_oeb   # AS SIMULATED

FACE_OF = {'N': 'N', 'S': 'S', 'E': 'E', 'W': 'W', 'U': 'U', 'D': 'D'}
DX = DY = DZ = None


def route_oe(cur, src, dst, dir_in):
    """Port of TRouter.cpp routingOddEven3D (-routing oddeven at Z>1).

    Differs from routingOddEvenBalanced/modified2 in two ways: the planar call
    is X-primary on EVERY plane (no cz-parity split), and planar+vertical
    directions COEXIST in both the up and down branches rather than being
    mutually exclusive.
    """
    cx, cy, cz = cur
    sx, sy, sz = src
    dx_, dy_, dz_ = dst
    if dir_in in (UP, DN):
        sx, sy = cx, cy
    s = (sx, sy, sz)
    ex, ey, ez = dx_ - cx, dy_ - cy, dz_ - cz
    if ez == 0:
        return oddEven(cur, s, dst)
    out = []
    if ez > 0:
        if ex == 0 and ey == 0:
            return [DN]
        if (cz % 2 == 1) or (cz == sz):
            out += oddEven(cur, s, dst)
        if (dz_ % 2 == 1) or (ez != 1):
            out.append(DN)
        return out
    if ex == 0 and ey == 0:
        return [UP]
    if cz % 2 == 0:
        out += oddEven(cur, s, dst)
    out.append(UP)
    return out


def xyz(n):
    return (n % DX, (n // DX) % DY, n // (DX * DY))


def degree(n):
    x, y, z = xyz(n)
    return sum(1 for a, b, c in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0),
                                 (0, 0, 1), (0, 0, -1))
               if 0 <= x + a < DX and 0 <= y + b < DY and 0 <= z + c < DZ)


def arrivals(src, dst, route):
    """Counter over final-hop directions across all admissible minimal paths."""
    memo = {}

    def rec(cur, sxy, din):
        if cur == dst:
            return collections.Counter({din: 1})
        k = (cur, sxy, din)
        if k in memo:
            return memo[k]
        tot = collections.Counter()
        for d in route(cur, (sxy[0], sxy[1], src[2]), dst, din):
            st = STEP[d]
            nxt = (cur[0] + st[0], cur[1] + st[1], cur[2] + st[2])
            if not (0 <= nxt[0] < DX and 0 <= nxt[1] < DY and 0 <= nxt[2] < DZ):
                continue
            tot += rec(nxt, (nxt[0], nxt[1]) if d in (UP, DN) else sxy, d)
        memo[k] = tot
        return tot

    sys.setrecursionlimit(20000)
    return rec(src, (src[0], src[1]), None)


def main(path, dims, routing, top):
    global DX, DY, DZ
    DX, DY, DZ = dims
    route = {"oe": route_oe, "oeb": route_oeb, "oeb2": route_oeb2}[routing]

    senders = collections.defaultdict(list)
    inload = collections.Counter()
    for line in open(path):
        if line.startswith('%') or not line.strip():
            continue
        f = line.split()
        s, d, pir = int(f[0]), int(f[1]), float(f[2])
        senders[d].append((s, pir))
        inload[d] += pir

    print(f"{path}   mesh {DX}x{DY}x{DZ}   routing {routing}")
    print(f"{'node':>5} {'coord':>10} {'fan-in':>7} {'in f/c':>7} {'deg':>4} "
          f"{'faces':>6} {'peak':>7} {'worst/mean':>11}")
    # Score EVERY destination -- the objective is a property of the placement,
    # not of how many rows we chose to print.  `top` controls display only.
    peak_global = (0.0, None, None)
    shown = {n for n, _ in inload.most_common(top)}
    scored = 0
    for n, _ in inload.most_common():
        b = xyz(n)
        face = collections.Counter()
        for s, pir in senders[n]:
            c = arrivals(xyz(s), b, route)
            tot = sum(c.values())
            for d, cnt in c.items():
                face[d] += pir * cnt / tot
        used = [v * 16 for v in face.values() if v > 1e-12]
        if not used:
            continue
        scored += 1
        wm = max(used) / (sum(used) / 6)
        if max(used) > peak_global[0]:
            peak_global = (max(used), n, max(face, key=face.get))
        if n not in shown:
            continue
        print(f"{n:>5} {str(b):>10} {len(senders[n]):>7} {inload[n]*16:>7.3f} "
              f"{degree(n):>4} {len(used):>6} {max(used):>7.3f} {wm:>10.2f}x")
        print("        " + "  ".join(f"{k}={v*16:.3f}"
                                     for k, v in sorted(face.items()) if v > 1e-12))
    print(f"\nOBJECTIVE  peak arrival-face load = {peak_global[0]:.3f} flits/cyc "
          f"at node {peak_global[1]} face {peak_global[2]}   (1.000 saturates a link)"
          f"\n           scored all {scored} sinks; --top {top} controls display only")


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    routing = "oeb"          # the simulated substrate
    top = 8
    for i, x in enumerate(sys.argv):
        if x == "--routing":
            routing = sys.argv[i + 1]
        if x == "--top":
            top = int(sys.argv[i + 1])
    dims = tuple(int(v) for v in a[1:4]) if len(a) >= 4 else (6, 6, 3)
    main(a[0], dims, routing, top)
