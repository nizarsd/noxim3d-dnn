#!/usr/bin/env bash
# Does DP's greedy skip-if-busy explain its win, or is it the static ranking?
#
# Builds a second binary with the availability test in selectionDP neutralised
# (always take the best-ranked direction, even if the port is reserved), runs it
# against the stock binary at ls 0.026, and prints a paired comparison against the
# bufferlevel / random / dpcost arms already on disk.
#
# Your TRouter.cpp is patched, built, and restored -- a trap restores it even on
# Ctrl-C.  Nothing else in the repo is touched.
#
# Usage:  ./run_noskip_experiment.bash [SEEDS] [JOBS]
set -euo pipefail
cd "$(dirname "$0")"

SEEDS="${1:-0 2 5 10 15 20 25 30 35 40 45 50 55 60 65 70 75 80 85 90 95 100 105 110 115 120 125 130 135 140 45 150 155 160 165 170 175 180 185 190 195 200 205 210 215 220 225 230 235 240 245 250}"
JOBS="${2:-12}"
TABLE="traffics_dnn_6base/rn50_6b_ls0.026_diag_accint.txt"
OUT="results_6b_noskip"
SRC="TRouter.cpp"
BACKUP=".TRouter.cpp.noskip-backup"
PATTERN='if (reservation_table.isAvailable(directions\[i\]))'

[ -f "$TABLE" ] || { echo "ERROR: missing $TABLE" >&2; exit 1; }

# ---- 1. patch, build, restore -------------------------------------------------
n=$(grep -c "$PATTERN" "$SRC" || true)
if [ "$n" -ne 1 ]; then
    echo "ERROR: expected exactly 1 match for the availability test in $SRC, found $n." >&2
    echo "       selectionDP may have changed -- patch by hand instead." >&2
    exit 1
fi

cp "$SRC" "$BACKUP"
restore() { if [ -f "$BACKUP" ]; then mv -f "$BACKUP" "$SRC"; echo "  $SRC restored"; fi; }
trap restore EXIT INT TERM

echo "== building noxim_noskip (availability test disabled) =="
sed -i "s|$PATTERN|if (true) /* NOSKIP */|" "$SRC"
grep -n "NOSKIP" "$SRC" | head -1
make clean >/dev/null 2>&1
make -j"$JOBS" MODULE=noxim_noskip >/dev/null 2>&1
[ -x ./noxim_noskip ] || { echo "ERROR: build failed" >&2; exit 1; }

restore; trap - EXIT INT TERM

echo "== rebuilding stock noxim =="
make clean >/dev/null 2>&1          # MUST clean: objects carry the patched code
make -j"$JOBS" >/dev/null 2>&1
[ -x ./noxim ] || { echo "ERROR: stock rebuild failed" >&2; exit 1; }

# ---- 2. sanity: the two binaries must differ, and only here -------------------
echo "== sanity check =="
a=$(./noxim         -dimx 6 -dimy 6 -dimz 3 -buffer 16 -routing oddevenbalanced -sel dp -dpcost none \
     -cinterval 648 -size 16 16 -warmup 9720 -sim 124328 -samp 1 -traffic table "$TABLE" -seed 2 \
     2>&1 | grep 'Global average delay' | cut -d: -f2 | tr -d ' ')
b=$(./noxim_noskip  -dimx 6 -dimy 6 -dimz 3 -buffer 16 -routing oddevenbalanced -sel dp -dpcost none \
     -cinterval 648 -size 16 16 -warmup 9720 -sim 124328 -samp 1 -traffic table "$TABLE" -seed 2 \
     2>&1 | grep 'Global average delay' | cut -d: -f2 | tr -d ' ')
echo "  seed 2, dpcost none:  stock=$a   noskip=$b"
[ "$a" != "$b" ] || echo "  WARNING: identical -- the patch had no effect, results below are meaningless"

# ---- 3. run both dpcost arms --------------------------------------------------
mkdir -p "$OUT/rows" "$OUT/logs"
run_one() {
    local metric="$1" seed="$2"
    local tag="noskip_${metric}_s${seed}"
    local log="$OUT/logs/${tag}.log"
    ./noxim_noskip -dimx 6 -dimy 6 -dimz 3 -buffer 16 -routing oddevenbalanced -sel dp \
        -dpcost "$metric" -cinterval 648 -size 16 16 -warmup 9720 -sim 124328 -samp 1 \
        -traffic table "$TABLE" -seed "$seed" > "$log" 2>&1
    local d t m
    d=$(grep 'Global average delay'        "$log" | cut -d: -f2 | tr -d ' ')
    t=$(grep 'Throughput (flits/cycle/IP)' "$log" | cut -d: -f2 | tr -d ' ')
    m=$(grep 'Max delay'                   "$log" | cut -d: -f2 | tr -d ' ')
    echo "noskip-$metric,dp,$seed,${d:-NA},${t:-NA},${m:-NA}" > "$OUT/rows/${tag}.row"
}
export -f run_one
export OUT TABLE

echo "== running $(echo $SEEDS | wc -w) seeds x 2 metrics at -P $JOBS =="
{ for m in occupancy none; do for s in $SEEDS; do echo "$m $s"; done; done; } \
    | xargs -P "$JOBS" -n 2 bash -c 'run_one "$@"' _

# ---- 4. compare against everything already measured ---------------------------
python3 - "$OUT" <<'PYEOF'
import glob, os, sys, math, statistics as st

def betacf(a,b,x):
    F=1e-300;qab,qap,qam=a+b,a+1,a-1;c=1.0;d=1-qab*x/qap;d=1/(d if abs(d)>F else F);h=d
    for m in range(1,300):
        m2=2*m
        aa=m*(b-m)*x/((qam+m2)*(a+m2));d=1+aa*d;c=1+aa/c;d=1/(d if abs(d)>F else F);h*=d*c
        aa=-(a+m)*(qab+m)*x/((a+m2)*(qap+m2));d=1+aa*d;c=1+aa/c;d=1/(d if abs(d)>F else F)
        de=d*c;h*=de
        if abs(de-1)<3e-16: break
    return h
def betai(a,b,x):
    if x<=0: return 0.0
    if x>=1: return 1.0
    bt=math.exp(math.lgamma(a+b)-math.lgamma(a)-math.lgamma(b)+a*math.log(x)+b*math.log(1-x))
    return bt*betacf(a,b,x)/a if x<(a+1)/(a+b+2) else 1-bt*betacf(b,a,1-x)/b
def pval(t,df): return betai(df/2,0.5,df/(df+t*t))

arms={}
def add(name, pattern, dcol=3, seedcol=2):
    for f in glob.glob(pattern):
        p=open(f).read().strip().split(",")
        if len(p)<6 or p[dcol]=="ERROR": continue
        arms.setdefault(name,{})[int(p[seedcol])]=float(p[dcol])

add("bufferlevel", "results_6b_accint/rows/accint_bufferlevel_*.row")
add("random",      "results_6b_random/rows/*.row")
for f in glob.glob("results_6b_dpcost/rows/*.row"):
    p=open(f).read().strip().split(",")
    arms.setdefault("DP "+p[0], {})[int(p[2])]=float(p[3])
for f in glob.glob(os.path.join(sys.argv[1],"rows","*.row")):
    p=open(f).read().strip().split(",")
    arms.setdefault(p[0].replace("noskip-","DP noskip "), {})[int(p[2])]=float(p[3])

arms={k:v for k,v in arms.items() if v}
seeds=sorted(set.intersection(*[set(v) for v in arms.values()]))
n=len(seeds)
if n < 2:
    print("not enough shared seeds to compare"); raise SystemExit
b=[arms["bufferlevel"][s] for s in seeds]

order=["bufferlevel","random","DP wait","DP occupancy","DP none",
       "DP noskip occupancy","DP noskip none"]
print(f"\nls 0.026, interior placement, ci 648, n={n} paired seeds\n")
print(f"{'selection':<22} {'delay':>8} {'sd':>7} {'vs BL':>9} {'t':>7} {'p':>9}")
print("-"*66)
for k in order:
    if k not in arms: continue
    a=[arms[k][s] for s in seeds]
    if k=="bufferlevel":
        print(f"{k:<22} {st.mean(a):>8.2f} {st.stdev(a):>7.2f} {'baseline':>9}")
        continue
    d=[x-y for x,y in zip(a,b)]; m=st.mean(d); t=m/(st.stdev(d)/n**0.5)
    print(f"{k:<22} {st.mean(a):>8.2f} {st.stdev(a):>7.2f} "
          f"{100*m/st.mean(b):>+8.2f}% {t:>7.2f} {pval(t,n-1):>9.5f}")

print("\nthe question -- does removing skip-if-busy collapse DP toward random?")
for x,y in (("DP none","DP noskip none"),
            ("DP occupancy","DP noskip occupancy"),
            ("random","DP noskip none")):
    if x in arms and y in arms:
        u=[arms[x][s] for s in seeds]; v=[arms[y][s] for s in seeds]
        d=[p-q for p,q in zip(u,v)]; m=st.mean(d); t=m/(st.stdev(d)/n**0.5)
        print(f"  {x:<14} vs {y:<20}: {m:>+8.2f} cyc ({100*m/st.mean(v):>+7.2f}%)"
              f"  t={t:>6.2f}  p={pval(t,n-1):.4f}")
print("\n  collapses toward random  -> the availability check was the mechanism")
print("  stays near DP none       -> the static ranking is the mechanism")
PYEOF

echo
echo "rows in $OUT/rows ; stock tree restored ; extra binary: ./noxim_noskip"
