#!/usr/bin/env bash
# Is plain 3D odd-even (OE) a better substrate for DP than odd-even-balanced?
#
# Cheapest honest test: locate OE's OWN knee first.  Comparing two routings at a
# fixed load point is the FINDINGS.md trap -- the modified2 study's headline
# "+53%" was BL degrading faster than DP because the knees were in different
# places.  n=1 is deliberate: a knee needs load points, not seeds.
#
# NO CODE CHANGE NEEDED.  -routing oddeven -> ROUTING_ODD_EVEN -> routingOddEven3D
# at Z>1 (TRouter.cpp:409), and DP's legality mirror dispatches the same case to
# can_turnOddEven (DPNode.cpp:263), so DP's cost field stays legal.
#
# Tables are reused from results_block_7x7x3/tables (0.022 from the n=30 set):
# verified identical placement and CYCLES_PER_MAC=2e-4 to the OEB runs, so the
# two routings are compared on exactly the same traffic.
# Timing matches the n=30 OEB set: SIM=206674 WARMUP=14994 CINTERVAL=4998.
set -euo pipefail
cd "$(dirname "$0")"
OUTDIR=results_oe_knee
SCALES=${SCALES:-"0.012 0.016 0.020 0.022 0.025 0.028 0.032"}
SEEDS=${SEEDS:-"2"}
mkdir -p "$OUTDIR/logs" "$OUTDIR/rows"
run_one() {
    local scale="$1" sel="$2" seed="$3"
    local tbl="results_block_7x7x3/tables/dnn_ls${scale}.txt"
    [ "$scale" = "0.022" ] && tbl="results_block_ls022_n30/tables/dnn_ls0.022.txt"
    local tag="oe_ls${scale}_${sel}_seed${seed}"
    local log="$OUTDIR/logs/${tag}.log"
    ./noxim -dimx 7 -dimy 7 -dimz 3 -buffer 16 -routing oddeven -sel "$sel" \
        -size 16 16 -cinterval 4998 -warmup 14994 -sim 206674 -samp 1 \
        -traffic table "$tbl" -seed "$seed" > "$log" 2>&1 \
        || { echo "$scale,$sel,$seed,ERROR,ERROR,ERROR" > "$OUTDIR/rows/${tag}.row"; echo "  FAILED $tag"; return 0; }
    d=$(grep 'Global average delay' "$log" | cut -d: -f2 | tr -d ' ')
    t=$(grep 'Throughput (flits/cycle/IP)' "$log" | cut -d: -f2 | tr -d ' ')
    m=$(grep 'Max delay' "$log" | cut -d: -f2 | tr -d ' ')
    echo "$scale,$sel,$seed,${d:-NA},${t:-NA},${m:-NA}" > "$OUTDIR/rows/${tag}.row"
    echo "  done $tag"
}
export -f run_one; export OUTDIR
{ for s in $SCALES; do for sd in $SEEDS; do for sel in dp bufferlevel; do
    echo "$s $sel $sd"; done; done; done; } | xargs -P 8 -n 3 bash -c 'run_one "$@"' _
echo DONE
