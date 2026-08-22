#!/usr/bin/env bash
# EWMA screen, live: does carrying window history into the DP congestion field
# move p99 delay on the adopted configuration?
#
# Adopted substrate for all arms: relaxed OEB (planar/vertical coexist both
# branches) + noskip (availability check bypassed) + -dpcost occupancy, ls 0.028.
#
# Three-way, with attribution:
#   A  ci 648, alpha 0     <- current production, ALREADY RUN (results_6b_p99)
#   B  ci 162, alpha 0     <- isolates the window-length change alone
#   C  ci 162, alpha 0.9   <- isolates EWMA on top of B   (offline screen optimum,
#                             R^2 0.136 -> 0.214, tau ~1620 cycles)
# Only B and C are run here: 2 arms x 30 seeds = 60 runs.
#
# alpha is passed as env DPDECAY=<alpha*100>.  Unset/0 is a provable no-op:
# (inst_q8 >> 8) == (100*load)/(samples*maxb) exactly, so arm B at ci 648 must
# reproduce the stored production row bit-for-bit.  That is the correctness gate.
set -euo pipefail
cd "$(dirname "$0")"

SEEDS="${1:-0 2 5 10 15 20 25 30 35 40 45 50 55 60 65 70 75 80 85 90 95 100 105 110 115 120 125 130 135 140}"
JOBS="${2:-12}"
TABLE="traffics_dnn_6base/rn50_6b_ls0.028_diag_accint.txt"
OUT="results_6b_ewma"
BIN="noxim_ewma_p99"
AVAIL='if (reservation_table.isAvailable(directions\[i\]))'

mkdir -p "$OUT/rows" "$OUT/logs"

# ---- build the noskip binary (sources restored on any exit) -----------------
cp TRouter.cpp .TRouter.ewma.bak
restore() { [ -f .TRouter.ewma.bak ] && mv -f .TRouter.ewma.bak TRouter.cpp && echo "  TRouter.cpp restored"; }
trap restore EXIT INT TERM

n=$(grep -c "$AVAIL" TRouter.cpp || true)
[ "$n" -eq 1 ] || { echo "ERROR: availability pattern matched $n times" >&2; exit 1; }
sed -i "s|$AVAIL|if (true) /* NOSKIP */|" TRouter.cpp
make clean >/dev/null 2>&1
make -j"$JOBS" MODULE="$BIN" >/dev/null 2>&1
[ -x "./$BIN" ] || { echo "ERROR: build failed" >&2; exit 1; }
restore; trap - EXIT INT TERM
make clean >/dev/null 2>&1; make -j"$JOBS" >/dev/null 2>&1   # leave ./noxim as the pristine tree

run1() {   # ci alpha seed  -> one row
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

# ---- GATE: alpha=0 at ci 648 must reproduce the stored production row --------
echo "=== gate: DPDECAY=0, ci 648, seed 0 vs stored results_6b_p99 row ==="
run1 648 0 0
STORED=$(cat results_6b_p99/rows/noskip_occupancy_s0.row)
NEW=$(sed 's/^ci648_a0,/noskip_occupancy,/' "$OUT/rows/ci648_a0_s0.row")
echo "  stored: $STORED"
echo "  new   : $NEW"
if [ "$STORED" = "$NEW" ]; then
    echo "  PASS - EWMA code is a bit-exact no-op at alpha=0"
else
    echo "  FAIL - alpha=0 is NOT a no-op; aborting" >&2; exit 1
fi

# ---- sanity: alpha=0.9 must actually change something, and stay stable ------
echo "=== sanity: ci 162 alpha 0 vs alpha 90, seed 0 ==="
run1 162 0 0; run1 162 90 0
cat "$OUT/rows/ci162_a0_s0.row" "$OUT/rows/ci162_a90_s0.row" | sed 's/^/  /'

echo "=== running 2 arms x $(echo $SEEDS|wc -w) seeds ==="
{ for s in $SEEDS; do echo "162 0  $s"; done
  for s in $SEEDS; do echo "162 90 $s"; done; } \
  | xargs -P "$JOBS" -n 3 bash -c 'run1 "$@"' _
echo "done: $(ls $OUT/rows | wc -l) rows in $OUT/rows"
