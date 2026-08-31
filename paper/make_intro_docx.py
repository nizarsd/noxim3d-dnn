"""Generate paper/intro_draft.docx -- a working document for the Introduction.

No pandoc / python-docx on this machine, so the .docx is written directly:
a docx is a ZIP of OOXML parts.  Minimal valid set is [Content_Types].xml,
_rels/.rels and word/document.xml.  Headings use direct formatting rather
than a styles part, which keeps the file self-contained and editable.

Content is the agreed paragraph plan: P1 as drafted, P2-P5 as points plus
suggested text to take from and rephrase.  Numbers carry their provenance so
rewording cannot silently break a fact.
"""
import zipfile
from xml.sax.saxutils import escape

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

CT = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>'''

RELS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''


def para(text='', size=22, bold=False, italic=False, space_after=140,
         indent=0, color=None):
    rpr = '<w:rPr>'
    if bold:
        rpr += '<w:b/>'
    if italic:
        rpr += '<w:i/>'
    if color:
        rpr += f'<w:color w:val="{color}"/>'
    rpr += f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/></w:rPr>'
    ind = f'<w:ind w:left="{indent}"/>' if indent else ''
    return (f'<w:p><w:pPr>{ind}<w:spacing w:after="{space_after}"/></w:pPr>'
            f'<w:r>{rpr}<w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>')


def h1(t):
    return para(t, size=32, bold=True, space_after=180)


def h2(t):
    return para(t, size=26, bold=True, space_after=120)


def bullet(t, indent=360):
    return para('•  ' + t, indent=indent, space_after=80)


def note(t):
    return para(t, size=19, italic=True, color='806000', space_after=160)


BODY = []
A = BODY.append

A(h1('Introduction — working draft'))
A(note('Paper 1, DATE. Target ~0.75 page. P1 is drafted; P2–P5 give the '
       'points plus suggested text to take from and rephrase. Numbers carry '
       'their source so rewording cannot break a fact.'))

# ---------------------------------------------------------------- P1
A(h2('P1 — The stage (drafted)'))
A(para(
    'Deep Neural Networks (DNNs) have become the dominant workload class '
    'across computing. They underpin the vast majority of AI-based '
    'applications, and DNN inference has become infrastructure, running '
    'continuously from edge devices to warehouse-scale data centers [TPU]. '
    'The latency and energy budget of DNN accelerators is therefore a '
    'first-order design metric, and a primary axis of competition among chip '
    'designers and manufacturers. Weight movement is what drives this budget '
    'in conventional accelerators [Horowitz, Sze]. In-Memory Computing (IMC) '
    'eliminates weight traffic by keeping weights in place and performing '
    'Multiply-Accumulate (MAC) operations locally. This alleviates the '
    'weight-movement bottleneck, improving performance while reducing the '
    'communication energy budget and launching a new generation of IMC DNN '
    'accelerators [Sebastian, ISAAC, PRIME].'))
A(para(
    'However, a single array holds nowhere near enough weights for a full '
    'DNN, making many-tile architectures inevitable. For example, one '
    'ResNet-50 block requires 736 crossbars (CBs) and a full network requires '
    'over ten thousand. Because ADC peripherals have a large area and power '
    'overhead, they are shared across the arrays of a tile. This limits the '
    'number of CBs that fit in a tile, resulting in the computation being '
    'split among hundreds or even thousands of tiles [ISAAC].'))
A(para(
    'The consequence is that IMC does not eliminate communication; it '
    'relocates it. What remains mobile is activation scatter traffic and, '
    'dominantly, partial-sum reduction: at the default packing, roughly 82% '
    'of a block’s bytes converge on a few accumulator tiles via the '
    'on-chip network. The bottleneck that governs both performance and energy '
    'therefore becomes communication, and the design focus shifts from '
    'computation-centric to communication-centric.'))
A(note('Verified: 736 CBs = conv1 4×16 + conv2 18×16 + conv3 2×64 '
       '+ shortcut 4×64. 82% is the reduction share at (8,1,8) — it is '
       '45.6% at (8,2,4), hence “at the default packing”. 20 accumulator '
       'tiles of 92 active. ISAAC’s per-tile crossbar figure is still on the '
       'open-items list — confirm before it anchors §3.'))

# ---------------------------------------------------------------- P2
A(h2('P2 — Hook A: the wrong objective'))
A(bullet('How crossbars are grouped onto tiles — the packing orientation '
         '(r,s) at fixed per-tile density c — decides how much reduction '
         'stays on-tile and how much reaches the network.'))
A(bullet('Practice selects the packing on pre-NoC objectives: utilisation, '
         'tile count, communication volume.'))
A(bullet('The packing fixes a placement-invariant port floor — a per-node '
         'injection/ejection rate no later mapping or routing decision can '
         'lower.'))
A(bullet('Result: minimum-volume and minimum-floor orientations differ in 5 of '
         'the 8 (workload, density) cells where a choice exists.'))
A(para(
    'Suggested: “How the crossbars are grouped onto tiles — the packing '
    'orientation (r,s) at a fixed per-tile density c — decides how much of '
    'that reduction is internalised on-tile and how much reaches the network. '
    'Practice selects this packing on pre-NoC objectives: utilisation, tile '
    'count, communication volume. We show these objectives pick the wrong '
    'point. The packing fixes a placement-invariant port floor that no later '
    'mapping or routing decision can lower, and the minimum-volume orientation '
    'is not the minimum-floor orientation in five of the eight (workload, '
    'density) cells where a choice exists: at c = 16, ResNet-50’s '
    'minimum-volume packing carries a 2.78× higher floor than one costing '
    'only 8% more traffic.”', italic=True))
A(note('Alternative headline if VGG reads better: c = 32, 2.57× floor for 7% '
       'traffic. DeiT-S is the honest counterweight — 1.8–3.2× floor '
       'reduction but at 1.6× the traffic.'))

# ---------------------------------------------------------------- P3
A(h2('P3 — Hook B: the two regimes'))
A(bullet('The floor splits the design space in two, and which side a design '
         'sits on is decided at packing, before any mapping effort.'))
A(bullet('Below it: placement moves delay only in a band around the congestion '
         'knee — 1.34× at light load, 13.6× at the knee, 1.28× '
         'in saturation.'))
A(bullet('Above it: placement takes control — 4.6–31.8× delay '
         'spreads across placements, all three workloads.'))
A(bullet('Optional clause: hop count sets where the delay curve starts; the '
         'binding load sets where it bends.'))
A(para(
    'Suggested: “That floor splits the design space into two regimes, and '
    'which one a design occupies is decided at packing, before any mapping '
    'effort is spent. Below the floor, placement moves delay only within a '
    'band around the congestion knee. Above it, placement takes control '
    'outright, with delay spreads of 4.6–31.8× across placements of a '
    'single packing on all three workloads. The same optimisation is '
    'near-worthless in one regime and decisive in the other.”',
    italic=True))

# ---------------------------------------------------------------- P4
A(h2('P4 — Contributions (four bullets)'))
A(bullet('Layer attribution: the port floor is the packing’s quantity '
         '(placement-invariant, 5.8× span across orientations); peak link '
         'load is the placement’s (7.5× within one packing). Their '
         'maximum is where the layers meet.'))
A(bullet('A regime map: below the floor the orientation sets achievable delay '
         '(1.56–1.80× capacity at fixed density) and minimum-hop '
         'mapping captures nearly all of the rest; above it placement takes '
         'control. Peak link load predicts capacity (negative in 5 of 5 '
         'populations); escape-room metrics do not.'))
A(bullet('Two faces of adaptive selection: above the floor it is an '
         'unconditional throughput lever (1.15× delay, 1.36× p99, '
         '65/71 wins); at the knee it is a robustness lever — it '
         'compresses the delay spread across placements (8 of 8 populations, '
         'up to 7.5×) by rescuing the worst ones, returning the mapping '
         'freedom congestion took away.'))
A(bullet('A negative result with a design consequence: below the floor the '
         'policy choice is placement-specific and offline-unpredictable — '
         'a per-placement oracle beats always-adaptive by 4.2% on delay and '
         '11.6% on p99, and no offline metric calls it. The residual is real '
         'and needs an online signal.'))
A(note('Open: does the design rule (orientation on PF → min-CC map → '
       'then min PL → adaptive everywhere for tail) close this paragraph, '
       'or wait for Results? Claim numbers stay out of the paper.'))

# ---------------------------------------------------------------- P5
A(h2('P5 — Scope and organisation'))
A(para(
    'Suggested: “All results are cycle-accurate simulation on one '
    '6×6×3 substrate over ResNet-50, VGG-16 and DeiT-S blocks '
    '(approximately 20,600 runs, no failures). Thermal effects appear only as '
    'motivation for constrained placements, and the learned selection policy '
    'the final result motivates is left to follow-on work.”',
    italic=True))
A(note('Then one organisation sentence.'))

# ---------------------------------------------------------------- refs
A(h2('Numbers used, with provenance'))
for t in [
    '736 crossbars per ResNet-50 block; over 10,000 for the full network '
    '(25.6 M params / 2,048 weights per 128×128 array).',
    '92 tiles at c = 8 on a 108-node mesh; ~1,560 tiles for the full network.',
    '82% reduction share at (8,1,8); 45.6% at (8,2,4) — packing-specific.',
    '20 accumulator tiles of 92 active; two hottest absorb 32–38% of traffic.',
    'Port floor spans 5.8× over ResNet’s 11 feasible points; peak link '
    'load spans 7.5× within one packing.',
    '5 of 8 cells where minimum-volume and minimum-floor disagree; '
    '2.78× floor for 8% traffic (ResNet c=16); 2.57× for 7% (VGG c=32).',
    'Below-floor placement spread: 1.34× / 13.6× / 1.28× across load.',
    'Above-floor placement spread: 4.6–31.8×, three workloads.',
    'Adaptive selection above floor: 1.153× delay, 1.364× p99, 65/71.',
    'Spread compression: 8 of 8 qualifying populations, best 7.50×.',
    'Oracle vs always-adaptive below floor: 1.042× delay, 1.116× p99.',
]:
    A(bullet(t))

DOC = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
       f'<w:document xmlns:w="{W}"><w:body>' + ''.join(BODY) +
       '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
       '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/>'
       '</w:sectPr></w:body></w:document>')

OUT = '/home/nizar/noxim3d-dnn/paper/intro_draft.docx'
with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as z:
    z.writestr('[Content_Types].xml', CT)
    z.writestr('_rels/.rels', RELS)
    z.writestr('word/document.xml', DOC)
print('wrote', OUT)
