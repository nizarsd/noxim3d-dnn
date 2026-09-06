"""Methodology figure, version 2 (2026-09-06).

Changes against build() in make_methodflow_pptx.py:
  * the two inputs sit directly above layer 1 and feed it with straight arrows;
  * all three layers feed the 3D NoC: dashed, colour-coded arrows land on a
    border drawn around the 3D mesh (packing blue -> tiles/ports, mapping
    orange -> placement and link load, routing green -> paths);
  * the tile/router detail radiates from the accumulator node only (no lead
    from a layer block to the detail panel);
  * the outcome box (delay, p99) hangs under the NoC, fed by the NoC; the
    predictor B = max(PF, PL) moves to the formula lines of the detail panel.

Outputs (paper/figs/):
  fig_methodflow_editable_v2.svg   editable text, for Inkscape
  fig_methodflow_v2.png            preview (matplotlib, Liberation Serif)
  fig_methodflow_v2.pdf            matplotlib render, TrueType (no Type 3)

    python3 make_methodflow_v2.py
"""
import os
import math

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Ellipse, Polygon, FancyArrowPatch
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextToPath

from make_methodflow_pptx import PACK, MAP, ROUTE, INK, INK2, FAINT, GRIDL, mix
import make_methodflow_svg as msvg

HERE = os.path.dirname(os.path.abspath(__file__))
FIGS = os.path.join(HERE, 'figs')
X0, Y0 = 2.25, 6.3                # tikz -> page: X = x + X0, Y = Y0 - y  (cm)
SLIDE_W, SLIDE_H = 19.0, 9.0      # cm
PT_PER_CM = 72 / 2.54


# --------------------------------------------------------------------------
# matplotlib backend with the SvgDeck drawing interface (preview + PDF)
# --------------------------------------------------------------------------
class MplDeck:
    FAMILY = ['Liberation Serif', 'Times New Roman', 'DejaVu Serif']
    DASH = {None: 'solid', 'dash': (0, (4, 2.5)), 'sysDot': (0, (1, 1.6))}

    def __init__(self):
        plt.rcParams.update({'pdf.fonttype': 42, 'ps.fonttype': 42,
                             'lines.scale_dashes': False,
                             'font.family': 'serif', 'font.serif': self.FAMILY})
        self.fig = plt.figure(figsize=(SLIDE_W / 2.54, SLIDE_H / 2.54))
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, SLIDE_W); self.ax.set_ylim(SLIDE_H, 0); self.ax.axis('off')
        self.z = 0
        self.ttp = TextToPath()

    def _z(self):
        self.z += 1
        return self.z

    @staticmethod
    def _c(hexc):
        return '#' + hexc

    def _width_cm(self, s, size, bold):
        prop = FontProperties(family=self.FAMILY, size=size, weight='bold' if bold else 'normal')
        w, _, _ = self.ttp.get_text_width_height_descent(s, prop, ismath=False)
        return w / PT_PER_CM

    # ---- shapes ----------------------------------------------------------
    def box(self, x, y, w, h, paras=(), *, fill=None, line=None, lw=0.75,
            rounded=False, size=7, color=INK, align='l', anchor='ctr',
            dash=None, rot=0, shape=None, inset=0.12, name='box'):
        cx, cy = x + X0, Y0 - y
        kw = dict(facecolor=self._c(fill) if fill else 'none',
                  edgecolor=self._c(line) if line else 'none',
                  linewidth=lw if line else 0, linestyle=self.DASH[dash], zorder=self._z())
        if shape == 'ellipse':
            p = Ellipse((cx, cy), w, h, **kw)
        elif rounded:
            r = min(w, h) * 0.12
            p = FancyBboxPatch((cx - w/2 + r, cy - h/2 + r), w - 2*r, h - 2*r,
                               boxstyle=f'round,pad={r},rounding_size={r}', **kw)
        else:
            p = FancyBboxPatch((cx - w/2, cy - h/2), w, h, boxstyle='square,pad=0', **kw)
        if rot:
            p.set_transform(matplotlib.transforms.Affine2D().rotate_deg_around(cx, cy, rot)
                            + self.ax.transData)
        self.ax.add_patch(p)
        self._text(cx, cy, w, h, paras, size, color, align, anchor, inset, rot)

    def _text(self, cx, cy, W, H, paras, size, color, align, anchor, inset, rot):
        paras = [p for p in (paras or []) if p != '']
        if not paras:
            return
        lh = size * 1.22 / PT_PER_CM                       # line height, cm
        n = len(paras)
        y0 = (cy - (n - 1) * lh / 2 + size * 0.35 / PT_PER_CM) if anchor == 'ctr' \
            else (cy - H/2 + inset/2 + size / PT_PER_CM)
        th = math.radians(rot)

        def place(px, py):                                  # rotate about (cx, cy), y-down frame
            dx, dy = px - cx, py - cy
            return (cx + dx*math.cos(th) - dy*math.sin(th), cy + dx*math.sin(th) + dy*math.cos(th))
        for i, para in enumerate(paras):
            if isinstance(para, str):
                para = [(para, False, None)]
            widths = [self._width_cm(t, size, b) for t, b, _ in para]
            total = sum(widths)
            if align == 'l':
                x = cx - W/2 + inset
            elif align == 'r':
                x = cx + W/2 - inset - total
            else:
                x = cx - total/2
            y = y0 + i * lh
            for (t, b, col), wdt in zip(para, widths):
                px, py = place(x, y)
                self.ax.text(px, py, t, ha='left', va='baseline', fontsize=size,
                             color=self._c(col or color), weight='bold' if b else 'normal',
                             rotation=-rot, rotation_mode='anchor', zorder=self._z())
                x += wdt

    def text(self, x, y, w, h, paras, **kw):
        kw.setdefault('inset', 0.02)
        self.box(x, y, w, h, paras, name='label', **kw)

    def dot(self, x, y, r, fill, line=None, lw=0.75):
        self.box(x, y, 2*r, 2*r, fill=fill, line=line, lw=lw, shape='ellipse', name='node')

    def line(self, x1, y1, x2, y2, *, color=INK2, lw=0.8, dash=None, arrow=False, name='line'):
        X1, Y1, X2, Y2 = x1 + X0, Y0 - y1, x2 + X0, Y0 - y2
        if arrow:
            a = FancyArrowPatch((X1, Y1), (X2, Y2), arrowstyle='-|>,head_length=1.0,head_width=0.45',
                                mutation_scale=5*lw, linewidth=lw, color=self._c(color),
                                linestyle=self.DASH[dash], shrinkA=0, shrinkB=0,
                                capstyle='round', zorder=self._z())
            self.ax.add_patch(a)
        else:
            self.ax.plot([X1, X2], [Y1, Y2], color=self._c(color), linewidth=lw,
                         linestyle=self.DASH[dash], solid_capstyle='round', zorder=self._z())

    def path(self, pts, **kw):
        arrow = kw.pop('arrow', False)
        for i in range(len(pts) - 1):
            self.line(*pts[i], *pts[i+1], arrow=(arrow and i == len(pts) - 2), **kw)

    def poly(self, pts, *, fill, line, lw=0.5, name='plane'):
        P = [(x + X0, Y0 - y) for x, y in pts]
        self.ax.add_patch(Polygon(P, closed=True, facecolor=self._c(fill), edgecolor=self._c(line),
                                  linewidth=lw, joinstyle='round', zorder=self._z()))

    def write(self, png, pdf):
        self.fig.savefig(png, dpi=220, facecolor='white')
        self.fig.savefig(pdf, facecolor='white')


# --------------------------------------------------------------------------
# geometry
# --------------------------------------------------------------------------
def build_v2(d):
    B = lambda t, c=None: (t, True, c)        # bold run
    N = lambda t, c=None: (t, False, c)       # normal run

    # ---- inputs, straight down into layer 1
    d.box(0.4, 5.55, 2.3, 0.55, ['DNN layer shapes'], fill=mix(GRIDL, 30),
          line=INK2, lw=0.6, rounded=True, size=7.5, align='ctr')
    d.box(3.4, 5.55, 3.0, 0.72, ['hardware: 128×128 CBs,', 'c CBs per tile'],
          fill=mix(GRIDL, 30), line=INK2, lw=0.6, rounded=True, size=7.5, align='ctr')
    d.line(0.4, 5.275, 0.4, 4.86, lw=1.0, arrow=True)
    d.line(3.4, 5.19, 3.4, 4.86, lw=1.0, arrow=True)

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

    # ---- flow arrows between layers
    d.line(1.95, 3.11, 1.95, 2.91, lw=1.0, arrow=True)
    d.text(2.75, 3.01, 1.5, 0.25, ['traffic graph'], size=6, color=INK2, align='l')
    d.line(1.95, 1.65, 1.95, 1.30, lw=1.0, arrow=True)
    d.text(2.75, 1.47, 1.5, 0.25, ['placement π'], size=6, color=INK2, align='l')

    # ---- nested-search bracket
    d.path([(-0.75, 4.50), (-0.87, 4.50), (-0.87, 1.80), (-0.75, 1.80)],
           color=FAINT, lw=0.6)
    d.text(-1.3, 3.15, 3.0, 0.5, ['nested search:', 'each PO → own placement space'],
           size=6, color=INK2, align='ctr', rot=-90)

    # ---- the 3D NoC: border, then the mesh inside it
    bx, by, bw, bh = 8.65, 1.15, 5.5, 4.8          # border centre / size
    d.box(bx, by, bw, bh, fill=None, line=INK2, lw=0.7, rounded=True, name='NoC border')

    ox, oy = 7.3, 0.15
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
    # reduction funnel (placement sets these link loads)
    d.path([P(0, 0, 0), P(1, 0, 0), P(1, 1, 0)], color=MAP, lw=0.9, arrow=True)
    d.path([P(0, 2, 0), P(1, 2, 0), P(1, 1, 0)], color=MAP, lw=0.9, arrow=True)
    d.path([P(1, 1, 0), P(2, 1, 0)], color=MAP, lw=2.0, arrow=True)
    d.path([P(3, 0, 0), P(3, 1, 0), P(2, 1, 0)], color=MAP, lw=0.9, arrow=True)
    # routing alternatives
    d.path([P(0, 2, 1), P(2, 2, 1), P(2, 2, 0), P(2, 1, 0)], color=ROUTE, lw=0.9, arrow=True)
    d.path([P(0, 2, 1), P(0, 2, 0), P(0, 1, 0), P(1, 1, 0)], color=ROUTE, lw=0.9,
           dash='dash', arrow=True)
    # nodes; tiles (packing) in blue, the accumulator's placement ring in orange
    for z in (0, 1):
        for i in range(4):
            for j in range(3):
                d.dot(*P(i, j, z), 0.055, mix(INK2, 55))
    for (i, j, z) in [(0, 0, 0), (0, 2, 0), (3, 0, 0), (0, 2, 1)]:
        d.dot(*P(i, j, z), 0.085, PACK)
    acc = P(2, 1, 0)
    d.dot(*acc, 0.13, 'FFFFFF', line=MAP, lw=1.1)
    d.dot(*acc, 0.065, PACK)
    # mesh labels
    d.text(ox-0.85, oy+0.05, 1.0, 0.4, ['sender', 'tiles'], size=6, color=PACK, align='r')
    d.text(ox+2.4, oy-0.45, 1.9, 0.4, ['accumulator', '(reduction sink)'],
           size=6, color=MAP, align='l')
    d.text(ox+2.9, oy+3.05, 2.2, 0.4, ['two admissible paths;', 'selection picks one'],
           size=6, color=ROUTE, align='l')
    d.text(ox+1.7, oy-1.0, 4.2, 0.3, [[B('3D NoC', INK2), N(': tiles mapped onto the 6×6×3 mesh', INK2)]],
           size=6, align='ctr')

    # ---- layers -> NoC: dashed, colour-coded arrows onto the border
    bl = bx - bw/2                                  # border left edge
    d.path([(4.45, 3.98), (4.95, 3.98), (4.95, 3.0), (bl, 3.0)],
           color=PACK, lw=0.7, dash='dash', arrow=True)
    d.line(4.45, 2.28, bl, 2.28, color=MAP, lw=0.7, dash='dash', arrow=True)
    d.line(4.45, 0.62, bl, 0.62, color=ROUTE, lw=0.7, dash='dash', arrow=True)
    d.text((4.95+bl)/2, 3.2, 1.0, 0.25, ['sets PF'], size=6, color=PACK, align='ctr')
    d.text((4.45+bl)/2, 2.5, 1.5, 0.25, ['sets π, PL'], size=6, color=MAP, align='ctr')
    d.text((4.45+bl)/2, 0.84, 1.5, 0.25, ['picks the path'], size=6, color=ROUTE, align='ctr')

    # ---- NoC -> outcome
    bb = by - bh/2                                  # border bottom edge
    d.line(bx, bb, bx, bb-0.45, lw=1.0, arrow=True)
    d.box(bx, bb-0.78, 3.4, 0.62, [[B('delay, p99')], [N('cycle-accurate simulation', INK2)]],
          fill='FFFFFF', line=INK2, lw=0.8, rounded=True, size=7.5, align='ctr')

    # ---- detail panel: one node, radiating from the accumulator
    zx, zy = 12.4, 0.3
    d.box(zx+1.85, zy+1.475, 4.4, 4.05, fill='FFFFFF', line=FAINT, lw=0.7,
          rounded=True, name='zoom frame')
    d.text(zx+1.9, zy+3.05, 4.0, 0.7, [
        [N('PF = max(PIL, PEL)', INK), N('  — packing-fixed', PACK)],
        [N('PL = max_ℓ Λ_ℓ', INK), N('  — placement-set', MAP)],
        [N('B = max(PF, PL)', INK), N('  — predicts delay', INK2)]],
        size=6.5, align='l')
    R = (zx+1.85, zy+1.35)
    T = (zx+1.85, zy-0.12)
    d.box(*R, 1.05, 0.78, ['router'], fill=mix(GRIDL, 35), line=INK2, lw=0.8,
          rounded=True, size=7, align='ctr')
    d.box(*T, 1.05, 0.6, ['tile'], fill=mix(PACK, 8), line=PACK, lw=0.9,
          rounded=True, size=7, align='ctr', color=PACK)
    # ports (packing-fixed): injection thin, ejection thick -- the accumulator's floor
    d.line(R[0]-0.22, T[1]+0.30, R[0]-0.22, R[1]-0.39, color=PACK, lw=0.6, arrow=True)
    d.line(R[0]+0.22, R[1]-0.39, R[0]+0.22, T[1]+0.30, color=PACK, lw=2.2, arrow=True)
    d.text(R[0]-0.85, R[1]-0.72, 1.0, 0.4, ['inject', 'PIL'], size=6, color=PACK, align='r')
    d.text(R[0]+0.85, R[1]-0.72, 1.0, 0.4, ['eject', 'PEL'], size=6, color=PACK, align='l')
    # links (placement-set): the hot link thick
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
    d.text(L-0.58, R[1]+0.46, 1.3, 0.25, ['link load Λ_ℓ'], size=6, color=MAP, align='ctr')
    d.text(zx+2.95, zy-0.3, 1.7, 0.4, ['one port,', 'up to six links'],
           size=6, color=INK2, align='r')

    # leaders: accumulator node -> detail panel
    zl, zt, zb = zx-0.35, zy+3.5, zy-0.55
    d.line(*acc, zl, zt-0.15, color=INK2, lw=0.5, dash='dash')
    d.line(*acc, zl, zb+0.15, color=INK2, lw=0.5, dash='dash')
    return d


if __name__ == '__main__':
    # editable SVG
    msvg.X0, msvg.Y0, msvg.SLIDE_W, msvg.SLIDE_H = X0, Y0, SLIDE_W, SLIDE_H
    svg = build_v2(msvg.SvgDeck())
    svg_path = os.path.join(FIGS, 'fig_methodflow_editable_v2.svg')
    svg.write(svg_path)
    # preview + PDF
    m = build_v2(MplDeck())
    m.write(os.path.join(FIGS, 'fig_methodflow_v2.png'), os.path.join(FIGS, 'fig_methodflow_v2.pdf'))
    print('wrote', svg_path, 'and figs/fig_methodflow_v2.{png,pdf}')
