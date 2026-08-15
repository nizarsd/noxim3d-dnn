#!/usr/bin/env bash
# Separate HOP COUNT from PATH DIVERSITY as the cause of DP's degradation.
#
# The current and XY-diagonal placements move both at once, so the n=30 result
# (DP +16.65% slower under diagonal, p=0.0023) cannot be attributed. These two
# cells hold one variable fixed while moving the other:
#
#              hops 3.33          hops 4.96
#   div 25.5%  current (n=30)     CELL A   <- if DP degrades here, HOPS
#   div 67.2%  CELL B             diagonal (n=30)
#                ^ if DP degrades here, DIVERSITY
#
# Tables are node relabellings of the exact ls=0.022 table the n=30 runs used
# (search_placement.py + verified pir/window invariance), so the traffic graph,
# rates and phase windows are identical across all four cells.
set -euo pipefail
cd "$(dirname "$0")"
BIN=./noxim; OUTDIR=results_hopdiv
SEEDS=${SEEDS:-"2 6 10 14 18 22 26 30 34 38"}
CELLS=${CELLS:-"A B"}
mkdir -p "$OUTDIR/logs" "$OUTDIR/rows"
for c in $CELLS; do for s in $SEEDS; do rm -f "$OUTDIR/rows"/cell${c}_*_seed${s}.row; done; done
run_one() {
    local cell="$1" sel="$2" seed="$3"
    local tag="cell${cell}_${sel}_seed${seed}"
    local log="$OUTDIR/logs/${tag}.log"
    ./noxim -dimx 7 -dimy 7 -dimz 3 -buffer 16 -routing oddevenbalanced -sel "$sel" \
        -size 16 16 -cinterval 4998 -warmup 14994 -sim 206674 -samp 1 \
        -traffic table "$OUTDIR/tables/dnn_cell${cell}_ls0.022.txt" -seed "$seed" \
        > "$log" 2>&1 || { echo "$cell,$sel,$seed,ERROR,ERROR,ERROR" > "$OUTDIR/rows/${tag}.row"; return 0; }
    d=$(grep 'Global average delay' "$log" | cut -d: -f2 | tr -d ' ')
    t=$(grep 'Throughput (flits/cycle/IP)' "$log" | cut -d: -f2 | tr -d ' ')
    m=$(grep 'Max delay' "$log" | cut -d: -f2 | tr -d ' ')
    echo "$cell,$sel,$seed,$d,$t,$m" > "$OUTDIR/rows/${tag}.row"
    echo "  done $tag"
}
export -f run_one; export BIN OUTDIR
{ for c in $CELLS; do for s in $SEEDS; do for sel in dp bufferlevel; do
    echo "$c $sel $s"; done; done; done; } | xargs -P 8 -n 3 bash -c 'run_one "$@"' _
echo DONE
