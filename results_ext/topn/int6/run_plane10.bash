#!/bin/bash
# n=10 plane run at located onsets: base+int x {bl,dp,hyb} x seeds 1-10.
# rungs: r1628 k1800 (both arms); v1644 k0450 (both); v3284 int per selected_int5x
# (base arm = existing flow placements at k0620 tables to be generated? base arm
# for v3284/esxd uses the INT-run's rung on its EXISTING placements' tables:
# v3284 base = flow_v3284 minCC/fairE tables at k0620 (generate); esxd base =
# hill tables at k0600 (generate).
cd /home/nizar/noxim3d-dnn || exit 1
K=results_ext/topn/int6; H=results_stage3/mapping_pilot/pool1000/hill
declare -A SIM=( [r1628]=38536 [v1644]=115606 [esxd]=58097 [v3284]=115606 )
declare -A NN=(  [r1628]=23    [v1644]=25     [esxd]=25    [v3284]=22 )
python3 - <<'PY'
import glob, os
# base-arm tables at the int rungs for v3284 (k0620 from k0500 hill-side? use vgg3284 tables k0500) and esxd (k0600 from hill k0650)
for src,scale,out in ((glob.glob('results_ext/vgg3284/tables_v3284/*_k0500.txt'),620/500,'k0620'),
                      (glob.glob('results_stage3/mapping_pilot/pool1000/hill/tables_esxd/minES_*_k0650.txt'),600/650,'k0600')):
    for f in src:
        tag=os.path.basename(f).rsplit('_k',1)[0]
        pre='v3284_b_' if 'v3284' in f else 'esxd_b_'
        rows=[ln.split() for ln in open(f)]
        with open(f'results_ext/topn/int6/tables/{pre}{tag}_{out}.txt','w') as o:
            for p in rows:
                v=float(p[2])*scale
                o.write(f"{int(p[0]):5d} {int(p[1]):5d} {v:.10f} {v:.10f} {p[4]:>8} {p[5]:>8} {p[6]:>8}\n")
print('base tables done')
PY
run1(){ local f=$1 pol=$2 N=$3 ci=$4 sf=$5 sim=$6 s=$7
  local SEL="-sel bufferlevel"; [ "$pol" != bl ] && SEL="-sel dp -dpcost occupancy -cinterval $ci"
  local TP=""; [ "$pol" = hyb ] && TP="-dptopn $N $sf"
  out=$(timeout 2400 ./noxim -size 16 16 -dimx 6 -dimy 6 -dimz 3 -buffer 16 -routing oddevenbalanced \
        $SEL $TP -warmup 1944 -sim $sim -seed $s -traffic table $f 2>/dev/null)
  a=$(echo "$out"|grep -oP "average delay \(cycles\): \K[0-9.]+")
  p=$(echo "$out"|grep -oP "^% Delay p99 \(cycles\): \K[0-9.]+")
  echo "$(basename $f .txt) $pol $s ${a:-NA} ${p:-NA}"
}
export -f run1
: > $K/res_plane10.txt
{
# r1628 both arms k1800
for f in $K/tables/r1628_*_k1800.txt; do t=$(basename $f _k1800.txt)
  for pol in bl dp hyb; do ci=648; [ $pol = hyb ] && ci=138
    for s in $(seq 1 10); do echo "$f $pol 23 $ci $K/sinks_$t 38536 $s"; done; done; done
# v1644 both arms k0450 (int tables exist; base tables: generate? base had k0400... need k0450 for base too)
for f in $K/tables/v1644_*_k0450.txt; do t=$(basename $f _k0450.txt)
  for pol in bl dp hyb; do ci=648; [ $pol = hyb ] && ci=150
    for s in $(seq 1 10); do echo "$f $pol 25 $ci $K/sinks_$t 115606 $s"; done; done; done
# v3284: int at selected rungs; base at k0620
while read tag k dep; do case $tag in v3284_int*)
  for pol in bl dp hyb; do ci=648; [ $pol = hyb ] && ci=132
    for s in $(seq 1 10); do echo "$K/tables/${tag}_k${k}.txt $pol 22 $ci $K/sinks_${tag#*_} 115606 $s"; done; done;; esac
done < $K/selected_int5x.txt
for f in $K/tables/v3284_b_*_k0620.txt; do t=$(basename $f _k0620.txt); base=${t#v3284_b_}
  for pol in bl dp hyb; do ci=648; [ $pol = hyb ] && ci=132
    for s in $(seq 1 10); do echo "$f $pol 22 $ci results_ext/topn/sinks_v3284_$base 115606 $s"; done; done; done
# esxd: int at k0600; base (minES) at k0600
for f in $K/tables/esxd_int*_k0600.txt; do t=$(basename $f _k0600.txt)
  for pol in bl dp hyb; do ci=648; [ $pol = hyb ] && ci=150
    for s in $(seq 1 10); do echo "$f $pol 25 $ci $K/sinks_${t#*_} 58097 $s"; done; done; done
for f in $K/tables/esxd_b_*_k0600.txt; do t=$(basename $f _k0600.txt); base=${t#esxd_b_}
  for pol in bl dp hyb; do ci=648; [ $pol = hyb ] && ci=150
    for s in $(seq 1 10); do echo "$f $pol 25 $ci results_ext/topn/sinks_$base 58097 $s"; done; done; done
} | xargs -P 14 -n 7 bash -c 'run1 "$0" "$1" "$2" "$3" "$4" "$5" "$6"' >> $K/res_plane10.txt
echo "PLANE10 DONE $(date) rows=$(wc -l < $K/res_plane10.txt) NA=$(grep -c NA $K/res_plane10.txt)" | tee -a $K/../campaign.log
