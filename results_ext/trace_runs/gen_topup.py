#!/usr/bin/env python3
"""Generate top-up rung tables by linear k-scaling of an existing rung table.
usage: gen_topup.py <set> <src_k> <new_k,new_k,...>   (writes results_ext/trace_runs/tables_topup_<set>/)"""
import glob, os, sys
SET, SRCK = sys.argv[1], sys.argv[2]
NEW = [x for x in sys.argv[3].split(',')]
H = f'results_stage3/mapping_pilot/pool1000/hill/tables_{SET}'
OUT = f'results_ext/trace_runs/tables_topup_{SET}'
os.makedirs(OUT, exist_ok=True)
n=0
for f in sorted(glob.glob(f'{H}/*_k{SRCK}.txt')):
    tag = os.path.basename(f)[:-len(f'_k{SRCK}.txt')]
    rows = [ln.split() for ln in open(f)]
    for nk in NEW:
        sc = int(nk) / int(SRCK)
        with open(f'{OUT}/{tag}_k{nk}.txt', 'w') as o:
            for p in rows:
                v = float(p[2]) * sc
                o.write(f"{int(p[0]):5d} {int(p[1]):5d} {v:.10f} {v:.10f} {p[4]:>8} {p[5]:>8} {p[6]:>8}\n")
        n += 1
print(f'wrote {n} tables -> {OUT}')
