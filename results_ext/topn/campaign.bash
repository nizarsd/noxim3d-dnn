#!/bin/bash
# Full -dptopn campaign. Stages A-I, sequential, each internally parallel (J=14).
# All results under results_ext/{topn,vgg3284}. Logs to campaign.log.
cd /home/nizar/noxim3d-dnn || exit 1
R=results_ext/topn; V=results_ext/vgg3284; H=results_stage3/mapping_pilot/pool1000/hill
J=14; LOG=$R/campaign.log
say(){ echo "=== $1  $(date)" | tee -a $LOG; }
runx(){ # tab pol ci topn sinkf sim seed -> one result line on stdout
  local tab=$1 pol=$2 ci=$3 tn=$4 sf=$5 sim=$6 s=$7
  local SEL="-sel bufferlevel"; [ "$pol" != bufferlevel ] && SEL="-sel dp -dpcost occupancy -cinterval $ci"
  local TP=""; [ "$tn" != "-" ] && TP="-dptopn $tn $sf"
  out=$(timeout 2400 ./noxim -size 16 16 -dimx 6 -dimy 6 -dimz 3 -buffer 16 \
        -routing oddevenbalanced $SEL $TP -warmup 1944 -sim $sim -seed $s -traffic table $tab 2>/dev/null)
  a=$(echo "$out"|grep -oP "average delay \(cycles\): \K[0-9.]+")
  p=$(echo "$out"|grep -oP "^% Delay p99 \(cycles\): \K[0-9.]+")
  th=$(echo "$out"|grep -oP "Throughput \(flits/cycle/IP\): \K[0-9.]+")
  echo "$(basename $tab .txt) $pol $s ${a:-NA} ${p:-NA} ${th:-NA}"
}
export -f runx

say "A: VGG(32,8,4) knee probe (96 x 1-seed BL)"
if [ ! -s $V/probe.txt ]; then
ls $V/tables_v3284/*.txt | xargs -P $J -I{} bash -c 'runx {} bufferlevel 648 - - 115606 1' > $V/probe.txt
fi
python3 - <<'PY'
import collections, statistics as st
d=collections.defaultdict(list)
for ln in open('results_ext/vgg3284/probe.txt'):
    p=ln.split()
    if len(p)<6 or p[3]=='NA': continue
    tag,k=p[0].rsplit('_k',1); d[int(k)].append(float(p[3]))
ff=st.mean(d[min(d)])
ks=[k for k in sorted(d) if st.mean(d[k])/ff<30][:5]
open('results_ext/vgg3284/knee_ks.txt','w').write(' '.join(f'{k:04d}' for k in ks))
for k in sorted(d): print(f'  k{k/1000:.2f} ratio {st.mean(d[k])/ff:.1f}x')
print('selected:', ks)
PY

say "B: VGG(32,8,4) ladder BL/DP/hyb-b (+a knee spot), N=13 ci78"
for f in $V/tables_v3284/*_k0200.txt; do t=$(basename $f _k0200.txt)
  [ -s $R/sinks_v3284_$t ] || python3 tools/rank_sinks.py $f $R/sinks_v3284_$t >/dev/null; done
KS=$(cat $V/knee_ks.txt); KNEE=$(echo $KS | awk '{print $NF}')
: > $V/res_ladder.txt
{
for k in $KS; do for f in $V/tables_v3284/*_k${k}.txt; do t=$(basename $f _k${k}.txt)
  for s in 1 2 3; do
    echo "$f bufferlevel 648 - - 115606 $s bl"
    echo "$f dp 648 - - 115606 $s dp"
    echo "$f dp 78 13 $R/sinks_v3284_$t 115606 $s topnb"
    [ "$k" = "$KNEE" ] && echo "$f dp 648 13 $R/sinks_v3284_$t 115606 $s topna"
  done
done; done
} | xargs -P $J -n 8 bash -c 'L=$(runx "$0" "$1" "$2" "$3" "$4" "$5" "$6"); echo "${L/ $1 / $7 }"' >> $V/res_ladder.txt
say "B done: $(wc -l < $V/res_ladder.txt) rows, $(grep -c NA $V/res_ladder.txt) NA"

say "C: bf N-ladder"
: > $R/res_nladder.txt
for k in 0750 0950; do for f in $H/tables_bf/*_k${k}.txt; do t=$(basename $f _k${k}.txt)
  for N in 2 4 8 15 24 40 89; do ci=$((6*N)); [ $ci -gt 648 ] && ci=648
    for s in 1 2 3; do echo "$f dp $ci $N $R/sinks_$t 38536 $s N$N"; done
  done
done; done | xargs -P $J -n 8 bash -c 'L=$(runx "$0" "$1" "$2" "$3" "$4" "$5" "$6"); echo "${L/ dp / $7 }"' >> $R/res_nladder.txt
say "C done: $(wc -l < $R/res_nladder.txt) rows, $(grep -c NA $R/res_nladder.txt) NA"

say "D: bf cinterval ladder (N=15, k0950)"
: > $R/res_ciladder.txt
for f in $H/tables_bf/*_k0950.txt; do t=$(basename $f _k0950.txt)
  for ci in 45 90 162 324 648; do for s in 1 2 3; do
    echo "$f dp $ci 15 $R/sinks_$t 38536 $s ci$ci"; done; done
done | xargs -P $J -n 8 bash -c 'L=$(runx "$0" "$1" "$2" "$3" "$4" "$5" "$6"); echo "${L/ dp / $7 }"' >> $R/res_ciladder.txt
say "D done"

say "E: cc12 hyb-b x10 seeds (N=17 ci102)"
: > $R/res_cc12_full.txt
for t in m1 m2 maxCC1 maxCC2 maxCC3 maxCC4 maxCC5 maxCC6 minCC3 minCC4 minCC5 minCC6; do
  [ -s $R/sinks_cc12_$t ] || python3 tools/rank_sinks.py $H/tables_cc12/$t.txt $R/sinks_cc12_$t >/dev/null
  for s in 1 2 3 4 5 6 7 8 9 10; do echo "$H/tables_cc12/$t.txt dp 102 17 $R/sinks_cc12_$t 38536 $s"; done
done | xargs -P $J -n 7 bash -c 'L=$(runx "$0" "$1" "$2" "$3" "$4" "$5" "$6"); echo "${L/ dp / topnb }"' >> $R/res_cc12_full.txt
say "E done"

say "F: VGG(8,4,2) above-floor guard (N=42 ci252)"
: > $R/res_vgg842_guard.txt
for f in $H/tables_e3_vgg842/*_k0120.txt; do t=$(basename $f _k0120.txt)
  [ -s $R/sinks_g842_$t ] || python3 tools/rank_sinks.py $f $R/sinks_g842_$t >/dev/null; done
for k in 0120 0180 0240 0290 0340 0400 0480 0580; do for f in $H/tables_e3_vgg842/*_k${k}.txt; do
  t=$(basename $f _k${k}.txt)
  for s in 1 2 3; do echo "$f dp 252 42 $R/sinks_g842_$t 115606 $s"; done
done; done | xargs -P $J -n 7 bash -c 'L=$(runx "$0" "$1" "$2" "$3" "$4" "$5" "$6"); echo "${L/ dp / topnb }"' >> $R/res_vgg842_guard.txt
say "F done"

say "G: bf headline seeds 4-10 (BL/DP/hyb-b, k0750+k0950)"
: > $R/res_bf_n10.txt
for k in 0750 0950; do for f in $H/tables_bf/*_k${k}.txt; do t=$(basename $f _k${k}.txt)
  for s in 4 5 6 7 8 9 10; do
    echo "$f bufferlevel 648 - - 38536 $s bl"
    echo "$f dp 648 - - 38536 $s dp"
    echo "$f dp 90 15 $R/sinks_$t 38536 $s topnb"
  done
done; done | xargs -P $J -n 8 bash -c 'L=$(runx "$0" "$1" "$2" "$3" "$4" "$5" "$6"); echo "${L/ $1 / $7 }"' >> $R/res_bf_n10.txt
say "G done"

say "H: DeiT f3 (N27 ci162) + f4 (N16 ci96) hyb-b"
: > $R/res_deit_f34.txt
for SET in f3 f4; do
  N=27; CI=162; [ $SET = f4 ] && N=16 && CI=96
  k0=$(ls $H/tables_$SET | head -1 | grep -oP '_k\K[0-9]+')
  for f in $H/tables_$SET/*_k${k0}.txt; do t=$(basename $f _k${k0}.txt)
    [ -s $R/sinks_${SET}_$t ] || python3 tools/rank_sinks.py $f $R/sinks_${SET}_$t >/dev/null; done
  for f in $H/tables_$SET/*.txt; do
    t=$(basename $f .txt); tag=${t%_k*}
    for s in 1 2 3; do echo "$f dp $CI $N $R/sinks_${SET}_$tag 58097 $s ${SET}"; done
  done
done | xargs -P $J -n 8 bash -c 'L=$(runx "$0" "$1" "$2" "$3" "$4" "$5" "$6"); echo "$7 ${L/ dp / topnb }"' >> $R/res_deit_f34.txt
say "H done"

say "I: N=all equivalence n=27 (bf_0.90 k0750)"
: > $R/res_nall_eq.txt
for s in $(seq 4 30); do
  echo "$H/tables_bf/bf_0.90_0.80_k0750.txt dp 648 - - 38536 $s dp"
  echo "$H/tables_bf/bf_0.90_0.80_k0750.txt dp 648 89 $R/sinks_bf_0.90_0.80 38536 $s topn89"
done | xargs -P $J -n 8 bash -c 'L=$(runx "$0" "$1" "$2" "$3" "$4" "$5" "$6"); echo "${L/ dp / $7 }"' >> $R/res_nall_eq.txt
say "I done -- CAMPAIGN COMPLETE"
