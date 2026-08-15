#!/usr/bin/env bash
# 6x6x3 placement comparison: current vs XY-diagonal, at the knee (ls=0.013).
#
# Both placements run here (40 runs) -- unlike the 7x7x3 case there is no
# existing 6x6x3 baseline at this ls, SIM and -samp, so the current arm cannot
# be reused from results_dnn_scale_sweep (that ran SIM=259200, -samp 10, n=3).
#
# ls=0.013 is the interpolated knee from results_knee_6x6x3: BL delay 51.9 at
# 0.012 and 142.5 at 0.014, the steepest relative rise on the grid (2.75x).
# That is the same curve position 7x7x3's ls=0.022 occupied.
#
# The diagonal table is a node RELABELLING of the current one, so traffic graph,
# rates and phase windows are identical and placement is the single variable.
# Verified: packets-with-routing-choice 45.3% -> 56.9%, weighted hops 3.76 ->
# 4.10 (+9%; the 7x7x3 diagonal cost +49%, so 6x6x3 is a much cheaper change).
#
# Timing, 6x6x3: DP_CYCLE 3240, WARMUP 9720, SIM 133955 = 5 exact block passes.
#
# NOTE the CSV's total_received column holds received FLITS, matching what
# noximrun_dnn_traffic.bash's regex actually captures (its pattern ends on the
# last line matching /received/, which is the flits line, not packets).
set -euo pipefail
cd "$(dirname "$0")"

BIN=./noxim
OUTDIR=results_diag_6x6x3
# Overridable so a partial run can be completed without discarding what exists.
SEEDS=${SEEDS:-"2 6 10 14 18 22 26 30 34 38"}
PLACES=${PLACES:-"cur diag"}
JOBS=8

[[ -x $BIN ]] || { echo "no noxim binary"; exit 1; }
mkdir -p "$OUTDIR/logs" "$OUTDIR/rows"
# Only clear rows for the placements being (re)run -- never blanket-delete, or
# a completed arm is lost.
for p in $PLACES; do
    find "$OUTDIR/rows" -name "${p}_*.row" -delete 2>/dev/null || true
done

run_one() {
    local place="$1" sel="$2" seed="$3"
    local tbl="$OUTDIR/tables/dnn_ls0.013.txt"
    [[ $place == diag ]] && tbl="$OUTDIR/tables/dnn_diag_ls0.013.txt"
    local tag="${place}_sel_${sel}_seed_${seed}"
    local log="$OUTDIR/logs/${tag}.log"
    if ! "$BIN" -dimx 6 -dimy 6 -dimz 3 -buffer 16 \
        -routing oddevenbalanced -sel "$sel" -size 16 16 \
        -cinterval 3240 -warmup 9720 -sim 133955 -samp 1 \
        -traffic table "$tbl" -seed "$seed" > "$log" 2>&1
    then
        echo "$place,$sel,0.013,$seed,ERROR,ERROR,ERROR,ERROR,$log" \
            > "$OUTDIR/rows/${tag}.row"; echo "  FAILED: $tag"; return 0
    fi
    local d t f m
    d=$(grep 'Global average delay'          "$log" | tail -1 | cut -d: -f2 | tr -d ' ')
    t=$(grep 'Throughput (flits/cycle/IP)'   "$log" | tail -1 | cut -d: -f2 | tr -d ' ')
    f=$(grep 'Total received flits'          "$log" | tail -1 | cut -d: -f2 | tr -d ' ')
    m=$(grep 'Max delay'                     "$log" | tail -1 | cut -d: -f2 | tr -d ' ')
    echo "$place,$sel,0.013,$seed,${d:-NA},${t:-NA},${f:-NA},${m:-NA},$log" \
        > "$OUTDIR/rows/${tag}.row"
    echo "  done: $tag"
}
export -f run_one; export BIN OUTDIR

{ for place in $PLACES; do for seed in $SEEDS; do for sel in dp bufferlevel; do
    echo "$place $sel $seed"; done; done; done; } \
    | xargs -P "$JOBS" -n 3 bash -c 'run_one "$@"' _

{ echo "placement,selection,load_scale,seed,avg_delay,thru_per_ip,recv_flits,max_delay,raw_log"
  cat "$OUTDIR/rows/"*.row | sort -t, -k1,1 -k2,2 -k4,4n; } > "$OUTDIR/summary.csv"
echo "Done -> $OUTDIR/summary.csv"
