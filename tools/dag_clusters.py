"""Cluster-level traffic DAG, one circle per reduce group.

Each layer's tiles form a grid; the tiles sharing a column c reduce into the
accumulator at that column, so (layer, c) is the natural cluster and is drawn
as ONE circle.  Edges are inter-cluster data movement, coloured by the source
layer.  Volume is deliberately NOT encoded -- an edge means "this cluster
sends to that one", nothing more.  Layers are ranked left to right.

  python3 tools/dag_clusters.py <stem> [out_basename]

Reads traffics_dnn_packing/<stem>_{placement,flows}.csv, writes figs/<out>.dot
and renders .pdf/.png if graphviz is present.
"""
import collections
import csv
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PK = os.path.join(ROOT, 'traffics_dnn_packing')
FIGS = os.path.join(ROOT, 'figs')

# one hue per layer, in layer order; readable on white, distinct in grayscale
PALETTE = ['#ffffff', '#7f8c8d', '#4a90d9', '#f2d024', '#2eab6b',
           '#f0932b', '#e03131', '#8e44ad', '#16a085', '#c0392b']

TITLE = {'resnet50_bottleneck3': 'ResNet-50 stage-3 bottleneck',
         'vgg16_block3': 'VGG-16 block 3',
         'vitsmall_encoder1': 'DeiT-S encoder block'}


def load(stem):
    place, order = {}, []
    for r in csv.DictReader(open(f'{PK}/{stem}_placement.csv')):
        if not r['layer'] or r['c'] == '':
            continue                      # idle node
        node = int(r['node'])
        place[node] = (r['layer'], int(r['c']), r['role'])
        if r['layer'] not in order:
            order.append(r['layer'])
    flows = list(csv.DictReader(open(f'{PK}/{stem}_flows.csv')))
    return place, order, flows


def build(stem, out):
    place, order, flows = load(stem)
    colour = {L: PALETTE[i % len(PALETTE)] for i, L in enumerate(order)}
    # a white-filled layer still needs a visible edge/key colour
    ink = {L: ('#555555' if colour[L].lower() == '#ffffff' else colour[L])
           for L in order}

    members = collections.defaultdict(list)
    for n, (L, c, role) in place.items():
        members[(L, c)].append((n, role))

    edges, intra = set(), collections.Counter()
    for f in flows:
        a, b = place.get(int(f['src'])), place.get(int(f['dst']))
        if a is None or b is None:
            continue
        ka, kb = (a[0], a[1]), (b[0], b[1])
        if ka == kb:
            intra[ka] += 1                # hidden inside the circle
        else:
            edges.add((ka, kb, a[0]))

    sizes = {L: sorted({len(members[k]) for k in members if k[0] == L})
             for L in order}
    name = TITLE.get(stem.split('_xb')[0], stem)

    L = []
    L.append('digraph clusters {')
    L.append('  rankdir=LR; splines=line; bgcolor="white"; newrank=true;')
    L.append('  graph [margin=0.3,pad=0.25,nodesep=0.16,ranksep=1.5,'
             'fontname="Helvetica"];')
    L.append('  node [shape=circle,style=filled,fixedsize=true,width=0.34,'
             'label="",penwidth=1.1,color="#333333",fontname="Helvetica"];')
    L.append('  edge [arrowsize=0.45,penwidth=0.7];')
    L.append(f'  labelloc="t"; fontsize=13; label=<<b>{name}</b>'
             '<br/><font point-size="9">one circle = one reduce cluster '
             '(the tiles sharing an accumulator) &#183; arrow = inter-cluster '
             'traffic &#183; colour = source layer &#183; volume not encoded'
             '</font>>;')

    # legend, as a left-hand key like the reference figure
    L.append('  subgraph cluster_key {')
    L.append('    label=""; style="invis";')
    prev = None
    for i, lay in enumerate(order):
        s = sizes[lay]
        n = str(s[0]) if len(s) == 1 else f'{s[0]}-{s[-1]}'
        txt = f'{lay}  ({n} tile{"" if n == "1" else "s"} per cluster)'
        L.append(f'    "key_{i}" [shape=plaintext,style="",fixedsize=false,'
                 f'label=<<table border="0" cellborder="0" cellspacing="1">'
                 f'<tr><td><font face="Helvetica" point-size="15" '
                 f'color="{ink[lay]}">&#9679;</font></td>'
                 f'<td align="left"><font face="Helvetica" point-size="10">'
                 f'{txt}</font></td></tr></table>>];')
        if prev is not None:
            L.append(f'    "key_{i-1}" -> "key_{i}" [style=invis];')
        prev = i
    L.append('  }')

    for lay in order:
        keys = sorted([k for k in members if k[0] == lay], key=lambda k: k[1])
        L.append(f'  // ---- {lay}')
        L.append('  { rank=same; ' + ' '.join(
            f'"{lay}:{c}";' for _, c in keys) + ' }')
        for _, c in keys:
            acc = any(r == 'accumulator' for _, r in members[(lay, c)])
            pen = '1.6' if acc else '1.0'
            L.append(f'  "{lay}:{c}" [fillcolor="{colour[lay]}",'
                     f'penwidth={pen}];')

    for (ka, kb, src_layer) in sorted(edges):
        L.append(f'  "{ka[0]}:{ka[1]}" -> "{kb[0]}:{kb[1]}" '
                 f'[color="{ink[src_layer]}"];')

    L.append('}')

    dot = os.path.join(FIGS, out + '.dot')
    open(dot, 'w').write('\n'.join(L) + '\n')
    print(f'{out}.dot  layers={len(order)}  clusters={len(members)}  '
          f'inter-cluster edges={len(edges)}  (intra-cluster hidden: '
          f'{sum(intra.values())} flows)')
    for fmt in ('pdf', 'png'):
        try:
            subprocess.run(['dot', f'-T{fmt}', dot, '-o',
                            os.path.join(FIGS, f'{out}.{fmt}')], check=True)
        except Exception as e:                       # graphviz absent
            print('  render skipped:', e)
    return dot


if __name__ == '__main__':
    stem = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else 'dagc_' + stem.split('_xb')[0]
    build(stem, out)
