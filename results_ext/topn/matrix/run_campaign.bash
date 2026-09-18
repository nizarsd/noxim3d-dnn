#!/bin/bash
# c16 coherent matrix campaign — self-contained driver, survives session loss.
# 1) phase1b searches (minE40/minE50/aboveF)  2) tables+sinks  3) BL probe of
# every ladder  4) rung selection (nearest 5x own ff, band 4-6x)  5) main
# batch per arm policy split, 8 seeds.  All output under results_ext/topn/matrix.
cd /home/nizar/noxim3d-dnn || exit 1
K=results_ext/topn/matrix
exec >> $K/campaign.log 2>&1
echo "=== CAMPAIGN start $(date)"

python3 $K/phase1b_arms.py || { echo "PHASE1B FAILED"; exit 1; }
python3 $K/phase2b_gen.py || { echo "PHASE2B-GEN FAILED"; exit 1; }

declare -A SIM=( [r1628]=38536 [v1644]=115606 [esxd]=58097 )
declare -A NN=(  [r1628]=23    [v1644]=25     [esxd]=25 )
declare -A CI=(  [r1628]=138   [v1644]=150    [esxd]=150 )

run1(){ # tab pol sinks sim seed  (env NNARG CIARG for hyb)
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
export -f run1
export K
declare -p SIM NN CI > $K/.assoc; export BASH_ENV=$K/.assoc

echo "=== probe start $(date)"
ls $K/tables/*.txt | while read f; do
  SET=$(basename $f | cut -d_ -f1); echo "$f ${SIM[$SET]}"
done | xargs -P 14 -n 2 bash -c 'source $K/.assoc; run1 "$1" bl - "$2" 1' _ > $K/probe.txt
echo "=== probe done $(date)"

python3 - <<'PY'
import collections
d = collections.defaultdict(dict)
for ln in open('results_ext/topn/matrix/probe.txt'):
    p = ln.split()
    if p[3] == 'NA':
        continue
    tag, k = p[0].rsplit('_k', 1)
    d[tag][int(k)] = float(p[3])
sel = []
for tag in sorted(d):
    ks = d[tag]; ff = ks[min(ks)]
    best = min(ks.items(), key=lambda kv: abs(kv[1]/ff - 5))
    dep = best[1]/ff
    flag = 'OK' if 4.0 <= dep <= 6.0 else 'OOB'
    sel.append((tag, best[0], dep, flag))
    print(f"{tag:16s} k{best[0]/1000:.2f} depth {dep:.1f}x {flag}  ("
          + " ".join(f"{k/1000:.2f}:{v/ff:.1f}x" for k, v in sorted(ks.items())) + ")")
with open('results_ext/topn/matrix/run_spec.txt', 'w') as f:
    for tag, k, dep, flag in sel:
        f.write(f"{tag} {k:04d} {dep:.1f} {flag}\n")
oob = sum(1 for *_, fl in sel if fl == 'OOB')
print(f"selected {len(sel)} placements, {oob} out-of-band (still run, flagged)")
PY

echo "=== main batch start $(date)"
: > $K/res_matrix.txt
while read tag k dep flag; do
  case "$tag" in
    *_es*)           pols="bl dp hyb" ;;   # maxES
    *_af*)           pols="bl dp hyb" ;;   # aboveF
    *)               pols="bl dp" ;;       # e50/e40/ne40/ne50
  esac
  for pol in $pols; do
    for s in 1 2 3 4 5 6 7 8; do
      SET=${tag%%_*}
      echo "$K/tables/${tag}_k${k}.txt $pol $K/sinks_${tag} ${SIM[$SET]} $s"
    done
  done
done < $K/run_spec.txt | xargs -P 14 -n 5 bash -c 'source $K/.assoc; run1 "$1" "$2" "$3" "$4" "$5"' _ >> $K/res_matrix.txt
echo "=== main batch done $(date)"
wc -l $K/res_matrix.txt
grep -c NA $K/res_matrix.txt
echo "CAMPAIGN DONE $(date)"
