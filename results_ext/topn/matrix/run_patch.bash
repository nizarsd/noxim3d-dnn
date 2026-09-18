#!/bin/bash
# OOB patch driver: waits for the main batch, adds interpolated/extended rungs
# for out-of-band placements, probes them, re-selects, reruns those cells.
# Appends probe rows to probe.txt; writes run_spec_patch.txt and
# res_matrix_patch.txt (patch rows supersede flagged OOB rows in analysis).
cd /home/nizar/noxim3d-dnn || exit 1
K=results_ext/topn/matrix
exec >> $K/campaign.log 2>&1

until grep -q "main batch done" $K/campaign.log; do sleep 300; done
echo "=== patch start $(date)"

python3 $K/patch_oob.py || { echo "PATCH-GEN FAILED"; exit 1; }

declare -A SIM=( [r1628]=38536 [v1644]=115606 [esxd]=58097 )
declare -A NN=(  [r1628]=23    [v1644]=25     [esxd]=25 )
declare -A CI=(  [r1628]=138   [v1644]=150    [esxd]=150 )
declare -p SIM NN CI > $K/.assoc

run1(){ # tab pol sinks sim seed
  local tab=$1 pol=$2 sinks=$3 sim=$4 seed=$5
  local SET=$(basename $tab | cut -d_ -f1)
  local SEL="-sel bufferlevel" TP=""
  if [ "$pol" = dp ];  then SEL="-sel dp -dpcost occupancy -cinterval 648"; fi
  if [ "$pol" = hyb ]; then
    SEL="-sel dp -dpcost occupancy -cinterval ${CI[$SET]}"
    TP="-dptopn ${NN[$SET]} $sinks"
  fi
  out=$(timeout 2400 ./noxim -size 16 16 -dimx 6 -dimy 6 -dimz 3 -buffer 16 \
        -routing oddevenbalanced $SEL $TP -warmup 1944 -sim $sim -seed $seed \
        -traffic table $tab 2>/dev/null)
  a=$(echo "$out"|grep -oP "average delay \(cycles\): \K[0-9.]+")
  p=$(echo "$out"|grep -oP "^% Delay p99 \(cycles\): \K[0-9.]+")
  echo "$(basename $tab .txt) $pol $seed ${a:-NA} ${p:-NA}"
}
export -f run1; export K

xargs -P 14 -n 2 bash -c 'source $K/.assoc; run1 "$1" bl - "$2" 1' _ \
  < $K/patch_probe_list.txt >> $K/probe.txt
echo "=== patch probe done $(date)"

python3 - <<'PY'
import collections
d = collections.defaultdict(dict)
for ln in open('results_ext/topn/matrix/probe.txt'):
    p = ln.split()
    if p[3] == 'NA':
        continue
    tag, k = p[0].rsplit('_k', 1)
    d[tag][int(k)] = float(p[3])
oob = [ln.split()[0] for ln in open('results_ext/topn/matrix/run_spec.txt')
       if ln.split()[3] == 'OOB']
with open('results_ext/topn/matrix/run_spec_patch.txt', 'w') as f:
    for tag in oob:
        ks = d[tag]; ff = ks[min(ks)]
        best = min(ks.items(), key=lambda kv: abs(kv[1]/ff - 5))
        dep = best[1]/ff
        flag = 'OK' if 4.0 <= dep <= 6.0 else 'OOB2'
        f.write(f"{tag} {best[0]:04d} {dep:.1f} {flag}\n")
        print(f"patched {tag:16s} k{best[0]/1000:.2f} depth {dep:.1f}x {flag}")
PY

: > $K/res_matrix_patch.txt
while read tag k dep flag; do
  case "$tag" in
    *_es*|*_af*) pols="bl dp hyb" ;;
    *)           pols="bl dp" ;;
  esac
  for pol in $pols; do
    for s in 1 2 3 4 5 6 7 8; do
      SET=${tag%%_*}
      echo "$K/tables/${tag}_k${k}.txt $pol $K/sinks_${tag} ${SIM[$SET]} $s"
    done
  done
done < $K/run_spec_patch.txt | xargs -P 14 -n 5 bash -c 'source $K/.assoc; run1 "$1" "$2" "$3" "$4" "$5"' _ >> $K/res_matrix_patch.txt
echo "=== patch done $(date)"
wc -l $K/res_matrix_patch.txt
echo "PATCH DONE $(date)"
