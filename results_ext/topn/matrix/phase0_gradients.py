"""Phase 0 gradient sanity check for the level-form escape metrics.

Terms: ES (escape slope) = E20 - E5, the paper's tier metric: E_f = escapable
(non-forced) fraction of time-integrated load on the top-f fraction of links
ranked by load.  The LEVEL form E_L(x) uses a load threshold instead of a
count fraction: the tier is every link whose time-integrated load is >= x
times the peak link's, and E_L = 1 - forced/total on that tier.  E50 = x=0.5,
E40 = x=0.4.

Question: are E50/E40 non-degenerate (spread, tier size) and distinct from ES
on random c16 placements?  Flat or single-link tiers -> the arm is dead.

Output: results_ext/topn/matrix/phase0_gradients.txt
"""
import collections, importlib, os, random, statistics as st, sys

H = '/home/nizar/noxim3d-dnn/results_stage3/mapping_pilot/pool1000/hill'
sys.path.insert(0, H)
EPS = 1e-9
PACKS = [
    ('r1628', 'resnet50_bottleneck3_xb128_6x6x3_c16r2s8'),
    ('v1644', 'vgg16_block3_xb128_6x6x3_c16r4s4'),
    ('esxd',  'vitsmall_encoder1_xb128_6x6x3_c16r1s16'),
]
NSAMP = 200


def build(M):
    IV = []
    for a, b in zip(M.CUTS, M.CUTS[1:]):
        live = [(s, d, pir) for s, d, pir, on, off in M.ROWS if on <= a and off >= b]
        if live:
            IV.append((b - a, live))
    return IV


def loads(perm, M, IV):
    ld = collections.Counter(); fd = collections.Counter()
    for dur, live in IV:
        lk = collections.Counter(); fo = collections.Counter()
        for s, d, pir in live:
            a, c = perm[s], perm[d]; lam = pir * M.F
            for e, fr in M.edge_flow(a, c)[0]:
                lk[e] += lam * fr
                if fr > 1 - EPS:
                    fo[e] += lam
        for e, l in lk.items():
            ld[e] += l * dur; fd[e] += fo.get(e, 0.0) * dur
    return ld, fd


def es_tier(ld, fd, f):
    links = sorted(ld.items(), key=lambda kv: -kv[1])
    n = max(1, int(len(links) * f))
    tot = sum(l for _, l in links[:n]); frc = sum(fd[e] for e, _ in links[:n])
    return 1.0 - frc / tot


def e_level(ld, fd, x):
    pk = max(ld.values())
    tier = [e for e, l in ld.items() if l >= x * pk]
    tot = sum(ld[e] for e in tier); frc = sum(fd[e] for e in tier)
    return 1.0 - frc / tot, len(tier)


out = open('/home/nizar/noxim3d-dnn/results_ext/topn/matrix/phase0_gradients.txt', 'w')
def P(s):
    print(s, flush=True); out.write(s + '\n')

for tag, stem in PACKS:
    os.environ['DNN_BASE_TABLE'] = f'/home/nizar/noxim3d-dnn/traffics_dnn_packing/{stem}.txt'
    if 'metrics' in sys.modules:
        M = importlib.reload(sys.modules['metrics'])
    else:
        import metrics as M
    IV = build(M)
    rng = random.Random(4242)
    rows = []
    for i in range(NSAMP):
        perm = dict(zip(M.USED, rng.sample(range(108), len(M.USED))))
        ld, fd = loads(perm, M, IV)
        es = es_tier(ld, fd, 0.20) - es_tier(ld, fd, 0.05)
        e50, n50 = e_level(ld, fd, 0.5)
        e40, n40 = e_level(ld, fd, 0.4)
        rows.append((es, e50, e40, n50, n40))
    def col(i): return [r[i] for r in rows]
    def z(v):
        m = st.mean(v); s = st.pstdev(v)
        return [(x - m) / s if s else 0.0 for x in v]
    def pear(x, y): return st.mean(a * b for a, b in zip(z(x), z(y)))
    es, e50, e40, n50, n40 = (col(i) for i in range(5))
    P(f"=== {tag} ({stem.split('_')[-1]})  n={NSAMP} random perms, "
      f"{len(M.USED)} tiles, {len(IV)} intervals ===")
    for name, v in (('ES', es), ('E50', e50), ('E40', e40)):
        P(f"  {name:4s} {min(v):+.4f} .. {max(v):+.4f}  sd {st.pstdev(v):.4f}")
    P(f"  tier size E50 {min(n50)}..{max(n50)} (med {sorted(n50)[len(n50)//2]}), "
      f"E40 {min(n40)}..{max(n40)} (med {sorted(n40)[len(n40)//2]})")
    P(f"  r(ES,E50) {pear(es, e50):+.3f}  r(ES,E40) {pear(es, e40):+.3f}  "
      f"r(E50,E40) {pear(e50, e40):+.3f}")
    P("")
out.close()
