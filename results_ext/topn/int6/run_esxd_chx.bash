#!/bin/bash
# esxd chx block: probe chx0-7 into 4-6x (two-pass), then BL/DP/hyb n=10.
cd /home/nizar/noxim3d-dnn || exit 1
K=results_ext/topn/int6
run1(){ local f=$1 pol=$2 ci=$3 tp=$4 sf=$5 s=$6
  local SEL="-sel bufferlevel"; [ "$pol" != bl ] && SEL="-sel dp -dpcost occupancy -cinterval $ci"
  local TP=""; [ "$pol" = hyb ] && TP="-dptopn $tp $sf"
  out=$(timeout 2400 ./noxim -size 16 16 -dimx 6 -dimy 6 -dimz 3 -buffer 16 -routing oddevenbalanced \
        $SEL $TP -warmup 1944 -sim 58097 -seed $s -traffic table $f 2>/dev/null)
  a=$(echo "$out"|grep -oP "average delay \(cycles\): \K[0-9.]+")
  p=$(echo "$out"|grep -oP "^% Delay p99 \(cycles\): \K[0-9.]+")
  echo "$(basename $f .txt) $pol $s ${a:-NA} ${p:-NA}"
}
export -f run1
echo "=== probe pass 1 $(date)"
ls $K/tables/esxd_chx*_k0470.txt $K/tables/esxd_chx*_k0560.txt $K/tables/esxd_chx*_k0600.txt \
| xargs -P 14 -I{} bash -c 'run1 {} bl 648 - - 1' > $K/probe_esxd_chx.txt
python3 - <<'PY'
import collections
d=collections.defaultdict(dict)
for ln in open('results_ext/topn/int6/probe_esxd_chx.txt'):
    p=ln.split()
    if p[3]=='NA': continue
    tag,k=p[0].rsplit('_k',1); d[tag][int(k)]=float(p[3])
need=[]
sel={}
for tag,ks in d.items():
    ff=ks[470]
    inb=[(k,v/ff) for k,v in ks.items() if k!=470 and 4<=v/ff<=6]
    if inb: sel[tag]=min(inb,key=lambda kv:abs(kv[1]-5))
    else:
        # bracket: pick fine rung between the two probes
        lo=max((k for k,v in ks.items() if k!=470 and v/ff<4), default=560)
        need.append((tag,lo))
import os
for tag,lo in need:
    src=f'results_ext/topn/int6/tables/{tag}_k{lo:04d}.txt'
    rows=[l.split() for l in open(src)]
    for nk in (lo+20,lo+35):
        with open(f'results_ext/topn/int6/tables/{tag}_k{nk:04d}.txt','w') as o:
            for p in rows:
                v=float(p[2])*nk/lo
                o.write(f"{int(p[0]):5d} {int(p[1]):5d} {v:.10f} {v:.10f} {p[4]:>8} {p[5]:>8} {p[6]:>8}\n")
with open('results_ext/topn/int6/esxd_chx_need.txt','w') as f:
    for tag,lo in need: f.write(f"{tag} {lo+20} {lo+35}\n")
with open('results_ext/topn/int6/esxd_chx_sel.txt','w') as f:
    for t,(k,dep) in sel.items(): f.write(f"{t} {k:04d} {dep:.1f}\n")
print('pass1 selected:',len(sel),'need fine:',len(need))
PY
if [ -s $K/esxd_chx_need.txt ]; then
  echo "=== probe pass 2 $(date)"
  while read tag k1 k2; do printf "%s\n%s\n" "$K/tables/${tag}_k0$k1.txt" "$K/tables/${tag}_k0$k2.txt"; done < $K/esxd_chx_need.txt \
  | xargs -P 14 -I{} bash -c 'run1 {} bl 648 - - 1' >> $K/probe_esxd_chx.txt
  python3 - <<'PY'
import collections
d=collections.defaultdict(dict)
for ln in open('results_ext/topn/int6/probe_esxd_chx.txt'):
    p=ln.split()
    if p[3]=='NA': continue
    tag,k=p[0].rsplit('_k',1); d[tag][int(k)]=float(p[3])
sel={}
for ln in open('results_ext/topn/int6/esxd_chx_sel.txt'):
    p=ln.split(); sel[p[0]]=(int(p[1]),float(p[2]))
for tag,ks in d.items():
    if tag in sel: continue
    ff=ks[470]
    inb=[(k,v/ff) for k,v in ks.items() if k!=470 and 3.5<=v/ff<=6.5]
    if inb: sel[tag]=min(inb,key=lambda kv:abs(kv[1]-5))
with open('results_ext/topn/int6/esxd_chx_sel.txt','w') as f:
    for t,(k,dep) in sorted(sel.items()): f.write(f"{t} {k:04d} {dep:.1f}\n")
print('final selected:',len(sel))
PY
fi
echo "=== runs $(date)"
: > $K/res_esxd_chx.txt
while read tag k dep; do
  for pol in bl dp hyb; do
    ci=648; [ $pol = hyb ] && ci=150
    for s in $(seq 1 10); do
      echo "$K/tables/${tag}_k${k}.txt $pol $ci 25 $K/sinks_esxd_${tag#esxd_} $s"
    done
  done
done < $K/esxd_chx_sel.txt | xargs -P 14 -n 6 bash -c 'run1 "$0" "$1" "$2" "$3" "$4" "$5"' >> $K/res_esxd_chx.txt
echo "ESXD_CHX DONE $(date) rows=$(wc -l < $K/res_esxd_chx.txt) NA=$(grep -c NA $K/res_esxd_chx.txt)"
