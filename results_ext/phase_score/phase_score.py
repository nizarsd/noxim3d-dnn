#!/usr/bin/env python3
"""Two-axis phase-dynamism score per workload, from the traffic tables alone.

Axis 1 (timescale): volume-weighted phase-window length -- the length of the
global window a typical byte is injected in.  Global windows = intervals between
distinct t_on/t_off boundaries of the period.
Axis 2 (amplitude): CV of the total injection rate over the period (time-
weighted over windows), plus the always-on volume share (flows active the whole
period).  Score is per workload; packings of one workload are printed together
to show (in)variance.  No simulation; reads traffics_dnn_packing/*.txt.
"""
import glob, math, sys

def score(path):
    flows=[]; period=None
    for ln in open(path):
        if ln.startswith('%') or not ln.strip(): continue
        p=ln.split()
        pir=float(p[2]); t_on=int(p[4]); t_off=int(p[5]); per=int(p[6])
        flows.append((pir,t_on,t_off)); period=per
    bounds=sorted({b for _,a,o in flows for b in (a,o)}|{0,period})
    wins=[(a,b) for a,b in zip(bounds,bounds[1:]) if b>a and a<period]
    tot=sum(pir*(o-a) for pir,a,o in flows)
    vol_w=[]; rate_w=[]
    for a,b in wins:
        r=sum(pir for pir,x,y in flows if x<=a and y>=b)
        rate_w.append(r); vol_w.append(r*(b-a))
    ax1=sum(v*(b-a) for v,(a,b) in zip(vol_w,wins))/tot
    mean_r=sum(r*(b-a) for r,(a,b) in zip(rate_w,wins))/period
    var=sum((r-mean_r)**2*(b-a) for r,(a,b) in zip(rate_w,wins))/period
    cv=math.sqrt(var)/mean_r if mean_r else float('nan')
    on_share=sum(pir*(o-a) for pir,a,o in flows if a==0 and o==period)/tot
    return dict(period=period, n_flows=len(flows), n_windows=len(wins),
                wmin=min(b-a for a,b in wins), wmax=max(b-a for a,b in wins),
                ax1=ax1, ax1_rel=ax1/period, cv=cv, on=on_share)

print(f"{'table':46s} {'period':>7s} {'flows':>5s} {'win':>4s} {'min':>6s} {'max':>6s} "
      f"{'ax1 (cyc)':>9s} {'ax1/T':>6s} {'CV':>5s} {'on%':>5s}")
for f in sorted(glob.glob('traffics_dnn_packing/*.txt')):
    s=score(f)
    print(f"{f.split('/')[-1][:-4]:46s} {s['period']:7d} {s['n_flows']:5d} {s['n_windows']:4d} "
          f"{s['wmin']:6d} {s['wmax']:6d} {s['ax1']:9.0f} {s['ax1_rel']:6.2f} {s['cv']:5.2f} {100*s['on']:5.1f}")
