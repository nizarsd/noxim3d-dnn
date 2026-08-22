#!/usr/bin/env bash
# Re-locate the congestion knee on OEB with coexisting planar/Z turns.
#
# WHY.  The interior-placement knee (18.52@0.014 ... 191.93@0.026, elbow between
# 0.025 and 0.026) was located on -routing oddeven.  On OEB with the planar/vertical
# exclusivity disabled, bufferlevel at ls 0.026 is 131.66 instead of 191.93, so the
# knee has moved and ls 0.026 may no longer sit past it.  Percentages taken in
# saturation mean something different from those taken below it (FINDINGS.md), so
# the knee has to be re-found before any DP-vs-BL % on this substrate is quoted.
#
# n=3 by design: locating a knee needs load points, not seeds (FINDINGS.md method).
# Timing matches every other OEB run so the ls 0.026 column is directly comparable
# to results_6b_oeb: ci 648, warmup 9720, sim 124328 (3 whole block passes).
#
# Usage:  ./run_oeb_knee.bash [SEEDS] [JOBS]
set -euo pipefail
cd "$(dirname "$0")"

SEEDS="${1:-2 6 10}"
JOBS="${2:-12}"
LS_LIST="0.018 0.020 0.022 0.024 0.025 0.026 0.028 0.030"
OUT="results_6b_oeb_knee"

[ -x ./noxim ] || { echo "ERROR: ./noxim not built" >&2; exit 1; }
mkdir -p "$OUT/rows" "$OUT/logs"

run_one() {
    local ls="$1" sel="$2" seed="$3"
    local table="traffics_dnn_6base/rn50_6b_ls${ls}_diag_accint.txt"
    [ -f "$table" ] || { echo "  MISSING $table"; return 0; }
    local log="$OUT/logs/ls${ls}_${sel}_s${seed}.log"
    ./noxim -dimx 6 -dimy 6 -dimz 3 -buffer 16 -routing oddevenbalanced -sel "$sel" \
        -dpcost occupancy -cinterval 648 -size 16 16 -warmup 9720 -sim 124328 -samp 1 \
        -traffic table "$table" -seed "$seed" > "$log" 2>&1
    local d t m
    d=$(grep 'Global average delay'        "$log" | cut -d: -f2 | tr -d ' ')
    t=$(grep 'Throughput (flits/cycle/IP)' "$log" | cut -d: -f2 | tr -d ' ')
    m=$(grep 'Max delay'                   "$log" | cut -d: -f2 | tr -d ' ')
    echo "$ls,$sel,$seed,${d:-NA},${t:-NA},${m:-NA}" > "$OUT/rows/ls${ls}_${sel}_s${seed}.row"
}
export -f run_one; export OUT

echo "== OEB (coexisting planar/Z) knee sweep: $(echo $LS_LIST | wc -w) loads x 2 sel x $(echo $SEEDS | wc -w) seeds =="
{ for l in $LS_LIST; do for s in dp bufferlevel; do for d in $SEEDS; do echo "$l $s $d"; done; done; done; } \
    | xargs -P "$JOBS" -n 3 bash -c 'run_one "$@"' _

python3 - <<'PYEOF'
import glob, statistics as st
rows={}
for f in glob.glob("results_6b_oeb_knee/rows/*.row"):
    p=open(f).read().strip().split(",")
    if p[3]=="NA": continue
    rows.setdefault(float(p[0]),{}).setdefault(p[1],{})[int(p[2])]=(float(p[3]),float(p[4]))
print("\nOEB, coexisting planar/Z turns, interior placement, ci 648, 3 whole passes\n")
print(f"{'ls':>7} {'BL delay':>9} {'step':>6} {'DP delay':>9} {'step':>6} {'DP vs BL':>9} {'BL thru':>9}")
print("-"*62)
prevb=prevd=None
for ls in sorted(rows):
    r=rows[ls]
    if "bufferlevel" not in r or "dp" not in r: continue
    b=st.mean([v[0] for v in r["bufferlevel"].values()])
    d=st.mean([v[0] for v in r["dp"].values()])
    tb=st.mean([v[1] for v in r["bufferlevel"].values()])
    sb=f"{b/prevb:.2f}x" if prevb else "  -"
    sd=f"{d/prevd:.2f}x" if prevd else "  -"
    print(f"{ls:>7.3f} {b:>9.2f} {sb:>6} {d:>9.2f} {sd:>6} {100*(d-b)/b:>+8.2f}% {tb:>9.5f}")
    prevb, prevd = b, d
print("\nThe elbow is where the BL step ratio jumps well above the ~1.5x of the")
print("points below it.  On oddeven that was 2.74x between 0.025 and 0.026.")
PYEOF
echo; echo "rows in $OUT/rows"
