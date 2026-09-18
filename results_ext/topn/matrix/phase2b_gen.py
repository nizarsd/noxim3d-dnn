"""Phase 2 (arms2): ladder tables + sinkfiles for minE40/minE50/aboveF.

Same as phase2_gen_tables.py but reads arms2_<pack>.csv. aboveF placements get
a down-extended ladder (their knee sits earlier), anchored at their own
lightest rung per the per-placement banding convention.
"""
import collections, csv, os, sys

H = '/home/nizar/noxim3d-dnn/results_stage3/mapping_pilot/pool1000/hill'
OUT = '/home/nizar/noxim3d-dnn/results_ext/topn/matrix'
TD = '/home/nizar/noxim3d-dnn/traffics_dnn_packing'
sys.path.insert(0, H)

PACKS = [
    ('r1628', 'resnet50_bottleneck3_xb128_6x6x3_c16r2s8',
     [400, 700, 1000, 1400, 1700, 1800, 2100], [100, 150, 250, 400, 550, 700, 1000]),
    ('v1644', 'vgg16_block3_xb128_6x6x3_c16r4s4',
     [150, 250, 400, 430, 450, 480, 520], [60, 100, 150, 200, 250, 320, 400]),
    ('esxd',  'vitsmall_encoder1_xb128_6x6x3_c16r1s16',
     [470, 550, 580, 600, 620, 650, 700], [150, 250, 350, 450, 550, 650, 760]),
]
ARM = {'minE40': 'ne40', 'minE50': 'ne50', 'aboveF': 'af'}

n = 0
for pack, stem, ks_below, ks_above in PACKS:
    os.environ['DNN_BASE_TABLE'] = f'{TD}/{stem}.txt'
    for m in ('metrics', 'escapable_analytic'):
        sys.modules.pop(m, None)
    import metrics as M
    for r in csv.DictReader(open(f'{OUT}/arms2_{pack}.csv')):
        perm = dict(zip(M.USED, map(int, r['perm'].split())))
        assert len(set(perm.values())) == len(M.USED)
        tag = f"{pack}_{ARM[r['arm']]}{r['start'][3:]}"
        ks = ks_above if r['arm'] == 'aboveF' else ks_below
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
print(f'phase2b: wrote {n} tables + sinkfiles')
