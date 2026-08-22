#!/usr/bin/env bash
# Three configs at ls 0.028 with the full delay distribution (p50..p99.9).
#
#   1. relaxed  + noskip + dpcost occupancy
#   2. relaxed  + noskip + dpcost wait          <- wait untested on OEB so far
#   3. constrained + bufferlevel                <- BL's stronger turn model
#
# "relaxed"     = planar/vertical coexist ascending AND descending (current tree)
# "constrained" = ascending exclusivity restored (TRouter.cpp:1789, DPNode.cpp:1112)
#
# Both source files are backed up and restored by a trap on any exit.  The
# percentile print (TGlobalStats) is output-only and was verified to reproduce
# delay/throughput/maxdelay bit-identically against a stored row.
set -euo pipefail
cd "$(dirname "$0")"

SEEDS="${1:-0 2 5 10 15 20 25 30 35 40 45 50 55 60 65 70 75 80 85 90 95 100 105 110 115 120 125 130 135 140}"
JOBS="${2:-12}"
TABLE="traffics_dnn_6base/rn50_6b_ls0.028_diag_accint.txt"
OUT="results_6b_p99"
AVAIL='if (reservation_table.isAvailable(directions\[i\]))'

mkdir -p "$OUT/rows" "$OUT/logs"
cp TRouter.cpp .TRouter.p99.bak
cp DPNode.cpp  .DPNode.p99.bak
restore() {
    [ -f .TRouter.p99.bak ] && mv -f .TRouter.p99.bak TRouter.cpp
    [ -f .DPNode.p99.bak  ] && mv -f .DPNode.p99.bak  DPNode.cpp
    echo "  sources restored"
}
trap restore EXIT INT TERM

runner() {
    local arm="$1" seed="$2" bin="$3" sel dpc
    case "$arm" in
        noskip_occupancy) sel=dp;          dpc=occupancy ;;
        noskip_wait)      sel=dp;          dpc=wait      ;;
        bl_constrained)   sel=bufferlevel; dpc=occupancy ;;
    esac
    local log="$OUT/logs/${arm}_s${seed}.log"
    ./$bin -dimx 6 -dimy 6 -dimz 3 -buffer 16 -routing oddevenbalanced -sel "$sel" \
        -dpcost "$dpc" -cinterval 648 -size 16 16 -warmup 9720 -sim 124328 -samp 1 \
        -traffic table "$TABLE" -seed "$seed" > "$log" 2>&1
    g(){ grep "$1" "$log" | cut -d: -f2 | tr -d ' '; }
    echo "$arm,$seed,$(g 'Global average delay'),$(g 'Throughput (flits/cycle/IP)'),$(g 'Max delay'),$(g 'Delay p50'),$(g 'Delay p90'),$(g 'Delay p95'),$(g 'Delay p99 '),$(g 'Delay p99.9'),$(g 'Delay samples')" \
        > "$OUT/rows/${arm}_s${seed}.row"
}
export -f runner; export OUT TABLE

echo "=== phase 1: relaxed + noskip binary ==="
n=$(grep -c "$AVAIL" TRouter.cpp || true)
[ "$n" -eq 1 ] || { echo "ERROR: availability pattern matched $n times" >&2; exit 1; }
sed -i "s|$AVAIL|if (true) /* NOSKIP */|" TRouter.cpp
make clean >/dev/null 2>&1; make -j"$JOBS" MODULE=noxim_rx_noskip_p99 >/dev/null 2>&1
[ -x ./noxim_rx_noskip_p99 ] || { echo "ERROR: build 1 failed" >&2; exit 1; }
cp .TRouter.p99.bak TRouter.cpp        # undo the availability patch, keep relaxed turns

echo "=== phase 2: constrained (ascending exclusivity restored) ==="
grep -q '^    //else  *$' TRouter.cpp || echo "  note: TRouter ascending marker not on expected form"
sed -i '1789s|//else|else|' TRouter.cpp
sed -i '1112s|//else|else|' DPNode.cpp
grep -n "else" TRouter.cpp | sed -n '1p' >/dev/null
make clean >/dev/null 2>&1; make -j"$JOBS" MODULE=noxim_co_p99 >/dev/null 2>&1
[ -x ./noxim_co_p99 ] || { echo "ERROR: build 2 failed" >&2; exit 1; }
restore; trap - EXIT INT TERM
make clean >/dev/null 2>&1; make -j"$JOBS" >/dev/null 2>&1

echo "=== sanity: constrained BL seed 0 should match stored 0.028 row ==="
echo -n "  stored:  "; grep -h '^bufferlevel,' results_6b_oeb028/rows/bufferlevel_s0.row 2>/dev/null || echo "(none)"
echo -n "  new run: "
./noxim_co_p99 -dimx 6 -dimy 6 -dimz 3 -buffer 16 -routing oddevenbalanced -sel bufferlevel \
    -cinterval 648 -size 16 16 -warmup 9720 -sim 124328 -samp 1 -traffic table "$TABLE" -seed 0 2>&1 \
    | grep -E "Global average delay|Max delay" | tr '\n' ' '; echo

echo "=== running 3 arms x $(echo $SEEDS|wc -w) seeds ==="
{ for s in $SEEDS; do echo "noskip_occupancy $s noxim_rx_noskip_p99"; done
  for s in $SEEDS; do echo "noskip_wait $s noxim_rx_noskip_p99"; done
  for s in $SEEDS; do echo "bl_constrained $s noxim_co_p99"; done; } \
  | xargs -P "$JOBS" -n 3 bash -c 'runner "$@"' _
echo "done: $(ls $OUT/rows | wc -l) rows"
