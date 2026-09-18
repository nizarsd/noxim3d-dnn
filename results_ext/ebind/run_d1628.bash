#!/bin/bash
cd /home/nizar/noxim3d-dnn || exit 1
K=results_ext/ebind
exec >> $K/run_d1628.log 2>&1
echo "=== d1628 runs start $(date)"
run1(){
  local SEL="-sel bufferlevel"; [ "$2" = dp ] && SEL="-sel dp -dpcost occupancy -cinterval 648"
  out=$(timeout 2400 ./noxim -size 16 16 -dimx 6 -dimy 6 -dimz 3 -buffer 16 \
        -routing oddevenbalanced $SEL -warmup 1944 -sim 58097 -seed $3 -traffic table $1 2>/dev/null)
  a=$(echo "$out"|grep -oP "average delay \(cycles\): \K[0-9.]+")
  p=$(echo "$out"|grep -oP "^% Delay p99 \(cycles\): \K[0-9.]+")
  echo "$(basename $1 .txt) $2 $3 ${a:-NA} ${p:-NA}"
}
export -f run1
ls $K/tables/d1628_*.txt | while read f; do
  for pol in bl dp; do for s in 1 2 3; do echo "$f $pol $s"; done; done
done | xargs -P 14 -n 3 bash -c 'run1 "$@"' _ >> $K/res_ebind.txt
echo "=== d1628 runs done $(date)"
echo "D1628 DONE $(date)"
