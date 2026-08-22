#!/usr/bin/env bash
# Fill the missing OEB cells so the noskip result becomes interpretable.
#
# results_6b_noskip is currently the ONLY oddevenbalanced data on disk; every other
# results dir is -routing oddeven.  That makes its "vs bufferlevel" column invalid
# (it was compared against an oddeven baseline) and leaves routing confounded with
# the noskip patch.  This runs, all on OEB with the stock ./noxim:
#
#   bufferlevel            -> the missing baseline
#   dp -dpcost occupancy   -> OEB + skip
#   dp -dpcost none        -> OEB + skip
#
# Together with results_6b_noskip that completes the 2x2 and gives a real baseline.
#
# Usage:  ./run_oeb_arms.bash [SEEDS] [JOBS]
set -euo pipefail
cd "$(dirname "$0")"

SEEDS="${1:-0 2 5 10 15 20 25 30 35 40 45 50 55 60 65 70 75 80 85 90 95 100 105 110 115 120 125 130 135 140 150 155 160 165 170 175 180 185 190 195 200 205 210 215 220 225 230 235 240 245 250}"
JOBS="${2:-12}"
TABLE="traffics_dnn_6base/rn50_6b_ls0.026_diag_accint.txt"
OUT="results_6b_oeb"

[ -x ./noxim ] || { echo "ERROR: ./noxim not built (run: make clean && make -j$JOBS)" >&2; exit 1; }
mkdir -p "$OUT/rows" "$OUT/logs"

run_one() {
    local arm="$1" seed="$2" sel dpc
    case "$arm" in
        bufferlevel) sel=bufferlevel; dpc=occupancy ;;
        occupancy)   sel=dp;          dpc=occupancy ;;
        none)        sel=dp;          dpc=none      ;;
    esac
    local log="$OUT/logs/${arm}_s${seed}.log"
    ./noxim -dimx 6 -dimy 6 -dimz 3 -buffer 16 -routing oddevenbalanced -sel "$sel" \
        -dpcost "$dpc" -cinterval 648 -size 16 16 -warmup 9720 -sim 124328 -samp 1 \
        -traffic table "$TABLE" -seed "$seed" > "$log" 2>&1
    local d t m
    d=$(grep 'Global average delay'        "$log" | cut -d: -f2 | tr -d ' ')
    t=$(grep 'Throughput (flits/cycle/IP)' "$log" | cut -d: -f2 | tr -d ' ')
    m=$(grep 'Max delay'                   "$log" | cut -d: -f2 | tr -d ' ')
    echo "$arm,$sel,$seed,${d:-NA},${t:-NA},${m:-NA}" > "$OUT/rows/${arm}_s${seed}.row"
}
export -f run_one; export OUT TABLE

echo "== $(echo $SEEDS | wc -w) seeds x 3 arms, all -routing oddevenbalanced, -P $JOBS =="
{ for a in bufferlevel occupancy none; do for s in $SEEDS; do echo "$a $s"; done; done; } \
    | xargs -P "$JOBS" -n 2 bash -c 'run_one "$@"' _

python3 - <<'PYEOF'
import glob, math, statistics as st
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
for f in glob.glob("results_6b_oeb/rows/*.row"):
    p=open(f).read().strip().split(",")
    if p[3]=="NA": continue
    arms.setdefault({"bufferlevel":"bufferlevel","occupancy":"DP skip occupancy",
                     "none":"DP skip none"}[p[0]],{})[int(p[2])]=float(p[3])
for f in glob.glob("results_6b_noskip/rows/*.row"):
    p=open(f).read().strip().split(",")
    if p[3]=="NA": continue
    arms.setdefault(p[0].replace("noskip-","DP noskip "),{})[int(p[2])]=float(p[3])

seeds=sorted(set.intersection(*[set(v) for v in arms.values()])); n=len(seeds)
b=[arms["bufferlevel"][s] for s in seeds]
print(f"\nls 0.026, interior placement, OEB (planar/Z coexisting), n={n} paired seeds\n")
print(f"{'arm':<22} {'delay':>8} {'sd':>7} {'vs BL':>9} {'t':>7} {'p':>9}")
print("-"*66)
for k in ("bufferlevel","DP skip occupancy","DP skip none",
          "DP noskip occupancy","DP noskip none"):
    if k not in arms: continue
    a=[arms[k][s] for s in seeds]
    if k=="bufferlevel":
        print(f"{k:<22} {st.mean(a):>8.2f} {st.stdev(a):>7.2f} {'baseline':>9}"); continue
    d=[x-y for x,y in zip(a,b)]; m=st.mean(d); t=m/(st.stdev(d)/n**0.5)
    print(f"{k:<22} {st.mean(a):>8.2f} {st.stdev(a):>7.2f} {100*m/st.mean(b):>+8.2f}% "
          f"{t:>7.2f} {pval(t,n-1):>9.5f}")

print("\ndoes the congestion metric pay?  (occupancy - none; negative = metric helps)")
for tag in ("skip","noskip"):
    x,y=f"DP {tag} occupancy", f"DP {tag} none"
    if x in arms and y in arms:
        u=[arms[x][s] for s in seeds]; v=[arms[y][s] for s in seeds]
        d=[p-q for p,q in zip(u,v)]; m=st.mean(d); t=m/(st.stdev(d)/n**0.5)
        print(f"  OEB {tag:<7}: {100*m/st.mean(v):>+7.2f}%  t={t:>6.2f}  p={pval(t,n-1):.5f}")
print("  oddeven skip (on disk, n=30): +4.86%  t=  1.63  p=0.11  -- metric does NOT pay")
PYEOF
echo
echo "rows in $OUT/rows"
