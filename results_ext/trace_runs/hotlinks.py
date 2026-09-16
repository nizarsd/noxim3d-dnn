#!/usr/bin/env python3
"""Per-placement hot link (PL argmax) + task-8 phase metrics, offline.

usage: hotlinks.py <set>   (bf | f1 | f2 | esxd)
Writes results_ext/trace_runs/hotlinks_<set>.csv:
  tag,u,v,dir,PL,n_win,turnover_max,turnover_mean,cv_link
where u,v is the hot directed link (mesh node ids), dir the DPTRACE direction
(N0 E1 S2 W3 U4 D5), PL its peak per-interval load (flits/cycle), and the
task-8 columns are computed ON THAT LINK: per-interval loads -> boundary
turnover (|load change| at each interval boundary / time-mean load) and CV of
its load over the period.  Same route model / interval machinery as metrics.py.
"""
import collections, csv, os, sys
SET = sys.argv[1]
H = '/home/nizar/noxim3d-dnn/results_stage3/mapping_pilot/pool1000/hill'
CFG = {
 'bf':   ('resnet50_bottleneck3_xb128_6x6x3_c8r1s8', 'belowfloor_ejc_selected.csv', 'tag'),
 'f1':   ('resnet50_bottleneck3_xb128_6x6x3_c8r2s4', 'bf_c8r2s4_selected.csv', 'tag'),
 'f2':   ('vgg16_block3_xb128_6x6x3_c8r4s2', 'bf_vgg842_selected.csv', 'tag'),
 'esxd': ('vitsmall_encoder1_xb128_6x6x3_c16r1s16', 'esxd_sel.csv', 'arm'),
}
pack, sel, tagcol = CFG[SET]
os.environ['DNN_BASE_TABLE'] = f'/home/nizar/noxim3d-dnn/traffics_dnn_packing/{pack}.txt'
sys.path.insert(0, H)
import metrics as M

DIR = {(1,0,0):1, (-1,0,0):3, (0,1,0):2, (0,-1,0):0, (0,0,1):5, (0,0,-1):4}
CUTS = sorted({0, M.PERIOD} | {r[3] for r in M.ROWS} | {r[4] for r in M.ROWS})
SPANS = [(a, b) for a, b in zip(CUTS, CUTS[1:]) if b > a]

def link_profile(perm):
    """[(span, {link: load})]; returns hot link (peak over spans) + its profile."""
    prof = []
    for a, b in SPANS:
        lk = collections.Counter()
        for s, d, pir, on, off in M.ROWS:
            if not (on <= a and off >= b): continue
            pn, qn = perm[s], perm[d]
            lam = pir * M.F
            ef, _ = M.edge_flow(pn, qn)
            for (u, v), fr in ef:
                lk[(u, v)] += lam * fr
        prof.append(((a, b), lk))
    hot, pl = max(((l, load) for _, lk in prof for l, load in lk.items()),
                  key=lambda x: x[1])
    series = [(b - a, lk.get(hot, 0.0)) for (a, b), lk in prof]
    return hot, pl, series

out = csv.writer(open(f'/home/nizar/noxim3d-dnn/results_ext/trace_runs/hotlinks_{SET}.csv', 'w'))
out.writerow(['tag','u','v','dir','PL','n_win','turnover_max','turnover_mean','cv_link'])
for rec in csv.DictReader(open(f'{H}/{sel}')):
    perm = M.perm_of(rec)
    tag = rec[tagcol] + (f"_{rec['seed']}" if 'seed' in rec and not rec[tagcol].endswith(rec.get('seed','')) else '')
    (u, v), pl, series = link_profile(perm)
    du = tuple(x - y for x, y in zip(M.xyz(v), M.xyz(u)))
    d = DIR[du]
    T = sum(w for w, _ in series)
    mean = sum(w * l for w, l in series) / T
    var = sum(w * (l - mean) ** 2 for w, l in series) / T
    steps = [abs(series[i+1][1] - series[i][1]) / mean for i in range(len(series) - 1)]
    out.writerow([tag, u, v, d, f'{pl:.4f}', len(series),
                  f'{max(steps):.3f}' if steps else '0', f'{sum(steps)/len(steps):.3f}' if steps else '0',
                  f'{var**0.5/mean:.3f}'])
    print(tag, u, v, d, f'{pl:.4f}')
