"""Ladder tables from any selected-placements CSV.
   usage: gen_tables_generic.py <pack> <sel.csv> <outdir> <k,k,k> [tagcol]"""
import csv, os, sys
pack,sel,outd,kspec = sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4]
tagcol = sys.argv[5] if len(sys.argv)>5 else 'tag'
KS=[float(x) for x in kspec.split(',')]
H=os.path.dirname(os.path.abspath(__file__))
os.environ['DNN_BASE_TABLE']=f'/home/nizar/noxim3d-dnn/traffics_dnn_packing/{pack}.txt'
sys.path.insert(0,H)
import metrics as M
OUT=f'{H}/{outd}'; os.makedirs(OUT,exist_ok=True)
for f in os.listdir(OUT): os.remove(f'{OUT}/{f}')
n=0
for r in csv.DictReader(open(f'{H}/{sel}')):
    perm=M.perm_of(r); assert len(perm)==len(M.USED), f"{len(perm)} vs {len(M.USED)}"
    tag=r[tagcol] if tagcol in r else 'x'
    if 'seed' in r and not tag.endswith(r['seed']): tag=f"{tag}_{r['seed']}"
    for k in KS:
        with open(f"{OUT}/{tag}_k{int(round(k*1000)):04d}.txt",'w') as f:
            for s,d,pir,on,off in M.ROWS:
                v=pir*k
                f.write(f"{perm[s]:5d} {perm[d]:5d} {v:.10f} {v:.10f} {on:>8} {off:>8} {M.PERIOD:>8}\n")
        n+=1
print(f"  wrote {n} tables ({n//len(KS)} placements x {len(KS)} rungs) -> {outd}")
