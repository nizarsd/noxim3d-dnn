#!/bin/bash
# Hybrid over the paper's canonical knee-window cells (the Fig-6 populations),
# per-placement sinkfile + N@90 computed from each tag's own table, ci = 6*N,
# 3 seeds. Output: res_paper_hyb_<set>.txt per set.
cd /home/nizar/noxim3d-dnn || exit 1
R=results_ext/topn; H=results_stage3/mapping_pilot/pool1000/hill
declare -A SIM=( [ladder]=38536 [e7]=58097 [e3_vit]=58097 [e3_vgg]=115606 [e3_vgg824]=115606 [e3_vgg842]=115606 [bf]=38536 [f1]=38536 [f2]=115606 [esxd]=58097 )
declare -A DIR=( [ladder]=tables_ladder_c8r1s8 [e7]=tables_e7 [e3_vit]=tables_e3_vit [e3_vgg]=tables_e3_vgg [e3_vgg824]=tables_e3_vgg824 [e3_vgg842]=tables_e3_vgg842 [bf]=tables_bf [f1]=tables_f1 [f2]=tables_f2 [esxd]=tables_esxd )
declare -A KS=( [ladder]="0300 0400 0500 0550 0600 0650 0700 0750 0800 0850" \
                [e7]="0200 0300 0380 0450 0520 0620 0750" [e3_vit]="0200 0300 0380 0450 0520 0620 0750" \
                [e3_vgg]="0150 0250 0300 0340 0380 0420 0460 0520 0620" \
                [e3_vgg824]="0050 0090 0120 0150 0180 0220" [e3_vgg842]="0120 0180 0240 0290 0340 0400 0480" \
                [bf]="0300 0550 0750 0950" [f1]="0300 0550 0750 0950 1150 1400 1700" \
                [f2]="0150 0250 0350 0450 0550" [esxd]="0470 0550 0650" )
mkdir -p $R/paper_sinks
python3 - <<'PY'
import collections, glob, os
DIR={'ladder':'tables_ladder_c8r1s8','e7':'tables_e7','e3_vit':'tables_e3_vit','e3_vgg':'tables_e3_vgg',
     'e3_vgg824':'tables_e3_vgg824','e3_vgg842':'tables_e3_vgg842','bf':'tables_bf','f1':'tables_f1','f2':'tables_f2','esxd':'tables_esxd'}
H='results_stage3/mapping_pilot/pool1000/hill'
meta=open('results_ext/topn/paper_sinks/meta.txt','w')
for SET,d in DIR.items():
    tabs=sorted(glob.glob(f'{H}/{d}/*.txt'))
    tags={}
    for f in tabs:
        tag=os.path.basename(f).rsplit('_k',1)[0]
        tags.setdefault(tag,f)
    for tag,f in tags.items():
        v=collections.Counter()
        for ln in open(f):
            p=ln.split(); v[int(p[1])]+=float(p[2])*(int(p[5])-int(p[4]))
        tot=sum(v.values()); c=0; N=0; order=[]
        for d2,x in v.most_common():
            order.append(d2); c+=x; N+=1
            if c>=0.9*tot: break
        rest=[d2 for d2,_ in v.most_common()[N:]]
        with open(f'results_ext/topn/paper_sinks/{SET}__{tag}','w') as o:
            for d2 in order+rest: o.write(f'{d2}\n')
        meta.write(f'{SET} {tag} {N} {6*N}\n')
meta.close()
print('sinkfiles done')
PY
for SET in ladder e7 e3_vit e3_vgg e3_vgg824 e3_vgg842 bf f1 f2 esxd; do
  : > $R/res_paper_hyb_${SET}.txt
done
awk '{print $1, $2, $3, $4}' $R/paper_sinks/meta.txt | while read SET tag N ci; do
  for k in ${KS[$SET]}; do
    f=$H/${DIR[$SET]}/${tag}_k${k}.txt
    [ -f "$f" ] || continue
    for s in 1 2 3; do echo "$f $SET $tag $N $ci ${SIM[$SET]} $s"; done
  done
done | xargs -P 14 -n 7 bash -c '
  f=$0; SET=$1; tag=$2; N=$3; ci=$4; sim=$5; s=$6
  out=$(timeout 2400 ./noxim -size 16 16 -dimx 6 -dimy 6 -dimz 3 -buffer 16 -routing oddevenbalanced \
        -sel dp -dpcost occupancy -cinterval $ci -dptopn $N results_ext/topn/paper_sinks/${SET}__${tag} \
        -warmup 1944 -sim $sim -seed $s -traffic table $f 2>/dev/null)
  a=$(echo "$out"|grep -oP "average delay \(cycles\): \K[0-9.]+")
  p=$(echo "$out"|grep -oP "^% Delay p99 \(cycles\): \K[0-9.]+")
  echo "$(basename $f .txt) hyb $s ${a:-NA} ${p:-NA}" >> results_ext/topn/res_paper_hyb_${SET}.txt
'
echo "PAPER-HYB DONE $(date)" | tee -a $R/campaign.log
for SET in ladder e7 e3_vit e3_vgg e3_vgg824 e3_vgg842 bf f1 f2 esxd; do
  echo "$SET rows=$(wc -l < $R/res_paper_hyb_${SET}.txt) NA=$(grep -c NA $R/res_paper_hyb_${SET}.txt)"
done
