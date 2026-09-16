#!/bin/bash
# Traced below-floor rerun: BARRIERTRACE (per-packet) + DPTRACE (hot link) on
# every knee-window cell of the four below-floor sets, both policies, 3 seeds.
# stderr (B, and T, lines) gzipped per run; stdout summary appended per set.
cd /home/nizar/noxim3d-dnn || exit 1
R=results_ext/trace_runs; H=results_stage3/mapping_pilot/pool1000/hill
J=${JOBS:-14}
declare -A SIM=( [bf]=38536 [f1]=38536 [f2]=115606 [esxd]=58097 )
declare -A KS=( [bf]="0300 0550 0750 0950" [f1]="0300 0550 0750 0950 1150 1400 1700" \
                [f2]="0150 0250 0350 0450 0550" [esxd]="0470 0550 0650" )
for SET in bf f1 f2 esxd; do
  mkdir -p $R/traces_$SET
  : > $R/joblist_$SET
  while IFS=, read -r tag u v dir rest; do
    [ "$tag" = tag ] && continue
    for k in ${KS[$SET]}; do
      tab=$H/tables_$SET/${tag}_k${k}.txt
      [ -f "$tab" ] || { echo "MISSING $tab" >> $R/missing.log; continue; }
      for pol in bufferlevel dp; do for s in 1 2 3; do
        echo "$SET $tab $tag $k $pol $s $u:$dir ${SIM[$SET]}"
      done; done
    done
  done < $R/hotlinks_$SET.csv >> $R/joblist_$SET
done
cat $R/joblist_bf $R/joblist_f1 $R/joblist_f2 $R/joblist_esxd | \
xargs -P $J -n 8 bash -c '
  SET=$0; tab=$1; tag=$2; k=$3; pol=$4; s=$5; trc=$6; sim=$7
  R=results_ext/trace_runs
  gz=$R/traces_$SET/${tag}_k${k}_${pol}_s${s}.gz
  [ -s "$gz" ] && exit 0                              # resumable
  if [ "$pol" = dp ]; then SEL="-sel dp -dpcost occupancy -cinterval 648"; else SEL="-sel bufferlevel"; fi
  out=$(BARRIERTRACE=1 DPTRACE=$trc timeout 3600 ./noxim -size 16 16 -dimx 6 -dimy 6 -dimz 3 \
        -buffer 16 -routing oddevenbalanced $SEL -warmup 1944 -sim $sim -seed $s \
        -traffic table $tab 2> >(gzip > "$gz"))
  a=$(echo "$out"|grep -oP "average delay \(cycles\): \K[0-9.]+")
  p=$(echo "$out"|grep -oP "^% Delay p99 \(cycles\): \K[0-9.]+")
  t=$(echo "$out"|grep -oP "Throughput \(flits/cycle/IP\): \K[0-9.]+")
  echo "${tag}_k${k} $pol $s ${a:-NA} ${p:-NA} ${t:-NA}" >> $R/res_${SET}.txt
'
echo "DONE $(date)" >> results_ext/trace_runs/run.log
