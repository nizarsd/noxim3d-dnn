#!/bin/bash
# Wait-vs-occupancy pilot: DP with -dpcost wait on the bf set's knee cells
# (8 placements x 4 rungs x 3 seeds = 96 runs). Baselines exist (occupancy DP
# + BL in res_bf.txt). No traces needed.
cd /home/nizar/noxim3d-dnn || exit 1
R=results_ext/trace_runs; H=results_stage3/mapping_pilot/pool1000/hill
for k in 0300 0550 0750 0950; do
  for f in $H/tables_bf/*_k${k}.txt; do
    for s in 1 2 3; do echo "$f $s"; done
  done
done | xargs -P 14 -n 2 bash -c '
  f=$0; s=$1
  out=$(timeout 1800 ./noxim -size 16 16 -dimx 6 -dimy 6 -dimz 3 -buffer 16 \
        -routing oddevenbalanced -sel dp -dpcost wait -cinterval 648 \
        -warmup 1944 -sim 38536 -seed $s -traffic table $f 2>/dev/null)
  a=$(echo "$out"|grep -oP "average delay \(cycles\): \K[0-9.]+")
  p=$(echo "$out"|grep -oP "^% Delay p99 \(cycles\): \K[0-9.]+")
  t=$(echo "$out"|grep -oP "Throughput \(flits/cycle/IP\): \K[0-9.]+")
  echo "$(basename $f .txt) dpwait $s ${a:-NA} ${p:-NA} ${t:-NA}"
' > results_ext/trace_runs/res_bf_dpwait.txt
echo "WAIT PILOT DONE $(date)" >> results_ext/trace_runs/run.log
