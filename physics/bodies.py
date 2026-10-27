"""
bodies.py — the solid bodies of a scene, as a picture of the view ("Solid bodies" layer).

In potential flow a body is not a solid object: its surface is the dividing streamline that closes
around sources, sinks or doublets, and the mathematics also gives a (fictitious) flow inside it. Here
the body is the fluid whose streamline, followed backwards, starts at a source or a doublet instead of
far upstream: the inside of a cylinder, a Rankine oval or a Rankine half-body. Fluid that turns in
closed loops (around a free vortex in a uniform flow) is real flow and is not a body. (With a
fast-spinning cylinder, Γ > 4πV∞R, the ring of fluid that turns with it has no dividing streamline
between it and the cylinder: the cells of that one region vote, the larger part wins.)

The view is cut into cells (usually the screen pixels). The dividing streamlines are drawn into the
cells as barriers; the cells between them form regions (connected cells, 4-neighbour), and every
region is tested with a few streamlines traced backwards from its cells: most of them end at a
singular point (neither the far field nor a closed loop) -> the region is a body. Streamlines never cross a dividing streamline, so one region is either all body
or all free stream. Without a free stream (no uniform flow) there are no bodies.
"""
from __future__ import annotations

import numpy as np

from . import kernel
from .field import active, fluid_mask, reference_speed
from .stagnation import _far_field_box, _tracer

SAMPLES = 5                      # cells traced per region
MIN_CELLS = 12                   # smaller regions (slivers between two dividing lines) stay free stream


def _cell_centres(box, shape):
    x0, x1, y0, y1 = box
    rows, cols = shape
    x = x0 + (np.arange(cols) + 0.5) * (x1 - x0) / cols
    y = y0 + (np.arange(rows) + 0.5) * (y1 - y0) / rows
    return x, y


def draw_barriers(lines, box, shape) -> np.ndarray:
    """Cells crossed by the polylines (each (N, 2) in data coordinates), as an 8-connected chain of
    cells (a 4-neighbour fill cannot pass it). Row 0 = bottom (y0)."""
    x0, x1, y0, y1 = box
    rows, cols = shape
    out = np.zeros(shape, bool)
    sx, sy = cols / (x1 - x0), rows / (y1 - y0)
    for xy in lines:
        if len(xy) < 2:
            continue
        px, py = (xy[:, 0] - x0) * sx, (xy[:, 1] - y0) * sy
        seg = np.hypot(np.diff(px), np.diff(py))
        ok = np.isfinite(seg)
        if not ok.any():
            continue
        n = np.where(ok, np.ceil(seg / 0.35), 0).astype(np.int64)          # samples closer than a cell
        if not n.sum():
            continue
        t = np.concatenate([np.arange(k) / k for k in n if k > 0])
        idx = np.repeat(np.arange(seg.size), n)
        qx = np.concatenate([px[idx] + t * (px[idx + 1] - px[idx]), px[-1:]])
        qy = np.concatenate([py[idx] + t * (py[idx + 1] - py[idx]), py[-1:]])
        i, j = np.floor(qx).astype(np.int64), np.floor(qy).astype(np.int64)
        inside = (i >= 0) & (i < cols) & (j >= 0) & (j < rows)
        out[j[inside], i[inside]] = True
    return out


def _label(free):
    if kernel.HAVE_NUMBA:
        return kernel.label_regions(free)
    rows, cols = free.shape                  # without Numba: the same flood fill in Python (slower)
    labels = np.zeros(free.shape, np.int32)
    n = 0
    for j0, i0 in zip(*np.nonzero(free)):
        if labels[j0, i0]:
            continue
        n += 1
        labels[j0, i0] = n
        stack = [(j0, i0)]
        while stack:
            j, i = stack.pop()
            for jj, ii in ((j - 1, i), (j + 1, i), (j, i - 1), (j, i + 1)):
                if 0 <= jj < rows and 0 <= ii < cols and free[jj, ii] and not labels[jj, ii]:
                    labels[jj, ii] = n
                    stack.append((jj, ii))
    return labels, n


def body_mask(elements, box, shape, dividing, rng=None) -> np.ndarray | None:
    """Bool picture (rows, cols) of the box (x0, x1, y0, y1): True = inside a body. `dividing` = the
    dividing streamlines ((N, 2) arrays) of the scene. None if the scene has no free stream."""
    els = active(elements)
    if reference_speed(els) is None or not dividing:
        return None
    rows, cols = shape
    x, y = _cell_centres(box, shape)
    barrier = draw_barriers(dividing, box, shape)
    if any(e.fluid_region(np.zeros(1, complex)) is not None for e in els):         # walls, sector flows
        gx, gy = np.meshgrid(x, y)
        solid = ~fluid_mask(els, gx + 1j * gy)
    else:
        solid = np.zeros(shape, bool)
    labels, n = _label(~barrier & ~solid)
    if n == 0:
        return np.zeros(shape, bool)
    counts = np.bincount(labels.ravel(), minlength=n + 1)
    rng = rng or np.random.default_rng(1)
    flat = labels.ravel()
    order = np.argsort(flat, kind="stable")
    starts = np.concatenate([[0], np.cumsum(counts)])
    seeds, owner = [], []
    for k in range(1, n + 1):
        if counts[k] < MIN_CELLS:
            continue
        cells = order[starts[k]:starts[k + 1]]
        pick = rng.choice(cells, size=min(SAMPLES, cells.size), replace=False)
        seeds.extend(x[pick % cols] + 1j * y[pick // cols])
        owner.extend([k] * pick.size)
    if not seeds:
        return np.zeros(shape, bool)
    width = max(box[1] - box[0], box[3] - box[2])
    _lines, closed, left = _tracer(els, width).free_trace(np.array(seeds), -1.0, _far_field_box(box))
    from_body = ~np.asarray(left, bool) & ~np.asarray(closed, bool)     # started at a singular point
    owner = np.array(owner)
    body = np.zeros(n + 1, bool)
    for k in np.unique(owner):
        votes = from_body[owner == k]
        body[k] = votes.sum() * 2 > votes.size
    mask = body[labels]
    for _ in range(2):                                      # over the barrier cells next to a body
        grow = np.zeros(shape, bool)
        grow[1:, :] |= mask[:-1, :]
        grow[:-1, :] |= mask[1:, :]
        grow[:, 1:] |= mask[:, :-1]
        grow[:, :-1] |= mask[:, 1:]
        mask |= grow & barrier
    return mask
