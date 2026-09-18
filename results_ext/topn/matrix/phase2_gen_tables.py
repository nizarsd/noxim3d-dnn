"""Phase 2a: ladder tables + per-placement sinkfiles for the engineered arms.

Tables: matrix/tables/<pack>_<arm><i>_k<k>.txt for the 24 non-minCC placements
per packing, at the same probe ladders (and free-flow anchors) the int arm
used.  Sinkfiles: matrix/sinks_<pack>_<arm><i> — all destinations by
descending byte volume (dptopn takes the first N; N@90 = 23/25/25 per packing,
the established per-packing values).
"""
import collections, csv, os, sys

H = '/home/nizar/noxim3d-dnn/results_stage3/mapping_pilot/pool1000/hill'
OUT = '/home/nizar/noxim3d-dnn/results_ext/topn/matrix'
TD = '/home/nizar/noxim3d-dnn/traffics_dnn_packing'
sys.path.insert(0, H)
os.makedirs(f'{OUT}/tables', exist_ok=True)

PACKS = [
    ('r1628', 'resnet50_bottleneck3_xb128_6x6x3_c16r2s8',
     [400, 700, 1000, 1400, 1700, 1800, 2100]),
    ('v1644', 'vgg16_block3_xb128_6x6x3_c16r4s4',
     [150, 250, 400, 430, 450, 480, 520]),
    ('esxd',  'vitsmall_encoder1_xb128_6x6x3_c16r1s16',
     [470, 550, 580, 600, 620, 650, 700]),
]
ARM = {'maxES': 'es', 'maxE50': 'e50', 'maxE40': 'e40'}

n = 0
for pack, stem, ks in PACKS:
    os.environ['DNN_BASE_TABLE'] = f'{TD}/{stem}.txt'
    for m in ('metrics', 'escapable_analytic'):
        sys.modules.pop(m, None)
    import metrics as M
    for r in csv.DictReader(open(f'{OUT}/arms_{pack}.csv')):
        if r['arm'] == 'minCC':
            continue
        perm = dict(zip(M.USED, map(int, r['perm'].split())))
        assert len(set(perm.values())) == len(M.USED)          # valid perm
        tag = f"{pack}_{ARM[r['arm']]}{r['start'][3:]}"
        for k in ks:
            with open(f"{OUT}/tables/{tag}_k{k:04d}.txt", 'w') as f:
                for s, d, pir, on, off in M.ROWS:
                    v = pir * k / 1000.0
                    f.write(f"{perm[s]:5d} {perm[d]:5d} {v:.10f} {v:.10f} "
                            f"{on:>8} {off:>8} {M.PERIOD:>8}\n")
            n += 1
        vol = collections.Counter()
        for s, d, pir, on, off in M.ROWS:
            vol[perm[d]] += pir * (off - on)
        with open(f'{OUT}/sinks_{tag}', 'w') as f:
            for d2, _ in vol.most_common():
                f.write(f'{d2}\n')
print(f'wrote {n} tables + 72 sinkfiles -> {OUT}/tables')
