"""SVG version of fig_methodflow with every label as real, editable <text>.

Reuses the geometry in make_methodflow_pptx.build(); this file only supplies
an SVG backend with the same drawing calls (box / text / dot / line / path /
poly).  Fonts are referenced, not outlined, so the text stays editable in
Inkscape, Illustrator, and PowerPoint 2016+ (Insert > Pictures, then
Convert to Shape).

    python3 make_methodflow_svg.py   ->  figs/fig_methodflow_editable.svg
"""
import os
from xml.sax.saxutils import escape

from make_methodflow_pptx import (X0, Y0, SLIDE_W, SLIDE_H, INK, INK2, build)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figs',
                   'fig_methodflow_editable.svg')
PT = 28.3465                      # points per cm
FONT = "'Times New Roman', Times, serif"


def pt(v_cm):
    return round(v_cm * PT, 2)


class SvgDeck:
    def __init__(self):
        self.el, self.markers = [], {}

    # ---- helpers -----------------------------------------------------------
    def _marker(self, color):
        """One arrowhead marker per colour (SVG markers do not inherit stroke)."""
        mid = 'arr_' + color
        if mid not in self.markers:
            self.markers[mid] = (
                f'<marker id="{mid}" viewBox="0 0 10 10" refX="9" refY="5" '
                f'markerWidth="5" markerHeight="5" orient="auto-start-reverse" '
                f'markerUnits="strokeWidth"><path d="M0,0 L10,5 L0,10 z" '
                f'fill="#{color}"/></marker>')
        return mid

    @staticmethod
    def _dash(dash):
        return {None: '', 'dash': ' stroke-dasharray="4 2.5"',
                'sysDot': ' stroke-dasharray="1 1.6"'}[dash]

    # ---- shapes ------------------------------------------------------------
    def box(self, x, y, w, h, paras=(), *, fill=None, line=None, lw=0.75,
            rounded=False, size=7, color=INK, align='l', anchor='ctr',
            dash=None, rot=0, shape=None, inset=0.12, name='box'):
        cx, cy = pt(x + X0), pt(Y0 - y)
        W, H = pt(w), pt(h)
        g = f'<g class="{name}"' + (f' transform="rotate({rot} {cx} {cy})"' if rot else '') + '>'
        fillx = f'#{fill}' if fill else 'none'
        stroke = (f' stroke="#{line}" stroke-width="{lw}"{self._dash(dash)}'
                  if line else ' stroke="none"')
        if shape == 'ellipse':
            g += f'<ellipse cx="{cx}" cy="{cy}" rx="{W/2:.2f}" ry="{H/2:.2f}" fill="{fillx}"{stroke}/>'
        else:
            rx = f' rx="{min(W, H)*0.12:.2f}"' if rounded else ''
            g += (f'<rect x="{cx-W/2:.2f}" y="{cy-H/2:.2f}" width="{W:.2f}" '
                  f'height="{H:.2f}"{rx} fill="{fillx}"{stroke}/>')
        g += self._text(cx, cy, W, H, paras, size, color, align, anchor, inset)
        self.el.append(g + '</g>')

    def _text(self, cx, cy, W, H, paras, size, color, align, anchor, inset):
        paras = [p for p in (paras or []) if p != '']
        if not paras:
            return ''
        lh = size * 1.22                                   # line height, pt
        ins = pt(inset)
        if align == 'l':
            tx, ta = cx - W/2 + ins, 'start'
        elif align == 'r':
            tx, ta = cx + W/2 - ins, 'end'
        else:
            tx, ta = cx, 'middle'
        n = len(paras)
        if anchor == 'ctr':
            y0 = cy - (n - 1) * lh / 2 + size * 0.35
        else:                                             # top
            y0 = cy - H/2 + ins/2 + size
        out = (f'<text x="{tx:.2f}" y="{y0:.2f}" font-family="{FONT}" '
               f'font-size="{size}" fill="#{color}" text-anchor="{ta}" '
               f'xml:space="preserve">')
        for i, para in enumerate(paras):
            if isinstance(para, str):
                para = [(para, False, None)]
            out += f'<tspan x="{tx:.2f}"' + (f' dy="{lh:.2f}"' if i else '') + '>'
            for text, bold, col in para:
                attrs = (' font-weight="bold"' if bold else '') + \
                        (f' fill="#{col}"' if col else '')
                out += f'<tspan{attrs}>{escape(text)}</tspan>'
            out += '</tspan>'
        return out + '</text>'

    def text(self, x, y, w, h, paras, **kw):
        kw.setdefault('inset', 0.02)
        self.box(x, y, w, h, paras, name='label', **kw)

    def dot(self, x, y, r, fill, line=None, lw=0.75):
        self.box(x, y, 2*r, 2*r, fill=fill, line=line, lw=lw, shape='ellipse', name='node')

    def line(self, x1, y1, x2, y2, *, color=INK2, lw=0.8, dash=None,
             arrow=False, name='line'):
        m = f' marker-end="url(#{self._marker(color)})"' if arrow else ''
        self.el.append(
            f'<line x1="{pt(x1+X0)}" y1="{pt(Y0-y1)}" x2="{pt(x2+X0)}" y2="{pt(Y0-y2)}" '
            f'stroke="#{color}" stroke-width="{lw}" stroke-linecap="round"'
            f'{self._dash(dash)}{m}/>')

    def path(self, pts, **kw):
        arrow = kw.pop('arrow', False)
        for i in range(len(pts) - 1):
            self.line(*pts[i], *pts[i+1], arrow=(arrow and i == len(pts) - 2), **kw)

    def poly(self, pts, *, fill, line, lw=0.5, name='plane'):
        p = ' '.join(f'{pt(x+X0)},{pt(Y0-y)}' for x, y in pts)
        self.el.append(f'<polygon class="{name}" points="{p}" fill="#{fill}" '
                       f'stroke="#{line}" stroke-width="{lw}" stroke-linejoin="round"/>')

    # ---- document ----------------------------------------------------------
    def write(self, path):
        W, H = pt(SLIDE_W), pt(SLIDE_H)
        doc = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
               f'<svg xmlns="http://www.w3.org/2000/svg" width="{SLIDE_W}cm" '
               f'height="{SLIDE_H}cm" viewBox="0 0 {W} {H}">\n'
               f'<title>Layered design flow and the substrate it acts on</title>\n'
               f'<defs>{"".join(self.markers.values())}</defs>\n'
               f'<rect width="{W}" height="{H}" fill="#ffffff"/>\n'
               + '\n'.join(self.el) + '\n</svg>\n')
        open(path, 'w', encoding='utf-8').write(doc)


if __name__ == '__main__':
    d = build(SvgDeck())
    d.write(OUT)
    n_text = sum(e.count('<text ') for e in d.el)
    print(f'wrote {OUT}  elements={len(d.el)}  text elements={n_text}')
