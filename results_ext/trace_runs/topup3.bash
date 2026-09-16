#!/bin/bash
# esxd-only rerun of the top-up (k1000, k1100) with the env fix.
cd /home/nizar/noxim3d-dnn || exit 1
R=results_ext/trace_runs; J=${JOBS:-14}
source /dev/stdin <<< "$(sed -n '/^run_one ()/,/^}/p' $R/topup2.bash)"
export -f run_one
declare -A TRC
while IFS=, read -r tag u v dir rest; do [ "$tag" = tag ] || TRC[$tag]="$u:$dir"; done < $R/hotlinks_esxd.csv
for k in 1000 1100; do
  for f in $R/tables_topup_esxd/*_k${k}.txt; do
    tag=$(basename $f _k${k}.txt)
    for pol in bufferlevel dp; do for s in 1 2 3; do
      echo "esxd $f $pol $s 58097 $R/traces_topup_esxd/${tag}_k${k}_${pol}_s${s}.gz ${TRC[$tag]}"
    done; done
  done
done | xargs -P $J -n 7 bash -c '
  [ -s "$5" ] && exit 0
  run_one "$1" "$2" "$3" "$4" "$5" "$6" >> results_ext/trace_runs/res_topup_$0.txt'
echo "TOPUP3 DONE $(date)" >> $R/run.log
