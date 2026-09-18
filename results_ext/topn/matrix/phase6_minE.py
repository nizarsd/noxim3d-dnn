"""Phase 6: min-E arms at the SAME per-workload CC budget as the max-E arms,
in both regimes — the paired contrast that isolates escape room from CC.

  bN : below floor (PL <= 0.90 x PF), CC in the b2/aE target band, min E
  aN : above floor (PL in 1.08-1.12 x PF), same CC band, min E

Target CCx per workload = mean CCx of arms4 (aE). Stage A moves CC into the
band; stage B minimises E inside it.
"""
import collections, csv, multiprocessing as mp, os, random, statistics as st, sys
H='/home/nizar/noxim3d-dnn/results_stage3/mapping_pilot/pool1000/hill'
OUT='/home/nizar/noxim3d-dnn/results_ext/topn/matrix'
TD='/home/nizar/noxim3d-dnn/traffics_dnn_packing'
sys.path.insert(0,H); sys.path.insert(0,OUT)
import phase1_arms as PA
PACKS=[('r1628','resnet50_bottleneck3_xb128_6x6x3_c16r2s8',0.258178,
        [400,700,1000,1400,1700,1800,2100],[400,700,1000,1400,1700,1800,2100]),
       ('v1644','vgg16_block3_xb128_6x6x3_c16r4s4',0.942699,
        [150,250,400,430,450,480,520],[60,100,150,200,250,320,400]),
       ('esxd','vitsmall_encoder1_xb128_6x6x3_c16r1s16',0.905396,
        [470,550,580,600,620,650,700],[150,250,350,450,550,650,760])]
TOL=0.04; STEPS,KN=300,50; BAND=(1.08,1.12); PL_CAP=0.90
M=None; EA=None; TARGET=None
def job(a):
    pk,i,p0,p_af,PF,regime=a
    cc=lambda p: M.metrics(p)[2]; cc0=cc(p0); tgt=TARGET*cc0
    if regime=='below':
        place=lambda p: PA.stats(p)[0]<=PL_CAP*PF; start=dict(p0)
    else:
        place=lambda p: BAND[0]*PF<=PA.stats(p)[0]<=BAND[1]*PF; start=dict(p_af)
    rng=random.Random(hash((pk,i,regime,'minE'))&0xffff)
    perm=dict(start); idle=[n for n in range(108) if n not in set(perm.values())]
    for _ in range(STEPS):                       # stage A: CC into band
        if abs(cc(perm)-tgt)<=TOL*cc0: break
        cur=abs(cc(perm)-tgt); found=None
        for _ in range(KN):
            p2=dict(perm)
            if idle and rng.random()<0.3: p2[rng.choice(M.USED)]=rng.choice(idle)
            else:
                x,y=rng.sample(M.USED,2); p2[x],p2[y]=perm[y],perm[x]
            if not place(p2): continue
            v=abs(cc(p2)-tgt)
            if v<cur-1e-9 and (found is None or v<found[0]): found=(v,p2)
        if found is None: break
        cur,perm=found; idle=[n for n in range(108) if n not in set(perm.values())]
    band=lambda p: abs(cc(p)-tgt)<=TOL*cc0 and place(p)
    if band(perm):                               # stage B: min E in band
        cur=EA.local(perm)[1]
        for _ in range(STEPS):
            found=None
            for _ in range(KN):
                p2=dict(perm)
                if idle and rng.random()<0.3: p2[rng.choice(M.USED)]=rng.choice(idle)
                else:
                    x,y=rng.sample(M.USED,2); p2[x],p2[y]=perm[y],perm[x]
                if not band(p2): continue
                v=EA.local(p2)[1]
                if v<cur-1e-12 and (found is None or v<found[0]): found=(v,p2)
            if found is None: continue
            cur,perm=found; idle=[n for n in range(108) if n not in set(perm.values())]
    s=PA.stats(perm)
    return dict(arm='bN' if regime=='below' else 'aN',start=f'int{i}',
                E=round(EA.local(perm)[1],4),ES=round(s[1],4),E50=round(s[2],4),
                E40=round(s[3],4),PL_PF=round(s[0]/PF,4),CCx=round(cc(perm)/cc0,4),
                perm=' '.join(str(perm[n]) for n in M.USED))
if __name__=='__main__':
    for pk,stem,pf,ks_b,ks_a in PACKS:
        TARGET=st.mean(float(r['CCx']) for r in csv.DictReader(open(f'{OUT}/arms4_{pk}.csv')))
        globals()['TARGET']=TARGET
        os.environ['DNN_BASE_TABLE']=f'{TD}/{stem}.txt'
        for m in ('metrics','escapable_analytic'): sys.modules.pop(m,None)
        import metrics as M_, escapable_analytic as EA_
        M,EA=M_,EA_; PA.M=M_; globals()['M'],globals()['EA']=M_,EA_
        mins={}; afs={}
        for r in csv.reader(open(f'/home/nizar/noxim3d-dnn/results_ext/topn/int6/perms_{pk}.csv')):
            if r[0].startswith('int'): mins[r[0][3:]]=dict(zip(M.USED,map(int,r[3].split())))
        for r in csv.DictReader(open(f'{OUT}/arms2_{pk}.csv')):
            if r['arm']=='aboveF': afs[r['start'][3:]]=dict(zip(M.USED,map(int,r['perm'].split())))
        base=[(pk,int(i),mins[i],afs.get(i,mins[i]),pf) for i in sorted(mins)[:8]]
        for regime,code,ks in (('below','bN',ks_b),('above','aN',ks_a)):
            args=[t+(regime,) for t in base]
            with mp.Pool(8) as pool: rows=pool.map(job,args)
            with open(f'{OUT}/arms6_{code}_{pk}.csv','w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
            cc=[r['CCx'] for r in rows]; E=[r['E'] for r in rows]
            print(f"{pk} {code}: target CCx {TARGET:.2f}  achieved {st.mean(cc):.2f} "
                  f"[{min(cc):.2f}..{max(cc):.2f}]  E {st.mean(E):.3f} [{min(E):.2f}..{max(E):.2f}]  "
                  f"PL/PF {st.mean(r['PL_PF'] for r in rows):.2f}",flush=True)
            for r in rows:
                perm=dict(zip(M.USED,map(int,r['perm'].split())))
                tag=f"{pk}_{code}{r['start'][3:]}"
                for k in ks:
                    with open(f'{OUT}/tables/{tag}_k{k:04d}.txt','w') as f:
                        for s,d,pir,on,off in M.ROWS:
                            v=pir*k/1000.0
                            f.write(f"{perm[s]:5d} {perm[d]:5d} {v:.10f} {v:.10f} {on:>8} {off:>8} {M.PERIOD:>8}\n")
                vol=collections.Counter()
                for s,d,pir,on,off in M.ROWS: vol[perm[d]]+=pir*(off-on)
                with open(f'{OUT}/sinks_{tag}','w') as f:
                    for d2,_ in vol.most_common(): f.write(f'{d2}\n')
    print('PHASE6 DONE')
