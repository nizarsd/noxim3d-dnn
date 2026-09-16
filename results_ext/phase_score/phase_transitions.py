#!/usr/bin/env python3
"""Phase-transition anatomy per table, from the traffic tables alone.

Per boundary (distinct t_on/t_off, clustered within 2 cycles to absorb off-by-one
slivers): total injection rate before and after, the step, and the TURNOVER --
the summed rate of flows that stop plus flows that start there (composition
change; can be large when the net step is zero).  All normalised by the
time-mean total rate.  k-invariant (uniform rate scaling cancels).
"""
import glob, sys

def flows_of(path):
    fl=[]; per=None
    for ln in open(path):
        if ln.startswith('%') or not ln.strip(): continue
        p=ln.split(); fl.append((float(p[2]),int(p[4]),int(p[5]))); per=int(p[6])
    return fl,per

def cluster(bs,eps=2):
    out=[]
    for b in sorted(bs):
        if out and b-out[-1][-1]<=eps: out[-1].append(b)
        else: out.append([b])
    return {b:g[0] for g in out for b in g}, [g[0] for g in out]

def anatomy(path):
    fl,per=flows_of(path)
    cmap,bounds=cluster({b for _,a,o in fl for b in (a,o)})
    mean_r=sum(p*(o-a) for p,a,o in fl)/per
    rows=[]
    for t in bounds:
        if t==0 or t>=per: continue
        stop=sum(p for p,a,o in fl if cmap[o]==t); start=sum(p for p,a,o in fl if cmap[a]==t)
        # active just before t: started earlier, not yet ended (ending AT t = active before)
        r_before=sum(p for p,a,o in fl if cmap[a]<t and cmap[o]>=t)
        rows.append((t/per, r_before/mean_r, (r_before-stop+start)/mean_r,
                     (start-stop)/mean_r, (start+stop)/mean_r))
    return rows

FOCUS={'resnet50_bottleneck3_xb128_6x6x3_c8r1s8':'ResNet (8,1,8)',
       'resnet50_bottleneck3_xb128_6x6x3_c8r2s4':'ResNet (8,2,4)',
       'vgg16_block3_xb128_6x6x3_c8r4s2':'VGG (8,4,2)',
       'vitsmall_encoder1_xb128_6x6x3_c16r1s16':'DeiT-S (16,1,16)'}
print("boundary anatomy (rates normalised by the time-mean total rate)")
print(f"{'table':17s} {'t/T':>5s} {'before':>7s} {'after':>6s} {'step':>6s} {'turnover':>8s}")
for f in sorted(glob.glob('traffics_dnn_packing/*.txt')):
    stem=f.split('/')[-1][:-4]
    if stem not in FOCUS: continue
    for t,rb,ra,st,tv in anatomy(f):
        print(f"{FOCUS[stem]:17s} {t:5.2f} {rb:7.2f} {ra:6.2f} {st:+6.2f} {tv:8.2f}")
print()
print("summary over all packings per workload: mean and max turnover per boundary")
agg={}
for f in sorted(glob.glob('traffics_dnn_packing/*.txt')):
    wl=f.split('/')[-1].split('_')[0]
    tv=[r[4] for r in anatomy(f)]
    agg.setdefault(wl,[]).append((max(tv),sum(tv)/len(tv),len(tv)))
for wl,v in agg.items():
    mx=[x[0] for x in v]; mn=[x[1] for x in v]
    print(f"{wl:10s} tables={len(v):2d} boundaries={v[0][2]}  max turnover {min(mx):.2f}-{max(mx):.2f}  mean {min(mn):.2f}-{max(mn):.2f}")
