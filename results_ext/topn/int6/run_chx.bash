#!/bin/bash
cd /home/nizar/noxim3d-dnn || exit 1
K=results_ext/topn/int6
declare -A SIM=( [r1628]=38536 [v1644]=115606 [esxd]=58097 )
declare -A NN=(  [r1628]=23    [v1644]=25     [esxd]=25 )
declare -A CI=(  [r1628]=138   [v1644]=150    [esxd]=150 )
echo "=== probe $(date)"
ls $K/tables/*_chx*_k*.txt | while read f; do
  SET=$(basename $f | cut -d_ -f1); echo "$f ${SIM[$SET]}"
done | xargs -P 14 -n 2 bash -c '
  out=$(timeout 2400 ./noxim -size 16 16 -dimx 6 -dimy 6 -dimz 3 -buffer 16 -routing oddevenbalanced \
        -sel bufferlevel -warmup 1944 -sim $1 -seed 1 -traffic table $0 2>/dev/null)
  a=$(echo "$out"|grep -oP "average delay \(cycles\): \K[0-9.]+")
  echo "$(basename $0 .txt) probe 1 ${a:-NA}"
' > $K/probe_chx.txt
python3 - <<'PY'
import collections
FFK={'r1628':400,'v1644':150,'esxd':470}
d=collections.defaultdict(dict)
for ln in open('results_ext/topn/int6/probe_chx.txt'):
    p=ln.split()
    if p[3]=='NA': continue
    tag,k=p[0].rsplit('_k',1); d[tag][int(k)]=float(p[3])
sel={}
for tag,ks in d.items():
    SET=tag.split('_')[0]; ff=ks.get(FFK[SET])
    if not ff: continue
    inb=[(k,v/ff) for k,v in ks.items() if 3.5<=v/ff<=6.5 and k!=FFK[SET]]
    if inb: sel[tag]=min(inb,key=lambda kv:abs(kv[1]-5))
with open('results_ext/topn/int6/spec_chx.txt','w') as f:
    for t,(k,dep) in sorted(sel.items()):
        f.write(f"{t} {k:04d} {dep:.1f}\n")
        print(f"{t} k{k/1000:.2f} {dep:.1f}x")
print('in-band:',len(sel))
PY
echo "=== runs $(date)"
: > $K/res_chx.txt
while read tag k dep; do
  SET=${tag%%_*}
  for pol in bl dp hyb; do
    ci=648; [ $pol = hyb ] && ci=${CI[$SET]}
    for s in $(seq 1 10); do
      echo "$K/tables/${tag}_k${k}.txt $pol ${NN[$SET]} $ci $K/sinks_${SET}_${tag#*_} ${SIM[$SET]} $s"
    done
  done
done < $K/spec_chx.txt | xargs -P 14 -n 7 bash -c '
  f=$0; pol=$1; N=$2; ci=$3; sf=$4; sim=$5; s=$6
  SEL="-sel bufferlevel"; [ "$pol" != bl ] && SEL="-sel dp -dpcost occupancy -cinterval $ci"
  TP=""; [ "$pol" = hyb ] && TP="-dptopn $N $sf"
  out=$(timeout 2400 ./noxim -size 16 16 -dimx 6 -dimy 6 -dimz 3 -buffer 16 -routing oddevenbalanced \
        $SEL $TP -warmup 1944 -sim $sim -seed $s -traffic table $f 2>/dev/null)
  a=$(echo "$out"|grep -oP "average delay \(cycles\): \K[0-9.]+")
  p=$(echo "$out"|grep -oP "^% Delay p99 \(cycles\): \K[0-9.]+")
  echo "$(basename $f .txt) $pol $s ${a:-NA} ${p:-NA}"
' >> $K/res_chx.txt
echo "CHX DONE $(date) rows=$(wc -l < $K/res_chx.txt) NA=$(grep -c NA $K/res_chx.txt)"
