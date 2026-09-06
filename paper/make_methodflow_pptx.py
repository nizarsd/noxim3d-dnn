"""Editable PowerPoint version of fig_methodflow.tex -- native shapes, no deps.

Every box, arrow, node and label is a real DrawingML shape (stdlib zipfile
only; no python-pptx).  Geometry is taken from the TikZ source: the same
coordinate system in cm, mapped to EMU.  Slide 2 holds the rendered PNG for
reference.

    python3 make_methodflow_pptx.py   ->  figs/fig_methodflow.pptx
"""
import os
import zipfile
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'figs', 'fig_methodflow.pptx')
PNG = '/tmp/claude-1000/-home-nizar-noxim3d-dnn/94edddd2-19fb-4377-84c8-c822550a61f2/scratchpad/fig_hi-1.png'

CM = 360000                       # EMU per cm
X0, Y0 = 2.25, 5.95               # tikz -> slide: X = x + X0, Y = Y0 - y
SLIDE_W, SLIDE_H = 18.8, 7.6      # cm

PACK, MAP, ROUTE = '2A78D6', 'EB6834', '1BAF7A'
INK, INK2, FAINT, GRIDL = '101720', '3A4653', '9AA5B1', 'C9D2DB'
FONT = 'Times New Roman'


def mix(hexc, pct, base='FFFFFF'):
    """tikz  colour!pct  against white."""
    a = [int(hexc[i:i+2], 16) for i in (0, 2, 4)]
    b = [int(base[i:i+2], 16) for i in (0, 2, 4)]
    return ''.join(f'{round(x*pct/100 + y*(1-pct/100)):02X}' for x, y in zip(a, b))


def emu(v_cm):
    return int(round(v_cm * CM))


class Deck:
    def __init__(self):
        self.shapes, self.n = [], 1

    def _id(self):
        self.n += 1
        return self.n

    # ---- text runs -> <a:p> list ------------------------------------------
    @staticmethod
    def _runs(paras, size, color, align):
        out = []
        for para in paras:
            if isinstance(para, str):
                para = [(para, False, None)]
            rs = ''
            for text, bold, col in para:
                col = col or color
                rs += (f'<a:r><a:rPr lang="en-US" sz="{int(size*100)}"'
                       f'{" b=\"1\"" if bold else ""} dirty="0">'
                       f'<a:solidFill><a:srgbClr val="{col}"/></a:solidFill>'
                       f'<a:latin typeface="{FONT}"/><a:cs typeface="{FONT}"/>'
                       f'</a:rPr><a:t>{escape(text)}</a:t></a:r>')
            out.append(f'<a:p><a:pPr algn="{align}"/>{rs}</a:p>')
        return ''.join(out)

    # ---- box --------------------------------------------------------------
    def box(self, x, y, w, h, paras=(), *, fill=None, line=None, lw=0.75,
            rounded=False, size=7, color=INK, align='l', anchor='ctr',
            dash=None, rot=0, shape=None, inset=0.12, name='box'):
        """(x,y) = tikz centre in cm; w,h in cm."""
        X, Y = emu(x + X0 - w/2), emu(Y0 - y - h/2)
        prst = shape or ('roundRect' if rounded else 'rect')
        geom = (f'<a:prstGeom prst="{prst}"><a:avLst>'
                + ('<a:gd name="adj" fmla="val 12000"/>' if prst == 'roundRect' else '')
                + '</a:avLst></a:prstGeom>')
        fillx = (f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>'
                 if fill else '<a:noFill/>')
        if line:
            ln = (f'<a:ln w="{int(lw*12700)}"><a:solidFill><a:srgbClr val="{line}"/>'
                  f'</a:solidFill>{f"<a:prstDash val=\"{dash}\"/>" if dash else ""}</a:ln>')
        else:
            ln = '<a:ln><a:noFill/></a:ln>'
        ins = emu(inset)
        body = (f'<p:txBody><a:bodyPr wrap="square" lIns="{ins}" tIns="{ins//2}" '
                f'rIns="{ins}" bIns="{ins//2}" anchor="{anchor}"><a:normAutofit/>'
                f'</a:bodyPr><a:lstStyle/>{self._runs(paras or [""], size, color, align)}'
                f'</p:txBody>')
        self.shapes.append(
            f'<p:sp><p:nvSpPr><p:cNvPr id="{self._id()}" name="{name}"/><p:cNvSpPr/>'
            f'<p:nvPr/></p:nvSpPr><p:spPr><a:xfrm rot="{int(rot*60000)}">'
            f'<a:off x="{X}" y="{Y}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>'
            f'{geom}{fillx}{ln}</p:spPr>{body}</p:sp>')

    def text(self, x, y, w, h, paras, **kw):
        kw.setdefault('inset', 0.02)
        self.box(x, y, w, h, paras, name='text', **kw)

    def dot(self, x, y, r, fill, line=None, lw=0.75):
        self.box(x, y, 2*r, 2*r, fill=fill, line=line, lw=lw, shape='ellipse',
                 name='node')

    # ---- line / arrow -----------------------------------------------------
    def line(self, x1, y1, x2, y2, *, color=INK2, lw=0.8, dash=None,
             arrow=False, name='line'):
        X1, Y1, X2, Y2 = x1 + X0, Y0 - y1, x2 + X0, Y0 - y2
        flipH = ' flipH="1"' if X2 < X1 else ''
        flipV = ' flipV="1"' if Y2 < Y1 else ''
        X, Y = emu(min(X1, X2)), emu(min(Y1, Y2))
        W, H = emu(abs(X2 - X1)), emu(abs(Y2 - Y1))
        tail = '<a:tailEnd type="triangle" w="med" len="med"/>' if arrow else ''
        dsh = f'<a:prstDash val="{dash}"/>' if dash else ''
        self.shapes.append(
            f'<p:cxnSp><p:nvCxnSpPr><p:cNvPr id="{self._id()}" name="{name}"/>'
            f'<p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr><p:spPr>'
            f'<a:xfrm{flipH}{flipV}><a:off x="{X}" y="{Y}"/><a:ext cx="{W}" cy="{H}"/></a:xfrm>'
            f'<a:prstGeom prst="straightConnector1"><a:avLst/></a:prstGeom>'
            f'<a:ln w="{int(lw*12700)}" cap="rnd"><a:solidFill><a:srgbClr val="{color}"/>'
            f'</a:solidFill>{dsh}{tail}</a:ln></p:spPr></p:cxnSp>')

    def path(self, pts, **kw):
        arrow = kw.pop('arrow', False)
        for i in range(len(pts) - 1):
            self.line(*pts[i], *pts[i+1], arrow=(arrow and i == len(pts) - 2), **kw)

    # ---- freeform polygon -------------------------------------------------
    def poly(self, pts, *, fill, line, lw=0.5, name='plane'):
        xs = [p[0] + X0 for p in pts]
        ys = [Y0 - p[1] for p in pts]
        x0, y0, w, h = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
        pth = ''.join(
            ('<a:moveTo>' if i == 0 else '<a:lnTo>')
            + f'<a:pt x="{emu(x - x0)}" y="{emu(y - y0)}"/>'
            + ('</a:moveTo>' if i == 0 else '</a:lnTo>')
            for i, (x, y) in enumerate(zip(xs, ys))) + '<a:close/>'
        self.shapes.append(
            f'<p:sp><p:nvSpPr><p:cNvPr id="{self._id()}" name="{name}"/><p:cNvSpPr/>'
            f'<p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{emu(x0)}" y="{emu(y0)}"/>'
            f'<a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm><a:custGeom><a:avLst/>'
            f'<a:gdLst/><a:ahLst/><a:cxnLst/><a:rect l="0" t="0" r="r" b="b"/>'
            f'<a:pathLst><a:path w="{emu(w)}" h="{emu(h)}">{pth}</a:path></a:pathLst>'
            f'</a:custGeom><a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>'
            f'<a:ln w="{int(lw*12700)}"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill>'
            f'</a:ln></p:spPr><p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>')


# =============================================================== the figure
def build(d=None):
    d = d if d is not None else Deck()
    B = lambda t, c=None: (t, True, c)        # bold run
    N = lambda t, c=None: (t, False, c)       # normal run

    # ---- inputs
    d.box(0.0, 5.35, 2.7, 0.55, ['DNN layer shapes'], fill=mix(GRIDL, 30),
          line=INK2, lw=0.6, rounded=True, size=7.5, align='ctr')
    d.box(3.9, 5.35, 3.6, 0.72, ['hardware: 128×128 CBs,', 'c CBs per tile'],
          fill=mix(GRIDL, 30), line=INK2, lw=0.6, rounded=True, size=7.5, align='ctr')

    # ---- layer blocks (centre x=1.95; widths 5.0)
    d.box(1.95, 3.98, 5.0, 1.72, [
        [B('1  Architecture & packing', PACK)],
        [N('PD: density c (hardware-fixed)')],
        [N('PO: orientation (r,s), r·s = c')],
        [B('choose'), N(' (r,s):  min PF')],
        [N('out: traffic graph (rates, windows),  PF', INK2)]],
        fill=mix(PACK, 6), line=PACK, lw=0.9, rounded=True, size=7, anchor='ctr')
    d.box(1.95, 2.28, 5.0, 1.25, [
        [B('2  Mapping (tile → node)', MAP)],
        [N('place at min CC;  refine: max ES')],
        [N('    s.t. CC ≤ CC_min,  PL ≤ PL(CC_min)')],
        [N('out: placement π,  PL,  CC', INK2)]],
        fill=mix(MAP, 6), line=MAP, lw=0.9, rounded=True, size=7)
    d.box(1.95, 0.62, 5.0, 1.35, [
        [B('3  Routing & selection', ROUTE), N('  (run time)', INK2)],
        [N('odd–even-balanced routing: admissible paths R')],
        [N('selection: BL (1-hop buffer occupancy)')],
        [N('                 DP (multi-hop cost-to-go)')]],
        fill=mix(ROUTE, 6), line=ROUTE, lw=0.9, rounded=True, size=7)
    d.box(1.95, -0.55, 4.6, 0.5, ['delay, p99  ~  BIND = max(PF, PL)'],
          fill='FFFFFF', line=INK2, lw=0.8, rounded=True, size=7.5, align='ctr')

    # ---- flow arrows
    d.path([(0.0, 5.07), (0.0, 4.92), (1.15, 4.92), (1.15, 4.85)], lw=1.0, arrow=True)
    d.path([(3.9, 4.99), (3.9, 4.92), (2.75, 4.92), (2.75, 4.85)], lw=1.0, arrow=True)
    d.line(1.95, 3.11, 1.95, 2.91, lw=1.0, arrow=True)
    d.text(2.75, 3.01, 1.5, 0.25, ['traffic graph'], size=6, color=INK2, align='l')
    d.line(1.95, 1.65, 1.95, 1.30, lw=1.0, arrow=True)
    d.text(2.75, 1.47, 1.5, 0.25, ['placement π'], size=6, color=INK2, align='l')
    d.line(1.95, -0.06, 1.95, -0.30, lw=1.0, arrow=True)

    # ---- nested-search bracket
    d.path([(-0.75, 4.50), (-0.87, 4.50), (-0.87, 1.80), (-0.75, 1.80)],
           color=FAINT, lw=0.6)
    d.text(-1.3, 3.15, 3.0, 0.5, ['nested search:', 'each PO ⇒ own placement space'],
           size=6, color=INK2, align='ctr', rot=-90)

    # ---- the 3D mesh
    ox, oy = 6.85, 0.15
    P = lambda i, j, z: (ox + i*0.80 + j*0.32, oy + j*0.38 + z*1.40)
    for z in (0, 1):
        d.poly([(ox-0.22, oy-0.20+z*1.40), (ox+2.62, oy-0.20+z*1.40),
                (ox+3.58, oy+0.94+z*1.40), (ox+0.74, oy+0.94+z*1.40)],
               fill=mix(GRIDL, 22), line=GRIDL)
    for i in range(4):
        for j in range(3):
            d.line(*P(i, j, 0), *P(i, j, 1), color=FAINT, lw=0.4, dash='sysDot')
    gl = mix(INK2, 40, GRIDL)
    for z in (0, 1):
        for i in range(4):
            for j in range(2):
                d.line(*P(i, j, z), *P(i, j+1, z), color=gl, lw=0.45)
        for i in range(3):
            for j in range(3):
                d.line(*P(i, j, z), *P(i+1, j, z), color=gl, lw=0.45)
    # reduction funnel
    d.path([P(0, 0, 0), P(1, 0, 0), P(1, 1, 0)], color=MAP, lw=0.9, arrow=True)
    d.path([P(0, 2, 0), P(1, 2, 0), P(1, 1, 0)], color=MAP, lw=0.9, arrow=True)
    d.path([P(1, 1, 0), P(2, 1, 0)], color=MAP, lw=2.0, arrow=True)
    d.path([P(3, 0, 0), P(3, 1, 0), P(2, 1, 0)], color=MAP, lw=0.9, arrow=True)
    # routing alternatives
    d.path([P(0, 2, 1), P(2, 2, 1), P(2, 2, 0), P(2, 1, 0)], color=ROUTE, lw=0.9, arrow=True)
    d.path([P(0, 2, 1), P(0, 2, 0), P(0, 1, 0), P(1, 1, 0)], color=ROUTE, lw=0.9,
           dash='dash', arrow=True)
    # nodes
    for z in (0, 1):
        for i in range(4):
            for j in range(3):
                d.dot(*P(i, j, z), 0.055, mix(INK2, 55))
    for (i, j, z) in [(0, 0, 0), (0, 2, 0), (3, 0, 0), (0, 2, 1)]:
        d.dot(*P(i, j, z), 0.085, PACK)
    acc = P(2, 1, 0)
    d.dot(*acc, 0.13, 'FFFFFF', line=MAP, lw=1.1)
    d.dot(*acc, 0.06, MAP)
    # mesh labels
    d.text(ox-0.85, oy+0.05, 1.0, 0.4, ['sender', 'tiles'], size=6, color=PACK, align='r')
    d.text(ox+2.95, oy-0.32, 1.9, 0.4, ['accumulator', '(reduction sink)'],
           size=6, color=MAP, align='l')
    d.text(ox+2.9, oy+3.05, 2.2, 0.4, ['two admissible paths;', 'selection picks one'],
           size=6, color=ROUTE, align='l')
    d.text(ox+1.7, oy-0.85, 3.6, 0.3, ['tiles mapped onto the 6×6×3 mesh'],
           size=6, color=INK2, align='ctr')

    # ---- zoom panel
    zx, zy = 11.95, 0.3
    d.box(zx+1.85, zy+1.475, 4.4, 4.05, fill='FFFFFF', line=FAINT, lw=0.7,
          rounded=True, name='zoom frame')
    d.text(zx+1.9, zy+3.15, 4.0, 0.5, [
        [N('PF = max(PIL, PEL)', INK), N('  — packing-fixed', PACK)],
        [N('PL = max_ℓ Λ_ℓ', INK), N('  — placement-set', MAP)]],
        size=6.5, align='l')
    R = (zx+1.85, zy+1.35)
    T = (zx+1.85, zy-0.12)
    d.box(*R, 1.05, 0.78, ['router'], fill=mix(GRIDL, 35), line=INK2, lw=0.8,
          rounded=True, size=7, align='ctr')
    d.box(*T, 1.05, 0.6, ['tile'], fill=mix(MAP, 8), line=MAP, lw=0.9,
          rounded=True, size=7, align='ctr', color=MAP)
    # ports
    d.line(R[0]-0.22, T[1]+0.30, R[0]-0.22, R[1]-0.39, lw=0.6, arrow=True)
    d.line(R[0]+0.22, R[1]-0.39, R[0]+0.22, T[1]+0.30, color=MAP, lw=2.2, arrow=True)
    d.text(R[0]-0.85, R[1]-0.72, 1.0, 0.4, ['inject', 'PIL'], size=6, align='r')
    d.text(R[0]+0.85, R[1]-0.72, 1.0, 0.4, ['eject', 'PEL'], size=6, color=MAP, align='l')
    # links
    L, Rr = R[0]-0.525, R[0]+0.525
    d.line(L-1.15, R[1]+0.12, L, R[1]+0.12, color=MAP, lw=2.2, arrow=True)
    d.line(L, R[1]-0.12, L-1.15, R[1]-0.12, lw=0.6, arrow=True)
    d.line(Rr+1.15, R[1]+0.12, Rr, R[1]+0.12, lw=0.9, arrow=True)
    d.line(Rr, R[1]-0.12, Rr+1.15, R[1]-0.12, lw=0.6, arrow=True)
    top = R[1]+0.39
    d.line(R[0]-0.12, top+0.62, R[0]-0.12, top, lw=0.8, arrow=True)
    d.line(R[0]+0.12, top, R[0]+0.12, top+0.62, lw=0.6, arrow=True)
    d.line(R[0]-0.425, top, R[0]-0.825, top+0.55, color=FAINT, lw=0.6, dash='sysDot')
    d.line(R[0]+0.425, top, R[0]+0.825, top+0.55, color=FAINT, lw=0.6, dash='sysDot')
    d.text(L-0.58, R[1]+0.40, 1.3, 0.25, ['link load Λ_ℓ'], size=6, color=MAP, align='ctr')
    d.text(zx+2.95, zy-0.3, 1.7, 0.4, ['one port,', 'up to six links'],
           size=6, color=INK2, align='r')

    # ---- leaders
    zl, zt, zb = zx-0.35, zy+3.5, zy-0.55
    d.line(*acc, zl, zt-0.15, color=FAINT, lw=0.5, dash='dash')
    d.line(*acc, zl, zb+0.15, color=FAINT, lw=0.5, dash='dash')
    d.path([(4.45, 3.98), (4.8, 3.98), (zx+1.85, 3.98), (zx+1.85, zt)],
           color=PACK, lw=0.5, dash='dash')
    d.path([(4.45, 2.28), (4.8, 2.28), (6.55, 2.28)], color=MAP, lw=0.5, dash='dash')
    d.path([(4.45, 0.62), (4.8, 0.62), (6.55, 0.62)], color=ROUTE, lw=0.5, dash='dash')
    d.text(5.6, 4.21, 1.4, 0.25, ['sets PF'], size=6, color=PACK, align='l')
    d.text(5.7, 2.51, 1.6, 0.25, ['sets π, PL'], size=6, color=MAP, align='l')
    d.text(5.75, 0.85, 1.6, 0.25, ['picks the path'], size=6, color=ROUTE, align='l')
    return d


# =============================================================== OOXML shell
NS = ('xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
      'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"')


def slide_xml(shapes):
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<p:sld {NS}><p:cSld><p:spTree>'
            f'<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
            f'<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
            f'<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
            f'{"".join(shapes)}</p:spTree></p:cSld>'
            f'<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>')


def pic_slide(png_rel_id, w_cm, h_cm):
    sp = (f'<p:pic><p:nvPicPr><p:cNvPr id="2" name="reference render"/>'
          f'<p:cNvPicPr/><p:nvPr/></p:nvPicPr><p:blipFill><a:blip r:embed="{png_rel_id}"/>'
          f'<a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr><a:xfrm>'
          f'<a:off x="{emu(0.3)}" y="{emu(0.3)}"/><a:ext cx="{emu(w_cm)}" cy="{emu(h_cm)}"/>'
          f'</a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>')
    return slide_xml([sp])


REL = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
       '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
       '{}</Relationships>')
R_SLD = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/'


def theme():
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="fig">'
            '<a:themeElements><a:clrScheme name="fig">'
            '<a:dk1><a:srgbClr val="000000"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>'
            '<a:dk2><a:srgbClr val="3A4653"/></a:dk2><a:lt2><a:srgbClr val="EEEEEE"/></a:lt2>'
            '<a:accent1><a:srgbClr val="2A78D6"/></a:accent1><a:accent2><a:srgbClr val="EB6834"/></a:accent2>'
            '<a:accent3><a:srgbClr val="1BAF7A"/></a:accent3><a:accent4><a:srgbClr val="9AA5B1"/></a:accent4>'
            '<a:accent5><a:srgbClr val="C9D2DB"/></a:accent5><a:accent6><a:srgbClr val="101720"/></a:accent6>'
            '<a:hlink><a:srgbClr val="0563C1"/></a:hlink><a:folHlink><a:srgbClr val="954F72"/></a:folHlink>'
            '</a:clrScheme><a:fontScheme name="fig"><a:majorFont><a:latin typeface="Times New Roman"/>'
            '<a:ea typeface=""/><a:cs typeface=""/></a:majorFont><a:minorFont>'
            '<a:latin typeface="Times New Roman"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont>'
            '</a:fontScheme><a:fmtScheme name="fig"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/>'
            '</a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill>'
            '<a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="6350">'
            '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln w="12700"><a:solidFill>'
            '<a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln w="19050"><a:solidFill>'
            '<a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst>'
            '<a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle>'
            '<a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst>'
            '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/>'
            '</a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst>'
            '</a:fmtScheme></a:themeElements></a:theme>')


def master():
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<p:sldMaster {NS}><p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="FFFFFF"/>'
            f'</a:solidFill><a:effectLst/></p:bgPr></p:bg><p:spTree><p:nvGrpSpPr>'
            f'<p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr>'
            f'<a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/>'
            f'<a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>'
            f'<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" '
            f'accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" '
            f'accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
            f'<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>'
            f'<p:txStyles><p:titleStyle><a:lvl1pPr/></p:titleStyle><p:bodyStyle><a:lvl1pPr/>'
            f'</p:bodyStyle><p:otherStyle><a:lvl1pPr/></p:otherStyle></p:txStyles></p:sldMaster>')


def layout():
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<p:sldLayout {NS} type="blank" preserve="1"><p:cSld name="Blank"><p:spTree>'
            f'<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
            f'<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/>'
            f'<a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>'
            f'<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>')


def main():
    d = build()
    have_png = os.path.exists(PNG)
    slides = [slide_xml(d.shapes)]
    if have_png:
        slides.append(pic_slide('rId2', SLIDE_W - 0.6, (SLIDE_W - 0.6) * 192.676 / 514.122))

    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Default Extension="png" ContentType="image/png"/>'
          '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
          '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
          '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
          '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>'
          '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'
          '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
          + ''.join(f'<Override PartName="/ppt/slides/slide{i+1}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
                    for i in range(len(slides)))
          + '</Types>')

    pres = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<p:presentation {NS}><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/>'
            f'</p:sldMasterIdLst><p:sldIdLst>'
            + ''.join(f'<p:sldId id="{256+i}" r:id="rId{i+2}"/>' for i in range(len(slides)))
            + f'</p:sldIdLst><p:sldSz cx="{emu(SLIDE_W)}" cy="{emu(SLIDE_H)}"/>'
            f'<p:notesSz cx="6858000" cy="9144000"/><p:defaultTextStyle>'
            f'<a:defPPr><a:defRPr lang="en-US"/></a:defPPr><a:lvl1pPr marL="0" algn="l">'
            f'<a:defRPr sz="1800"><a:latin typeface="Times New Roman"/></a:defRPr></a:lvl1pPr>'
            f'</p:defaultTextStyle></p:presentation>')
    pres_rels = REL.format(
        f'<Relationship Id="rId1" Type="{R_SLD}slideMaster" Target="slideMasters/slideMaster1.xml"/>'
        + ''.join(f'<Relationship Id="rId{i+2}" Type="{R_SLD}slide" Target="slides/slide{i+1}.xml"/>'
                  for i in range(len(slides)))
        + f'<Relationship Id="rId{len(slides)+2}" Type="{R_SLD}theme" Target="theme/theme1.xml"/>')

    with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', ct)
        z.writestr('_rels/.rels', REL.format(
            f'<Relationship Id="rId1" Type="{R_SLD}officeDocument" Target="ppt/presentation.xml"/>'
            f'<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            f'<Relationship Id="rId3" Type="{R_SLD}extended-properties" Target="docProps/app.xml"/>'))
        z.writestr('docProps/core.xml',
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            '<dc:title>fig_methodflow</dc:title><dc:creator>noxim3d-dnn</dc:creator>'
            '<dcterms:created xsi:type="dcterms:W3CDTF">2026-09-02T00:00:00Z</dcterms:created>'
            '<dcterms:modified xsi:type="dcterms:W3CDTF">2026-09-02T00:00:00Z</dcterms:modified></cp:coreProperties>')
        z.writestr('docProps/app.xml',
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
            'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
            '<Application>Microsoft Office PowerPoint</Application><Slides>2</Slides>'
            '<AppVersion>15.0000</AppVersion></Properties>')
        z.writestr('ppt/presentation.xml', pres)
        z.writestr('ppt/_rels/presentation.xml.rels', pres_rels)
        z.writestr('ppt/slideMasters/slideMaster1.xml', master())
        z.writestr('ppt/slideMasters/_rels/slideMaster1.xml.rels', REL.format(
            f'<Relationship Id="rId1" Type="{R_SLD}slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
            f'<Relationship Id="rId2" Type="{R_SLD}theme" Target="../theme/theme1.xml"/>'))
        z.writestr('ppt/slideLayouts/slideLayout1.xml', layout())
        z.writestr('ppt/slideLayouts/_rels/slideLayout1.xml.rels', REL.format(
            f'<Relationship Id="rId1" Type="{R_SLD}slideMaster" Target="../slideMasters/slideMaster1.xml"/>'))
        z.writestr('ppt/theme/theme1.xml', theme())
        for i, sx in enumerate(slides):
            z.writestr(f'ppt/slides/slide{i+1}.xml', sx)
            rels = f'<Relationship Id="rId1" Type="{R_SLD}slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
            if i == 1:
                rels += f'<Relationship Id="rId2" Type="{R_SLD}image" Target="../media/image1.png"/>'
            z.writestr(f'ppt/slides/_rels/slide{i+1}.xml.rels', REL.format(rels))
        if have_png:
            z.write(PNG, 'ppt/media/image1.png')
    print(f'wrote {OUT}  shapes={len(d.shapes)}  slides={len(slides)}')


if __name__ == '__main__':
    main()
