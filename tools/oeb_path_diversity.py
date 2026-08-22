#!/usr/bin/env python3
"""How much routing CHOICE does modified2 odd-even-balanced give each flow?

A Python port of the router's own routing function, used to count the minimal
paths admitted for every (src,dst) pair in a generated traffic table.  DP and
bufferlevel selection can only differ where that count is > 1; on a flow with a
single admissible path the two policies are provably identical.

Port source (verified line-by-line against the C++):
  TRouter.cpp  routingOddEvenBalanced  ~1687   -- the modified2 3D wrapper
               routingOddEven          ~813    -- X-primary, used on even z
               routingOddEven0         ~1219   -- Y-primary, used on odd z
               routingOddEven1                 -- alias of routingOddEven

Direction semantics recovered from the C++ rather than assumed:
  e1 = -(d1-c1);  e1>0 -> NORTH   =>  NORTH = y-1,  SOUTH = y+1
  ez =  dz-cz;    ez>0 -> DOWN    =>  DOWN  = z+1,  UP    = z-1
  EAST = x+1, WEST = x-1

!! NOT cross-checked against the simulator's own hop traces.  The port is
   validated by construction and by the fact that axis-aligned flows provably
   yield a single direction (an e0==0 / e1==0 branch returns one push).  Verify
   against real traces before any number from here goes into a paper.

Usage:
  python3 oeb_path_diversity.py FLOWS.csv DIMX DIMY DIMZ
  python3 oeb_path_diversity.py            # both committed ResNet block tables
"""
import csv
import statistics as st
import sys

N, S, E, W, UP, DN = 'N', 'S', 'E', 'W', 'U', 'D'
STEP = {N: (0, -1, 0), S: (0, 1, 0), E: (1, 0, 0), W: (-1, 0, 0),
        UP: (0, 0, -1), DN: (0, 0, 1)}


def oddEven(c, s, d):
    """routingOddEven / routingOddEven1 -- X-primary, used on even z planes."""
    c0, c1 = c[0], c[1]; s0 = s[0]; d0, d1 = d[0], d[1]
    e0 = d0 - c0; e1 = -(d1 - c1); out = []
    if e0 == 0:
        out.append(N if e1 > 0 else S)
    elif e0 > 0:
        if e1 == 0:
            out.append(E)
        else:
            if (c0 % 2 == 1) or (c0 == s0): out.append(N if e1 > 0 else S)
            if (d0 % 2 == 1) or (e0 != 1):  out.append(E)
    else:
        out.append(W)
        if c0 % 2 == 0:
            if e1 > 0: out.append(N)
            if e1 < 0: out.append(S)
    return out


def oddEven0(c, s, d):
    """routingOddEven0 -- Y-primary, used on odd z planes."""
    c0, c1 = c[0], c[1]; s1 = s[1]; d0, d1 = d[0], d[1]
    e0 = -(d0 - c0); e1 = d1 - c1; out = []
    if e1 == 0:
        if e0 > 0: out.append(W)
        if e0 < 0: out.append(E)
    elif e1 > 0:
        if e0 == 0:
            out.append(S)
        else:
            if (c1 % 2 == 1) or (c1 == s1):
                if e0 > 0: out.append(W)
                if e0 < 0: out.append(E)
            if (d1 % 2 == 1) or (e1 != 1): out.append(S)
    else:
        out.append(N)
        if c1 % 2 == 0:
            if e0 > 0: out.append(W)
            if e0 < 0: out.append(E)
    return out


def route(cur, src, dst, dir_in):
    """routingOddEvenBalanced, modified2: planar and vertical are mutually
    exclusive in BOTH branches -- a hop is either in-plane or vertical, never
    offered as a choice between the two."""
    cx, cy, cz = cur; sx, sy, sz = src; dx_, dy_, dz_ = dst
    if dir_in in (UP, DN):            # vertical arrival rewrites the source xy
        sx, sy = cx, cy
    s = (sx, sy, sz)
    ex, ey, ez = dx_ - cx, dy_ - cy, dz_ - cz
    if ez == 0:
        return oddEven(cur, s, dst) if cz % 2 == 0 else oddEven0(cur, s, dst)
    if ez > 0:                        # going down
        if ex == 0 and ey == 0: return [DN]
        if (cz % 2 == 1) or (cz == sz):
            return oddEven(cur, s, dst) if cz % 2 == 0 else oddEven0(cur, s, dst)
        if (dz_ % 2 == 1) or (ez > 1): return [DN]
        return []
    if (ex != 0 or ey != 0) and (cz % 2 == 0):   # going up
        return oddEven(cur, s, dst)
    return [UP]


def route_relaxed(cur, src, dst, dir_in):
    """routingOddEvenBalanced AS SIMULATED -- the RELAXED variant.

    Port of TRouter.cpp routingOddEvenBalanced (~1751).  It differs from
    `route` (modified2) only in that planar and vertical are NOT mutually
    exclusive: in the C++ the `//else` is commented out in both the descending
    and the ascending branch, so a hop may be offered as a CHOICE between an
    in-plane and a vertical move.  Everything else -- the cz-parity split, the
    (cz%2==1 || cz==sz) planar gate, the (dz%2==1 || ez>1) descend gate, and the
    vertical-arrival source rewrite -- is identical.

    This is the routing behind every relaxed-OEB number in FINDINGS.md /
    SESSION-NOTES; `route` is kept for reproducing the older modified2 analysis.
    """
    cx, cy, cz = cur; sx, sy, sz = src; dx_, dy_, dz_ = dst
    if dir_in in (UP, DN):            # vertical arrival rewrites the source xy
        sx, sy = cx, cy
    s = (sx, sy, sz)
    ex, ey, ez = dx_ - cx, dy_ - cy, dz_ - cz

    if ez == 0:
        return oddEven(cur, s, dst) if cz % 2 == 0 else oddEven0(cur, s, dst)

    out = []
    if ez > 0:                        # going down
        if ex == 0 and ey == 0:
            return [DN]
        if (cz % 2 == 1) or (cz == sz):
            out += oddEven(cur, s, dst) if cz % 2 == 0 else oddEven0(cur, s, dst)
        if (dz_ % 2 == 1) or (ez > 1):        # coexists with the planar options
            out.append(DN)
        return out

    # ez < 0, going up
    if (ex != 0 or ey != 0) and (cz % 2 == 0):
        out += oddEven(cur, s, dst)
    out.append(UP)                            # always offered alongside planar
    return out


class Mesh:
    def __init__(self, dx, dy, dz):
        self.DX, self.DY, self.DZ = dx, dy, dz

    def xyz(self, n):
        return (n % self.DX, (n // self.DX) % self.DY, n // (self.DX * self.DY))

    def nid(self, x, y, z):
        """Mirror of coord2Id in NoximDefs.h."""
        return x + y * self.DX + z * self.DX * self.DY

    def hops(self, a, b):
        A, B = self.xyz(a), self.xyz(b)
        return sum(abs(A[i] - B[i]) for i in range(3))

    def npaths(self, src, dst):
        """Distinct minimal paths the router admits from src to dst.

        Memoised over (node, effective source xy, incoming direction) -- the
        routing function keys off all three, so the state cannot be collapsed
        to the node alone.
        """
        seen = {}
        def rec(cur, sxy, dir_in):
            if cur == dst: return 1
            key = (cur, sxy, dir_in)
            if key in seen: return seen[key]
            tot = 0
            for d in route(cur, (sxy[0], sxy[1], src[2]), dst, dir_in):
                st_ = STEP[d]
                nxt = (cur[0]+st_[0], cur[1]+st_[1], cur[2]+st_[2])
                if not (0 <= nxt[0] < self.DX and 0 <= nxt[1] < self.DY
                        and 0 <= nxt[2] < self.DZ):
                    continue
                nsxy = (nxt[0], nxt[1]) if d in (UP, DN) else sxy
                tot += rec(nxt, nsxy, d)
            seen[key] = tot
            return tot
        sys.setrecursionlimit(20000)
        return rec(src, (src[0], src[1]), None)

    def diagonal_walk(self):
        """Alternative allocation order: offset each mesh row's x by its y, Z
        innermost.  A bijection over all DX*DY*DZ nodes.  Breaks the axis
        alignment that the current box placement gives the reduction flows."""
        return [self.nid((i + j) % self.DX, j, z) for j in range(self.DY)
                for i in range(self.DX) for z in range(self.DZ)]

    def remap_to_diagonal(self, used):
        """Map the occupied nodes, in the walk order the current placement
        fills them (y outer, x mid, z inner), onto the diagonal walk."""
        order = sorted(used, key=lambda n: ((n // self.DX) % self.DY, n % self.DX,
                                            n // (self.DX * self.DY)))
        return dict(zip(order, self.diagonal_walk()))


def report(tag, flows_csv, dims):
    """Diversity and hop cost under the current placement and the diagonal one."""
    m = Mesh(*dims)
    R = list(csv.DictReader(open(flows_csv)))
    used = sorted({int(r['src']) for r in R} | {int(r['dst']) for r in R})
    remap = m.remap_to_diagonal(used)
    nodes = m.DX * m.DY * m.DZ
    print(f"\n### {tag}   mesh {m.DX}x{m.DY}x{m.DZ} = {nodes} nodes   "
          f"{len(R)} flows   {len(used)} tiles ({len(used)/nodes*100:.0f}% occupancy)")
    print(f"  {'placement':12s} {'rows>1path':>11} {'bytes>1path':>12} "
          f"{'wpaths':>7} {'mean hop':>9} {'w hop':>7}")
    for name, use in (('current', False), ('diagonal', True)):
        tb = dv = wp = hs = wh = 0.0; nr = nd = 0
        for r in R:
            s, d = int(r['src']), int(r['dst'])
            if use: s, d = remap[s], remap[d]
            if s == d: continue
            b = float(r['bytes'])
            n = m.npaths(m.xyz(s), m.xyz(d))
            nr += 1; tb += b; wp += n * b
            h = m.hops(s, d); hs += h; wh += h * b
            if n > 1: nd += 1; dv += b
        print(f"  {name:12s} {nd/nr*100:>10.1f}% {dv/tb*100:>11.1f}% "
              f"{wp/tb:>7.2f} {hs/nr:>9.2f} {wh/tb:>7.2f}")


if __name__ == '__main__':
    if len(sys.argv) > 4:
        report(sys.argv[1], sys.argv[1], tuple(int(a) for a in sys.argv[2:5]))
    else:
        report("ResNet-50 block, 7x7x3 (odd x odd)",
               "traffics_dnn/resnet50_bottleneck3_xb128_7x7x3_flows.csv", (7, 7, 3))
        report("ResNet-50 block, 6x6x3 (even x even)",
               "traffics_dnn/resnet50_bottleneck3_xb128_6x6x3_flows.csv", (6, 6, 3))
