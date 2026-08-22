#!/usr/bin/env bash
# Arm D: EWMA at PRODUCTION window length -- ci 648, alpha 0.7 (tau ~2160 cycles).
#
# Why this arm exists.  Arms B/C in run_ewma_p99.bash change ci 648 -> 162 AND add
# EWMA, so "C vs A" confounds two variables.  D holds ci at 648 and turns on EWMA
# alone, giving a single-variable test of the mechanism against the stored
# production arm A (results_6b_p99/rows/noskip_occupancy_s*).  The offline screen
# put ci 648 / alpha 0.7 at R^2 0.212 -- statistically level with the ci 162 /
# alpha 0.9 optimum (0.214), because both land at tau ~1600-2200 cycles.
#
# Reuses ./noxim_ewma_p99 built by run_ewma_p99.bash (noskip + percentiles).
set -euo pipefail
cd "$(dirname "$0")"
SEEDS="${1:-0 2 5 10 15 20 25 30 35 40 45 50 55 60 65 70 75 80 85 90 95 100 105 110 115 120 125 130 135 140}"
JOBS="${2:-12}"
TABLE="traffics_dnn_6base/rn50_6b_ls0.028_diag_accint.txt"
OUT="results_6b_ewma"
BIN="noxim_ewma_p99"
[ -x "./$BIN" ] || { echo "ERROR: ./$BIN missing - run run_ewma_p99.bash first" >&2; exit 1; }
mkdir -p "$OUT/rows" "$OUT/logs"
run1() {
    local ci="$1" a="$2" seed="$3"
    local log="$OUT/logs/ci${ci}_a${a}_s${seed}.log"
    DPDECAY="$a" ./$BIN -dimx 6 -dimy 6 -dimz 3 -buffer 16 -routing oddevenbalanced \
        -sel dp -dpcost occupancy -cinterval "$ci" -size 16 16 \
        -warmup 9720 -sim 124328 -samp 1 -traffic table "$TABLE" -seed "$seed" > "$log" 2>&1
    g(){ grep "$1" "$log" | cut -d: -f2 | tr -d ' '; }
    echo "ci${ci}_a${a},$seed,$(g 'Global average delay'),$(g 'Throughput (flits/cycle/IP)'),$(g 'Max delay'),$(g 'Delay p50'),$(g 'Delay p90'),$(g 'Delay p95'),$(g 'Delay p99 '),$(g 'Delay p99.9'),$(g 'Delay samples')" \
        > "$OUT/rows/ci${ci}_a${a}_s${seed}.row"
}
export -f run1; export OUT TABLE BIN
echo "=== arm D: ci 648 alpha 70, $(echo $SEEDS|wc -w) seeds ==="
for s in $SEEDS; do echo "648 70 $s"; done | xargs -P "$JOBS" -n 3 bash -c 'run1 "$@"' _
echo "done: $(ls $OUT/rows/ci648_a70_s*.row 2>/dev/null | wc -l) rows"
