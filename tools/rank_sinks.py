#!/usr/bin/env python3
"""Rank a run table's destinations by received bytes; write the sinkfile.

usage: rank_sinks.py TABLE.txt [OUT.sinks]
Volume per destination = sum over its inflow rows of pir x (t_off - t_on).
The generated run tables carry mesh node ids (already permuted), so the output
is directly usable as -dptopn's sinkfile. Prints the cumulative coverage so N
choices are auditable; ties broken by node id for determinism.
"""
import collections, sys
tab = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else tab.rsplit('.', 1)[0] + '.sinks'
v = collections.Counter()
for ln in open(tab):
    if ln.startswith('%') or not ln.strip():
        continue
    p = ln.split()
    v[int(p[1])] += float(p[2]) * (int(p[5]) - int(p[4]))
tot = sum(v.values())
ranked = sorted(v.items(), key=lambda kv: (-kv[1], kv[0]))
c = 0
with open(out, 'w') as f:
    for i, (d, x) in enumerate(ranked, 1):
        f.write(f'{d}\n')
        c += x
        print(f'{i:4d} {d:5d} {100*x/tot:7.3f}% cum {100*c/tot:6.2f}%')
print(f'{len(ranked)} sinks -> {out}')
