"""
bodies.py — the solid bodies of a scene: where they are (a picture of a region) and their surfaces.

In potential flow a body is not a solid object: its surface is a streamline that closes around sources
or doublets, and the mathematics also gives a (fictitious) flow inside it. The body is the fluid whose
streamline, followed backwards, starts at a source or a doublet, or turns round one
(stagnation.trace_origin, BODY): the inside of a cylinder, a Rankine oval or a Rankine half-body (also
in a corner flow). Fluid turning round a free vortex is real flow; fluid from far away is the free
stream (a uniform flow or a sector flow). Without a free stream there are no bodies.
A source / doublet the free stream passes THROUGH makes no body (stagnation.open_elements, OPEN): a
doublet not along the flow at it (δ ≠ α, or a vortex beside it turning the flow there), a source–sink
pair across the flow. That is decided per element, for the whole scene, so the picture is the same at
every zoom. (A fast-spinning cylinder, Γ > 4πV∞a: the ring of fluid that turns with it belongs to the
body too: nothing in the flow tells it apart from the cylinder, whose surface r = a is then an
ordinary closed streamline.)

How (body_map): the region is cut into cells (for the plot: the screen pixels). The dividing
streamlines are drawn into the cells as barriers; the cells between them form regions (connected
cells, 4-neighbour), and every region is tested with a few streamlines traced backwards from its cells
(the most frequent origin wins; lines that stopped do not count). Streamlines never cross a dividing streamline, so a region is all body
or all other fluid.

find_bodies: the bodies with their surfaces (parts of the dividing streamlines and of such traced
surfaces) as polylines ordered counter-clockwise (body on the left), for surface pressure and forces.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import kernel
from .field import active, fluid_mask, singular_points
from .stagnation import BODY, FAR, OPEN, STOPPED, has_free_stream, no_outflow_elements, trace_ends

SAMPLES = 5                      # cells traced per region
MIN_CELLS = 12                   # smaller regions (slivers between two dividing lines) stay free stream
PROBE_CELLS = 3.0                # surface test: this many cells to each side of a line


# ---------------------------------------------------------------------- cells
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
        n = np.where(np.isfinite(seg), np.ceil(seg / 0.35), 0).astype(np.int64)   # samples < a cell apart
        if not n.sum():
            continue
        t = np.concatenate([np.arange(k) / k for k in n if k > 0])
        idx = np.repeat(np.arange(seg.size), n)
        qx = np.concatenate([px[idx] + t * (px[idx + 1] - px[idx]), px[-1:]])
        qy = np.concatenate([py[idx] + t * (py[idx + 1] - py[idx]), py[-1:]])
        ok = np.isfinite(qx) & np.isfinite(qy)
        i, j = np.floor(qx[ok]).astype(np.int64), np.floor(qy[ok]).astype(np.int64)
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


# ---------------------------------------------------------------------- where the bodies are
@dataclass
class BodyMap:
    """Cells of `box` = (x0, x1, y0, y1): labels[row, col] = number of the body there (1 … count),
    0 = no body. Row 0 = bottom."""
    box: tuple
    labels: np.ndarray
    count: int

    @property
    def mask(self) -> np.ndarray:
        return self.labels > 0

    def body_at(self, z) -> np.ndarray:
        """Body number (0 = none) at the points z (complex array); 0 outside the box."""
        z = np.asarray(z, complex)
        x0, x1, y0, y1 = self.box
        rows, cols = self.labels.shape
        with np.errstate(invalid="ignore"):
            i = np.floor((z.real - x0) / (x1 - x0) * cols)
            j = np.floor((z.imag - y0) / (y1 - y0) * rows)
        ok = (i >= 0) & (i < cols) & (j >= 0) & (j < rows)
        out = np.zeros(z.shape, np.int32)
        out[ok] = self.labels[j[ok].astype(np.int64), i[ok].astype(np.int64)]
        return out

    def contains(self, z) -> np.ndarray:
        return self.body_at(z) > 0


def body_map(elements, box, shape, dividing, rng=None, hint: BodyMap | None = None) -> BodyMap | None:
    """The bodies in `box` on a grid of `shape` = (rows, cols) cells. `dividing` = the dividing
    streamlines ((N, 2) arrays) of the scene (none: the whole box is one region, e.g. zoomed into a
    body). `hint`: a coarser map of the whole scene, asked for regions none of whose traced lines tell
    anything (zoomed in next to a stagnation point the flow is too slow to follow). None if the scene
    has no free stream."""
    els = active(elements)
    if not has_free_stream(els):
        return None
    box = tuple(map(float, box))
    rng = rng or np.random.default_rng(1)
    x, y = _cell_centres(box, shape)
    if any(e.fluid_region(np.zeros(1, complex)) is not None for e in els):         # walls, sector flows
        gx, gy = np.meshgrid(x, y)
        solid = ~fluid_mask(els, gx + 1j * gy)
    else:
        solid = np.zeros(shape, bool)
    barrier = draw_barriers(dividing, box, shape)
    labels, n = _label(~barrier & ~solid)
    body = _classify(els, box, labels, n, x, y, rng, hint)
    _absorb_slivers(labels, n, body)
    numbers = np.zeros(n + 1, np.int32)
    numbers[np.nonzero(body)[0]] = np.arange(1, int(body.sum()) + 1)
    out = numbers[labels]
    for _ in range(2):                                   # over the barrier cells next to a body
        grow = out.copy()
        for src, dst in (((slice(None, -1), slice(None)), (slice(1, None), slice(None))),
                         ((slice(1, None), slice(None)), (slice(None, -1), slice(None))),
                         ((slice(None), slice(None, -1)), (slice(None), slice(1, None))),
                         ((slice(None), slice(1, None)), (slice(None), slice(None, -1)))):
            take = (grow[dst] == 0) & barrier[dst] & (out[src] > 0)
            grow[dst][take] = out[src][take]
        out = grow
    return BodyMap(box, out, int(body.sum()))


SLIVER_SHARE = 5e-4             # regions up to this share of the cells (at least MIN_CELLS) …
SLIVER_REACH = 2                 # … with body on most sides within this many cells become body


def _absorb_slivers(labels, n, body):
    """Tiny regions surrounded mostly by body become body (in place). Next to the stagnation points of
    a practically closed body (a doublet in a slightly non-uniform flow lets a hair of free stream
    through) the branches into the body and its surface cut off a wedge of a few pixels: real flow,
    but drawn white inside the body it looked like a crack."""
    rows, cols = labels.shape
    counts = np.bincount(labels.ravel(), minlength=n + 1)
    limit = max(MIN_CELLS, SLIVER_SHARE * rows * cols)
    small = np.nonzero((counts > 0) & (counts <= limit) & ~body)[0]
    small = small[small > 0]
    if not small.size or not body.any():
        return
    order = np.argsort(labels.ravel(), kind="stable")
    starts = np.concatenate([[0], np.cumsum(counts)])
    k_reach = SLIVER_REACH
    offsets = [(dr, dc) for dr in range(-k_reach, k_reach + 1) for dc in range(-k_reach, k_reach + 1)
               if (dr, dc) != (0, 0)]
    for k in small:
        cells = order[starts[k]:starts[k + 1]]
        r, c = cells // cols, cells % cols
        near = []
        for dr, dc in offsets:
            rr, cc = r + dr, c + dc
            ok = (rr >= 0) & (rr < rows) & (cc >= 0) & (cc < cols)
            near.append(labels[rr[ok], cc[ok]])
        near = np.concatenate(near)
        near = near[(near > 0) & (near != k)]                # other regions (not barrier, not itself)
        if near.size and body[near].mean() > 0.5:
            body[k] = True


def _classify(els, box, labels, n, x, y, rng, hint=None) -> np.ndarray:
    """body[k] for every region k (the most frequent known origin of its sample points is BODY)."""
    rows, cols = labels.shape
    counts = np.bincount(labels.ravel(), minlength=n + 1)
    order = np.argsort(labels.ravel(), kind="stable")
    starts = np.concatenate([[0], np.cumsum(counts)])
    seeds, owner = [], []
    for k in range(1, n + 1):
        if counts[k] < MIN_CELLS:
            continue
        cells = order[starts[k]:starts[k + 1]]
        pick = rng.choice(cells, size=min(SAMPLES, cells.size), replace=False)
        seeds.extend(x[pick % cols] + 1j * y[pick // cols])
        owner.extend([k] * pick.size)
    body = np.zeros(n + 1, bool)
    if not seeds:
        return body
    width = max(box[1] - box[0], box[3] - box[2])
    seeds, owner = np.array(seeds), np.array(owner)
    found, came_from = trace_ends(els, seeds, box, width, -1.0)
    # body fluid of a group without net outflow (a doublet, a Rankine oval) must go back into it: if
    # it goes off to the far field, it is a hair of free stream passing through (no body)
    closed = no_outflow_elements(els)
    check = np.nonzero((found == BODY) & np.isin(came_from, list(closed)))[0] if closed else []
    if len(check):
        goes, _ = trace_ends(els, seeds[check], box, width, 1.0)
        found[check[goes == FAR]] = OPEN
    for k in np.unique(owner):
        votes = found[(owner == k) & (found != STOPPED)]
        if votes.size:
            kinds, num = np.unique(votes, return_counts=True)
            body[k] = kinds[np.argmax(num)] == BODY
        elif hint is not None:                           # nothing known: as in the coarse map
            body[k] = hint.contains(seeds[owner == k]).mean() > 0.5
    return body


# ---------------------------------------------------------------------- surfaces
GAP_CELLS = 12                   # a surface piece broken for at most this long (both sides body there) goes on


def _bridge(side, s, gap):
    """In place: short runs of 0 between two runs of the same body on the same side take that value.
    Next to the stagnation points of a practically closed body a sliver beside the surface is body
    too (_absorb_slivers): there the line has body on both sides, and the outline had a small break."""
    k, n = 0, side.size
    while k < n:
        if side[k] != 0:
            k += 1
            continue
        j = k
        while j < n and side[j] == 0:
            j += 1
        if 0 < k and j < n and side[k - 1] == side[j] and s[j] - s[k - 1] <= gap:
            side[k:j] = side[j]
        k = j


def surface_pieces(bmap: BodyMap, lines) -> list[tuple[int, np.ndarray]]:
    """The parts of the lines ((N, 2) arrays: the dividing streamlines) with a body on one side and no
    body on the other: [(body number, (N, 2) piece), …], each piece turned so
    that the body is on its LEFT (pieces go counter-clockwise round the body). A surface drawn twice
    (from both of its stagnation points) is kept once."""
    x0, x1, y0, y1 = bmap.box
    cell = max((x1 - x0) / bmap.labels.shape[1], (y1 - y0) / bmap.labels.shape[0])
    probe = PROBE_CELLS * cell
    pieces = []
    for xy in lines:
        if len(xy) < 2:
            continue
        z = xy[:, 0] + 1j * xy[:, 1]
        t = np.gradient(z)
        n = 1j * t / np.where(np.abs(t) > 0, np.abs(t), 1.0)              # left normal
        left, right = bmap.body_at(z + probe * n), bmap.body_at(z - probe * n)
        side = np.where((left > 0) & (right == 0), left, np.where((right > 0) & (left == 0), -right, 0))
        _bridge(side, np.concatenate([[0.0], np.cumsum(np.abs(np.diff(z)))]), GAP_CELLS * cell)
        # runs of points with the same body on the same side
        k = 0
        while k < side.size:
            if side[k] == 0:
                k += 1
                continue
            j = k
            while j + 1 < side.size and side[j + 1] == side[k]:
                j += 1
            if j > k:
                part = z[k:j + 1] if side[k] > 0 else z[k:j + 1][::-1]
                pieces.append((abs(int(side[k])), part))
            k = j + 1
    pieces.sort(key=lambda p: -np.sum(np.abs(np.diff(p[1]))))         # long first
    kept = []
    for body, z in pieces:                                             # drop repeats
        tol = 2.0 * probe
        if any(b == body and np.median(np.min(np.abs(z[:, None] - w[None, ::max(1, w.size // 400)]), axis=1)) < tol
               for b, w in kept):
            continue
        kept.append((body, z))
    return [(b, np.column_stack([z.real, z.imag])) for b, z in kept]


@dataclass
class Body:
    """One body: its surface as polylines ordered counter-clockwise (body on the left; one closed
    ring when the whole body is in the region, else open parts that end at the region border) and
    the singular points inside it."""
    surface: list[np.ndarray]
    closed: bool
    singular: list[complex]

    @property
    def length(self) -> float:
        return float(sum(np.sum(np.hypot(*np.diff(s, axis=0).T)) for s in self.surface))


def scene_map(elements, result, cells: int = 400) -> BodyMap | None:
    """A coarse map of all bodies of the scene (the hint of body_map), from the scene-wide dividing
    streamlines of a StreamlineSet; None when it has none."""
    if not result.scene_dividing or result.scene_region is None:
        return None
    x0, x1, y0, y1 = result.scene_region
    w, h = x1 - x0, y1 - y0
    shape = (max(8, int(round(cells * h / max(w, h)))), max(8, int(round(cells * w / max(w, h)))))
    return body_map(elements, result.scene_region, shape,
                    list(result.scene_dividing) + list(getattr(result, "scene_inner", [])))


def find_bodies(elements, dividing, region, cells: int = 480, inner=()) -> list[Body]:
    """The bodies of a scene in `region` = (x0, x1, y0, y1) (a grid of about `cells` cells across is
    used to tell the sides of the lines apart; the surfaces themselves are the traced lines).
    `inner`: the branches into bodies (borders, never surfaces). Body regions that touch (e.g. the
    ring of a fast-spinning cylinder and the cylinder) are one body."""
    x0, x1, y0, y1 = map(float, region)
    w, h = x1 - x0, y1 - y0
    shape = (max(8, int(round(cells * h / max(w, h)))), max(8, int(round(cells * w / max(w, h)))))
    bmap = body_map(elements, (x0, x1, y0, y1), shape, list(dividing) + list(inner))
    if bmap is None or bmap.count == 0:
        return []
    labels, count = _label(bmap.mask)                                  # touching regions: one body
    bmap = BodyMap(bmap.box, labels.astype(np.int32), int(count))
    pieces = surface_pieces(bmap, dividing)
    sing = np.array(singular_points(active(elements)), dtype=complex)
    cell = max(w / shape[1], h / shape[0])
    out = []
    for k in range(1, bmap.count + 1):
        mine = [p[:, 0] + 1j * p[:, 1] for b, p in pieces if b == k]
        if not mine:
            continue
        chains, closed = _chain(mine, 4.0 * cell)
        inside = [complex(s) for s in sing if bmap.body_at(np.array([s]))[0] == k]
        out.append(Body([np.column_stack([c.real, c.imag]) for c in chains], closed, inside))
    return out


def _chain(parts, tol):
    """Join pieces end to start (all go the same way round) into as few polylines as possible.
    Returns (chains, closed): closed = one chain whose end meets its start."""
    parts = list(parts)
    chains = []
    while parts:
        # start at a piece that no other piece leads into (an open end), else anywhere
        ends = [p[-1] for p in parts]
        first = next((i for i, p in enumerate(parts)
                      if min((abs(p[0] - e) for j, e in enumerate(ends) if j != i), default=np.inf) > tol), 0)
        chain = parts.pop(first)
        while parts:
            gaps = [abs(p[0] - chain[-1]) for p in parts]
            j = int(np.argmin(gaps))
            if gaps[j] > tol:
                break
            chain = np.concatenate([chain, parts.pop(j)[1:]])
        chains.append(chain)
    closed = len(chains) == 1 and abs(chains[0][-1] - chains[0][0]) <= tol
    return chains, closed


def body_mask(elements, box, shape, dividing, rng=None) -> np.ndarray | None:
    """Bool picture (rows, cols) of the box: True = inside a body (see body_map)."""
    bmap = body_map(elements, box, shape, dividing, rng)
    return None if bmap is None else bmap.mask
