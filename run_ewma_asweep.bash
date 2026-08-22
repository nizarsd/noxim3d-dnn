#!/usr/bin/env bash
# Alpha sweep at arm C's window (ci 162), adopted config
# (relaxed OEB + noskip + dpcost occupancy, ls 0.028).
#
# Grid matches the offline screen: alpha in {0, .5, .7, .9, .95, .98}.
# a0 (=arm B) and a90 (=arm C) already exist in results_6b_ewma/rows; this
# fills a50 a70 a95 a98.  Reuses ./noxim_ewma_p99 (noskip + percentiles) built
# by run_ewma_p99.bash; DPDECAY=<alpha*100>, unset/0 = bit-exact boxcar.
set -euo pipefail
cd "$(dirname "$0")"
SEEDS="${1:-0 2 5 10 15 20 25 30 35 40 45 50 55 60 65 70 75 80 85 90 95 100 105 110 115 120 125 130 135 140}"
JOBS="${2:-12}"
ALPHAS="${3:-50 70 95 98}"
TABLE="traffics_dnn_6base/rn50_6b_ls0.028_diag_accint.txt"
OUT="results_6b_ewma"; BIN="noxim_ewma_p99"; CI=162
[ -x "./$BIN" ] || { echo "ERROR: ./$BIN missing - run run_ewma_p99.bash first" >&2; exit 1; }
mkdir -p "$OUT/rows" "$OUT/logs"
run1() {
    local a="$1" seed="$2"
    local log="$OUT/logs/ci162_a${a}_s${seed}.log"
    DPDECAY="$a" ./$BIN -dimx 6 -dimy 6 -dimz 3 -buffer 16 -routing oddevenbalanced \
        -sel dp -dpcost occupancy -cinterval 162 -size 16 16 \
        -warmup 9720 -sim 124328 -samp 1 -traffic table "$TABLE" -seed "$seed" > "$log" 2>&1
    g(){ grep "$1" "$log" | cut -d: -f2 | tr -d ' '; }
    echo "ci162_a${a},$seed,$(g 'Global average delay'),$(g 'Throughput (flits/cycle/IP)'),$(g 'Max delay'),$(g 'Delay p50'),$(g 'Delay p90'),$(g 'Delay p95'),$(g 'Delay p99 '),$(g 'Delay p99.9'),$(g 'Delay samples')" \
        > "$OUT/rows/ci162_a${a}_s${seed}.row"
}
export -f run1; export OUT TABLE BIN
echo "=== ci162 alpha sweep: {$ALPHAS} x $(echo $SEEDS|wc -w) seeds ==="
{ for a in $ALPHAS; do for s in $SEEDS; do echo "$a $s"; done; done; } \
  | xargs -P "$JOBS" -n 2 bash -c 'run1 "$@"' _
echo "done: ci162 rows now = $(ls $OUT/rows/ci162_*.row | wc -l)"
