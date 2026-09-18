#!/bin/bash
# DeiT ES-arm x hybrid cross: 16 placements (minES/maxES x 8 seeds) x 3 rungs x
# 3 seeds, arms a (ci 648) and b (ci 84), N=14. Baselines exist (traced batch).
cd /home/nizar/noxim3d-dnn || exit 1
R=results_ext/topn; H=results_stage3/mapping_pilot/pool1000/hill
for f in $H/tables_esxd/*_k0470.txt; do t=$(basename $f _k0470.txt)
  [ -s $R/sinks_$t ] || python3 tools/rank_sinks.py $f $R/sinks_$t >/dev/null; done
for k in 0470 0550 0650; do for f in $H/tables_esxd/*_k${k}.txt; do
  t=$(basename $f _k${k}.txt)
  for arm in a b; do ci=648; [ $arm = b ] && ci=84
    for s in 1 2 3; do echo "$f $t $k $ci $arm $s"; done
  done
done; done | xargs -P 14 -n 6 bash -c '
  f=$0; t=$1; k=$2; ci=$3; arm=$4; s=$5
  out=$(timeout 1800 ./noxim -size 16 16 -dimx 6 -dimy 6 -dimz 3 -buffer 16 \
        -routing oddevenbalanced -sel dp -dpcost occupancy -cinterval $ci \
        -dptopn 14 results_ext/topn/sinks_$t -warmup 1944 -sim 58097 -seed $s -traffic table $f 2>/dev/null)
  a=$(echo "$out"|grep -oP "average delay \(cycles\): \K[0-9.]+")
  p=$(echo "$out"|grep -oP "^% Delay p99 \(cycles\): \K[0-9.]+")
  th=$(echo "$out"|grep -oP "Throughput \(flits/cycle/IP\): \K[0-9.]+")
  echo "${t}_k${k} topn$4 $s ${a:-NA} ${p:-NA} ${th:-NA}"
' >> results_ext/topn/res_deit_cross.txt
echo "DEIT CROSS DONE $(date)" >> results_ext/topn/run.log
