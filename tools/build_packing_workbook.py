"""Build docs/packing_all_wl.xlsx -- every (c,r,s) of every workload, all metrics.

One sheet per workload plus a combined sheet.  Everything is recomputed from the
traffic tables so the workbook is self-consistent and reproducible; nothing is
copied from earlier CSVs.

Columns
  c,r,s                packing density and orientation (r*s = c)
  tiles, flows         occupied nodes, flow-table rows
  crossbars            c * tiles;  occupancy = ideal / crossbars
  bytes_period         total bytes moved per period  (sum pir*(off-on)*FLIT_BYTES)
  BW_GBps              bytes_period / period, at 1 ns/cycle
  PIL, PEL             peak injection / ejection port load, flits/cycle (cap 1.0)
  PF = max(PIL,PEL)    the port floor;  bound = which side binds
  PIL_over_PEL         >1 injection-bound.  shelf_over_PF = PIL/PF
  sust_PIL, sust_PEL   TIME-AVERAGED port loads (peak is over a phase window)
  sust_PF, burst       sust_PF = max of the two;  burst = PF / sust_PF
  k_max                1 / sust_PF -- load multiplier at sustained saturation
  feasible             tiles <= 108 AND sust_PF <= 1   (the two real criteria)
  CC_ident, hops_mean  comm cost and traffic-weighted mean hops, identity placement
  PL_ident, PL_PF_id   peak link load at the identity placement
  n_contrib, top_share, first_hop, E     hot-link anatomy, identity placement

Usage:  python3 tools/build_packing_workbook.py
"""
import collections
import functools
import glob
import math
import os
import re
import sys

sys.path.insert(0, '/home/nizar/noxim3d-dnn/tools')
from oeb_path_diversity import STEP, UP, DN, route_relaxed as route

TD = '/home/nizar/noxim3d-dnn/traffics_dnn_packing'
OUT = '/home/nizar/noxim3d-dnn/docs/packing_all_wl.xlsx'
DX, DY, DZ = 6, 6, 3
F = 16                      # flits per packet
FLIT_BYTES = 4
CLOCK_NS = 1.0
EPS = 1e-9


def xyz(n):
    return (n % DX, (n // DX) % DY, n // (DX * DY))


def nid(c):
    return c[0] + c[1] * DX + c[2] * DX * DY


def hops(a, b):
    p, q = xyz(a), xyz(b)
    return abs(p[0]-q[0]) + abs(p[1]-q[1]) + abs(p[2]-q[2])


@functools.lru_cache(maxsize=None)
def edge_flow(src, dst):
    """({(u,v): fraction of OEB-admissible minimal paths using u->v}, n_paths)."""
    s, d = xyz(src), xyz(dst)

    @functools.lru_cache(maxsize=None)
    def npaths(cur, sxy, din):
        if cur == d:
            return 1
        t = 0
        for k in route(cur, (sxy[0], sxy[1], s[2]), d, din):
            st = STEP[k]
            nxt = (cur[0]+st[0], cur[1]+st[1], cur[2]+st[2])
            t += npaths(nxt, (nxt[0], nxt[1]) if k in (UP, DN) else sxy, k)
        return t

    out = collections.Counter()
    tot = npaths(s, (s[0], s[1]), -1)
    if tot == 0:
        return {}, 0

    def walk(cur, sxy, din, frac):
        if cur == d:
            return
        opts = []
        for k in route(cur, (sxy[0], sxy[1], s[2]), d, din):
            st = STEP[k]
            nxt = (cur[0]+st[0], cur[1]+st[1], cur[2]+st[2])
            n = npaths(nxt, (nxt[0], nxt[1]) if k in (UP, DN) else sxy, k)
            if n > 0:
                opts.append((k, nxt, n))
        tt = sum(n for _, _, n in opts)
        for k, nxt, n in opts:
            fr = frac * n / tt
            out[(nid(cur), nid(nxt))] += fr
            walk(nxt, (nxt[0], nxt[1]) if k in (UP, DN) else sxy, k, fr)

    walk(s, (s[0], s[1]), -1, 1.0)
    return dict(out), tot


def read_table(path):
    rows, period = [], None
    for line in open(path):
        if line.startswith('%') or not line.strip():
            continue
        f = line.split()
        rows.append((int(f[0]), int(f[1]), float(f[2]), int(f[4]), int(f[5])))
        period = int(f[6])
    return rows, period


def analyse(path):
    rows, period = read_table(path)
    used = sorted({r[0] for r in rows} | {r[1] for r in rows})
    perm = {n: n for n in used}                      # identity placement

    # elementary phase intervals -> peak port loads
    cuts = sorted({0, period} | {r[3] for r in rows} | {r[4] for r in rows})
    intervals = []
    for a, b in zip(cuts, cuts[1:]):
        live = [(s, d, pir) for s, d, pir, on, off in rows if on <= a and off >= b]
        if live:
            intervals.append(live)

    pil = pel = 0.0
    for live in intervals:
        inj, ejc = collections.Counter(), collections.Counter()
        for s, d, pir in live:
            inj[perm[s]] += pir * F
            ejc[perm[d]] += pir * F
        if inj:
            pil = max(pil, max(inj.values()))
        if ejc:
            pel = max(pel, max(ejc.values()))

    # time-averaged (sustained) port loads
    sinj, sejc = collections.Counter(), collections.Counter()
    for s, d, pir, on, off in rows:
        w = pir * (off - on) * F / period
        sinj[perm[s]] += w
        sejc[perm[d]] += w
    s_pil = max(sinj.values()) if sinj else 0.0
    s_pel = max(sejc.values()) if sejc else 0.0

    # volume, comm cost, mean hops at identity
    vol_bytes = sum(pir * (off - on) * F * FLIT_BYTES for _, _, pir, on, off in rows)
    cc = sum(pir * (off - on) * F * hops(perm[s], perm[d])
             for s, d, pir, on, off in rows)
    flits = sum(pir * (off - on) * F for _, _, pir, on, off in rows)
    hops_mean = cc / flits if flits else 0.0

    # peak link load + hot-link anatomy at identity
    best = None
    for live in intervals:
        lk = collections.Counter()
        ct = collections.defaultdict(list)
        for s, d, pir in live:
            a, c = perm[s], perm[d]
            lam = pir * F
            ef, _ = edge_flow(a, c)
            for (u, v), fr in ef.items():
                lk[(u, v)] += lam * fr
                ct[(u, v)].append((lam, fr, a))
        if lk:
            hot, pl = max(lk.items(), key=lambda kv: kv[1])
            if best is None or pl > best[1]:
                best = (hot, pl, ct[hot])
    if best:
        hot, pl, cs = best
        shares = sorted((l * f / pl for l, f, _ in cs), reverse=True)
        forced = sum(l for l, f, _ in cs if f > 1 - EPS) / pl
        fh = sum(l * f for l, f, a in cs if a == hot[0]) / pl
        etr = sum(l * f for l, f, a in cs if a != hot[0] and f <= 1 - EPS) / pl
        anat = dict(PL_ident=pl, n_contrib=len(cs), top_share=shares[0],
                    first_hop=fh, E_ident=1 - forced, E_transit_ident=etr)
    else:
        anat = dict(PL_ident=0.0, n_contrib=0, top_share=0.0,
                    first_hop=0.0, E_ident=0.0, E_transit_ident=0.0)

    pf = max(pil, pel)
    s_pf = max(s_pil, s_pel)
    d = dict(tiles=len(used), flows=len(rows), period=period,
             bytes_period=vol_bytes,
             BW_GBps=vol_bytes / (period * CLOCK_NS),
             PIL=pil, PEL=pel, PF=pf,
             bound='inj' if pil >= pel else 'ejc',
             PIL_over_PEL=pil / pel if pel else float('inf'),
             shelf_over_PF=pil / pf if pf else 0.0,
             sust_PIL=s_pil, sust_PEL=s_pel, sust_PF=s_pf,
             burst=pf / s_pf if s_pf else 0.0,
             k_max=1.0 / s_pf if s_pf else float('inf'),
             CC_ident=cc, hops_mean=hops_mean)
    d.update(anat)
    d['PL_PF_ident'] = d['PL_ident'] / pf if pf else 0.0
    return d


COLS = [
    ('c', 'c'), ('r', 'r'), ('s', 's'),
    ('tiles', 'tiles'), ('flows', 'flows'),
    ('crossbars', 'crossbars'), ('occupancy', 'occupancy'),
    ('bytes_period', 'bytes/period'), ('BW_GBps', 'BW (GB/s)'),
    ('PIL', 'PIL'), ('PEL', 'PEL'), ('PF', 'PF'), ('bound', 'bound'),
    ('PIL_over_PEL', 'PIL/PEL'), ('shelf_over_PF', 'shelf PIL/PF'),
    ('sust_PIL', 'sust PIL'), ('sust_PEL', 'sust PEL'), ('sust_PF', 'sust PF'),
    ('burst', 'burst PF/sust'), ('k_max', 'k_max'),
    ('feasible', 'feasible'),
    ('CC_ident', 'CC (identity)'), ('hops_mean', 'mean hops'),
    ('PL_ident', 'PL (identity)'), ('PL_PF_ident', 'PL/PF (identity)'),
    ('n_contrib', 'hot-link flows'), ('top_share', 'top flow share'),
    ('first_hop', 'first-hop share'),
    ('E_ident', 'E (identity)'), ('E_transit_ident', 'E_transit (identity)'),
    ('simulated', 'simulated?'),
]

SIMULATED = {
    ('resnet50_bottleneck3', 8, 1, 8): 'yes - main arm, n=24 above + n=8 below',
    ('vgg16_block3', 32, 8, 4): 'yes - n=22 above',
    ('vgg16_block3', 8, 2, 4): 'yes - n=10 above',
    ('vgg16_block3', 8, 4, 2): 'yes - n=8 above',
    ('vitsmall_encoder1', 8, 1, 8): 'yes - n=7 above',
}


def main():
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    data = collections.defaultdict(list)
    for path in sorted(glob.glob(f'{TD}/*.txt')):
        b = os.path.basename(path)[:-4]
        if '_xb128_6x6x3_' not in b:
            continue
        wl, crs = b.split('_xb128_6x6x3_')
        m = re.match(r'c(\d+)r(\d+)s(\d+)', crs)
        if not m:
            continue
        c, r, s = (int(x) for x in m.groups())
        d = analyse(path)
        d.update(c=c, r=r, s=s, workload=wl, crs=crs)
        d['crossbars'] = c * d['tiles']
        d['simulated'] = SIMULATED.get((wl, c, r, s), '')
        data[wl].append(d)
        print(f"  {wl[:18]:18s} {crs:>9s}  PF {d['PF']:7.4f}  {d['bound']}  "
              f"tiles {d['tiles']:3d}  BW {d['BW_GBps']:6.3f} GB/s")

    for wl, rows in data.items():                    # occupancy + feasibility
        ideal = min(x['crossbars'] for x in rows)
        for x in rows:
            x['occupancy'] = ideal / x['crossbars']
            x['feasible'] = 'yes' if (x['tiles'] <= 108 and x['sust_PF'] <= 1.0) \
                            else 'NO'

    wb = Workbook()
    wb.remove(wb.active)
    hdr_f = Font(bold=True, color='FFFFFF')
    hdr_fill = PatternFill('solid', fgColor='2F6FB2')
    best_fill = PatternFill('solid', fgColor='D6ECD2')
    bad_fill = PatternFill('solid', fgColor='F6D5CC')
    sim_fill = PatternFill('solid', fgColor='FFF2CC')

    def write_sheet(ws, rows, title_note):
        ws.cell(1, 1, title_note).font = Font(bold=True, size=11)
        for j, (_, label) in enumerate(COLS, start=1):
            cell = ws.cell(3, j, label)
            cell.font = hdr_f
            cell.fill = hdr_fill
            cell.alignment = Alignment(horizontal='center', wrap_text=True)
        minpf = min(x['PF'] for x in rows)
        minbw = min(x['BW_GBps'] for x in rows)
        for i, x in enumerate(sorted(rows, key=lambda x: (x['c'], x['r'])), start=4):
            for j, (key, _) in enumerate(COLS, start=1):
                v = x.get(key, '')
                if isinstance(v, float):
                    v = round(v, 6 if abs(v) < 10 else 2)
                cell = ws.cell(i, j, v)
                if key == 'PF' and abs(x['PF'] - minpf) < 1e-12:
                    cell.fill = best_fill
                    cell.font = Font(bold=True)
                if key == 'BW_GBps' and abs(x['BW_GBps'] - minbw) < 1e-12:
                    cell.fill = best_fill
                    cell.font = Font(bold=True)
                if key == 'feasible' and v == 'NO':
                    cell.fill = bad_fill
                if key == 'simulated' and v:
                    cell.fill = sim_fill
        ws.freeze_panes = 'D4'
        for j, (key, label) in enumerate(COLS, start=1):
            ws.column_dimensions[get_column_letter(j)].width = \
                max(9, min(22, len(label) + 3))

    for wl in sorted(data):
        rows = data[wl]
        mpf = min(rows, key=lambda x: x['PF'])
        mbw = min(rows, key=lambda x: x['BW_GBps'])
        note = (f"{wl}  --  {len(rows)} packings on 6x6x3 (108 nodes), "
                f"period {rows[0]['period']} cycles.   "
                f"min-PF: ({mpf['c']},{mpf['r']},{mpf['s']}) PF={mpf['PF']:.4f}   |   "
                f"min-BW: ({mbw['c']},{mbw['r']},{mbw['s']}) "
                f"{mbw['BW_GBps']:.3f} GB/s   "
                f"[green = best in column, orange = infeasible, "
                f"yellow = simulated]")
        write_sheet(wb.create_sheet(wl[:28]), rows, note)

    allrows = [x for rows in data.values() for x in rows]
    ws = wb.create_sheet('ALL', 0)
    ws.cell(1, 1, f"All {len(allrows)} packings, all workloads. "
                  "Port and link capacity are both 1 flit/cycle; PF is the "
                  "fraction of a port consumed at peak. Feasibility = tiles<=108 "
                  "AND sustained port rate <=1.").font = Font(bold=True)
    cols2 = [('workload', 'workload')] + COLS
    for j, (_, label) in enumerate(cols2, start=1):
        cell = ws.cell(3, j, label)
        cell.font = hdr_f
        cell.fill = hdr_fill
        cell.alignment = Alignment(horizontal='center', wrap_text=True)
    for i, x in enumerate(sorted(allrows, key=lambda x: (x['workload'], x['c'], x['r'])),
                          start=4):
        for j, (key, _) in enumerate(cols2, start=1):
            v = x.get(key, '')
            if isinstance(v, float):
                v = round(v, 6 if abs(v) < 10 else 2)
            cell = ws.cell(i, j, v)
            if key == 'feasible' and v == 'NO':
                cell.fill = bad_fill
            if key == 'simulated' and v:
                cell.fill = sim_fill
    ws.freeze_panes = 'B4'
    for j, (key, label) in enumerate(cols2, start=1):
        ws.column_dimensions[get_column_letter(j)].width = \
            max(9, min(24, len(label) + 3))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    wb.save(OUT)
    print(f"\nwrote {OUT}")
    print(f"  sheets: ALL + {', '.join(sorted(data))}")
    print(f"  {len(allrows)} packings, {len(COLS)} metrics each")


if __name__ == '__main__':
    main()
