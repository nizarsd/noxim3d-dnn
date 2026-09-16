#!/usr/bin/env python3
"""Task 2: hot-link blocking decomposition from the DPTRACE T lines.

Per (set, cell, policy), pooled over seeds: on the placement's hot link,
  blocking[w]      = sum of downstream queue occupancy over the window w
  head vs body     = the first HEAD cycles after each window boundary vs the rest
                     (head spans the drain tail + field refresh: 1500 cycles)
  util[w]          = departures per cycle (first difference of flits_total)
Prints per set: DP-minus-BL blocking share by (head, body) and per window.
MEAN-DELAY-SIDE quantity (occupancy integrals); no p99 anywhere.
usage: dptrace_bins.py [set ...]
"""
import collections, csv, glob, gzip, os, sys
R='/home/nizar/noxim3d-dnn/results_ext/trace_runs'
PACK={'bf':'resnet50_bottleneck3_xb128_6x6x3_c8r1s8','f1':'resnet50_bottleneck3_xb128_6x6x3_c8r2s4',
      'f2':'vgg16_block3_xb128_6x6x3_c8r4s2','esxd':'vitsmall_encoder1_xb128_6x6x3_c16r1s16'}
HEAD=1500
def windows(pack):
    per=None; bs=set()
    for ln in open(f'/home/nizar/noxim3d-dnn/traffics_dnn_packing/{pack}.txt'):
        if ln.startswith('%') or not ln.strip(): continue
        p=ln.split(); bs|={int(p[4]),int(p[5])}; per=int(p[6])
    bs|={0,per}; cl=[]
    for b in sorted(bs):
        if cl and b-cl[-1][-1]<=2: cl[-1].append(b)
        else: cl.append([b])
    bounds=[g[0] for g in cl]
    if bounds[-1]<per: bounds.append(per)
    return per,bounds
SETS=sys.argv[1:] or ['bf','f1','f2','esxd']
for SET in SETS:
    per,bounds=windows(PACK[SET]); W=len(bounds)-1
    acc=collections.defaultdict(lambda: [ [0.0]*W,[0.0]*W,[0]*W ])  # (cell,pol) -> head occ, body occ, cycles
    for path in sorted(glob.glob(f'{R}/traces_{SET}/*.gz'))+sorted(glob.glob(f'{R}/traces_topup_{SET}/*.gz')):
        b=os.path.basename(path)[:-3]; stem,pol,seed=b.rsplit('_',2)
        A=acc[(stem,pol)]
        with gzip.open(path,'rt') as f:
            for ln in f:
                if not ln.startswith('T,'): continue
                _,st_,q,_tot=ln.split(','); t=int(st_)%per; q=int(q)
                for w in range(W):
                    if bounds[w]<=t<bounds[w+1]:
                        if t-bounds[w]<HEAD: A[0][w]+=q
                        else: A[1][w]+=q
                        A[2][w]+=1
                        break
    rows=collections.defaultdict(dict)
    for (stem,pol),(h,b,c) in acc.items():
        if sum(c)==0: continue
        rows[stem][pol]=(sum(h),sum(b),h,b)
    out=csv.writer(open(f'{R}/blocking_{SET}.csv','w'))
    out.writerow(['cell','bl_head','bl_body','dp_head','dp_body'])
    th=tb=nh=0.0; n=0
    for stem,d in sorted(rows.items()):
        if 'bufferlevel' not in d or 'dp' not in d: continue
        bh,bb,_,_=d['bufferlevel']; dh,db,_,_=d['dp']
        out.writerow([stem,f'{bh:.0f}',f'{bb:.0f}',f'{dh:.0f}',f'{db:.0f}'])
        th+=dh-bh; tb+=db-bb; n+=1
    if n:
        tot=th+tb
        print(f"{SET}: cells={n} hot-link blocking, DP minus BL: head(<{HEAD}cyc past boundary) {th:+.0f}  "
              f"body {tb:+.0f}  head share of |diff| {abs(th)/(abs(th)+abs(tb))*100:.0f}%")
