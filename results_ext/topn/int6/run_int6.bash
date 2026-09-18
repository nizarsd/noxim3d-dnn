#!/bin/bash
# Interior-sink experiment at knee onset (~5x own ff), c=16 plane + v3284.
# Stage 1: 1-seed BL probe of every table. Stage 2: per placement pick the rung
# nearest 5x; run BL/DP/hyb x3 seeds. Hybrid: per-packing N@90 and ci=6N.
cd /home/nizar/noxim3d-dnn || exit 1
K=results_ext/topn/int6
declare -A SIM=( [r1628]=38536 [v1644]=115606 [esxd]=58097 [v3284]=115606 )
declare -A NN=(  [r1628]=23    [v1644]=25     [esxd]=25    [v3284]=22 )
run1(){ # tab pol N ci sinks sim seed
  local SEL="-sel bufferlevel"; [ "$2" != bl ] && SEL="-sel dp -dpcost occupancy -cinterval $4"
  local TP=""; [ "$2" = hyb ] && TP="-dptopn $3 $5"
  out=$(timeout 2400 ./noxim -size 16 16 -dimx 6 -dimy 6 -dimz 3 -buffer 16 -routing oddevenbalanced \
        $SEL $TP -warmup 1944 -sim $6 -seed $7 -traffic table $1 2>/dev/null)
  a=$(echo "$out"|grep -oP "average delay \(cycles\): \K[0-9.]+")
  p=$(echo "$out"|grep -oP "^% Delay p99 \(cycles\): \K[0-9.]+")
  echo "$(basename $1 .txt) $2 $7 ${a:-NA} ${p:-NA}"
}
export -f run1
echo "=== probe $(date)"
ls $K/tables/*.txt | while read f; do
  SET=$(basename $f | cut -d_ -f1); echo "$f ${SIM[$SET]}"
done | xargs -P 14 -n 2 bash -c 'run1 $0 bl - 648 - $1 1' > $K/probe.txt
python3 - <<'PY'
import collections, statistics as st
d=collections.defaultdict(dict)
for ln in open('results_ext/topn/int6/probe.txt'):
    p=ln.split()
    if p[3]=='NA': continue
    tag,k=p[0].rsplit('_k',1)
    d[tag][int(k)]=float(p[3])
sel=[]
for tag,ks in d.items():
    kmin=min(ks); ff=ks[kmin]
    best=None
    for k,v in ks.items():
        dep=v/ff
        if best is None or abs(dep-5)<abs(best[1]-5): best=(k,dep)
    sel.append((tag,best[0],best[1]))
    print(f"{tag:18s} onset k{best[0]/1000:.2f} depth {best[1]:.1f}x  (ladder: "+" ".join(f"{k/1000:.2f}:{v/ff:.1f}x" for k,v in sorted(ks.items()))+")")
with open('results_ext/topn/int6/selected.txt','w') as f:
    for tag,k,dep in sel: f.write(f"{tag} {k:04d} {dep:.1f}\n")
PY
echo "=== onset runs $(date)"
: > $K/res_int6.txt
while read tag k dep; do
  SET=$(echo $tag | cut -d_ -f1)
  for pol in bl dp hyb; do
    ci=648; [ $pol = hyb ] && ci=$((6*${NN[$SET]}))
    for s in 1 2 3; do
      echo "$K/tables/${tag}_k${k}.txt $pol ${NN[$SET]} $ci $K/sinks_${tag#*_} $SET $s"
    done
  done
done < $K/selected.txt | sed "s|sinks_\(.*\) \([a-z0-9]*\) |sinks_\2_\1 \2 |" > /dev/null # noop
while read tag k dep; do
  SET=$(echo $tag | cut -d_ -f1); ARM=${tag#*_}
  for pol in bl dp hyb; do
    ci=648; [ $pol = hyb ] && ci=$((6*${NN[$SET]}))
    for s in 1 2 3; do
      echo "$K/tables/${tag}_k${k}.txt $pol ${NN[$SET]} $ci $K/sinks_${SET}_${ARM} ${SIM[$SET]} $s"
    done
  done
done < $K/selected.txt | xargs -P 14 -n 7 bash -c 'run1 "$0" "$1" "$2" "$3" "$4" "$5" "$6"' >> $K/res_int6.txt
echo "=== DONE $(date) rows=$(wc -l < $K/res_int6.txt) NA=$(grep -c NA $K/res_int6.txt)"
