#!/usr/bin/env bash
# 7x7x3 DP-occ-noskip vs BL on the interior (diag_accint) placement, to compare
# the DP-vs-BL %gap against 6x6x3. Locked substrate: relaxed OEB + noskip + occupancy.
# Binary noxim_ewma_p99 (noskip + percentiles, DPDECAY off = no EWMA). New files only;
# 6x6x3 assets untouched.
set -euo pipefail
cd "$(dirname "$0")"
BIN=noxim_ewma_p99
OUT=results_7b_routing_check
SEEDS="0 2 5 10 15 20 25 30 35 40"
JOBS=12
mkdir -p "$OUT/rows" "$OUT/logs"
run1(){
  local ls="$1" sel="$2" seed="$3"; local tag="ls${ls}_${sel}"
  local T="traffics_dnn_7base/rn50_7b_ls${ls}_diag_accint.txt"
  local log="$OUT/logs/${tag}_s${seed}.log"
  ./noxim_ewma_p99 -dimx 7 -dimy 7 -dimz 3 -buffer 16 -routing oddevenbalanced -sel "$sel" -dpcost occupancy \
     -cinterval 1029 -size 16 16 -warmup 15435 -sim 131043 -samp 1 -traffic table "$T" -seed "$seed" > "$log" 2>&1
  g(){ grep "$1" "$log" | cut -d: -f2 | tr -d ' '; }
  echo "${tag},${seed},$(g 'Global average delay'),$(g 'Throughput (flits/cycle/IP)'),$(g 'Max delay'),$(g 'Delay p50'),$(g 'Delay p90'),$(g 'Delay p95'),$(g 'Delay p99 '),$(g 'Delay p99.9'),$(g 'Delay samples')" \
     > "$OUT/rows/${tag}_s${seed}.row"
}
export -f run1; export OUT
{ for ls in 0.028 0.022; do for sel in dp bufferlevel; do for s in $SEEDS; do echo "$ls $sel $s"; done; done; done; } \
  | xargs -P "$JOBS" -n 3 bash -c 'run1 "$@"' _
echo "done: $(ls $OUT/rows|wc -l)/40 rows"
