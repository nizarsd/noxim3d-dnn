#!/usr/bin/env bash
# DP vs bufferlevel on 6x6x3, over a chosen set of seeds and -cinterval values.
#
# The mesh is the Stage 2 default: ResNet-50 stage-3 bottleneck, 92 tiles at
# 8 crossbars/tile (the BASE partition, not the inflated 108-tile artefacts in
# traffics_dnn/), XY-diagonal placement.  See STAGE2.md and FINDINGS.md.
#
# Timing (4x dp_clock, settle 0):  dp_cycle = (ceil(diameter/4)+3) * nodes
#   6x6x3 -> (ceil(12/4)+3) * 108 = 648        <- the matched -cinterval
#   7x7x3 -> (ceil(14/4)+3) * 147 = 1029
# The sweep scripts' DP_CYCLE = 2*nodes*(diam+3) = 3240 is the legacy 1x/settle-1
# formula: fine for sizing warmup, WRONG for -cinterval.
#
# SIM is derived so the measured window is a whole number of block passes:
#   SIM = WARMUP + PASSES*t_period - 1000       (t_period read from the table)
# Partial passes bias the phase mix, so PASSES must stay an integer.
#
# Usage:
#   ./run_6x6x3.bash --seeds "2 6 10" --ci "648 1029"
#   ./run_6x6x3.bash --seeds "$(seq 2 4 118)" --ci 648 --passes 5
#   ./run_6x6x3.bash --seeds "2 6" --ci 648 --routing oddevenbalanced
#
# Options (all optional except --seeds / --ci):
#   --seeds "N N N"   seed list                      (required)
#   --ci    "N N N"   -cinterval list                (required)
#   --sel   "a b"     selection policies             (default "dp bufferlevel")
#   --routing NAME    -routing                       (default oddeven)
#   --table PATH      traffic table                  (default 6x6x3 base diagonal)
#   --passes N        whole block passes measured    (default 3)
#   --warmup N        -warmup                        (default 9720)
#   --buffer N        -buffer                        (default 16)
#   --jobs N          parallel runs                  (default 8)
#   --outdir DIR      results directory              (default results_6x6x3)
set -euo pipefail
cd "$(dirname "$0")"

SEEDS=""; CIS=""
SELS="dp bufferlevel"
ROUTING="oddeven"
TABLE="traffics_dnn_6base/resnet50_bottleneck3_xb128_6x6x3_base_diag.txt"
PASSES=3
WARMUP=9720
BUFFER=16
JOBS=8
OUTDIR="results_6x6x3"

while [ $# -gt 0 ]; do
    case "$1" in
        --seeds)   SEEDS="$2";   shift 2 ;;
        --ci)      CIS="$2";     shift 2 ;;
        --sel)     SELS="$2";    shift 2 ;;
        --routing) ROUTING="$2"; shift 2 ;;
        --table)   TABLE="$2";   shift 2 ;;
        --passes)  PASSES="$2";  shift 2 ;;
        --warmup)  WARMUP="$2";  shift 2 ;;
        --buffer)  BUFFER="$2";  shift 2 ;;
        --jobs)    JOBS="$2";    shift 2 ;;
        --outdir)  OUTDIR="$2";  shift 2 ;;
        -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
        *) echo "unknown option: $1  (try --help)" >&2; exit 1 ;;
    esac
done

[ -n "$SEEDS" ] || { echo "ERROR: --seeds is required" >&2; exit 1; }
[ -n "$CIS" ]   || { echo "ERROR: --ci is required" >&2; exit 1; }
[ -f "$TABLE" ] || { echo "ERROR: no such table: $TABLE" >&2; exit 1; }
[ -x ./noxim ]  || { echo "ERROR: ./noxim not built" >&2; exit 1; }

# t_period is the last field of any data row; every row shares it.
TPERIOD=$(grep -v '^%' "$TABLE" | awk 'NF{print $7; exit}')
[ -n "$TPERIOD" ] || { echo "ERROR: could not read t_period from $TABLE" >&2; exit 1; }
SIM=$(( WARMUP + PASSES * TPERIOD - 1000 ))

mkdir -p "$OUTDIR/logs" "$OUTDIR/rows"

echo "mesh 6x6x3   routing $ROUTING   buffer $BUFFER"
echo "table   $TABLE  (t_period $TPERIOD)"
echo "warmup  $WARMUP   sim $SIM   -> $PASSES whole passes, $((SIM-WARMUP)) cycles measured"
echo "seeds   $SEEDS"
echo "ci      $CIS"
echo "sel     $SELS"

run_one() {
    local ci="$1" sel="$2" seed="$3"
    local tag="ci${ci}_${sel}_seed${seed}"
    local log="$OUTDIR/logs/${tag}.log"
    ./noxim -dimx 6 -dimy 6 -dimz 3 -buffer "$BUFFER" -routing "$ROUTING" \
        -sel "$sel" -cinterval "$ci" -size 16 16 \
        -warmup "$WARMUP" -sim "$SIM" -samp 1 \
        -traffic table "$TABLE" -seed "$seed" > "$log" 2>&1 \
        || { echo "$ci,$sel,$seed,ERROR,ERROR,ERROR" > "$OUTDIR/rows/${tag}.row"
             echo "  FAILED $tag"; return 0; }
    local d t m
    d=$(grep 'Global average delay'         "$log" | cut -d: -f2 | tr -d ' ')
    t=$(grep 'Throughput (flits/cycle/IP)'  "$log" | cut -d: -f2 | tr -d ' ')
    m=$(grep 'Max delay'                    "$log" | cut -d: -f2 | tr -d ' ')
    echo "$ci,$sel,$seed,${d:-NA},${t:-NA},${m:-NA}" > "$OUTDIR/rows/${tag}.row"
    echo "  done $tag"
}
export -f run_one
export OUTDIR BUFFER ROUTING TABLE WARMUP SIM

{ for ci in $CIS; do for sel in $SELS; do for sd in $SEEDS; do
      echo "$ci $sel $sd"
  done; done; done; } | xargs -P "$JOBS" -n 3 bash -c 'run_one "$@"' _

echo
python3 - "$OUTDIR" <<'EOF'
import glob, os, statistics as st, sys
rows = {}
for f in glob.glob(os.path.join(sys.argv[1], "rows", "*.row")):
    ci, sel, sd, d, t, m = open(f).read().strip().split(",")
    if d == "ERROR":
        continue
    rows.setdefault(int(ci), {}).setdefault(sel, {})[int(sd)] = (
        float(d), float(t), float(m))

hdr = f"{'ci':>6} {'sel':>12} {'n':>3} {'delay':>9} {'sd':>8} {'thru':>10} {'maxdelay':>10}"
print(hdr); print("-" * len(hdr))
for ci in sorted(rows):
    for sel in sorted(rows[ci]):
        v = rows[ci][sel]
        d = [x[0] for x in v.values()]
        print(f"{ci:>6} {sel:>12} {len(d):>3} {st.mean(d):>9.2f} "
              f"{(st.stdev(d) if len(d) > 1 else 0):>8.2f} "
              f"{st.mean([x[1] for x in v.values()]):>10.5f} "
              f"{st.mean([x[2] for x in v.values()]):>10.1f}")

pairs = [ci for ci in sorted(rows) if {"dp", "bufferlevel"} <= set(rows[ci])]
if pairs:
    print(f"\n{'ci':>6} {'n':>3} {'BL':>9} {'DP':>9} {'DP-BL':>9} {'%':>8} "
          f"{'t':>7} {'DP wins':>9}")
    for ci in pairs:
        seeds = sorted(set(rows[ci]["dp"]) & set(rows[ci]["bufferlevel"]))
        bl = [rows[ci]["bufferlevel"][s][0] for s in seeds]
        dp = [rows[ci]["dp"][s][0] for s in seeds]
        diff = [a - b for a, b in zip(dp, bl)]
        n = len(seeds)
        if n < 2:
            print(f"{ci:>6} {n:>3} {st.mean(bl):>9.2f} {st.mean(dp):>9.2f} "
                  f"{st.mean(diff):>+9.2f} {'':>8} {'':>7} {'':>9}  (n<2)")
            continue
        m, sd_ = st.mean(diff), st.stdev(diff)
        t = m / (sd_ / n ** 0.5) if sd_ else float("inf")
        print(f"{ci:>6} {n:>3} {st.mean(bl):>9.2f} {st.mean(dp):>9.2f} "
              f"{m:>+9.2f} {100*m/st.mean(bl):>+7.2f}% {t:>7.2f} "
              f"{sum(1 for x in diff if x < 0):>4}/{n:<4}")
    print("\nnegative DP-BL = DP faster.  Paired over shared seeds.")
EOF
