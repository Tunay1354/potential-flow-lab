"""
grid_item.py — the plot's background grid, drawn in screen pixels.

pyqtgraph's GridItem draws its lines in data units; the graphics card's painter magnifies a line's width with
the zoom beyond ~10 000 px per unit (see scaled_curve.py), so far zoomed in with GPU on the grid became wide
grey bands (his report of 31 Oct). This one computes the same lines (pyqtgraph's spacing and fading rule) and
draws them with the screen's own transform: always 1 px, whatever the zoom.
"""
from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from pyqtgraph import functions as fn
from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainter, QPicture


class PaperGridItem(pg.GridItem):
    def generatePicture(self):
        lvr = self.boundingRect()
        dt = self.deviceTransform_()
        if lvr.isNull() or dt is None:
            return
        self.picture = QPicture()
        p = QPainter()
        p.begin(self.picture)
        p.setWorldTransform(fn.invertQTransform(dt))          # draw in screen pixels (identity on screen)
        vr = self.getViewWidget().rect()
        dim = [vr.width(), vr.height()]
        ul = np.array([lvr.left(), lvr.top()])
        br = np.array([lvr.right(), lvr.bottom()])
        if ul[1] > br[1]:
            ul[1], br[1] = br[1], ul[1]
        lastd = [None, None]
        for i in range(self.grid_depth - 1, -1, -1):
            dist = br - ul
            d = 10. ** np.floor(np.log10(np.abs(dist / 10. ** i)) + 0.5)
            for ax in range(2):
                ts = self.opts["tickSpacing"][ax]
                try:
                    if ts[i] is not None:
                        d[ax] = ts[i]
                except IndexError:
                    pass
                lastd[ax] = d[ax]
            ul1 = np.floor(ul / d) * d
            br1 = np.ceil(br / d) * d
            nl = (br1 - ul1) / d + 0.5
            for ax in range(2):
                if i >= len(self.opts["tickSpacing"][ax]) or d[ax] < lastd[ax]:
                    continue
                ppl = dim[ax] / nl[ax]
                pen = pg.mkPen(self.opts["pen"])
                c = pen.color()
                c.setAlpha(int(fn.clip_scalar(5 * (ppl - 3), 0, 50)))
                pen.setColor(c)
                pen.setCosmetic(True)
                p.setPen(pen)
                bx = (ax + 1) % 2
                for k in range(int(nl[ax])):
                    p1, p2 = np.zeros(2), np.zeros(2)
                    p1[ax] = p2[ax] = ul1[ax] + k * d[ax]
                    p1[bx], p2[bx] = ul[bx], br[bx]
                    if p1[ax] < min(ul[ax], br[ax]) or p1[ax] > max(ul[ax], br[ax]):
                        continue
                    p.drawLine(dt.map(QPointF(p1[0], p1[1])), dt.map(QPointF(p2[0], p2[1])))
        p.end()
