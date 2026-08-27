#!/usr/bin/env python3
"""Break a traffic table into its ELEMENTARY TIME INTERVALS and find the busiest.

Named phases are not the right unit.  Windows overlap -- a DEPS DAG runs q/k/v
concurrently, and a residual spans every layer it bypasses -- so two rows with
different (t_on,t_off) can be injecting into the same cycle.  What loads the
network is the sum over every row whose window covers that cycle.

So: cut the period at every window boundary, and for each elementary interval sum
the rows live in it.  The busiest interval is what sets congestion; whole-table
averages dilute it by the idle stretches.

Static analysis only -- no simulation.

  python3 tools/table_phase_load.py TABLE.txt [TABLE.txt ...] [--dims 6 6 3] [--all]
"""
import sys

DX = DY = DZ = None
F = 16                                   # flits per packet (-size 16 16)


def xyz(n): return (n % DX, (n // DX) % DY, n // (DX * DY))


def hops(a, b):
    x1, y1, z1 = xyz(a); x2, y2, z2 = xyz(b)
    return abs(x1 - x2) + abs(y1 - y2) + abs(z1 - z2)


def read(path):
    rows, period = [], None
    for L in open(path):
        if L.startswith('%') or not L.strip():
            continue
        f = L.split()
        rows.append((int(f[0]), int(f[1]), float(f[2]), int(f[4]), int(f[5])))
        period = int(f[6])
    return rows, period


def intervals(rows, period):
    """Elementary intervals: cut at every t_on and t_off."""
    cuts = sorted({0, period} | {r[3] for r in rows} | {r[4] for r in rows})
    out = []
    for a, b in zip(cuts, cuts[1:]):
        if b <= a:
            continue
        live = [r for r in rows if r[3] <= a and r[4] >= b]
        out.append((a, b, live))
    return out


def stats(live):
    if not live:
        return dict(flows=0, offered=0.0, peak_out=0.0, peak_in=0.0,
                    mean_hops=0.0, cc_rate=0.0)
    out, inn = {}, {}
    tot = cc = 0.0
    for s, d, pir, _, _ in live:
        lam = pir * F
        out[s] = out.get(s, 0) + lam
        inn[d] = inn.get(d, 0) + lam
        tot += lam
        cc += lam * hops(s, d)
    return dict(flows=len(live), offered=tot,
                peak_out=max(out.values()), peak_in=max(inn.values()),
                mean_hops=cc / tot, cc_rate=cc)


def report(path, show_all):
    rows, period = read(path)
    iv = intervals(rows, period)
    scored = [(a, b, stats(live)) for a, b, live in iv]
    busiest = max(scored, key=lambda t: t[2]['offered'])

    name = path.rsplit('/', 1)[-1].replace('.txt', '')
    print(f"\n### {name}   period {period:,} cycles   {len(rows)} rows   "
          f"{len(iv)} elementary intervals")
    print(f"{'interval':>22} {'cycles':>9} {'%period':>8} {'flows':>6} "
          f"{'offered f/c':>12} {'peak out':>9} {'peak in':>8} {'hops':>6} {'link-f/c':>10}")
    shown = scored if show_all else [s for s in scored if s[2]['offered'] > 0]
    for a, b, st in shown:
        mark = '  <-- BUSIEST' if (a, b) == (busiest[0], busiest[1]) else ''
        print(f"{f'[{a:,}, {b:,})':>22} {b-a:>9,} {(b-a)/period:>7.1%} "
              f"{st['flows']:>6} {st['offered']:>12.4f} {st['peak_out']:>9.4f} "
              f"{st['peak_in']:>8.4f} {st['mean_hops']:>6.2f} {st['cc_rate']:>10.2f}{mark}")

    bs = busiest[2]
    dur = busiest[1] - busiest[0]
    whole = sum(s['offered'] * (b - a) for a, b, s in scored) / period
    print(f"\n  BUSIEST [{busiest[0]:,}, {busiest[1]:,})  {dur:,} cycles "
          f"({dur/period:.1%} of the period)")
    print(f"    offered {bs['offered']:.4f} flits/cyc network-wide "
          f"= {bs['offered']/(DX*DY*DZ):.5f} per node")
    print(f"    vs period-average {whole:.4f} f/c  ->  the busiest interval runs "
          f"{bs['offered']/whole:.2f}x the average")
    print(f"    hottest injector {bs['peak_out']:.4f} f/c, hottest sink "
          f"{bs['peak_in']:.4f} f/c  (1.000 saturates a link)")
    return name, busiest, whole


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    dims = (6, 6, 3)
    if '--dims' in sys.argv:
        i = sys.argv.index('--dims'); dims = tuple(int(v) for v in sys.argv[i+1:i+4])
        args = [a for a in args if a not in sys.argv[i+1:i+4]]
    DX, DY, DZ = dims
    for p in args:
        report(p, '--all' in sys.argv)
