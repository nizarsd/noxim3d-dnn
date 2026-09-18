#!/bin/bash
# Final stage: waits for PATCH DONE, runs the aboveF N@95 coverage arm,
# then writes ANALYSIS.txt. Fully offline.
cd /home/nizar/noxim3d-dnn || exit 1
K=results_ext/topn/matrix
exec >> $K/campaign.log 2>&1

until grep -q "PATCH DONE" $K/campaign.log; do sleep 300; done
echo "=== finish stage start $(date)"

declare -A SIM=( [r1628]=38536 [v1644]=115606 [esxd]=58097 )
declare -p SIM > $K/.assoc2

# N@95 per aboveF placement from its own table volumes
python3 - <<'PY'
import collections, glob, os
spec = {}
for fn in ('results_ext/topn/matrix/run_spec.txt',
           'results_ext/topn/matrix/run_spec_patch.txt'):
    if os.path.exists(fn):
        for ln in open(fn):
            t, k, dep, flag = ln.split()
            spec[t] = (k, flag)
with open('results_ext/topn/matrix/af_n95_list.txt', 'w') as out:
    for t, (k, flag) in sorted(spec.items()):
        if '_af' not in t or flag != 'OK':
            continue
        tab = f'results_ext/topn/matrix/tables/{t}_k{k}.txt'
        v = collections.Counter()
        for ln in open(tab):
            p = ln.split()
            v[int(p[1])] += float(p[2]) * (int(p[5]) - int(p[4]))
        tot = sum(v.values()); c = 0; N = 0
        for _, x in v.most_common():
            c += x; N += 1
            if c >= 0.95 * tot:
                break
        out.write(f'{t} {k} {N}\n')
print('af_n95_list written')
PY

run95(){ # tag k N sim
  local tab=results_ext/topn/matrix/tables/$1_k$2.txt
  local sinks=results_ext/topn/matrix/sinks_$1
  for s in 1 2 3 4 5 6 7 8; do
    out=$(timeout 2400 ./noxim -size 16 16 -dimx 6 -dimy 6 -dimz 3 -buffer 16 \
          -routing oddevenbalanced -sel dp -dpcost occupancy -cinterval $((6*$3)) \
          -dptopn $3 $sinks -warmup 1944 -sim $4 -seed $s -traffic table $tab 2>/dev/null)
    a=$(echo "$out"|grep -oP "average delay \(cycles\): \K[0-9.]+")
    p=$(echo "$out"|grep -oP "^% Delay p99 \(cycles\): \K[0-9.]+")
    echo "$1_k$2 hyb95 $s ${a:-NA} ${p:-NA}"
  done
}
export -f run95

: > $K/res_af_n95.txt
while read t k N; do
  SET=${t%%_*}
  echo "$t $k $N ${SIM[$SET]}"
done < $K/af_n95_list.txt | xargs -P 7 -n 4 bash -c 'run95 "$1" "$2" "$3" "$4"' _ >> $K/res_af_n95.txt
echo "=== coverage arm done $(date)"

python3 $K/analyze_matrix.py
echo "ALL DONE $(date)"
