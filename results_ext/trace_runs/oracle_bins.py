#!/usr/bin/env python3
"""Task 1: phase-gated oracle from the per-packet traces.

Per (set, tag, k): bin delivered packets (B,<dst>,<inject ts>,<arrival>) by
inject-ts mod period into the table's global phase windows (boundaries clustered
within 2 cycles), pooled over seeds.  Mean delay per window per policy; then
  per-cell oracle      = min over policies of the run mean            (paper's)
  phase-gated oracle   = sum_w n_w * min(BL_w, DP_w) / sum_w n_w      (bound)
with n_w the mean of the two policies' packet counts in w.  MEAN DELAY ONLY.
usage: oracle_bins.py [set ...]   (default: all four)
Writes oracle_cells_<set>.csv + prints pooled summary.
"""
import collections, csv, glob, gzip, os, sys
R = '/home/nizar/noxim3d-dnn/results_ext/trace_runs'
PACK = {'bf':'resnet50_bottleneck3_xb128_6x6x3_c8r1s8',
        'f1':'resnet50_bottleneck3_xb128_6x6x3_c8r2s4',
        'f2':'vgg16_block3_xb128_6x6x3_c8r4s2',
        'esxd':'vitsmall_encoder1_xb128_6x6x3_c16r1s16'}

def windows(pack):
    per=None; bs=set()
    for ln in open(f'/home/nizar/noxim3d-dnn/traffics_dnn_packing/{pack}.txt'):
        if ln.startswith('%') or not ln.strip(): continue
        p=ln.split(); bs|={int(p[4]),int(p[5])}; per=int(p[6])
    bs|={0,per}
    cl=[]
    for b in sorted(bs):
        if cl and b-cl[-1][-1]<=2: cl[-1].append(b)
        else: cl.append([b])
    bounds=[g[0] for g in cl]
    if bounds[-1]<per: bounds.append(per)
    return per, bounds

def binfile(path, per, bounds):
    n=[0]*(len(bounds)-1); s=[0.0]*(len(bounds)-1)
    with gzip.open(path,'rt') as f:
        for ln in f:
            if not ln.startswith('B,'): continue
            _,dst,ts,arr=ln.split(',')
            ts=float(ts); d=float(arr)-ts; t=ts%per
            for w in range(len(bounds)-1):
                if bounds[w]<=t<bounds[w+1]: n[w]+=1; s[w]+=d; break
    return n,s

SETS = sys.argv[1:] or ['bf','f1','f2','esxd']
for SET in SETS:
    per,bounds=windows(PACK[SET]); W=len(bounds)-1
    cells=collections.defaultdict(lambda: {'bufferlevel':([0]*W,[0.0]*W),'dp':([0]*W,[0.0]*W)})
    for path in sorted(glob.glob(f'{R}/traces_{SET}/*.gz'))+sorted(glob.glob(f'{R}/traces_topup_{SET}/*.gz')):
        b=os.path.basename(path)[:-3]
        stem,pol,seed=b.rsplit('_',2)
        n,s=binfile(path,per,bounds)
        N,S=cells[stem][pol]
        for w in range(W): N[w]+=n[w]; S[w]+=s[w]
    out=csv.writer(open(f'{R}/oracle_cells_{SET}.csv','w'))
    out.writerow(['cell']+[f'w{w}_len' for w in range(W)]+['bl_mean','dp_mean','cell_oracle','phase_oracle','winners'])
    agg=dict(bl=0.0,dp=0.0,co=0.0,po=0.0,n=0)
    for stem,pols in sorted(cells.items()):
        (nb,sb),(nd,sd)=pols['bufferlevel'],pols['dp']
        if not sum(nb) or not sum(nd): continue
        bl=sum(sb)/sum(nb); dp=sum(sd)/sum(nd)
        po_n=po_s=0.0; winners=''
        for w in range(W):
            if not nb[w] or not nd[w]: continue
            mb,md=sb[w]/nb[w],sd[w]/nd[w]; nw=(nb[w]+nd[w])/2
            po_s+=nw*min(mb,md); po_n+=nw; winners+='D' if md<mb else 'B'
        po=po_s/po_n
        out.writerow([stem]+[bounds[w+1]-bounds[w] for w in range(W)]+
                     [f'{bl:.2f}',f'{dp:.2f}',f'{min(bl,dp):.2f}',f'{po:.2f}',winners])
        agg['bl']+=bl; agg['dp']+=dp; agg['co']+=min(bl,dp); agg['po']+=po; agg['n']+=1
    if agg['n']:
        n=agg['n']
        print(f"{SET}: cells={n}  windows={W}  pooled-cell-mean BL {agg['bl']/n:.1f}  DP {agg['dp']/n:.1f}  "
              f"cell-oracle {agg['co']/n:.1f}  PHASE-oracle {agg['po']/n:.1f}  "
              f"phase gain over cell-oracle {(agg['co']/agg['po']-1)*100:+.1f}%")
