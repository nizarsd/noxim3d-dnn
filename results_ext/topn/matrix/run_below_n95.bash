#!/bin/bash
# N@95 on every in-band below-floor cell, so T1 can report 90/95 in both regimes.
cd /home/nizar/noxim3d-dnn || exit 1
K=results_ext/topn/matrix; I6=results_ext/topn/int6
exec >> $K/campaign_bn95.log 2>&1
echo "=== below-floor N@95 start $(date)"
declare -A SIM=( [r1628]=38536 [v1644]=115606 [esxd]=58097 )
declare -A N95=( [r1628]=27    [v1644]=38     [esxd]=45 )
declare -p SIM N95 > $K/.assocn95
run1(){ # tab sinks sim N
  local ci=$((6*$4))
  out=$(timeout 2400 ./noxim -size 16 16 -dimx 6 -dimy 6 -dimz 3 -buffer 16 \
        -routing oddevenbalanced -sel dp -dpcost occupancy -cinterval $ci \
        -dptopn $4 $2 -warmup 1944 -sim $3 -seed $5 -traffic table $1 2>/dev/null)
  a=$(echo "$out"|grep -oP "average delay \(cycles\): \K[0-9.]+")
  p=$(echo "$out"|grep -oP "^% Delay p99 \(cycles\): \K[0-9.]+")
  echo "$(basename $1 .txt) hyb95 $5 ${a:-NA} ${p:-NA}"
}
export -f run1; export K
: > $K/res_below_n95.txt
{
  # int arm (c16 knee runs) — tables and sinks live under int6
  while read tag k dep; do
    SET=${tag%%_*}
    echo "$I6/tables/${tag}_k${k}.txt $I6/sinks_${tag} ${SIM[$SET]} ${N95[$SET]}"
  done < $I6/run_spec_c16.txt
  # bE / b2 / bN arms — tables and sinks under matrix
  for sp in run_spec_bE.txt run_spec_b2.txt run_spec_minE.txt; do
    [ -f $K/$sp ] || continue
    while read tag k dep flag; do
      [ "$flag" = OK ] || continue
      case "$tag" in *_bE*|*_b2*|*_bN*) ;; *) continue;; esac
      SET=${tag%%_*}
      echo "$K/tables/${tag}_k${k}.txt $K/sinks_${tag} ${SIM[$SET]} ${N95[$SET]}"
    done < $K/$sp
  done
} | while read tab sinks sim n; do
     for s in 1 2 3 4 5 6 7 8; do echo "$tab $sinks $sim $n $s"; done
   done | xargs -P 14 -n 5 bash -c 'run1 "$@"' _ >> $K/res_below_n95.txt
echo "=== below-floor N@95 done $(date)"; wc -l $K/res_below_n95.txt; grep -c NA $K/res_below_n95.txt
echo "BN95 DONE $(date)"
