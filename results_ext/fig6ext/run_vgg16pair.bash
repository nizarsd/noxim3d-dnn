#!/bin/bash
# VGG-16 c=16 packing pair (min-PF (16,4,4) vs min-BW (16,8,2)) — same protocol
# as ladder_po2.py cells: 3 min-CC placements/arm, shared k ladder, BL+DP, 3 seeds.
cd /home/nizar/noxim3d-dnn || exit 1
K=results_ext/fig6ext
H=results_stage3/mapping_pilot/pool1000/hill
python3 - <<'PY'
import csv, multiprocessing as mp, os, random, sys
H='/home/nizar/noxim3d-dnn/results_stage3/mapping_pilot/pool1000/hill'
K='/home/nizar/noxim3d-dnn/results_ext/fig6ext'
TD='/home/nizar/noxim3d-dnn/traffics_dnn_packing'
ARMS=[dict(tag='flowPO', stem='vgg16_block3_xb128_6x6x3_c16r4s4', PF=0.942699, note='min-PF'),
      dict(tag='basePO', stem='vgg16_block3_xb128_6x6x3_c16r8s2', PF=1.193633, note='min-BW')]
STEPS,KN,NSEED=320,50,3
def load(stem):
    os.environ['DNN_BASE_TABLE']=f'{TD}/{stem}.txt'
    for m in ('metrics','escapable_analytic'): sys.modules.pop(m,None)
    sys.path.insert(0,H); import metrics as M; return M
def job(a):
    arm,seed=a
    M=load(arm['stem']); rng=random.Random(seed); used=M.USED
    perm=dict(zip(used,rng.sample(range(108),len(used)))); cc=M.metrics(perm)[2]
    idle=[n for n in range(108) if n not in set(perm.values())]
    for _ in range(STEPS):
        found=None
        for _ in range(KN):
            p2=dict(perm)
            if idle and rng.random()<0.3: p2[rng.choice(used)]=rng.choice(idle)
            else:
                x,y=rng.sample(used,2); p2[x],p2[y]=perm[y],perm[x]
            v=M.metrics(p2)[2]
            if v<cc-1e-9 and (found is None or v<found[0]): found=(v,p2)
        if found is None: continue
        cc,perm=found; idle=[n for n in range(108) if n not in set(perm.values())]
    pl,pr,cc,pv=M.metrics(perm)
    return dict(arm=arm['tag'],note=arm['note'],seed=seed,stem=arm['stem'],
                PF=arm['PF'],PL=round(pl,6),PL_PF=round(pl/arm['PF'],4),CC=round(cc,1),
                perm=' '.join(str(perm[n]) for n in M.USED))
args=[(a,900+10*i+j) for i,a in enumerate(ARMS) for j in range(NSEED)]
with mp.Pool(6) as pool: out=pool.map(job,args)
with open(f'{K}/ladder_vgg16_placements.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
for r in out: print(f"{r['arm']} seed {r['seed']} PL/PF {r['PL_PF']:.3f} CC {r['CC']:.0f}")
# tables
KS=[0.05,0.10,0.15,0.25,0.40,0.60,0.90,1.30]
os.makedirs(f'{K}/tables',exist_ok=True)
n=0
for stem in sorted({r['stem'] for r in out}):
    M=load(stem)
    for r in [x for x in out if x['stem']==stem]:
        perm=dict(zip(M.USED,map(int,r['perm'].split())))
        for k in KS:
            with open(f"{K}/tables/{r['arm']}_{r['seed']}_k{int(round(k*1000)):04d}.txt",'w') as f:
                for s,d,pir,on,off in M.ROWS:
                    v=pir*k; f.write(f"{perm[s]:5d} {perm[d]:5d} {v:.10f} {v:.10f} {on:>8} {off:>8} {M.PERIOD:>8}\n")
            n+=1
print(f'wrote {n} tables')
PY
run1(){ # tab pol seed
  local SEL="-sel bufferlevel"; [ "$1" = dp ] && SEL="-sel dp -dpcost occupancy -cinterval 648"
  out=$(timeout 2400 ./noxim -size 16 16 -dimx 6 -dimy 6 -dimz 3 -buffer 16 -routing oddevenbalanced \
        $SEL -warmup 1944 -sim 115606 -seed $2 -traffic table $0 2>/dev/null)
  a=$(echo "$out"|grep -oP "average delay \(cycles\): \K[0-9.]+")
  p=$(echo "$out"|grep -oP "^% Delay p99 \(cycles\): \K[0-9.]+")
  echo "$(basename $0 .txt) $1 $2 ${a:-NA} ${p:-NA}"
}
export -f run1
for pol in bl dp; do
  : > $K/res_ladder_vgg16_${pol}.txt
  ls $K/tables/*.txt | while read f; do for s in 1 2 3; do echo "$f $pol $s"; done; done \
    | xargs -P 14 -n 3 bash -c 'run1 "$@"' >> $K/res_ladder_vgg16_${pol}.txt
done
echo "VGG16PAIR DONE $(date)"
wc -l $K/res_ladder_vgg16_bl.txt $K/res_ladder_vgg16_dp.txt
