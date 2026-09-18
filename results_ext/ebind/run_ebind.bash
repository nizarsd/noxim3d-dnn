#!/bin/bash
# Ladders for the two new E x PL grids: BL and DP, 3 seeds, all rungs.
cd /home/nizar/noxim3d-dnn || exit 1
K=results_ext/ebind
exec >> $K/run.log 2>&1
until grep -q "GRIDS DONE" $K/build.log 2>/dev/null; do sleep 20; done
echo "=== ebind runs start $(date)"
declare -A SIM=( [d1616]=58097 [r824]=38536 )
declare -p SIM > $K/.assoc
run1(){ # tab pol seed sim
  local SEL="-sel bufferlevel"; [ "$2" = dp ] && SEL="-sel dp -dpcost occupancy -cinterval 648"
  out=$(timeout 2400 ./noxim -size 16 16 -dimx 6 -dimy 6 -dimz 3 -buffer 16 \
        -routing oddevenbalanced $SEL -warmup 1944 -sim $4 -seed $3 -traffic table $1 2>/dev/null)
  a=$(echo "$out"|grep -oP "average delay \(cycles\): \K[0-9.]+")
  p=$(echo "$out"|grep -oP "^% Delay p99 \(cycles\): \K[0-9.]+")
  echo "$(basename $1 .txt) $2 $3 ${a:-NA} ${p:-NA}"
}
export -f run1
: > $K/res_ebind.txt
ls $K/tables/*.txt | while read f; do
  SET=$(basename $f | cut -d_ -f1)
  for pol in bl dp; do for s in 1 2 3; do echo "$f $pol $s ${SIM[$SET]}"; done; done
done | xargs -P 14 -n 4 bash -c 'run1 "$@"' _ >> $K/res_ebind.txt
echo "=== ebind runs done $(date)"; wc -l $K/res_ebind.txt; grep -c NA $K/res_ebind.txt
echo "EBIND DONE $(date)"
