#!/bin/bash
# N@90 retests, queued behind the running batch: waits for res_n90_others.txt to
# stop growing, then cc12 at N=23 ci138 x10 seeds and f4 at N=25 ci150 x3 seeds.
cd /home/nizar/noxim3d-dnn || exit 1
R=results_ext/topn; H=results_stage3/mapping_pilot/pool1000/hill
prev=-1
while :; do n=$(wc -l < $R/res_n90_others.txt 2>/dev/null || echo 0)
  [ "$n" = "$prev" ] && [ "$(pgrep -c noxim)" -lt 2 ] && break
  prev=$n; sleep 60
done
echo "=== retests start $(date)" >> $R/campaign.log
{
for t in m1 m2 maxCC1 maxCC2 maxCC3 maxCC4 maxCC5 maxCC6 minCC3 minCC4 minCC5 minCC6; do
  for s in 1 2 3 4 5 6 7 8 9 10; do echo "$H/tables_cc12/$t.txt cc12n23 23 138 $R/sinks_cc12_$t 38536 $s"; done
done
for f in $H/tables_f4/*.txt; do t=$(basename $f .txt); tag=${t%_k*}
  for s in 1 2 3; do echo "$f f4n25 25 150 $R/sinks_f4_$tag 58097 $s"; done
done
} | xargs -P 14 -n 7 bash -c '
  f=$0; lbl=$1; N=$2; ci=$3; sf=$4; sim=$5; s=$6
  out=$(timeout 2400 ./noxim -size 16 16 -dimx 6 -dimy 6 -dimz 3 -buffer 16 \
        -routing oddevenbalanced -sel dp -dpcost occupancy -cinterval $ci \
        -dptopn $N $sf -warmup 1944 -sim $sim -seed $s -traffic table $f 2>/dev/null)
  a=$(echo "$out"|grep -oP "average delay \(cycles\): \K[0-9.]+")
  p=$(echo "$out"|grep -oP "^% Delay p99 \(cycles\): \K[0-9.]+")
  echo "$lbl $(basename $f .txt) $s ${a:-NA} ${p:-NA}"
' >> $R/res_n90_retests.txt
echo "=== retests done $(date)" >> $R/campaign.log
