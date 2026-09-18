#!/bin/bash
# c=16 min-PF plane, interior-pinned min-CC placements, per-placement 4-6x knee
# rungs, three policies, 10 seeds. 8 placements per packing.
cd /home/nizar/noxim3d-dnn || exit 1
K=results_ext/topn/int6
declare -A SIM=( [r1628]=38536 [v1644]=115606 [esxd]=58097 )
declare -A NN=(  [r1628]=23    [v1644]=25     [esxd]=25 )
declare -A CI=(  [r1628]=138   [v1644]=150    [esxd]=150 )
KEEP="r1628_int0 r1628_int1 r1628_int2 r1628_int3 r1628_int4 r1628_int5 r1628_int6 r1628_int7 \
v1644_int0 v1644_int1 v1644_int2 v1644_int3 v1644_int4 v1644_int5 v1644_int6 v1644_int7 \
esxd_int0 esxd_int1 esxd_int2 esxd_int3 esxd_int4 esxd_int6 esxd_int7 esxd_int9"
: > $K/res_c16knee.txt
while read tag k dep; do
  echo " $KEEP " | grep -q " $tag " || continue
  SET=${tag%%_*}
  for pol in bl dp hyb; do
    ci=648; [ $pol = hyb ] && ci=${CI[$SET]}
    for s in $(seq 1 10); do
      echo "$K/tables/${tag}_k${k}.txt $pol ${NN[$SET]} $ci $K/sinks_${SET}_${tag#*_} ${SIM[$SET]} $s"
    done
  done
done < $K/run_spec_c16.txt | xargs -P 14 -n 7 bash -c '
  f=$0; pol=$1; N=$2; ci=$3; sf=$4; sim=$5; s=$6
  SEL="-sel bufferlevel"; [ "$pol" != bl ] && SEL="-sel dp -dpcost occupancy -cinterval $ci"
  TP=""; [ "$pol" = hyb ] && TP="-dptopn $N $sf"
  out=$(timeout 2400 ./noxim -size 16 16 -dimx 6 -dimy 6 -dimz 3 -buffer 16 -routing oddevenbalanced \
        $SEL $TP -warmup 1944 -sim $sim -seed $s -traffic table $f 2>/dev/null)
  a=$(echo "$out"|grep -oP "average delay \(cycles\): \K[0-9.]+")
  p=$(echo "$out"|grep -oP "^% Delay p99 \(cycles\): \K[0-9.]+")
  echo "$(basename $f .txt) $pol $s ${a:-NA} ${p:-NA}"
' >> $K/res_c16knee.txt
echo "C16KNEE DONE $(date) rows=$(wc -l < $K/res_c16knee.txt) NA=$(grep -c NA $K/res_c16knee.txt)"
