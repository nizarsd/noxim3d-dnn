"""min-CC baseline + fair-E mapping (max E s.t. CC<=1.05x AND PL<=PL_minCC).
   usage: flow_search_generic.py <pack> <PF> <tag> [nseed]"""
import collections, csv, multiprocessing as mp, os, random, statistics as st, sys
PACK,PF,TAG = sys.argv[1], float(sys.argv[2]), sys.argv[3]
NSEED = int(sys.argv[4]) if len(sys.argv)>4 else 8
CCBUD=1.05; STEPS,K,EPS=320,60,1e-9
H=os.path.dirname(os.path.abspath(__file__))
os.environ['DNN_BASE_TABLE']=f'/home/nizar/noxim3d-dnn/traffics_dnn_packing/{PACK}.txt'
sys.path.insert(0,H)
import metrics as M
def hot(perm):
    best=None
    for live in M.INTERVALS:
        lk=collections.Counter(); ct=collections.defaultdict(list)
        for s,d,pir in live:
            a,c=perm[s],perm[d]; lam=pir*M.F
            for (u,v),fr in M.edge_flow(a,c)[0]:
                lk[(u,v)]+=lam*fr; ct[(u,v)].append((lam,fr,a))
        if lk:
            h,pl=max(lk.items(),key=lambda kv:kv[1])
            if best is None or pl>best[1]: best=(h,pl,ct[h])
    if not best: return 0.,0.,0.,0.
    h,pl,cs=best
    forced=sum(l for l,f,_ in cs if f>1-EPS)/pl
    etr=sum(l*f for l,f,a in cs if a!=h[0] and f<=1-EPS)/pl
    fh=sum(l*f for l,f,a in cs if a==h[0])/pl
    return pl,1.0-forced,etr,fh
def climb(seed,score,steps=STEPS,constraint=None,start=None):
    rng=random.Random(seed); used=M.USED
    perm=dict(start) if start else dict(zip(used,rng.sample(range(108),len(used))))
    cur=score(perm); idle=[n for n in range(108) if n not in set(perm.values())]
    for _ in range(steps):
        found=None
        for _ in range(K):
            p2=dict(perm)
            if idle and rng.random()<0.3: p2[rng.choice(used)]=rng.choice(idle)
            else:
                a,b=rng.sample(used,2); p2[a],p2[b]=perm[b],perm[a]
            if constraint and not constraint(p2): continue
            v=score(p2)
            if v<cur-1e-12 and (found is None or v<found[0]): found=(v,p2)
        if found is None: continue
        cur,perm=found; idle=[n for n in range(108) if n not in set(perm.values())]
    return perm
def job(seed):
    cc=lambda p: M.metrics(p)[2]
    p_cc=climb(seed,cc); ccmin=cc(p_cc); pl0=hot(p_cc)[0]
    ok=lambda p: cc(p)<=ccmin*CCBUD and hot(p)[0]<=pl0
    p_fe=climb(seed*13+7,lambda p:-hot(p)[1],constraint=ok,start=p_cc)
    out=[]
    for nm,p in (('minCC',p_cc),('fairE',p_fe)):
        pl,e,et,fh=hot(p)
        out.append(dict(arm=nm,seed=seed,PL=round(pl,6),PL_PF=round(pl/PF,4),E=round(e,4),
                        E_transit=round(et,4),first_hop=round(fh,4),CC=round(cc(p),1),
                        CCx=round(cc(p)/ccmin,4),perm=' '.join(str(p[n]) for n in M.USED)))
    return out
if __name__=='__main__':
    with mp.Pool(min(8,NSEED)) as pool: res=pool.map(job,[4000+i for i in range(NSEED)])
    rows=[r for g in res for r in g]
    with open(f'{H}/flow_{TAG}_sel.csv','w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    for arm in ('minCC','fairE'):
        g=[r for r in rows if r['arm']==arm]
        print(f"  {arm:6s} PL/PF {st.mean(r['PL_PF'] for r in g):.3f}  E {st.mean(r['E'] for r in g):.3f}"
              f"  CCx {st.mean(r['CCx'] for r in g):.3f}  ({len(g)} placements, {len(M.USED)} tiles)")
