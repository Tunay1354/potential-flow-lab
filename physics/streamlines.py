"""
streamlines.py — evenly spaced streamlines with direction arrows
(Jobard & Lefer, "Creating evenly-spaced streamlines of arbitrary density", 1997; vectorised).

How it works
1. d is the desired distance between neighbouring streamlines (smaller d = higher density).
2. The FIRST line starts in the middle of the edge where the flow enters the view. Every accepted
   line then proposes new seeds on both sides of it, exactly d away (neighbour seeding), so the
   picture grows outwards with an even spacing. When no neighbour seed is left, the next seed comes
   from a priority list (rings around singular points, points along walls), and finally from a
   regular grid that fills whatever is still empty.
3. Seeds are integrated in batches with RK4, forwards and backwards along the direction field V/|V|
   (step = arc length), which gives the geometric streamline.
4. A line stops when it comes closer than STOP_RATIO·d to another line, leaves the view, comes close
   to a singular point, leaves the fluid region, reaches a stagnation point, or closes on itself.
   Ends caused by "too close to another line" are marked (`tapers`) so the plot can fade them out
   instead of ending them abruptly.

"Distance to existing lines" is looked up in two rasters (cell size d/4) in which every accepted
line is stamped with a disk of radius STOP_RATIO·d (stop test) and SEED_RATIO·d (seed test).

The velocity always comes from the analytic superposition (field.py), never from a picture, so the
streamlines are exact up to the integration error.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Sequence

import numpy as np

from .base import FlowElement
from .field import active, complex_potential, complex_velocity, fluid_mask, singular_points
from .images import resolve

BASE_LINES_ACROSS = 26          # ~ number of line spacings across the view at density 1
STOP_RATIO = 0.4                # a line stops at STOP_RATIO·d from another line
SEED_RATIO = 0.9                # a seed must be at least SEED_RATIO·d from every line
MIN_LENGTH_RATIO = 2.0          # lines shorter than this many d (+ fading ends) are not drawn
TAPER_RATIO = 1.5               # length (in d) over which a cut line end fades out (used by the plot)
MAX_TURN_COS = 0.7              # turning more than ~45° in one step = stagnation (saddle) point
FADE_LEVELS = 4                 # number of opacity steps in a fading line end
ARROW_SPACING_RATIO = 6.5       # distance between arrows (in d) at arrow density 1


class Cancelled(Exception):
    """Raised inside trace_streamlines when the `cancelled` callback returns True."""


@dataclass
class StreamlineSet:
    lines: list[np.ndarray] = field(default_factory=list)          # each (N, 2), ordered in flow direction
    arrows: list[tuple[float, float, float]] = field(default_factory=list)   # (x, y, angle_rad)
    tapers: list[tuple[bool, bool]] = field(default_factory=list)  # per line: (start cut, end cut)
    separation: float = 0.0                                        # line spacing d used


class _Raster:
    """Boolean raster over the (extended) view used for 'is there a line within radius r?' tests."""

    def __init__(self, x0, y0, W, H, cell):
        self.x0, self.y0, self.c = x0, y0, cell
        self.nx, self.ny = max(1, math.ceil(W / cell)), max(1, math.ceil(H / cell))
        self.a = np.zeros((self.ny, self.nx), dtype=bool)

    def index(self, z):
        ix = np.clip(((z.real - self.x0) / self.c).astype(int), 0, self.nx - 1)
        iy = np.clip(((z.imag - self.y0) / self.c).astype(int), 0, self.ny - 1)
        return iy, ix

    def test(self, z):
        iy, ix = self.index(z)
        return self.a[iy, ix]

    def stamp(self, z, radius):
        r = int(math.ceil(radius / self.c))
        oy, ox = np.mgrid[-r:r + 1, -r:r + 1]
        keep = (ox**2 + oy**2) * self.c**2 <= radius**2
        oy, ox = oy[keep], ox[keep]
        iy, ix = self.index(z)
        yy = np.clip(iy[:, None] + oy[None, :], 0, self.ny - 1)
        xx = np.clip(ix[:, None] + ox[None, :], 0, self.nx - 1)
        self.a[yy, xx] = True


def trace_streamlines(elements: Sequence[FlowElement], xlim, ylim, density: float = 1.0,
                      arrow_density: float = 1.0, batch_size: int = 32, max_length_factor: float = 4.0,
                      cancelled: Callable[[], bool] | None = None, seeds: Sequence[complex] = (),
                      **_ignored) -> StreamlineSet:
    """Evenly spaced streamlines of the visible region.
    density        1 = default spacing; 2 = twice as many lines
    arrow_density  1 = default spacing between arrows; 0 = no arrows
    cancelled      called now and then; returning True aborts with `Cancelled`
    seeds          points whose streamlines are drawn first (e.g. through a stagnation point)"""
    els = active(elements)              # user's elements (walls give the fluid region)
    flows = resolve(els)                # flow elements + wall images (give the velocity)
    x0, x1 = map(float, xlim)
    y0, y1 = map(float, ylim)
    W, H = x1 - x0, y1 - y0
    out = StreamlineSet()
    if not flows or W <= 0 or H <= 0:
        return out

    # line spacing from the FLUID area in view (walls / wedges may hide part of the view)
    gx, gy = np.meshgrid(np.linspace(x0, x1, 33), np.linspace(y0, y1, 33))
    fluid_fraction = max(float(np.mean(fluid_mask(els, gx + 1j * gy))), 0.02)
    d = math.sqrt(W * H * fluid_fraction) / (BASE_LINES_ACROSS * max(density, 0.05))
    d_stop = STOP_RATIO * d
    h = d / 3.0                                   # integration step (arc length) far from singularities
    out.separation = d

    sing = np.array(singular_points(els), dtype=np.complex128)
    r_sing = 0.5 * d

    # typical speed in the view -> threshold for stagnation points
    gx, gy = np.meshgrid(np.linspace(x0, x1, 17), np.linspace(y0, y1, 17))
    with np.errstate(invalid="ignore"):
        sp = np.abs(complex_velocity(flows, gx + 1j * gy))
    sp = sp[fluid_mask(els, gx + 1j * gy)]
    sp = sp[np.isfinite(sp)]
    if sp.size == 0 or np.nanmedian(sp) == 0:
        return out
    v_min = 1e-4 * float(np.nanmedian(sp))

    margin = 0.02 * max(W, H)
    bx0, bx1, by0, by1 = x0 - margin, x1 + margin, y0 - margin, y1 + margin
    n_max = int(max_length_factor * (W + H) / h) + 1

    near_stop = _Raster(bx0, by0, bx1 - bx0, by1 - by0, d / 4.0)    # lines within STOP_RATIO·d
    near_seed = _Raster(bx0, by0, bx1 - bx0, by1 - by0, d / 4.0)    # lines within SEED_RATIO·d
    # walls and wedge sides are streamlines too: mark them, so lines keep the same spacing from them
    for e in els:
        for origin, direc, _normal, ray in _boundary_lines(e):
            t_lo, t_hi = _line_range(origin, direc, bx0, bx1, by0, by1, ray)
            if t_hi > t_lo:
                wall = origin + np.arange(t_lo, t_hi + d / 4.0, d / 4.0) * direc
                near_stop.stamp(wall, STOP_RATIO * d)
                near_seed.stamp(wall, SEED_RATIO * d)

    def check_cancel():
        if cancelled is not None and cancelled():
            raise Cancelled()

    def direction(z):
        """Unit direction (complex) and speed of the flow at z."""
        vel = np.conj(complex_velocity(flows, z))        # u + i v
        speed = np.abs(vel)
        with np.errstate(divide="ignore", invalid="ignore"):
            return vel / speed, speed

    def blocked(z):
        """Points where a line must stop without including the point."""
        bad = ~fluid_mask(els, z)
        if sing.size:
            bad |= np.min(np.abs(z[:, None] - sing[None, :]), axis=1) < r_sing
        return bad

    barrier_elements = [e for e in els if e.crosses_boundary(np.zeros(1, complex), np.zeros(1, complex)) is not None]

    def crossed(za, zb):
        """Step za -> zb crosses a boundary with fluid on both sides (e.g. a plate)."""
        res = np.zeros(za.shape, dtype=bool)
        for e in barrier_elements:
            res |= e.crosses_boundary(za, zb)
        return res

    def local_step(z):
        """Arc-length step: h far away, smaller near singular points (where curvature ~ 1/r)."""
        if not sing.size:
            return np.full(z.shape, h)
        dist = np.min(np.abs(z[:, None] - sing[None, :]), axis=1)
        return np.clip(0.2 * dist, h / 8.0, h)

    def integrate(seeds: np.ndarray, sign: float):
        """Integrate all seeds; returns point arrays (complex), closed flags and 'stopped near a line' flags."""
        B = seeds.size
        traj = np.full((n_max + 1, B), np.nan + 0j)
        traj[0] = seeds
        cur = seeds.copy()
        alive = np.ones(B, dtype=bool)
        length = np.zeros(B)
        closed = np.zeros(B, dtype=bool)
        near_end = np.zeros(B, dtype=bool)
        alive &= np.isfinite(direction(seeds)[0])
        for step in range(n_max):
            idx = np.nonzero(alive)[0]
            if idx.size == 0:
                break
            if step % 64 == 0:
                check_cancel()
            z = cur[idx]
            hz = local_step(z)
            k1 = direction(z)[0] * sign
            k2 = direction(z + 0.5 * hz * k1)[0] * sign
            k3 = direction(z + 0.5 * hz * k2)[0] * sign
            k4 = direction(z + hz * k3)[0] * sign
            z_new = z + hz * (k1 + 2 * k2 + 2 * k3 + k4) / 6.0
            k_new, speed_new = direction(z_new)
            k_new = k_new * sign

            other = ~np.isfinite(z_new) | ~np.isfinite(k_new) | blocked(z_new)
            other |= speed_new < v_min                                     # stagnation point
            other |= (k1.real * k_new.real + k1.imag * k_new.imag) < MAX_TURN_COS   # saddle / reversal
            other |= np.abs(z_new - z) < 0.5 * hz                          # no progress (stagnation)
            if barrier_elements:
                other |= crossed(z, z_new)                                 # would cross a plate
            near = near_stop.test(z_new)                                   # too close to a line
            stop_before = other | near
            near_end[idx[near & ~other]] = True
            ok = ~stop_before
            ok_idx = idx[ok]
            zn = z_new[ok]
            traj[step + 1, ok_idx] = zn
            cur[ok_idx] = zn
            length[ok_idx] += hz[ok]

            outside = (zn.real < bx0) | (zn.real > bx1) | (zn.imag < by0) | (zn.imag > by1)
            back_home = (length[ok_idx] > 3.0 * d) & (np.abs(zn - seeds[ok_idx]) < 0.75 * hz[ok])
            closed[ok_idx[back_home]] = True
            alive[idx[stop_before]] = False
            alive[ok_idx[outside | back_home]] = False

        lines = []
        for j in range(B):
            col = traj[:, j]
            finite = np.isfinite(col)
            n = col.size if finite.all() else int(np.argmax(~finite))
            pts = col[:n]
            if closed[j]:
                pts = np.append(pts, seeds[j])           # close the loop exactly
            lines.append(pts)
        return lines, closed, near_end

    def seed_ok(z):
        z = np.atleast_1d(z)
        return ~blocked(z) & ~near_seed.test(z) & (z.real > x0) & (z.real < x1) & (z.imag > y0) & (z.imag < y1)

    # ------------------------------------------------------------------ seed sources
    def stream_fn(z):
        with np.errstate(all="ignore"):
            return complex_potential(flows, z).imag

    def pick(source: deque, limit: int):
        """Up to `limit` seeds from `source` that are usable now, at least 2d apart and (very
        probably) on different streamlines (different ψ). Seeds that only clash with this batch
        go back to the front of the queue; seeds that are no longer usable are dropped (the
        rasters only fill up, so they can never become usable again)."""
        batch, b_psi, b_tol, deferred = [], [], [], []
        while source and len(batch) < limit:
            n = min(len(source), 8 * batch_size)
            cand = np.array([source.popleft() for _ in range(n)])
            ok = seed_ok(cand)
            psi = stream_fn(cand)
            speed = np.abs(complex_velocity(flows, cand))
            for z, good, p, v in zip(cand, ok, psi, speed):
                if not good:
                    continue
                if len(batch) >= limit:
                    deferred.append(z)
                    continue
                if any(abs(z - b) < 2.0 * d for b in batch) or (
                        np.isfinite(p) and any(abs(p - bp) < bt for bp, bt in zip(b_psi, b_tol))):
                    deferred.append(z)
                    continue
                batch.append(z)
                b_psi.append(p if np.isfinite(p) else np.inf)
                b_tol.append(0.3 * d * v if np.isfinite(v) else 0.0)
            if batch and deferred:
                break
        source.extendleft(reversed(deferred))
        return np.array(batch) if batch else None

    queue: deque = deque()                       # neighbour seeds of accepted lines (processed first)
    priority = deque(_priority_seeds(els, x0, x1, y0, y1, d, sing, r_sing))
    grid = deque(_grid_seeds(x0, x1, y0, y1, d))
    first = np.concatenate([np.asarray(seeds, dtype=complex).ravel(), _inflow_seeds(els, flows, x0, x1, y0, y1, d)])
    first = first[seed_ok(first)] if first.size else first

    def next_batch():
        nonlocal first
        if first is not None:
            batch, first = first, None
            if batch.size:
                return batch
        for source in (queue, priority, grid):
            batch = pick(source, batch_size)
            if batch is not None:
                return batch
        return None

    # ------------------------------------------------------------------ main loop
    while True:
        check_cancel()
        seeds = next_batch()
        if seeds is None:
            break
        fwd, closed, fwd_near = integrate(seeds, +1.0)
        bwd = [np.array([s]) for s in seeds]
        bwd_near = np.zeros(seeds.size, dtype=bool)
        need_back = np.nonzero(~closed)[0]
        if need_back.size:
            back_lines, _, back_near = integrate(seeds[need_back], -1.0)
            for k, j in enumerate(need_back):
                bwd[j] = back_lines[k]
                bwd_near[j] = back_near[k]

        for j in range(seeds.size):
            if near_seed.test(seeds[j:j + 1])[0]:
                continue                                          # a line from this batch passed nearby
            pts = np.concatenate([bwd[j][::-1], fwd[j][1:]])       # ordered along the flow
            s = bwd[j].size - 1                                    # index of the seed
            if pts.size < 3:
                continue
            hit = near_stop.test(pts)                             # lines accepted earlier in this batch
            after = np.nonzero(hit[s + 1:])[0]
            end = s + 1 + after[0] if after.size else pts.size
            before = np.nonzero(hit[:s])[0]
            start = before[-1] + 1 if before.size else 0
            seg = pts[start:end]
            if seg.size < 3:
                continue
            is_closed = bool(closed[j]) and start == 0 and end == pts.size
            taper = (False, False) if is_closed else (bool(bwd_near[j] or start > 0),
                                                      bool(fwd_near[j] or end < pts.size))
            # every line needs a fully opaque middle part: a fading end costs TAPER_RATIO·d extra
            min_len = (MIN_LENGTH_RATIO + TAPER_RATIO * (int(taper[0]) + int(taper[1]))) * d
            if float(np.sum(np.abs(np.diff(seg)))) < min_len:
                continue
            near_stop.stamp(seg, d_stop)
            near_seed.stamp(seg, SEED_RATIO * d)
            out.lines.append(np.column_stack([seg.real, seg.imag]))
            out.tapers.append(taper)
            queue.extend(_neighbour_seeds(seg, d))
    out.arrows = _place_arrows(out.lines, out.tapers, d, arrow_density,
                               (x0 + 0.5 * d, y0 + 0.5 * d, W - d, H - d))
    return out


# ---------------------------------------------------------------------- seeds
def _neighbour_seeds(seg: np.ndarray, d: float) -> list[complex]:
    """Points at distance d on both sides of a line, every d along it (alternating sides)."""
    ds = np.abs(np.diff(seg))
    s = np.concatenate([[0.0], np.cumsum(ds)])
    if s[-1] <= 0:
        return []
    out = []
    for target in np.arange(0.5 * d, s[-1], d):
        k = int(np.clip(np.searchsorted(s, target), 1, seg.size - 1))
        t = seg[k] - seg[k - 1]
        if abs(t) == 0:
            continue
        nrm = 1j * t / abs(t)
        out.append(seg[k] + d * nrm)
        out.append(seg[k] - d * nrm)
    return out


def _priority_seeds(els, x0, x1, y0, y1, d, sing, r_sing) -> np.ndarray:
    """Seeds used when no neighbour seed is left, in this order:
    1. small rings around singular points (closed circles around a vortex, lines out of a source),
    2. points d away from walls and wedge sides (lines that follow the wall)."""
    ring = []
    inside = sing[(sing.real > x0) & (sing.real < x1) & (sing.imag > y0) & (sing.imag < y1)] if sing.size else sing
    for p in inside:
        ring.append(p + 1.5 * r_sing * np.exp(2j * np.pi * np.arange(8) / 8))

    wall_seeds = []
    for e in els:
        for origin, direc, normal, ray in _boundary_lines(e):
            t_lo, t_hi = _line_range(origin, direc, x0, x1, y0, y1, ray)
            if t_hi <= t_lo:
                continue
            t = np.arange(t_lo + d, t_hi, 2.0 * d)
            if t.size:
                wall_seeds.append(origin + t * direc + d * normal)

    parts = ring + wall_seeds
    return np.concatenate(parts) if parts else np.zeros(0, complex)


def _inflow_seeds(els, flows, x0, x1, y0, y1, d) -> np.ndarray:
    """Seeds along the part of the view border where the flow ENTERS the view, spaced so that the
    lines start exactly d apart (measured across the flow). Each inflow stretch is anchored at its
    middle, so symmetric scenes give symmetric pictures. Returned middle-first, strongest stretch
    first (earlier seeds win when lines of the same batch come too close)."""
    inset = 0.3 * d
    corners = [complex(x0 + inset, y0 + inset), complex(x1 - inset, y0 + inset),
               complex(x1 - inset, y1 - inset), complex(x0 + inset, y1 - inset)]
    step = d / 8.0
    pts, nrm = [], []
    for k in range(4):                                   # counter-clockwise around the view
        a, b = corners[k], corners[(k + 1) % 4]
        L = abs(b - a)
        if L <= 0:
            continue
        n = max(2, int(math.ceil(L / step)))
        pts.append(a + (np.arange(n) / n) * (b - a))
        nrm.append(np.full(n, 1j * (b - a) / L))         # left of the direction = into the view
    if not pts:
        return np.zeros(0, complex)
    P, N = np.concatenate(pts), np.concatenate(nrm)
    M = 0.5 * (P + np.roll(P, -1))                      # middle of the border piece P[i] -> P[i+1]
    with np.errstate(all="ignore"):
        vel = np.conj(complex_velocity(flows, P))
        cos_in = (vel * np.conj(N)).real / np.abs(vel)
        vel_m = np.conj(complex_velocity(flows, M))
        cos_m = (vel_m * np.conj(N)).real / np.abs(vel_m)  # N[i] is the normal of piece i (also at corners)
    cos_m = np.where(np.isfinite(cos_m), np.maximum(cos_m, 0.0), 0.0)
    ok = np.isfinite(cos_in) & (cos_in > 0.05) & fluid_mask(els, P)
    if not ok.any():
        return np.zeros(0, complex)
    if not ok.all():                                     # start the walk at a point without inflow
        r = int(np.argmax(~ok))
        P, cos_m, ok = np.roll(P, -r), np.roll(cos_m, -r), np.roll(ok, -r)
    edges = np.diff(np.concatenate([[0], ok.astype(int), [0]]))
    starts, ends = np.nonzero(edges == 1)[0], np.nonzero(edges == -1)[0]
    runs = []
    for i0, i1 in zip(starts, ends):
        seg, c = P[i0:i1], cos_m[i0:i1 - 1]
        if seg.size < 2:
            continue
        ds = np.abs(np.diff(seg))
        C = np.concatenate([[0.0], np.cumsum(c * ds)])   # distance across the flow (midpoint rule)
        total = C[-1]
        if total < 0.6 * d:
            continue
        mid = 0.5 * total
        k = np.arange(-math.floor(mid / d), math.floor(mid / d) + 1)
        levels = mid + k * d
        levels = levels[(levels >= 0.3 * d) & (levels <= total - 0.3 * d)]
        levels = levels[np.argsort(np.abs(levels - mid), kind="stable")]
        idx = np.arange(seg.size)
        f = np.interp(levels, C, idx)
        i = np.clip(np.floor(f).astype(int), 0, seg.size - 2)
        z = seg[i] + (f - i) * (seg[i + 1] - seg[i])
        runs.append((total, z))
    runs.sort(key=lambda r: -r[0])
    return np.concatenate([z for _, z in runs]) if runs else np.zeros(0, complex)


def _boundary_lines(e):
    """Straight boundaries of an element as (origin, unit direction, unit normal into the fluid, is_ray)."""
    if e.IS_BOUNDARY and hasattr(e, "normal"):
        return [(e.point, e.direction, e.normal, False)]
    if e.TYPE == "sector":
        a1, a2 = math.radians(e.theta1), math.radians(e.theta1 + e.beta_deg)
        d1, d2 = complex(math.cos(a1), math.sin(a1)), complex(math.cos(a2), math.sin(a2))
        return [(e.z0, d1, 1j * d1, True), (e.z0, d2, -1j * d2, True)]
    return []


def _line_range(origin, direc, x0, x1, y0, y1, ray):
    t0, t1 = (0.0 if ray else -np.inf), np.inf
    for pc, dc, lo, hi in ((origin.real, direc.real, x0, x1), (origin.imag, direc.imag, y0, y1)):
        if abs(dc) < 1e-15:
            if pc < lo or pc > hi:
                return 0.0, -1.0
            continue
        a, b = (lo - pc) / dc, (hi - pc) / dc
        t0, t1 = max(t0, min(a, b)), min(t1, max(a, b))
    return t0, t1


def _grid_seeds(x0, x1, y0, y1, d) -> np.ndarray:
    """Regular grid (spacing d), ordered from the view center outwards (repeatable, symmetric)."""
    cx = np.arange(x0 + 0.5 * d, x1, d)
    cy = np.arange(y0 + 0.5 * d, y1, d)
    CX, CY = np.meshgrid(cx, cy)
    g = (CX + 1j * CY).ravel()
    c = complex(0.5 * (x0 + x1), 0.5 * (y0 + y1))
    return g[np.argsort(np.abs(g - c), kind="stable")]


# ---------------------------------------------------------------------- arrows
def _place_arrows(lines: list[np.ndarray], tapers: list[tuple[bool, bool]], d: float,
                  arrow_density: float, box) -> list[tuple[float, float, float]]:
    """Direction arrows spread evenly over the PICTURE (not a fixed number per line).
    A hexagonal lattice of spacing ARROW_SPACING_RATIO·d / arrow_density is fixed to the plot
    coordinates; every lattice point is moved to the nearest point of a streamline and becomes an
    arrow (pointing in the flow direction). Rows of the lattice are shifted by half a spacing, so
    the arrows are staggered, and because the lattice does not move with the view, arrows stay in
    place while panning. Fading ends and the first / last half d of a line get no arrow."""
    if arrow_density <= 0 or not lines:
        return []
    R = ARROW_SPACING_RATIO * d / arrow_density
    pts, tan = [], []
    for xy, (cut0, cut1) in zip(lines, tapers):
        seg = xy[:, 0] + 1j * xy[:, 1]
        s = np.concatenate([[0.0], np.cumsum(np.abs(np.diff(seg)))])
        lo = TAPER_RATIO * d if cut0 else 0.5 * d
        hi = s[-1] - (TAPER_RATIO * d if cut1 else 0.5 * d)
        if hi <= lo:
            continue
        targets = np.arange(lo, hi, d / 4.0)
        k = np.clip(np.searchsorted(s, targets), 1, seg.size - 1)
        ds = np.maximum(s[k] - s[k - 1], 1e-300)
        f = np.clip((targets - s[k - 1]) / ds, 0.0, 1.0)
        pts.append(seg[k - 1] + f * (seg[k] - seg[k - 1]))
        tan.append(seg[k] - seg[k - 1])
    if not pts:
        return []
    P, T = np.concatenate(pts), np.concatenate(tan)

    bx, by, bw, bh = box
    ry = R * math.sqrt(3.0) / 2.0
    lattice = []
    for j in range(math.floor(by / ry), math.ceil((by + bh) / ry) + 1):
        shift = 0.5 * R if j % 2 else 0.0
        i = np.arange(math.floor((bx - shift) / R), math.ceil((bx + bw - shift) / R) + 1)
        lattice.append(i * R + shift + 1j * j * ry)
    L = np.concatenate(lattice)
    L = L[(L.real >= bx) & (L.real <= bx + bw) & (L.imag >= by) & (L.imag <= by + bh)]

    arrows = []
    chunk = max(1, 400000 // P.size)
    for c0 in range(0, L.size, chunk):
        D = np.abs(L[c0:c0 + chunk, None] - P[None, :])
        nearest = np.argmin(D, axis=1)
        dist = D[np.arange(nearest.size), nearest]
        for k, dk in zip(nearest, dist):
            if dk < 0.75 * d:
                arrows.append((float(P[k].real), float(P[k].imag), float(np.angle(T[k]))))
    return arrows


def _length(xy: np.ndarray) -> float:
    return float(np.sum(np.hypot(np.diff(xy[:, 0]), np.diff(xy[:, 1]))))


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
    out: list[list[np.ndarray]] = [[] for _ in range(levels + 1)]
    gap = np.array([[np.nan, np.nan]])
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
            out[0] += [_piece(xy, s, a, b), gap]
        for k in range(1, levels + 1):
            lo, hi = Lt * (levels - k) / levels, Lt * (levels - k + 1) / levels
            if cut0:
                out[k] += [_piece(xy, s, lo, hi), gap]
            if cut1:
                out[k] += [_piece(xy, s, total - hi, total - lo), gap]
    return [np.vstack(parts) if parts else np.zeros((0, 2)) for parts in out]


def _piece(xy: np.ndarray, s: np.ndarray, a: float, b: float) -> np.ndarray:
    """Part of a polyline between arc lengths a and b (end points interpolated)."""
    inner = (s > a) & (s < b)
    pa = np.array([np.interp(a, s, xy[:, 0]), np.interp(a, s, xy[:, 1])])
    pb = np.array([np.interp(b, s, xy[:, 0]), np.interp(b, s, xy[:, 1])])
    return np.vstack([pa, xy[inner], pb])
