"""OOB patch, stage A: new ladder rungs for out-of-band placements.

For each OOB tag in run_spec.txt: if its ladder brackets the 4-6x band
(some rung <4x, some >4x), add 3 evenly spaced k between the bracketing
rungs; if it never reaches 4x (ResNet aboveF), extend the top by
{1.2,1.44,1.7,2.0,2.4} x its max k.  Writes the tables and
patch_probe_list.txt (table sim) for the probe stage.
"""
import collections, csv, os, sys

H = '/home/nizar/noxim3d-dnn/results_stage3/mapping_pilot/pool1000/hill'
OUT = '/home/nizar/noxim3d-dnn/results_ext/topn/matrix'
TD = '/home/nizar/noxim3d-dnn/traffics_dnn_packing'
sys.path.insert(0, H)

STEM = {'r1628': 'resnet50_bottleneck3_xb128_6x6x3_c16r2s8',
        'v1644': 'vgg16_block3_xb128_6x6x3_c16r4s4',
        'esxd':  'vitsmall_encoder1_xb128_6x6x3_c16r1s16'}
SIM = {'r1628': 38536, 'v1644': 115606, 'esxd': 58097}
CODE2ARM = [('ne40', 'minE40'), ('ne50', 'minE50'), ('e50', 'maxE50'),
            ('e40', 'maxE40'), ('es', 'maxES'), ('af', 'aboveF')]

# ladder depths from the original probe
lad = collections.defaultdict(dict)
for ln in open(f'{OUT}/probe.txt'):
    p = ln.split()
    if p[3] == 'NA':
        continue
    tag, k = p[0].rsplit('_k', 1)
    lad[tag][int(k)] = float(p[3])

oob = [ln.split()[0] for ln in open(f'{OUT}/run_spec.txt') if ln.split()[3] == 'OOB']

# perms: arms_ + arms2_ CSVs
perms = {}
for pack in STEM:
    for fn in (f'{OUT}/arms_{pack}.csv', f'{OUT}/arms2_{pack}.csv'):
        if not os.path.exists(fn):
            continue
        for r in csv.DictReader(open(fn)):
            if r['arm'] == 'minCC':
                continue
            code = dict((a, c) for c, a in CODE2ARM)[r['arm']]
            perms[f"{pack}_{code}{r['start'][3:]}"] = r['perm']

plist = open(f'{OUT}/patch_probe_list.txt', 'w')
n = 0
cur_pack = None
for tag in oob:
    pack = tag.split('_')[0]
    ks = sorted(lad[tag]); ff = lad[tag][ks[0]]
    dep = {k: lad[tag][k] / ff for k in ks}
    above = [k for k in ks if dep[k] > 4.0]
    if above:
        hi = min(above)
        lo = max([k for k in ks if k < hi and dep[k] < 4.0])
        new = [lo + (hi - lo) * i // 4 for i in (1, 2, 3)]
    else:
        top = ks[-1]
        new = [int(top * f) for f in (1.2, 1.44, 1.7, 2.0, 2.4)]
    new = sorted({k for k in new if k not in lad[tag]})
    if pack != cur_pack:
        os.environ['DNN_BASE_TABLE'] = f'{TD}/{STEM[pack]}.txt'
        for m in ('metrics',):
            sys.modules.pop(m, None)
        import metrics as M
        cur_pack = pack
    perm = dict(zip(M.USED, map(int, perms[tag].split())))
    for k in new:
        fn = f'{OUT}/tables/{tag}_k{k:04d}.txt'
        with open(fn, 'w') as f:
            for s, d, pir, on, off in M.ROWS:
                v = pir * k / 1000.0
                f.write(f"{perm[s]:5d} {perm[d]:5d} {v:.10f} {v:.10f} "
                        f"{on:>8} {off:>8} {M.PERIOD:>8}\n")
        plist.write(f'{fn} {SIM[pack]}\n')
        n += 1
plist.close()
print(f'patch: {len(oob)} OOB tags, {n} new rung tables')
