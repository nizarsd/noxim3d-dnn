#!/usr/bin/env bash
# ls 0.028 on the BOTH-RELAXED oeb (planar/vertical coexist ascending AND descending).
#
# Phase 1 (stock ./noxim) : bufferlevel, dp -dpcost occupancy, dp -dpcost none, random
# Phase 2 (patched binary): dp -dpcost occupancy, dp -dpcost none   [availability check off]
#
# Sequential by necessity: phase 2 patches TRouter.cpp and runs make clean, which would
# corrupt anything running concurrently.  A trap restores TRouter.cpp on any exit.
set -euo pipefail
cd "$(dirname "$0")"

SEEDS="${1:-0 2 5 10 15 20 25 30 35 40 45 50 55 60 65 70 75 80 85 90 95 100 105 110 115 120 125 130 135 140}"
JOBS="${2:-12}"
TABLE="traffics_dnn_6base/rn50_6b_ls0.028_diag_accint.txt"
OUT="results_6b_oebrx028"
SRC="TRouter.cpp"; BACKUP=".TRouter.rx.bak"
PATTERN='if (reservation_table.isAvailable(directions\[i\]))'

[ -f "$TABLE" ] || { echo "ERROR: missing $TABLE" >&2; exit 1; }
mkdir -p "$OUT/rows" "$OUT/logs"

runner() {   # $1 arm  $2 seed  $3 binary
    local arm="$1" seed="$2" bin="$3" sel dpc
    case "$arm" in
        bufferlevel)      sel=bufferlevel; dpc=occupancy ;;
        random)           sel=random;      dpc=occupancy ;;
        skip_occupancy|noskip_occupancy)   sel=dp; dpc=occupancy ;;
        skip_none|noskip_none)             sel=dp; dpc=none ;;
    esac
    local log="$OUT/logs/${arm}_s${seed}.log"
    ./$bin -dimx 6 -dimy 6 -dimz 3 -buffer 16 -routing oddevenbalanced -sel "$sel" \
        -dpcost "$dpc" -cinterval 648 -size 16 16 -warmup 9720 -sim 124328 -samp 1 \
        -traffic table "$TABLE" -seed "$seed" > "$log" 2>&1
    local d t m
    d=$(grep 'Global average delay'        "$log" | cut -d: -f2 | tr -d ' ')
    t=$(grep 'Throughput (flits/cycle/IP)' "$log" | cut -d: -f2 | tr -d ' ')
    m=$(grep 'Max delay'                   "$log" | cut -d: -f2 | tr -d ' ')
    echo "$arm,$sel,$seed,${d:-NA},${t:-NA},${m:-NA}" > "$OUT/rows/${arm}_s${seed}.row"
}
export -f runner; export OUT TABLE

echo "=== phase 1/2: stock binary, 4 arms x $(echo $SEEDS|wc -w) seeds ==="
{ for a in bufferlevel random skip_occupancy skip_none; do for s in $SEEDS; do echo "$a $s noxim"; done; done; } \
  | xargs -P "$JOBS" -n 3 bash -c 'runner "$@"' _
echo "  phase 1 done: $(ls $OUT/rows | wc -l) rows"

echo "=== phase 2/2: building noskip binary ==="
n=$(grep -c "$PATTERN" "$SRC" || true)
[ "$n" -eq 1 ] || { echo "ERROR: availability pattern matched $n times, expected 1" >&2; exit 1; }
cp "$SRC" "$BACKUP"
restore(){ [ -f "$BACKUP" ] && mv -f "$BACKUP" "$SRC" && echo "  $SRC restored"; }
trap restore EXIT INT TERM
sed -i "s|$PATTERN|if (true) /* NOSKIP */|" "$SRC"
make clean >/dev/null 2>&1; make -j"$JOBS" MODULE=noxim_noskip_rx >/dev/null 2>&1
[ -x ./noxim_noskip_rx ] || { echo "ERROR: noskip build failed" >&2; exit 1; }
restore; trap - EXIT INT TERM
make clean >/dev/null 2>&1; make -j"$JOBS" >/dev/null 2>&1
[ -x ./noxim ] || { echo "ERROR: stock rebuild failed" >&2; exit 1; }

a=$(./noxim            -dimx 6 -dimy 6 -dimz 3 -buffer 16 -routing oddevenbalanced -sel dp -dpcost none -cinterval 648 -size 16 16 -warmup 9720 -sim 124328 -samp 1 -traffic table "$TABLE" -seed 2 2>&1 | grep 'Global average delay' | cut -d: -f2 | tr -d ' ')
b=$(./noxim_noskip_rx  -dimx 6 -dimy 6 -dimz 3 -buffer 16 -routing oddevenbalanced -sel dp -dpcost none -cinterval 648 -size 16 16 -warmup 9720 -sim 124328 -samp 1 -traffic table "$TABLE" -seed 2 2>&1 | grep 'Global average delay' | cut -d: -f2 | tr -d ' ')
echo "  sanity seed 2 dpcost none: stock=$a noskip=$b"
[ "$a" != "$b" ] || echo "  WARNING: identical -- patch had no effect"

{ for a in noskip_occupancy noskip_none; do for s in $SEEDS; do echo "$a $s noxim_noskip_rx"; done; done; } \
  | xargs -P "$JOBS" -n 3 bash -c 'runner "$@"' _
echo "  phase 2 done: $(ls $OUT/rows | wc -l) rows total"
