#!/usr/bin/env python3
"""Channel-dependency-graph cycle search for the odd-even-balanced turn variants.

WHY.  STAGE3-MAPPING-FINDINGS.md §5 says planar/vertical exclusivity is a performance
choice and that the variants are deadlock-free per the IET paper.  That covers the
variants the paper analysed.  Relaxing a *second* branch is not automatically covered,
and the relaxation currently in the working tree has not been checked at all.

METHOD.  A wormhole network is deadlock-free if its channel dependency graph is acyclic
(Dally & Seitz).  Channels are (node, out_dir).  A dependency c1 -> c2 exists iff some
packet can hold c1 and then request c2, i.e. iff there is a (src,dst) pair for which the
router, at the node c1 delivers into and with the corresponding dir_in, returns c2's
direction.  Turns are collected by *actually walking* every (src,dst) pair, so only
realizable turns are included -- no conservative over-approximation, hence:

    cycle found  => NOT deadlock-free (definitive)
    no cycle     => deadlock-free ON THIS MESH SIZE (strong evidence, not a proof
                    for all sizes)

CONTROL.  'modified2' (both branches exclusive) is the published variant and must come
back ACYCLIC.  If it does not, this script is wrong and no other row means anything.

In-plane ports oddEven / oddEven0 are taken verbatim from oeb_path_diversity.py, which
is already in the repo and validated by construction against TRouter.cpp.

Usage:  python3 check_deadlock.py [DIMX DIMY DIMZ]...
"""
import sys

N, S, E, W, UP, DN = 0, 1, 2, 3, 4, 5
NAME = {N: "N", S: "S", E: "E", W: "W", UP: "U", DN: "D"}
STEP = {N: (0, -1, 0), S: (0, 1, 0), E: (1, 0, 0), W: (-1, 0, 0),
        UP: (0, 0, -1), DN: (0, 0, 1)}          # DN = +z, matches ez>0 -> DIRECTION_DOWN
OPP = {N: S, S: N, E: W, W: E, UP: DN, DN: UP}
LOCAL = -1


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


def make_route(relax_down, relax_up):
    """routingOddEvenBalanced.  relax_* = the corresponding `else` is commented out,
    so planar and vertical are offered together instead of exclusively."""
    def route(cur, src, dst, dir_in):
        cx, cy, cz = cur; sx, sy, sz = src; dx_, dy_, dz_ = dst
        if dir_in in (UP, DN):                 # vertical arrival rewrites source xy
            sx, sy = cx, cy
        s = (sx, sy, sz)
        ex, ey, ez = dx_ - cx, dy_ - cy, dz_ - cz
        if ez == 0:
            return oddEven(cur, s, dst) if cz % 2 == 0 else oddEven0(cur, s, dst)
        if ez > 0:                             # descending (DIRECTION_DOWN)
            if ex == 0 and ey == 0:
                return [DN]
            out = []
            planar = (cz % 2 == 1) or (cz == sz)
            if planar:
                out += oddEven(cur, s, dst) if cz % 2 == 0 else oddEven0(cur, s, dst)
            if (not planar) or relax_down:
                if (dz_ % 2 == 1) or (ez > 1):
                    out.append(DN)
            return out
        # ascending (DIRECTION_UP)
        out = []
        planar = (ex != 0 or ey != 0) and (cz % 2 == 0)
        if planar:
            out += oddEven(cur, s, dst)
        if (not planar) or relax_up:
            out.append(UP)
        return out
    return route


class Mesh:
    def __init__(self, dx, dy, dz):
        self.DX, self.DY, self.DZ = dx, dy, dz
        self.NN = dx * dy * dz

    def xyz(self, n):
        return (n % self.DX, (n // self.DX) % self.DY, n // (self.DX * self.DY))

    def nid(self, x, y, z):
        return x + y * self.DX + z * self.DX * self.DY

    def nbr(self, n, d):
        x, y, z = self.xyz(n); ddx, ddy, ddz = STEP[d]
        x += ddx; y += ddy; z += ddz
        if 0 <= x < self.DX and 0 <= y < self.DY and 0 <= z < self.DZ:
            return self.nid(x, y, z)
        return None


def build_cdg(mesh, route):
    """Walk every (src,dst); collect only turns the router actually realizes."""
    cdg = {}
    def ch(n, d): return n * 6 + d
    for s in range(mesh.NN):
        S3 = mesh.xyz(s)
        for t in range(mesh.NN):
            if s == t: continue
            D3 = mesh.xyz(t)
            seen = set()
            stack = [(s, LOCAL)]
            while stack:
                u, din = stack.pop()
                if (u, din) in seen: continue
                seen.add((u, din))
                for o in route(mesh.xyz(u), S3, D3, din):
                    v = mesh.nbr(u, o)
                    if v is None: continue
                    if v != t:
                        nxt = route(mesh.xyz(v), S3, D3, OPP[o])
                        if nxt:
                            a = ch(u, o)
                            e = cdg.setdefault(a, set())
                            for o2 in nxt:
                                if mesh.nbr(v, o2) is not None:
                                    e.add(ch(v, o2))
                        stack.append((v, OPP[o]))
    return cdg


def find_cycle(cdg):
    """Iterative DFS, 0=unseen 1=on-stack 2=done.  Returns a cycle or None."""
    colour, parent = {}, {}
    for root in list(cdg):
        if colour.get(root, 0): continue
        stack = [(root, iter(cdg.get(root, ())))]
        colour[root] = 1
        while stack:
            node, it = stack[-1]
            adv = False
            for nxt in it:
                c = colour.get(nxt, 0)
                if c == 0:
                    colour[nxt] = 1; parent[nxt] = node
                    stack.append((nxt, iter(cdg.get(nxt, ()))))
                    adv = True; break
                if c == 1:                       # back edge -> cycle
                    cyc = [nxt]; cur = node
                    while cur != nxt and cur in parent:
                        cyc.append(cur); cur = parent[cur]
                    cyc.append(nxt)
                    return list(reversed(cyc))
            if not adv:
                colour[node] = 2
                stack.pop()
    return None


def main(dims_list):
    variants = [("modified2  (stock: both exclusive)", False, False),
                ("current    (descending relaxed)",   True,  False),
                ("both       (also ascending)",       True,  True)]
    for dims in dims_list:
        mesh = Mesh(*dims)
        print(f"\n=== mesh {dims[0]}x{dims[1]}x{dims[2]}  ({mesh.NN} nodes, "
              f"{mesh.NN*6} channels) ===")
        print(f"{'variant':<36} {'CDG edges':>10} {'result':>12}")
        print("-" * 62)
        for label, rd, ru in variants:
            cdg = build_cdg(mesh, make_route(rd, ru))
            ne = sum(len(v) for v in cdg.values())
            cyc = find_cycle(cdg)
            if cyc is None:
                print(f"{label:<36} {ne:>10} {'ACYCLIC':>12}")
            else:
                print(f"{label:<36} {ne:>10} {'CYCLE':>12}")
                seq = " -> ".join(f"{c//6}{NAME[c%6]}" for c in cyc)
                print(f"{'':36} len {len(cyc)-1}: {seq[:150]}")
        print("  control: 'modified2' MUST be ACYCLIC; if not, this script is wrong.")


if __name__ == "__main__":
    a = [int(x) for x in sys.argv[1:]]
    dims = [tuple(a[i:i+3]) for i in range(0, len(a), 3)] if len(a) >= 3 else \
           [(4, 4, 3), (6, 6, 3)]
    main(dims)
