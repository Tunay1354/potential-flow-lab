"""
drawing.py — the lines cut into pieces of decreasing opacity at their fading (cut) ends, for drawing.
"""
from __future__ import annotations

import numpy as np

from .. import kernel
from .common import FADE_LEVELS, TAPER_RATIO


# ---------------------------------------------------------------------- fading ends (for drawing)
def fade_pieces(lines: list[np.ndarray], tapers: list[tuple[bool, bool]], d: float,
                levels: int = FADE_LEVELS) -> list[np.ndarray]:
    """Cut the lines into pieces for drawing with fading ends.

    Returns `levels + 1` arrays of (x, y) points, pieces separated by a NaN row:
      [0]      the full-opacity part of every line,
      [k ≥ 1]  the k-th step of the fading ends (counted from the full part outwards);
               draw it with opacity (levels + 1 − k) / (levels + 1).
    A cut end (taper flag True) fades over TAPER_RATIO·d (at most half of a line); other ends,
    e.g. at the view border, a wall or a singular point, stay fully opaque."""
    gap = np.array([[np.nan, np.nan]])
    out = []
    for parts in fade_piece_lists(lines, tapers, d, levels):
        out.append(np.vstack([x for p in parts for x in (p, gap)]) if parts else np.zeros((0, 2)))
    return out


def fade_piece_lists(lines: list[np.ndarray], tapers: list[tuple[bool, bool]], d: float,
                     levels: int = FADE_LEVELS) -> list[list[np.ndarray]]:
    """Like fade_pieces, but every opacity level is a list of separate (N, 2) pieces."""
    return [parts for parts, _boxes in fade_piece_boxes(lines, tapers, d, levels)]


def fade_piece_boxes(lines: list[np.ndarray], tapers: list[tuple[bool, bool]], d: float,
                     levels: int = FADE_LEVELS) -> list[tuple[list[np.ndarray], np.ndarray]]:
    """Per opacity level: (pieces, their bounding boxes (n, 4) = x0, x1, y0, y1) — for drawing only
    what is near the view."""
    if kernel.HAVE_NUMBA and lines:
        xy = np.ascontiguousarray(np.concatenate(lines), dtype=float).reshape(-1, 2)
        offs = np.concatenate([[0], np.cumsum([len(ln) for ln in lines])]).astype(np.int64)
        cut0 = np.array([t[0] for t in tapers], bool)
        cut1 = np.array([t[1] for t in tapers], bool)
        pts, po, plev, boxes = kernel.fade_cut(xy, offs, cut0, cut1, float(d), int(levels), TAPER_RATIO)
        out = []
        for k in range(levels + 1):
            idx = np.nonzero(plev == k)[0]
            out.append(([pts[po[i]:po[i + 1]] for i in idx], boxes[idx].reshape(-1, 4)))
        return out
    lists = _fade_piece_lists_numpy(lines, tapers, d, levels)
    return [(parts, np.array([(p[:, 0].min(), p[:, 0].max(), p[:, 1].min(), p[:, 1].max()) for p in parts])
             .reshape(-1, 4)) for parts in lists]


def _fade_piece_lists_numpy(lines, tapers, d, levels):
    out: list[list[np.ndarray]] = [[] for _ in range(levels + 1)]
    for xy, (cut0, cut1) in zip(lines, tapers):
        if xy.shape[0] < 2:
            continue
        s = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(xy[:, 0]), np.diff(xy[:, 1])))])
        total = s[-1]
        n_cut = int(cut0) + int(cut1)
        Lt = min(TAPER_RATIO * d, total / n_cut) if n_cut else 0.0
        a = Lt if cut0 else 0.0
        b = total - Lt if cut1 else total
        if b > a:
            out[0].append(_piece(xy, s, a, b))
        for k in range(1, levels + 1):
            lo, hi = Lt * (levels - k) / levels, Lt * (levels - k + 1) / levels
            if cut0:
                out[k].append(_piece(xy, s, lo, hi))
            if cut1:
                out[k].append(_piece(xy, s, total - hi, total - lo))
    return out


def _piece(xy: np.ndarray, s: np.ndarray, a: float, b: float) -> np.ndarray:
    """Part of a polyline between arc lengths a and b (end points interpolated)."""
    inner = (s > a) & (s < b)
    pa = np.array([np.interp(a, s, xy[:, 0]), np.interp(a, s, xy[:, 1])])
    pb = np.array([np.interp(b, s, xy[:, 0]), np.interp(b, s, xy[:, 1])])
    return np.vstack([pa, xy[inner], pb])
