#!/usr/bin/env bash
# XY-diagonal placement vs the current placement, at ls=0.022.
#
# Only the NEW mapping runs here (20 runs).  The baseline is the first 10 seeds
# already in results_block_ls022_n30 -- same ls, same SIM, same -samp 1, so the
# two are directly comparable and the current mapping costs nothing to re-run.
#
# ls=0.022 is the ONLY point where that holds: results_block_7x7x3 (ls 0.012-
# 0.032) ran at SIM=207674 with -samp 10, a different measurement window.
#
# The table is a node RELABELLING of the exact table those baseline runs used
# (remap_table_diagonal.py) -- identical traffic graph, rates and phase windows,
# so placement is the single variable.
set -euo pipefail
cd "$(dirname "$0")"

BIN=./noxim
TBL=results_diag_ls022/tables/dnn_diag_ls0.022.txt
OUTDIR=results_diag_ls022
# Overridable so the arm can be extended without re-running what exists.
SEEDS=${SEEDS:-"2 6 10 14 18 22 26 30 34 38"}
JOBS=8

[[ -x $BIN ]] || { echo "no noxim binary"; exit 1; }
[[ -f $TBL ]] || { echo "no table at $TBL -- run remap_table_diagonal.py"; exit 1; }
mkdir -p "$OUTDIR/logs" "$OUTDIR/rows"
# Clear ONLY the seeds about to be re-run -- a blanket delete would discard a
# completed arm (learned the hard way on the 6x6x3 run).
for s in $SEEDS; do
    rm -f "$OUTDIR/rows"/*_seed_"$s".row
done

run_one() {
    local sel="$1" seed="$2"
    local tag="diag_sel_${sel}_ls_0.022_seed_${seed}"
    local log="$OUTDIR/logs/${tag}.log"
    if ! "$BIN" -dimx 7 -dimy 7 -dimz 3 -buffer 16 \
        -routing oddevenbalanced -sel "$sel" -size 16 16 \
        -cinterval 4998 -warmup 14994 -sim 206674 -samp 1 \
        -traffic table "$TBL" -seed "$seed" > "$log" 2>&1
    then
        echo "16,$sel,0.022,$seed,ERROR,ERROR,ERROR,ERROR,ERROR,$log" \
            > "$OUTDIR/rows/${tag}.row"; echo "  FAILED: $tag"; return 0
    fi
    local d t r e
    d=$(grep -i 'average delay' "$log" | tail -1 | grep -Eo '[0-9.]+([eE][-+]?[0-9]+)?$')
    t=$(grep -i 'Throughput (flits/cycle/IP)' "$log" | tail -1 | grep -Eo '[0-9.]+([eE][-+]?[0-9]+)?$')
    r=$(grep -i 'received packets' "$log" | tail -1 | grep -Eo '[0-9]+$')
    e=$(grep -i 'Total energy' "$log" | tail -1 | grep -Eo '[0-9.]+([eE][-+]?[0-9]+)?$')
    echo "16,$sel,0.022,$seed,${d:-NA},${t:-NA},${r:-NA},NA,${e:-NA},$log" \
        > "$OUTDIR/rows/${tag}.row"
    echo "  done: $tag"
}
export -f run_one; export BIN TBL OUTDIR

{ for seed in $SEEDS; do for sel in dp bufferlevel; do echo "$sel $seed"; done; done; } \
    | xargs -P "$JOBS" -n 2 bash -c 'run_one "$@"' _

{ echo "buffer,selection,load_scale,seed,avg_delay,avg_throughput,total_received,total_sent,total_energy,raw_log"
  cat "$OUTDIR/rows/"*.row | sort -t, -k2,2 -k4,4n; } > "$OUTDIR/summary.csv"
echo "Done -> $OUTDIR/summary.csv"
