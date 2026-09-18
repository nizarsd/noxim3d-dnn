#!/bin/bash
# bE arm: CC-matched, max-E, below-floor control. probe -> rung -> BL/DP/DPN x8 seeds.
cd /home/nizar/noxim3d-dnn || exit 1
K=results_ext/topn/matrix
exec >> $K/campaign_bE.log 2>&1
echo "=== bE start $(date)"
declare -A SIM=( [r1628]=38536 [v1644]=115606 [esxd]=58097 )
declare -A NN=(  [r1628]=23    [v1644]=25     [esxd]=25 )
declare -A CI=(  [r1628]=138   [v1644]=150    [esxd]=150 )
declare -p SIM NN CI > $K/.assoc3
run1(){ # tab pol sinks sim seed
  local tab=$1 pol=$2 sinks=$3 sim=$4 seed=$5
  local SET=$(basename $tab | cut -d_ -f1)
  local SEL="-sel bufferlevel" TP=""
  [ "$pol" = dp ] && SEL="-sel dp -dpcost occupancy -cinterval 648"
  if [ "$pol" = hyb ]; then
    SEL="-sel dp -dpcost occupancy -cinterval ${CI[$SET]}"; TP="-dptopn ${NN[$SET]} $sinks"
  fi
  out=$(timeout 2400 ./noxim -size 16 16 -dimx 6 -dimy 6 -dimz 3 -buffer 16 \
        -routing oddevenbalanced $SEL $TP -warmup 1944 -sim $sim -seed $seed \
        -traffic table $tab 2>/dev/null)
  a=$(echo "$out"|grep -oP "average delay \(cycles\): \K[0-9.]+")
  p=$(echo "$out"|grep -oP "^% Delay p99 \(cycles\): \K[0-9.]+")
  echo "$(basename $tab .txt) $pol $seed ${a:-NA} ${p:-NA}"
}
export -f run1; export K
ls $K/tables/*_bE*_k*.txt | while read f; do
  SET=$(basename $f | cut -d_ -f1); echo "$f ${SIM[$SET]}"
done | xargs -P 14 -n 2 bash -c 'source $K/.assoc3; run1 "$1" bl - "$2" 1' _ > $K/probe_bE.txt
echo "=== bE probe done $(date)"
python3 - <<'PY'
import collections
d=collections.defaultdict(dict)
for ln in open('results_ext/topn/matrix/probe_bE.txt'):
    p=ln.split()
    if p[3]=='NA': continue
    tag,k=p[0].rsplit('_k',1); d[tag][int(k)]=float(p[3])
with open('results_ext/topn/matrix/run_spec_bE.txt','w') as f:
    for tag in sorted(d):
        ks=d[tag]; ff=ks[min(ks)]
        best=min(ks.items(), key=lambda kv: abs(kv[1]/ff-5)); dep=best[1]/ff
        flag='OK' if 4.0<=dep<=6.0 else 'OOB'
        f.write(f"{tag} {best[0]:04d} {dep:.1f} {flag}\n")
        print(f"{tag:14s} k{best[0]/1000:.2f} depth {dep:.1f}x {flag}  ("
              +" ".join(f"{k/1000:.2f}:{v/ff:.1f}x" for k,v in sorted(ks.items()))+")")
PY
: > $K/res_bE.txt
while read tag k dep flag; do
  for pol in bl dp hyb; do for s in 1 2 3 4 5 6 7 8; do
    SET=${tag%%_*}; echo "$K/tables/${tag}_k${k}.txt $pol $K/sinks_${tag} ${SIM[$SET]} $s"
  done; done
done < $K/run_spec_bE.txt | xargs -P 14 -n 5 bash -c 'source $K/.assoc3; run1 "$1" "$2" "$3" "$4" "$5"' _ >> $K/res_bE.txt
echo "=== bE main done $(date)"; wc -l $K/res_bE.txt; grep -c NA $K/res_bE.txt
echo "BE DONE $(date)"
