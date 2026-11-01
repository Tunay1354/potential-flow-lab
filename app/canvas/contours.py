"""
contours.py — contour lines and filled contour bands on a grid, and the color scales of the field
layers (|V| and Cp). No plot items here: field_layer.py makes them.

Uses contourpy when installed (smooth vector contours); otherwise a NumPy marching-squares fallback for
the lines (and the caller draws the bands as a pixel image).
"""
import math

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

try:                                    # fast, smooth contours (pip install contourpy); without it: fallback
    import contourpy
    HAVE_CONTOURPY = True
except ImportError:                     # pragma: no cover - depends on the installation
    contourpy = None
    HAVE_CONTOURPY = False

BANDS = 12                       # about this many color bands
CROWD_SPEED = 5.0                # "much faster than typical": × the median speed of the view


def nice_step(span: float, count: int) -> float:
    """A round step (1, 2, 2.5, 5 × 10^k) that divides `span` into about `count` parts."""
    if not np.isfinite(span) or span <= 0:
        return 1.0
    raw = span / max(count, 1)
    k = 10.0 ** math.floor(math.log10(raw))
    for m in (1.0, 2.0, 2.5, 5.0, 10.0):
        if raw <= m * k * 1.0001:
            return m * k
    return 10.0 * k


def cut_mask(f: np.ndarray, speed: np.ndarray, hx: float, hy: float, factor: float = 4.0,
             period: float | None = None) -> np.ndarray:
    """True at grid points next to a jump of f (a branch cut): |Δf| between neighbors much larger
    than |V| · h, the most a smooth potential can change over one grid step. With `period`, jumps by a
    whole multiple of it do not count (they do not change sin(πf/(period/2)), see field_layer)."""
    bad = np.zeros(f.shape, bool)
    for axis, h in ((1, hx), (0, hy)):
        df = np.diff(f, axis=axis)
        if period:
            df = df - period * np.round(df / period)
        df = np.abs(df)
        sp = np.diff(speed, axis=axis) * 0.5 + np.take(speed, range(speed.shape[axis] - 1), axis=axis)
        jump = df > factor * np.nan_to_num(sp, nan=0.0) * h + 1e-12
        jump &= np.isfinite(df)
        if axis == 1:
            bad[:, :-1] |= jump
            bad[:, 1:] |= jump
        else:
            bad[:-1, :] |= jump
            bad[1:, :] |= jump
    return bad


def contour_xy(x, y, z, levels):
    """Contour lines of z (NaN = no data) at `levels`, as one (N, 2) array with NaN rows between
    lines (for one PlotCurveItem with connect='finite')."""
    if not HAVE_CONTOURPY:
        return _marching_squares(x, y, z, levels)
    zm = np.ma.masked_invalid(z)
    if zm.mask.all() or not len(levels):
        return np.zeros((0, 2))
    gen = contourpy.contour_generator(x, y, zm, line_type=contourpy.LineType.ChunkCombinedNan)
    parts = []
    gap = np.array([[np.nan, np.nan]])
    for lev in levels:
        (chunks,) = gen.lines(lev)
        for pts in chunks:
            if pts is not None and len(pts):
                parts += [pts, gap]
    return np.vstack(parts) if parts else np.zeros((0, 2))


# marching squares (fallback without contourpy): which cell edges a contour joins, per corner case
# corners: a (i, j), b (i+1, j), c (i+1, j+1), d (i, j+1); bit a=1 b=2 c=4 d=8
# edges: 0 = a-b (bottom), 1 = b-c (right), 2 = d-c (top), 3 = a-d (left)
_CASES = {1: ((3, 0),), 2: ((0, 1),), 3: ((3, 1),), 4: ((1, 2),), 5: ((3, 0), (1, 2)), 6: ((0, 2),),
          7: ((3, 2),), 8: ((2, 3),), 9: ((0, 2),), 10: ((0, 1), (2, 3)), 11: ((1, 2),), 12: ((1, 3),),
          13: ((0, 1),), 14: ((0, 3),)}


def _marching_squares(x, y, z, levels):
    """Contour lines as short straight pieces (two points + a NaN row each), NumPy only."""
    a, b, c, d = z[:-1, :-1], z[:-1, 1:], z[1:, 1:], z[1:, :-1]
    ok = np.isfinite(a) & np.isfinite(b) & np.isfinite(c) & np.isfinite(d)
    X0, Y0 = np.meshgrid(x[:-1], y[:-1])
    X1, Y1 = np.meshgrid(x[1:], y[1:])
    out = []
    with np.errstate(invalid="ignore", divide="ignore"):
        for lev in levels:
            case = ((a > lev) * 1 + (b > lev) * 2 + (c > lev) * 4 + (d > lev) * 8) * ok

            def frac(v0, v1):
                return np.clip((lev - v0) / (v1 - v0), 0.0, 1.0)

            pts = {0: (X0 + frac(a, b) * (X1 - X0), Y0),
                   1: (X1, Y0 + frac(b, c) * (Y1 - Y0)),
                   2: (X0 + frac(d, c) * (X1 - X0), Y1),
                   3: (X0, Y0 + frac(a, d) * (Y1 - Y0))}
            for k, pairs in _CASES.items():
                sel = case == k
                if not sel.any():
                    continue
                for e0, e1 in pairs:
                    n = int(sel.sum())
                    seg = np.full((n, 3, 2), np.nan)
                    seg[:, 0, 0], seg[:, 0, 1] = pts[e0][0][sel], pts[e0][1][sel]
                    seg[:, 1, 0], seg[:, 1, 1] = pts[e1][0][sel], pts[e1][1][sel]
                    out.append(seg.reshape(-1, 2))
    return np.vstack(out) if out else np.zeros((0, 2))


def filled_paths(x, y, z, edges):
    """Filled contour bands of z between consecutive `edges` (the first band is open downwards, the
    last upwards), as one QPainterPath per band (holes via the odd-even rule). Vector shapes: smooth
    on the screen and sharp in SVG / PDF exports. None without contourpy (then a pixel image is used)."""
    if not HAVE_CONTOURPY:
        return None
    zm = np.ma.masked_invalid(z)
    if zm.mask.all():
        return []
    gen = contourpy.contour_generator(x, y, zm, fill_type=contourpy.FillType.OuterOffset)
    zmin, zmax = float(zm.min()), float(zm.max())
    out = []
    n = len(edges) - 1
    for k in range(n):
        lo = edges[k] if k > 0 else min(edges[0], zmin) - 1.0
        hi = edges[k + 1] if k < n - 1 else max(edges[-1], zmax) + 1.0
        points, offsets = gen.filled(lo, hi)
        xs, ys, conn = [], [], []
        for pts, offs in zip(points, offsets):
            for a, b in zip(offs[:-1], offs[1:]):
                ring = pts[a:b]
                if len(ring) < 3:
                    continue
                c = np.ones(len(ring), dtype=np.int32)
                c[-1] = 0
                xs.append(ring[:, 0])
                ys.append(ring[:, 1])
                conn.append(c)
        if not xs:
            out.append(None)
            continue
        path = pg.arrayToQPath(np.concatenate(xs), np.concatenate(ys), np.concatenate(conn))
        path.setFillRule(Qt.OddEvenFill)
        out.append(path)
    return out


def mix(a: QColor, b: QColor, t: float) -> tuple:
    t = min(max(t, 0.0), 1.0)
    return tuple(int(round(a.getRgb()[i] + (b.getRgb()[i] - a.getRgb()[i]) * t)) for i in range(3))


def ramp(stops: list, t: float) -> tuple:
    """Color at t (0…1) of a piecewise-linear ramp through `stops` (hex colors, equally spaced)."""
    t = min(max(t, 0.0), 1.0) * (len(stops) - 1)
    i = min(int(t), len(stops) - 2)
    return mix(QColor(stops[i]), QColor(stops[i + 1]), t - i)


def speed_bands(speed: np.ndarray, stops: list):
    """Band edges (0 … a round top value) and colors of |V|. The top is robust: faster points (next to
    singular points) fall into the last band instead of stretching the scale."""
    vals = speed[np.isfinite(speed)]
    if not vals.size:
        return [], []
    hi = float(min(np.percentile(vals, 98), CROWD_SPEED * np.median(vals)))
    if not hi > 0:
        hi = float(vals.max()) or 1.0
    step = nice_step(hi, BANDS)
    top = max(step, math.ceil(hi / step) * step)
    edges = np.arange(0.0, top + 0.5 * step, step)
    n = len(edges) - 1
    return edges, [ramp(stops, (k + 0.5) / n) for k in range(n)]


def cp_bands(cp: np.ndarray, colors3):
    """Band edges (… 1) and diverging colors (negative, zero, positive) of Cp. 1 − Cp ∝ V², so the low
    end has the same robust cap as |V| (at most CROWD_SPEED × the median speed)."""
    vals = cp[np.isfinite(cp)]
    if not vals.size:
        return [], []
    floor = 1.0 - CROWD_SPEED ** 2 * max(float(np.median(1.0 - vals)), 0.0)
    lo = float(min(max(np.percentile(vals, 2), floor), -0.25))
    step = nice_step(1.0 - lo, BANDS)
    bottom = math.floor(lo / step) * step
    edges = [e for e in np.arange(bottom, 1.0 + 0.5 * step, step) if e < 1.0 - 0.25 * step]
    edges.append(1.0)                                   # Cp ≤ 1 everywhere (1 = stagnation)
    neg, mid, pos = (QColor(c) for c in colors3)
    colors = []
    for a, b in zip(edges[:-1], edges[1:]):
        c = 0.5 * (a + b)
        colors.append(mix(mid, neg, c / bottom) if c < 0 else mix(mid, pos, c / max(edges[-1], 1e-9)))
    return np.asarray(edges, float), colors          # Cp below the first edge: in the first band
