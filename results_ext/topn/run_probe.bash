#!/bin/bash
# Two-set hybrid probe: arms a (assignment, ci 648) and b (+freshness, ci = period)
# on bf (N=15) and f1 (N=40), all knee rungs, 3 seeds. Baselines exist.
cd /home/nizar/noxim3d-dnn || exit 1
R=results_ext/topn; H=results_stage3/mapping_pilot/pool1000/hill
# per-placement sinkfiles (rank is rung-invariant; use the lowest rung's table)
for f in $H/tables_bf/*_k0300.txt;  do t=$(basename $f _k0300.txt); [ -s $R/sinks_$t ] || python3 tools/rank_sinks.py $f $R/sinks_$t >/dev/null; done
for f in $H/tables_f1/*_k0300.txt;  do t=$(basename $f _k0300.txt); [ -s $R/sinks_$t ] || python3 tools/rank_sinks.py $f $R/sinks_$t >/dev/null; done
{
for k in 0300 0550 0750 0950; do for f in $H/tables_bf/*_k${k}.txt; do
  t=$(basename $f _k${k}.txt); for arm in a b; do ci=648; [ $arm = b ] && ci=90
    for s in 1 2 3; do echo "$f $t $k 15 $ci $arm $s"; done; done; done; done
for k in 0300 0550 0750 0950 1150 1400 1700; do for f in $H/tables_f1/*_k${k}.txt; do
  t=$(basename $f _k${k}.txt); for arm in a b; do ci=648; [ $arm = b ] && ci=240
    for s in 1 2 3; do echo "$f $t $k 40 $ci $arm $s"; done; done; done; done
} | xargs -P 14 -n 7 bash -c '
  f=$0; t=$1; k=$2; n=$3; ci=$4; arm=$5; s=$6
  out=$(timeout 1800 ./noxim -size 16 16 -dimx 6 -dimy 6 -dimz 3 -buffer 16 \
        -routing oddevenbalanced -sel dp -dpcost occupancy -cinterval $ci \
        -dptopn $n results_ext/topn/sinks_$t -warmup 1944 -sim 38536 -seed $s -traffic table $f 2>/dev/null)
  a=$(echo "$out"|grep -oP "average delay \(cycles\): \K[0-9.]+")
  p=$(echo "$out"|grep -oP "^% Delay p99 \(cycles\): \K[0-9.]+")
  th=$(echo "$out"|grep -oP "Throughput \(flits/cycle/IP\): \K[0-9.]+")
  ns=$(echo "$out"|grep -oP "^% Delay samples: \K[0-9]+")
  echo "${t}_k${k} topn$5 $s ${a:-NA} ${p:-NA} ${th:-NA} ${ns:-NA}"
' >> results_ext/topn/res_probe.txt
echo "PROBE DONE $(date)" >> results_ext/topn/run.log
