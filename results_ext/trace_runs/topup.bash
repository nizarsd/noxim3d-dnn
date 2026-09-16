#!/bin/bash
# DeiT band top-up: 1-seed BL probe over candidate rungs, pick the two whose
# set-mean BL delay lands in 15-30x the set's free-flow, then full traced runs.
# ff references measured from the existing ladders (census 2026-09-16):
#   e7 15.7  e3_vit 16.0  esxd 44.9   (set-mean BL mean delay at lowest rung)
cd /home/nizar/noxim3d-dnn || exit 1
R=results_ext/trace_runs; J=${JOBS:-14}
declare -A SIM=( [e7]=58097 [e3_vit]=58097 [esxd]=58097 )
declare -A FF=( [e7]=15.7 [e3_vit]=16.0 [esxd]=44.9 )
run_one () {  # tab pol seed sim trace(gz path or "") dptrace("" ok)
  local tab=$1 pol=$2 s=$3 sim=$4 gz=$5 trc=$6
  local SEL="-sel bufferlevel"; [ "$pol" = dp ] && SEL="-sel dp -dpcost occupancy -cinterval 648"
  local ENV=""
  if [ -n "$gz" ]; then
    out=$(BARRIERTRACE=1 ${trc:+DPTRACE=$trc} timeout 3600 ./noxim -size 16 16 -dimx 6 -dimy 6 -dimz 3 \
          -buffer 16 -routing oddevenbalanced $SEL -warmup 1944 -sim $sim -seed $s \
          -traffic table $tab 2> >(gzip > "$gz"))
  else
    out=$(timeout 3600 ./noxim -size 16 16 -dimx 6 -dimy 6 -dimz 3 \
          -buffer 16 -routing oddevenbalanced $SEL -warmup 1944 -sim $sim -seed $s \
          -traffic table $tab 2>/dev/null)
  fi
  a=$(echo "$out"|grep -oP "average delay \(cycles\): \K[0-9.]+")
  p=$(echo "$out"|grep -oP "^% Delay p99 \(cycles\): \K[0-9.]+")
  t=$(echo "$out"|grep -oP "Throughput \(flits/cycle/IP\): \K[0-9.]+")
  echo "$(basename $tab .txt) $pol $s ${a:-NA} ${p:-NA} ${t:-NA}"
}
export -f run_one
echo "=== probe $(date)"
for SET in e7 e3_vit esxd; do
  ls $R/tables_topup_$SET/*.txt | while read f; do echo "$f ${SIM[$SET]} $SET"; done
done | xargs -P $J -n 3 bash -c 'run_one $0 bufferlevel 1 $1 "" "" | sed "s/^/$2 /"' >> $R/probe.txt
echo "=== probe done, selecting rungs"
python3 - <<'PY'
import collections, statistics as st
FF={'e7':15.7,'e3_vit':16.0,'esxd':44.9}
d=collections.defaultdict(list)
for ln in open('results_ext/trace_runs/probe.txt'):
    p=ln.split()
    if len(p)<7 or p[4]=='NA': continue
    tag,k=p[1].rsplit('_k',1); d[(p[0],int(k))].append(float(p[4]))
sel={}
for (SET,k),v in sorted(d.items()):
    r=st.mean(v)/FF[SET]
    print(SET,k,'ratio %.1fx n=%d'%(r,len(v)))
    if 15<=r<30: sel.setdefault(SET,[]).append(k)
with open('results_ext/trace_runs/topup_selected.txt','w') as f:
    for SET,ks in sel.items(): f.write(f"{SET} {' '.join('%04d'%k for k in sorted(ks)[:2])}\n")
print('selected:', sel)
PY
echo "=== full top-up runs $(date)"
declare -A TRC   # esxd hot links for DPTRACE
while IFS=, read -r tag u v dir rest; do [ "$tag" = tag ] || TRC[$tag]="$u:$dir"; done < $R/hotlinks_esxd.csv
while read SET k1 k2; do
  mkdir -p $R/traces_topup_$SET
  for k in $k1 $k2; do
    [ -z "$k" ] && continue
    for f in $R/tables_topup_$SET/*_k${k}.txt; do
      tag=$(basename $f _k${k}.txt)
      for pol in bufferlevel dp; do for s in 1 2 3; do
        gz=$R/traces_topup_$SET/${tag}_k${k}_${pol}_s${s}.gz
        [ "$SET" = esxd ] && trc=${TRC[$tag]} || trc=""
        echo "$f $pol $s ${SIM[$SET]} $gz $trc $SET"
      done; done
    done
  done
done < $R/topup_selected.txt | xargs -P $J -n 7 bash -c '[ -s "$4" ] && exit 0; run_one $0 $1 $2 $3 "$4" "$5" >> results_ext/trace_runs/res_topup_$6.txt'
echo "TOPUP DONE $(date)" >> $R/run.log
