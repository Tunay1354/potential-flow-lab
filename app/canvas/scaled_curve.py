"""
scaled_curve.py — a plot curve whose points are kept in a local, view-sized coordinate system.

Why: the graphics card's painter (Qt's OpenGL paint engine) strokes a line in the item's own coordinates and
limits how much those may be magnified: beyond about 10 000 screen pixels per coordinate unit a 1.4 px line
became 14 px, then hundreds (his report of 31 Oct: zoomed far in with GPU on, the streamlines grew thick, then
the whole plot turned blue; the processor's painter has no such limit). So the curve stores its points as
(x − cx) / s, (y − cy) / s and carries the transform x = cx + s·x', y = cy + s·y' itself: whatever the zoom,
one local unit is about one screen pixel. The painted picture is the same; xy() gives the data points
(getData() the local ones, which pyqtgraph draws).
When the view changes a lot (zoom), the local system is chosen again (viewRangeChanged).
"""
from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QRectF
from PySide6.QtGui import QTransform

LOCAL_UNITS_ACROSS = 1000.0       # the view is about this many local units wide (≈ 1 unit per screen pixel)
RENEW_FACTOR = 16.0               # a new local system when the zoom changed by more than this
PAD_UNITS = 12.0                  # bounding box margin in local units (≈ px: the pen's width and more)


class ScaledCurve(pg.PlotCurveItem):
    _raw = None                                  # (x, y) in data units, as given (None: no data yet)
    _ref = (0.0, 0.0, 1.0)                       # (cx, cy, s) of the local system
    _bounds = None                               # bounding box in local units (pyqtgraph's own assumes data units)

    def setData(self, *args, **kwargs):
        if len(args) >= 2:
            x, y, rest = args[0], args[1], args[2:]
        elif "x" in kwargs or "y" in kwargs:
            x, y, rest = kwargs.pop("x", None), kwargs.pop("y", None), args
        else:
            super().setData(*args, **kwargs)     # (only options, e.g. a pen)
            return
        if x is None or y is None:
            super().setData(*args, **kwargs)
            return
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        self._raw = (x, y)
        cx, cy, s = self._choose_ref(x, y)
        self._ref = (cx, cy, s)
        xl, yl = (x - cx) / s, (y - cy) / s
        fin = np.isfinite(xl) & np.isfinite(yl)
        self.prepareGeometryChange()
        if fin.any():
            p = PAD_UNITS * max(1.0, self._ref_ratio())
            a, b, c, d = float(xl[fin].min()), float(xl[fin].max()), float(yl[fin].min()), float(yl[fin].max())
            self._bounds = QRectF(a - p, c - p, b - a + 2 * p, d - c + 2 * p)
        else:
            self._bounds = QRectF()
        super().setData(xl, yl, *rest, **kwargs)
        self.setTransform(QTransform(s, 0.0, 0.0, s, cx, cy))

    def boundingRect(self):
        if self._bounds is None:
            return super().boundingRect()
        return QRectF(self._bounds)

    def _ref_ratio(self) -> float:
        """Local units per screen pixel (about 1; more when the view is wider than LOCAL_UNITS_ACROSS px)."""
        vb = self.getViewBox()
        if vb is None:
            return 1.0
        try:
            px = max(vb.width(), vb.height())
        except RuntimeError:
            return 1.0
        return LOCAL_UNITS_ACROSS / px if px > 0 else 1.0

    def xy(self):
        """The points in data units (getData() gives the local ones pyqtgraph draws)."""
        if self._raw is None:
            return super().getData()
        return self._raw

    def _choose_ref(self, x, y):
        vb = self.getViewBox()
        if vb is not None:
            (x0, x1), (y0, y1) = vb.viewRange()
            w = max(x1 - x0, y1 - y0)
            if np.isfinite(w) and w > 0:
                return 0.5 * (x0 + x1), 0.5 * (y0 + y1), w / LOCAL_UNITS_ACROSS
        fin = np.isfinite(x) & np.isfinite(y)
        if not fin.any():
            return 0.0, 0.0, 1.0
        xs, ys = x[fin], y[fin]
        w = max(float(xs.max() - xs.min()), float(ys.max() - ys.min()))
        s = w / LOCAL_UNITS_ACROSS if w > 0 else max(1e-300, abs(float(xs[0])) * 1e-6 or 1.0)
        return float(0.5 * (xs.max() + xs.min())), float(0.5 * (ys.max() + ys.min())), s

    def viewRangeChanged(self):
        super().viewRangeChanged()
        if self._raw is None or self._raw[0].size == 0:
            return
        vb = self.getViewBox()
        if vb is None:
            return
        (x0, x1), (y0, y1) = vb.viewRange()
        w = max(x1 - x0, y1 - y0)
        s = self._ref[2]
        if not (np.isfinite(w) and w > 0):
            return
        ideal = w / LOCAL_UNITS_ACROSS
        cx, cy = self._ref[0], self._ref[1]
        far = max(abs(0.5 * (x0 + x1) - cx), abs(0.5 * (y0 + y1) - cy)) > 1000.0 * w     # (panned very far)
        if s / ideal > RENEW_FACTOR or ideal / s > RENEW_FACTOR or far:
            self.setData(*self._raw)
