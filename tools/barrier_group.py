#!/usr/bin/env python3
"""Group BARRIERTRACE dumps into per-(accumulator, phase, period) barrier times.

Reads lines  B,<dst>,<inject_ts>,<arrival_ts>  (emitted by TStats.cpp when
BARRIERTRACE is set) from a file or stdin. Groups delivered packets by destination
node, phase window, and period; max(arrival) per group = the barrier time (the
slowest partial sum that gates a reduction). Phase completion = max over accumulators.

Defaults match traffics_dnn_6base/*_base.txt (ResNet-50 bottleneck-3):
  conv1=[0,5138) conv2=[5138,28259) conv3=[28259,38535), t_period=38536.
For a different workload pass its own windows from that table's header line.
"""
import sys, argparse
from collections import defaultdict

def phase_of(t, phases):
    for name, lo, hi in phases:
        if lo <= t < hi:
            return name, lo
    return None, None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?", help="BARRIERTRACE capture (default: stdin)")
    ap.add_argument("--t-period", type=float, default=38536)
    ap.add_argument("--phases", default="conv1:0:5138,conv2:5138:28259,conv3:28259:38535")
    args = ap.parse_args()

    phases = [(n, float(lo), float(hi))
              for n, lo, hi in (s.split(":") for s in args.phases.split(","))]

    fh = open(args.file) if args.file else sys.stdin
    barrier = {}                        # (dst, phase, period) -> max arrival rel. to phase start
    for line in fh:
        if not line.startswith("B,"):
            continue
        _, dst, inj, arr = line.rstrip("\n").split(",")
        dst, inj, arr = int(dst), float(inj), float(arr)
        period = int(inj // args.t_period)
        name, lo = phase_of(inj % args.t_period, phases)
        if name is None:
            continue
        rel = arr - (period * args.t_period + lo)
        key = (dst, name, period)
        if key not in barrier or rel > barrier[key]:
            barrier[key] = rel

    per_dst = defaultdict(list)
    per_phase_period = defaultdict(dict)
    for (dst, name, period), rel in barrier.items():
        per_dst[(dst, name)].append(rel)
        per_phase_period[(name, period)][dst] = rel

    print("# per-accumulator barrier (cycles from phase start)")
    print("# dst  phase   n     mean      max      min")
    for (dst, name) in sorted(per_dst):
        v = per_dst[(dst, name)]
        print(f"{dst:4d} {name:6s} {len(v):3d} {sum(v)/len(v):8.1f} {max(v):8.1f} {min(v):8.1f}")

    print("\n# phase completion = max over accumulators (the reduction gate)")
    print("# phase period  completion  straggler_dst")
    comp = defaultdict(list)
    for (name, period), dmap in sorted(per_phase_period.items()):
        s = max(dmap, key=dmap.get)
        print(f"{name:6s} {period:4d} {dmap[s]:10.1f}  {s}")
        comp[name].append(dmap[s])

    print("\n# phase-completion summary across periods")
    for name in [p[0] for p in phases]:
        if comp[name]:
            v = comp[name]
            print(f"{name:6s} n={len(v)} mean={sum(v)/len(v):.1f} max={max(v):.1f}")

if __name__ == "__main__":
    main()
