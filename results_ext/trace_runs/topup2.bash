#!/bin/bash
# Top-up, stage 2: extra esxd probe (k 0.90/1.00/1.10), reselect, then full
# traced runs for the selected rungs of all three sets.  '-' = no DPTRACE.
cd /home/nizar/noxim3d-dnn || exit 1
R=results_ext/trace_runs; J=${JOBS:-14}
run_one () {
  local tab=$1 pol=$2 s=$3 sim=$4 gz=$5 trc=$6
  local SEL="-sel bufferlevel"; [ "$pol" = dp ] && SEL="-sel dp -dpcost occupancy -cinterval 648"
  local D=""; [ "$trc" != "-" ] && D=$trc
  if [ "$gz" = "-" ]; then
    out=$(timeout 3600 ./noxim -size 16 16 -dimx 6 -dimy 6 -dimz 3 -buffer 16 \
          -routing oddevenbalanced $SEL -warmup 1944 -sim $sim -seed $s -traffic table $tab 2>/dev/null)
  else
    out=$(env BARRIERTRACE=1 ${D:+DPTRACE=$D} timeout 3600 ./noxim -size 16 16 -dimx 6 -dimy 6 -dimz 3 -buffer 16 \
          -routing oddevenbalanced $SEL -warmup 1944 -sim $sim -seed $s -traffic table $tab 2> >(gzip > "$gz"))
  fi
  a=$(echo "$out"|grep -oP "average delay \(cycles\): \K[0-9.]+")
  p=$(echo "$out"|grep -oP "^% Delay p99 \(cycles\): \K[0-9.]+")
  t=$(echo "$out"|grep -oP "Throughput \(flits/cycle/IP\): \K[0-9.]+")
  echo "$(basename $tab .txt) $pol $s ${a:-NA} ${p:-NA} ${t:-NA}"
}
export -f run_one
echo "=== esxd extra probe $(date)"
ls $R/tables_topup_esxd/*_k0900.txt $R/tables_topup_esxd/*_k1000.txt $R/tables_topup_esxd/*_k1100.txt \
| xargs -P $J -I{} bash -c 'run_one {} bufferlevel 1 58097 - - | sed "s/^/esxd /"' >> $R/probe.txt
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
echo "=== full top-up $(date)"
declare -A SIM=( [e7]=58097 [e3_vit]=58097 [esxd]=58097 )
declare -A TRC
while IFS=, read -r tag u v dir rest; do [ "$tag" = tag ] || TRC[$tag]="$u:$dir"; done < $R/hotlinks_esxd.csv
while read SET k1 k2; do
  mkdir -p $R/traces_topup_$SET
  for k in $k1 $k2; do
    [ -z "$k" ] && continue
    for f in $R/tables_topup_$SET/*_k${k}.txt; do
      tag=$(basename $f _k${k}.txt)
      trc=-; [ "$SET" = esxd ] && [ -n "${TRC[$tag]}" ] && trc=${TRC[$tag]}
      for pol in bufferlevel dp; do for s in 1 2 3; do
        echo "$SET $f $pol $s ${SIM[$SET]} $R/traces_topup_$SET/${tag}_k${k}_${pol}_s${s}.gz $trc"
      done; done
    done
  done
done < $R/topup_selected.txt | xargs -P $J -n 7 bash -c '
  [ -s "$5" ] && exit 0
  run_one "$1" "$2" "$3" "$4" "$5" "$6" >> results_ext/trace_runs/res_topup_$0.txt'
echo "TOPUP2 DONE $(date)" >> $R/run.log
