#!/usr/bin/env bash
# Curve-shape probe for the XY-DIAGONAL placement: ls=0.016 and 0.028, n=3.
#
# WHY.  The diagonal walk costs +49% mean hops, so it saturates at a lower load
# scale than the current placement.  If diagonal is slower at ls=0.022 that is
# ambiguous between "worse mapping" and "further past its own knee".  Three
# points locate the diagonal's own knee well enough to tell which.
#
# Diagonal only -- the current mapping's knee (0.022-0.025) is already known
# from results_block_7x7x3, and the 1000-cycle SIM difference is 0.5%.
#
# Waits for any running sweep to clear before starting, so it does not contend
# for the 8 cores with run_diag_ls022.bash.
set -euo pipefail
cd "$(dirname "$0")"

BIN=./noxim
OUTDIR=results_diag_ls022
SEEDS="2 6 10"
SCALES="0.016 0.028"
JOBS=8

while pgrep -x noxim >/dev/null; do sleep 20; done

mkdir -p "$OUTDIR/logs" "$OUTDIR/probe_rows"
find "$OUTDIR/probe_rows" -name '*.row' -delete 2>/dev/null || true

run_one() {
    local sel="$1" scale="$2" seed="$3"
    local tbl="$OUTDIR/tables/dnn_diag_ls${scale}.txt"
    local tag="diag_sel_${sel}_ls_${scale}_seed_${seed}"
    local log="$OUTDIR/logs/${tag}.log"
    if ! "$BIN" -dimx 7 -dimy 7 -dimz 3 -buffer 16 \
        -routing oddevenbalanced -sel "$sel" -size 16 16 \
        -cinterval 4998 -warmup 14994 -sim 206674 -samp 1 \
        -traffic table "$tbl" -seed "$seed" > "$log" 2>&1
    then
        echo "16,$sel,$scale,$seed,ERROR,ERROR,ERROR,ERROR,ERROR,$log" \
            > "$OUTDIR/probe_rows/${tag}.row"; echo "  FAILED: $tag"; return 0
    fi
    local d t r e
    d=$(grep -i 'average delay' "$log" | tail -1 | grep -Eo '[0-9.]+([eE][-+]?[0-9]+)?$')
    t=$(grep -i 'Throughput (flits/cycle/IP)' "$log" | tail -1 | grep -Eo '[0-9.]+([eE][-+]?[0-9]+)?$')
    r=$(grep -i 'received packets' "$log" | tail -1 | grep -Eo '[0-9]+$')
    e=$(grep -i 'Total energy' "$log" | tail -1 | grep -Eo '[0-9.]+([eE][-+]?[0-9]+)?$')
    echo "16,$sel,$scale,$seed,${d:-NA},${t:-NA},${r:-NA},NA,${e:-NA},$log" \
        > "$OUTDIR/probe_rows/${tag}.row"
    echo "  done: $tag"
}
export -f run_one; export BIN OUTDIR

{ for scale in $SCALES; do for seed in $SEEDS; do for sel in dp bufferlevel; do
    echo "$sel $scale $seed"; done; done; done; } \
    | xargs -P "$JOBS" -n 3 bash -c 'run_one "$@"' _

{ echo "buffer,selection,load_scale,seed,avg_delay,avg_throughput,total_received,total_sent,total_energy,raw_log"
  cat "$OUTDIR/probe_rows/"*.row | sort -t, -k3,3n -k2,2 -k4,4n; } > "$OUTDIR/probe.csv"
echo "Done -> $OUTDIR/probe.csv"
