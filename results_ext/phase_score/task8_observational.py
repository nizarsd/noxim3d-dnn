#!/usr/bin/env python3
"""Task 8 observational arm (registered prediction: higher hot-link boundary
turnover -> lower DP/BL gain).  Hot-link metrics from trace_runs/hotlinks_*.csv
(offline route model); per-cell gains from the EXISTING hill res files.
Correlations at placement level (mean gain over knee cells) and cell level.
"""
import collections, csv, math, statistics as st
H='/home/nizar/noxim3d-dnn/results_stage3/mapping_pilot/pool1000/hill'
R='/home/nizar/noxim3d-dnn/results_ext/trace_runs'
KS={'bf':[300,550,750,950],'f1':[300,550,750,950,1150,1400,1700],
    'f2':[150,250,350,450,550],'esxd':[470,550,650]}
def load(f):
    d=collections.defaultdict(list)
    for ln in open(f):
        p=ln.split()
        if len(p)<5 or p[3]=='NA': continue
        tag,k=p[0].rsplit('_k',1); d[(tag,int(k))].append((float(p[3]),float(p[4])))
    return d
def m(d,t,k,i): return st.mean(v[i] for v in d[(t,k)])
def pear(x,y):
    mx,my=st.mean(x),st.mean(y)
    sx=math.sqrt(sum((a-mx)**2 for a in x)); sy=math.sqrt(sum((b-my)**2 for b in y))
    return sum((a-mx)*(b-my) for a,b in zip(x,y))/(sx*sy) if sx*sy else float('nan')
def rank(v):
    s=sorted(range(len(v)),key=lambda i:v[i]); r=[0]*len(v)
    for i,j in enumerate(s): r[j]=i
    return r
def spear(x,y): return pear(rank(x),rank(y))

allP={}
for SET in KS:
    BL,DP=load(f'{H}/res_{SET}_bl.txt'),load(f'{H}/res_{SET}_dp.txt')
    hot={r['tag']:r for r in csv.DictReader(open(f'{R}/hotlinks_{SET}.csv'))}
    rows=[]
    for tag,hr in hot.items():
        g_mean=[];g_p99=[]
        for k in KS[SET]:
            if (tag,k) in BL and (tag,k) in DP:
                g_mean.append(m(BL,tag,k,0)/m(DP,tag,k,0)); g_p99.append(m(BL,tag,k,1)/m(DP,tag,k,1))
        if not g_mean: continue
        rows.append(dict(tag=tag,tv=float(hr['turnover_max']),tvm=float(hr['turnover_mean']),
                         cv=float(hr['cv_link']),gm=st.mean(g_mean),gp=st.mean(g_p99)))
    allP[SET]=rows
print(f"{'set':5s} {'n':>2s}  metric vs mean-gain: pearson spearman | vs p99-gain: pearson spearman")
for SET,rows in allP.items():
    for met in ('tv','tvm','cv'):
        x=[r[met] for r in rows]
        print(f"{SET:5s} {len(rows):2d}  {met:3s}  {pear(x,[r['gm'] for r in rows]):+6.2f}  {spear(x,[r['gm'] for r in rows]):+6.2f}"
              f"   |   {pear(x,[r['gp'] for r in rows]):+6.2f}  {spear(x,[r['gp'] for r in rows]):+6.2f}")
pool=[r for s in ('bf','f1') for r in allP[s]]           # same workload, two packings
x=[r['tv'] for r in pool]
print(f"\npooled ResNet (bf+f1, n={len(pool)}): tv vs mean {pear(x,[r['gm'] for r in pool]):+.2f}/{spear(x,[r['gm'] for r in pool]):+.2f}"
      f"  vs p99 {pear(x,[r['gp'] for r in pool]):+.2f}/{spear(x,[r['gp'] for r in pool]):+.2f}")
for SET,rows in allP.items():
    print(f"\n{SET}: tag  tv_max  cv  gain_mean  gain_p99")
    for r in sorted(rows,key=lambda r:r['tv']):
        print(f"  {r['tag']:20s} {r['tv']:6.2f} {r['cv']:5.2f} {r['gm']:6.2f} {r['gp']:6.2f}")
