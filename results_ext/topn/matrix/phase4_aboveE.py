"""Phase 4: max-E ABOVE the floor ("aE") — the missing 2x2 cell.

Three-stage generator, continuing the existing above-floor arm:
  stage 1+2 (done, arms2_*.csv): max PL into 1.10xPF +/- 2%, then min CC in band
  stage 3 (here):                max E, holding PL in band and CC <= 1.45 x
                                 the min-CC start's CC (same budget as the bE arm)
Starts are the aboveF placements themselves, so aE differs from aboveF only in
escape room.
"""
import collections, csv, multiprocessing as mp, os, random, statistics as st, sys
H='/home/nizar/noxim3d-dnn/results_stage3/mapping_pilot/pool1000/hill'
OUT='/home/nizar/noxim3d-dnn/results_ext/topn/matrix'
TD='/home/nizar/noxim3d-dnn/traffics_dnn_packing'
sys.path.insert(0,H); sys.path.insert(0,OUT)
import phase1_arms as PA
PACKS=[('r1628','resnet50_bottleneck3_xb128_6x6x3_c16r2s8',0.258178,
        [400,700,1000,1400,1700,1800,2100]),
       ('v1644','vgg16_block3_xb128_6x6x3_c16r4s4',0.942699,
        [60,100,150,200,250,320,400]),
       ('esxd','vitsmall_encoder1_xb128_6x6x3_c16r1s16',0.905396,
        [150,250,350,450,550,650,760])]
CC_BUDGET=1.45; BAND=(1.08,1.12); STEPS,KN=300,50
M=None; EA=None
def job(a):
    pk,i,p_af,p0,PF=a
    cc=lambda p: M.metrics(p)[2]
    cc0=cc(p0)                      # min-CC start's CC = budget reference
    inband=lambda pl: BAND[0]*PF<=pl<=BAND[1]*PF
    ok=lambda p: cc(p)<=CC_BUDGET*cc0 and inband(PA.stats(p)[0])
    rng=random.Random(hash((pk,i,'aE'))&0xffff)
    perm=dict(p_af)
    if not ok(perm):                # start may exceed budget; keep it anyway
        pass
    cur=-EA.local(perm)[1]
    idle=[n for n in range(108) if n not in set(perm.values())]
    for _ in range(STEPS):
        found=None
        for _ in range(KN):
            p2=dict(perm)
            if idle and rng.random()<0.3: p2[rng.choice(M.USED)]=rng.choice(idle)
            else:
                x,y=rng.sample(M.USED,2); p2[x],p2[y]=perm[y],perm[x]
            if not ok(p2): continue
            v=-EA.local(p2)[1]
            if v<cur-1e-12 and (found is None or v<found[0]): found=(v,p2)
        if found is None: continue
        cur,perm=found; idle=[n for n in range(108) if n not in set(perm.values())]
    s=PA.stats(perm)
    return dict(arm='aE',start=f'int{i}',E=round(EA.local(perm)[1],4),
                E0=round(EA.local(p_af)[1],4),ES=round(s[1],4),E50=round(s[2],4),
                E40=round(s[3],4),PL_PF=round(s[0]/PF,4),CCx=round(cc(perm)/cc0,4),
                perm=' '.join(str(perm[n]) for n in M.USED))
if __name__=='__main__':
    import importlib
    for pk,stem,pf,ks in PACKS:
        os.environ['DNN_BASE_TABLE']=f'{TD}/{stem}.txt'
        for m in ('metrics','escapable_analytic'): sys.modules.pop(m,None)
        import metrics as M_, escapable_analytic as EA_
        M,EA=M_,EA_; PA.M=M_; globals()['M'],globals()['EA']=M_,EA_
        mins={}
        for r in csv.reader(open(f'/home/nizar/noxim3d-dnn/results_ext/topn/int6/perms_{pk}.csv')):
            if r[0].startswith('int'): mins[r[0][3:]]=dict(zip(M.USED,map(int,r[3].split())))
        args=[]
        for r in csv.DictReader(open(f'{OUT}/arms2_{pk}.csv')):
            if r['arm']!='aboveF': continue
            i=r['start'][3:]
            args.append((pk,int(i),dict(zip(M.USED,map(int,r['perm'].split()))),mins[i],pf))
        with mp.Pool(8) as pool: rows=pool.map(job,args)
        with open(f'{OUT}/arms4_{pk}.csv','w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
        print(f"{pk}: aE  E {st.mean(r['E'] for r in rows):.3f} "
              f"(aboveF start E {st.mean(r['E0'] for r in rows):.3f})  "
              f"CCx {st.mean(r['CCx'] for r in rows):.2f}  "
              f"PL/PF {st.mean(r['PL_PF'] for r in rows):.3f}",flush=True)
        n=0
        for r in rows:
            perm=dict(zip(M.USED,map(int,r['perm'].split())))
            assert len(set(perm.values()))==len(M.USED)
            tag=f"{pk}_aE{r['start'][3:]}"
            for k in ks:
                with open(f'{OUT}/tables/{tag}_k{k:04d}.txt','w') as f:
                    for s,d,pir,on,off in M.ROWS:
                        v=pir*k/1000.0
                        f.write(f"{perm[s]:5d} {perm[d]:5d} {v:.10f} {v:.10f} {on:>8} {off:>8} {M.PERIOD:>8}\n")
                n+=1
            vol=collections.Counter()
            for s,d,pir,on,off in M.ROWS: vol[perm[d]]+=pir*(off-on)
            with open(f'{OUT}/sinks_{tag}','w') as f:
                for d2,_ in vol.most_common(): f.write(f'{d2}\n')
        print(f"   wrote {n} tables + sinkfiles",flush=True)
    print('PHASE4 DONE')
