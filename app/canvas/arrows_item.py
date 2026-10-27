"""
arrows_item.py — all streamline direction arrows in ONE plot item.

pyqtgraph's ArrowItem is one graphics item per arrow; with ~100 arrows the plot then makes ~100
Python paint calls per frame. Here the arrow heads are drawn together in screen coordinates:
the size stays constant in pixels (like ArrowItem), the direction follows the data -> screen mapping
(correct for any aspect ratio), and the tip is at the arrow position.
"""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QRectF
from PySide6.QtGui import QBrush, QPainter, QPen


class ArrowsItem(pg.GraphicsObject):
    def __init__(self, size_px: float = 6.5, length_ratio: float = 1.35):
        super().__init__()
        self.size = size_px                       # width of an arrow head in pixels
        self.length = length_ratio * size_px      # length of an arrow head in pixels
        self._x = self._y = self._c = self._s = np.zeros(0)
        self._pen, self._brush = QPen(), QBrush()
        self._bounds = QRectF()

    def setData(self, arrows):
        """arrows: list of (x, y, angle in radians, measured in data coordinates)."""
        a = np.asarray(arrows, dtype=float).reshape(-1, 3)
        self.prepareGeometryChange()
        self._x, self._y = a[:, 0], a[:, 1]
        self._c, self._s = np.cos(a[:, 2]), np.sin(a[:, 2])
        self._update_bounds()
        self.update()

    def setColor(self, color):
        self._pen = pg.mkPen(color, width=1)
        self._brush = pg.mkBrush(color)
        self.update()

    def count(self) -> int:
        return int(self._x.size)

    # ------------------------------------------------------------------ QGraphicsItem
    def _update_bounds(self):
        if self._x.size == 0:
            self._bounds = QRectF()
            return
        px = self.pixelSize() if self.scene() is not None else None
        pad_x = pad_y = 0.0
        if px is not None and all(np.isfinite(px)):
            pad_x, pad_y = 2.0 * self.length * px[0], 2.0 * self.length * px[1]
        x0, x1, y0, y1 = self._x.min(), self._x.max(), self._y.min(), self._y.max()
        self._bounds = QRectF(x0 - pad_x, y0 - pad_y, (x1 - x0) + 2 * pad_x, (y1 - y0) + 2 * pad_y)

    def viewTransformChanged(self):
        """Zoom changes how many data units the pixel-sized heads cover."""
        self.prepareGeometryChange()
        self._update_bounds()

    def boundingRect(self):
        return self._bounds

    def paint(self, p, *args):
        n = self._x.size
        if n == 0:
            return
        k = self._exportOpts.get("resolutionScale", 1.0) if self._exportOpts else 1.0   # k× PNG export
        size, length = self.size * k, self.length * k
        tr = p.transform()
        m11, m12, m21, m22, dx, dy = tr.m11(), tr.m12(), tr.m21(), tr.m22(), tr.dx(), tr.dy()
        sx = m11 * self._x + m21 * self._y + dx            # tips in screen pixels
        sy = m12 * self._x + m22 * self._y + dy
        ux = m11 * self._c + m21 * self._s                  # flow direction on the screen
        uy = m12 * self._c + m22 * self._s
        norm = np.hypot(ux, uy)
        norm[norm == 0] = 1.0
        ux, uy = ux / norm, uy / norm
        bx, by = sx - length * ux, sy - length * uy                # middle of the base
        hx, hy = -uy * 0.5 * size, ux * 0.5 * size                # half base, perpendicular
        # every head: tip -> base corner -> base corner -> tip, as one path built from arrays
        xs = np.column_stack([sx, bx + hx, bx - hx, sx]).ravel()
        ys = np.column_stack([sy, by + hy, by - hy, sy]).ravel()
        connect = np.tile(np.array([1, 1, 1, 0], dtype=np.int32), n)
        path = pg.arrayToQPath(xs, ys, connect=connect)
        p.save()
        p.resetTransform()
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(self._pen)
        p.setBrush(self._brush)
        p.drawPath(path)
        p.restore()
