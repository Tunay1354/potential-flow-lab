"""
streamlines.py — evenly spaced streamlines with direction arrows
(Jobard & Lefer, "Creating evenly-spaced streamlines of arbitrary density", 1997).

How it works
1. d is the desired distance between neighbouring streamlines (smaller d = higher density).
2. The FIRST lines start on the border where the flow enters the region, exactly d apart. Every
   accepted line then proposes new seeds on both sides of it, d away (neighbour seeding), so the
   picture grows outwards with an even spacing. When no neighbour seed is left, the next seeds come
   from rings around singular points and points along walls, and finally from a regular grid.
3. Seeds are integrated with RK4 forwards and backwards along the direction field V/|V|
   (step = arc length). The compiled kernel (kernel.py) is used when available, else NumPy.
4. A line stops when it comes closer than STOP_RATIO·d to another line, leaves the region, comes
   close to a singular point, leaves the fluid, reaches a stagnation point, or closes on itself.
   Ends caused by "too close to another line" fade out in the plot (`tapers`).

"Distance to existing lines" is looked up in rasters (cell size d/4) in which every line is stamped
with a disk of radius STOP_RATIO·d (stop test) and SEED_RATIO·d (seed test).

Interactive use (the plot): StreamlineField keeps its lines. When the visible region grows
(pan / zoom out) the old lines stay exactly where they are: lines that ended at the old region border
are continued, and only the new area gets new seeds. StreamlineCache keeps one field per spacing
level d = 2^−L (the level changes only after a clear zoom). Optionally a finer level can start from
the lines of the coarser one (COARSE_LEVELS).

The velocity always comes from the analytic superposition, never from a picture, so the streamlines
are exact up to the integration error.
"""
from __future__ import annotations

import itertools
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Sequence

import numpy as np

from . import kernel
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
BOX_MARGIN_RATIO = 0.6          # lines may run this many d beyond the region before they stop
BATCH_SIZE = 32

WALL_ID = 2 ** 30               # owner id of walls in the stop raster (never equal to a line id)
_line_ids = itertools.count()   # every line ever created gets its own id


class Cancelled(Exception):
    """Raised inside the computation when the `cancelled` callback returns True."""


@dataclass
class StreamlineSet:
    lines: list[np.ndarray] = field(default_factory=list)          # each (N, 2), ordered in flow direction
    arrows: list[tuple[float, float, float]] = field(default_factory=list)   # (x, y, angle_rad)
    tapers: list[tuple[bool, bool]] = field(default_factory=list)  # per line: (start cut, end cut)
    separation: float = 0.0                                        # line spacing d used
    domain: tuple[float, float, float, float] | None = None        # region filled with lines (x0, x1, y0, y1)
    stagnation: list = field(default_factory=list)                 # StagnationPoint (stagnation.py)
    dividing: list[np.ndarray] = field(default_factory=list)       # dividing streamlines, (N, 2) each
    dividing_owner: list[int] = field(default_factory=list)        # index in `stagnation` of each one


@dataclass
class _Line:
    """A streamline: points ordered along the flow and why each end stops:
    "near" (came too close to another line -> fades out), "box" (left the computed region; may be
    continued later), "stop" (wall, singular point, stagnation point ...), "closed" (a loop)."""
    id: int
    pts: np.ndarray
    start: str
    end: str

    @property
    def taper(self) -> tuple[bool, bool]:
        return self.start == "near", self.end == "near"


# ---------------------------------------------------------------------- rasters
class _Raster:
    """Boolean raster over a region: 'is there a line within radius r?'"""

    def __init__(self, x0, y0, W, H, cell):
        self.x0, self.y0, self.c = x0, y0, cell
        self.nx, self.ny = max(1, math.ceil(W / cell)), max(1, math.ceil(H / cell))
        self.a = np.zeros((self.ny, self.nx), dtype=bool)

    def index(self, z):
        ix = np.clip(((z.real - self.x0) / self.c).astype(int), 0, self.nx - 1)
        iy = np.clip(((z.imag - self.y0) / self.c).astype(int), 0, self.ny - 1)
        return iy, ix

    def _disk(self, z, radius):
        r = int(math.ceil(radius / self.c))
        oy, ox = np.mgrid[-r:r + 1, -r:r + 1]
        keep = (ox**2 + oy**2) * self.c**2 <= radius**2
        oy, ox = oy[keep], ox[keep]
        iy, ix = self.index(z)
        yy = np.clip(iy[:, None] + oy[None, :], 0, self.ny - 1)
        xx = np.clip(ix[:, None] + ox[None, :], 0, self.nx - 1)
        return yy, xx

    def test(self, z):
        iy, ix = self.index(z)
        return self.a[iy, ix]

    def stamp(self, z, radius):
        yy, xx = self._disk(z, radius)
        self.a[yy, xx] = True


class _OwnerRaster(_Raster):
    """Stop raster that remembers WHICH lines are near a cell (two ids per cell, −1 = none), so a
    line that is being continued is not stopped by itself. Two slots are enough: a cell near two or
    more lines always holds at least one id that is not the testing line's own."""

    def __init__(self, x0, y0, W, H, cell):
        super().__init__(x0, y0, W, H, cell)
        self.a = np.full((2, self.ny, self.nx), -1, dtype=np.int32)

    def test(self, z, self_id=-1):
        iy, ix = self.index(z)
        r0, r1 = self.a[0, iy, ix], self.a[1, iy, ix]
        return ((r0 >= 0) & (r0 != self_id)) | ((r1 >= 0) & (r1 != self_id))

    def stamp(self, z, radius, owner=0):
        yy, xx = self._disk(z, radius)
        lin = np.unique(yy.ravel() * self.nx + xx.ravel())
        l0, l1 = self.a[0].reshape(-1), self.a[1].reshape(-1)        # views
        cur = l0[lin]
        l0[lin[cur == -1]] = owner
        l1[lin[(cur != -1) & (cur != owner)]] = owner


# ---------------------------------------------------------------------- one spacing level
class StreamlineField:
    """Evenly spaced streamlines of one scene at line spacing d, for a region that can grow.
    extend(region) fills `region` with lines; lines found before never move."""

    def __init__(self, elements: Sequence[FlowElement], d: float, v_min: float | None = None,
                 use_kernel: bool = True):
        self.els = active(elements)              # user's elements (walls give the fluid region)
        self.flows = resolve(self.els)           # flow elements + wall images (give the velocity)
        self.d = float(d)
        self.h = self.d / 3.0                    # integration step (arc length) far from singularities
        self.r_sing = 0.5 * self.d
        self.sing = np.array(singular_points(self.els), dtype=np.complex128)
        self.v_min = v_min
        self.compiled = kernel.compile_scene(self.els, self.flows) if use_kernel else None
        self.domain: tuple[float, float, float, float] | None = None
        self.lines: list[_Line] = []             # lines of this level
        self.base_lines: list[_Line] = []        # lines of the coarser level (kept as they are)
        self._base_source: list[_Line] = []      # the same lines as given (before refining)
        self._fresh_parts: list[np.ndarray] = []  # new pieces of the coarser picture since the last fill
        self.queue: deque = deque()
        self.special_seeds = np.zeros(0, complex)   # e.g. points on dividing streamlines: used first
        self._cancelled: Callable[[], bool] | None = None
        self._barriers = [e for e in self.els
                          if e.crosses_boundary(np.zeros(1, complex), np.zeros(1, complex)) is not None]

    # ------------------------------------------------------------------ public
    @property
    def all_lines(self) -> list[_Line]:
        return self.base_lines + self.lines

    def contains(self, region) -> bool:
        if self.domain is None:
            return False
        x0, x1, y0, y1 = region
        a0, a1, b0, b1 = self.domain
        return a0 <= x0 and x1 <= a1 and b0 <= y0 and y1 <= b1

    def set_base(self, lines: list[_Line]):
        """Lines of the coarser level: drawn and avoided, never changed by this level. They were
        traced with a longer step, so points are added in between (on the exact tangent
        directions) until their step is as small as this level's."""
        # remember the parts of the coarser picture that are NEW (new lines, lengthened ends): this
        # level has to make room for them (see _yield_to_fresh_base)
        known = np.concatenate([ln.pts for ln in self._base_source]) if self._base_source else np.zeros(0, complex)
        for ln in lines:
            new = ~np.isin(ln.pts, known)
            if not new.any():
                continue
            edges = np.diff(np.concatenate([[0], new.astype(int), [0]]))
            for a, b in zip(np.nonzero(edges == 1)[0], np.nonzero(edges == -1)[0]):
                part = ln.pts[max(a - 1, 0):min(b + 1, ln.pts.size)]          # with the joining point
                self._fresh_parts.append(_refine(part, self.h, self.flows))
        self._base_source = list(lines)
        self.base_lines = [_Line(ln.id, _refine(ln.pts, self.h, self.flows), ln.start, ln.end) for ln in lines]

    def extend(self, region, seeds: Sequence[complex] = (),
               cancelled: Callable[[], bool] | None = None) -> bool:
        """Fill `region` = (x0, x1, y0, y1) with lines. Returns False if it was filled already."""
        if self.contains(region) and not len(seeds):
            return False
        old_domain = self.domain
        try:
            return self._extend(region, seeds, cancelled)
        except Cancelled:
            self.domain = old_domain          # the new area is not complete: fill it again next time
            raise

    def _extend(self, region, seeds, cancelled) -> bool:
        self._cancelled = cancelled
        first = self.domain is None
        x0, x1, y0, y1 = map(float, region)
        if not first:
            a0, a1, b0, b1 = self.domain
            x0, x1, y0, y1 = min(x0, a0), max(x1, a1), min(y0, b0), max(y1, b1)
        if not self.flows or x1 <= x0 or y1 <= y0:
            return False
        if self.v_min is None:
            self.v_min = _stagnation_speed(self.els, self.flows, (x0, x1, y0, y1))
            if self.v_min is None:
                return False
        self.domain = (x0, x1, y0, y1)
        d = self.d
        m = BOX_MARGIN_RATIO * d
        self.box = (x0 - m, x1 + m, y0 - m, y1 + m)
        bx0, bx1, by0, by1 = self.box
        self.n_max = int(4.0 * (bx1 - bx0 + by1 - by0) / self.h) + 1

        # rasters for the whole (new) region: walls and every existing line
        self.near_stop = _OwnerRaster(bx0, by0, bx1 - bx0, by1 - by0, d / 4.0)
        self.near_seed = _Raster(bx0, by0, bx1 - bx0, by1 - by0, d / 4.0)
        for e in self.els:     # walls and wedge sides are streamlines too: lines keep the spacing from them
            for origin, direc, _normal, ray in _boundary_lines(e):
                t_lo, t_hi = _line_range(origin, direc, bx0, bx1, by0, by1, ray)
                if t_hi > t_lo:
                    wall = origin + np.arange(t_lo, t_hi + d / 4.0, d / 4.0) * direc
                    self.near_stop.stamp(wall, STOP_RATIO * d, WALL_ID)
                    self.near_seed.stamp(wall, SEED_RATIO * d)
        for ln in self.base_lines:
            self._stamp(ln.pts, ln.id)
        self._yield_to_fresh_base()
        for ln in self.lines:
            self._stamp(ln.pts, ln.id)

        if not first:
            self._continue_lines()
        if not first or self.base_lines:
            for ln in self.all_lines:                      # gaps along existing lines (d away from them)
                self.queue.extend(_neighbour_seeds(ln.pts, d))
            self.queue = deque(self._usable(np.array(self.queue, dtype=complex)))
        rx0, rx1, ry0, ry1 = map(float, region)
        priority = deque(self._usable(_priority_seeds(self.els, x0, x1, y0, y1, d, self.sing, self.r_sing)))
        grid = deque(self._usable(_grid_seeds(x0, x1, y0, y1, d,
                                              center=complex(0.5 * (rx0 + rx1), 0.5 * (ry0 + ry1)))))
        # the first lines start on the inflow border; a grown region, or a level built on a coarser
        # one, continues from the existing lines (neighbour seeds d away), so the spacing stays even
        inflow = (_inflow_seeds(self.els, self.flows, x0, x1, y0, y1, d) if first and not self.base_lines
                  else np.zeros(0, complex))
        sp = self.special_seeds
        inside = (sp.real > x0) & (sp.real < x1) & (sp.imag > y0) & (sp.imag < y1)
        special, self.special_seeds = sp[inside], sp[~inside]          # each special seed is used once
        start = np.concatenate([np.asarray(seeds, dtype=complex).ravel(), special, inflow])
        self._fill(start, priority, grid)
        return True

    def result(self, arrow_density: float = 1.0, arrow_box=None) -> StreamlineSet:
        """All lines (this level and the coarser ones) for drawing; arrows inside `arrow_box`
        (x, y, width, height), default: the whole region."""
        lines = self.all_lines
        out = StreamlineSet(lines=[np.column_stack([ln.pts.real, ln.pts.imag]) for ln in lines],
                            tapers=[ln.taper for ln in lines], separation=self.d, domain=self.domain)
        if arrow_box is None and self.domain is not None:
            x0, x1, y0, y1 = self.domain
            arrow_box = (x0 + 0.5 * self.d, y0 + 0.5 * self.d, x1 - x0 - self.d, y1 - y0 - self.d)
        if arrow_box is not None:
            out.arrows = _place_arrows(out.lines, out.tapers, self.d, arrow_density, arrow_box)
        return out

    def free_trace(self, seeds, sign: float, box):
        """Streamlines from `seeds` in one direction inside `box` = (x0, x1, y0, y1), WITHOUT avoiding
        other lines (used for dividing streamlines and the 'inside a body?' test).
        Returns (point arrays, closed, left_box) — left_box True = the line reached the box border."""
        x0, x1, y0, y1 = map(float, box)
        if self.v_min is None:
            self.v_min = _stagnation_speed(self.els, self.flows, (x0, x1, y0, y1)) or 0.0
        self.box = (x0, x1, y0, y1)
        self.n_max = int(4.0 * (x1 - x0 + y1 - y0) / self.h) + 1
        self.near_stop = _OwnerRaster(x0, y0, x1 - x0, y1 - y0, max(x1 - x0, y1 - y0) / 4.0)
        lines, closed, _near, left = self._integrate(np.atleast_1d(np.asarray(seeds, complex)), sign)
        return lines, closed, left

    # ------------------------------------------------------------------ helpers
    def _check_cancel(self):
        if self._cancelled is not None and self._cancelled():
            raise Cancelled()

    def _stamp(self, pts, owner):
        self.near_stop.stamp(pts, STOP_RATIO * self.d, owner)
        self.near_seed.stamp(pts, SEED_RATIO * self.d)

    def _blocked(self, z):
        """Points where a line must stop without including the point."""
        bad = ~fluid_mask(self.els, z)
        if self.sing.size:
            bad |= np.min(np.abs(z[:, None] - self.sing[None, :]), axis=1) < self.r_sing
        return bad

    def _usable(self, z):
        """Seeds that may start a new line now (inside the region, in the fluid, away from lines)."""
        z = np.atleast_1d(z)
        if z.size == 0:
            return z
        x0, x1, y0, y1 = self.domain
        ok = (z.real > x0) & (z.real < x1) & (z.imag > y0) & (z.imag < y1)
        ok[ok] &= ~self._blocked(z[ok]) & ~self.near_seed.test(z[ok])
        return z[ok]

    def _seed_ok(self, z):
        z = np.atleast_1d(z)
        x0, x1, y0, y1 = self.domain
        return (~self._blocked(z) & ~self.near_seed.test(z) & (z.real > x0) & (z.real < x1)
                & (z.imag > y0) & (z.imag < y1))

    # ------------------------------------------------------------------ integration
    def _integrate(self, seeds, sign, self_ids=None, close_to=None):
        """Lines from all seeds in one direction: (point arrays, closed, near_end, left_box)."""
        seeds = np.asarray(seeds, dtype=np.complex128)
        B = seeds.size
        self_ids = np.full(B, -1, np.int32) if self_ids is None else np.asarray(self_ids, np.int32)
        close_to = seeds.copy() if close_to is None else np.asarray(close_to, np.complex128)
        bx0, bx1, by0, by1 = self.box
        self._check_cancel()
        if self.compiled is not None:
            F, R, W = self.compiled
            ns = self.near_stop
            traj, closed, near_end, left_box = kernel.trace_batch(
                seeds, float(sign), F, R, W, self.sing, self.r_sing, self.h, self.n_max, self.v_min,
                MAX_TURN_COS, self.d, ns.a, self_ids, close_to, bx0, bx1, by0, by1, ns.x0, ns.y0, ns.c)
        else:
            traj, closed, near_end, left_box = self._integrate_numpy(seeds, sign, self_ids, close_to)
        return _columns(traj, close_to, closed), closed, near_end, left_box

    def _direction(self, z):
        vel = np.conj(complex_velocity(self.flows, z))        # u + i v
        speed = np.abs(vel)
        with np.errstate(divide="ignore", invalid="ignore"):
            return vel / speed, speed

    def _integrate_numpy(self, seeds, sign, self_ids, close_to):
        """Same rules as kernel.trace_batch, vectorised over the seeds with NumPy."""
        B, h, d = seeds.size, self.h, self.d
        bx0, bx1, by0, by1 = self.box
        traj = np.full((self.n_max + 1, B), np.nan + 0j)
        traj[0] = seeds
        cur = seeds.copy()
        alive = np.isfinite(self._direction(seeds)[0])
        length = np.zeros(B)
        closed = np.zeros(B, dtype=bool)
        near_end = np.zeros(B, dtype=bool)
        left_box = np.zeros(B, dtype=bool)
        sing = self.sing
        for step in range(self.n_max):
            idx = np.nonzero(alive)[0]
            if idx.size == 0:
                break
            if step % 64 == 0:
                self._check_cancel()
            z = cur[idx]
            if sing.size:
                hz = np.clip(0.2 * np.min(np.abs(z[:, None] - sing[None, :]), axis=1), h / 8.0, h)
            else:
                hz = np.full(z.shape, h)
            k1 = self._direction(z)[0] * sign
            k2 = self._direction(z + 0.5 * hz * k1)[0] * sign
            k3 = self._direction(z + 0.5 * hz * k2)[0] * sign
            k4 = self._direction(z + hz * k3)[0] * sign
            z_new = z + hz * (k1 + 2 * k2 + 2 * k3 + k4) / 6.0
            k_new, speed_new = self._direction(z_new)
            k_new = k_new * sign

            with np.errstate(invalid="ignore"):
                other = ~np.isfinite(z_new) | ~np.isfinite(k_new) | self._blocked(z_new)
                other |= speed_new < self.v_min                                     # stagnation point
                other |= (k1.real * k_new.real + k1.imag * k_new.imag) < MAX_TURN_COS   # saddle / reversal
                other |= np.abs(z_new - z) < 0.5 * hz                               # no progress
            for e in self._barriers:
                other |= e.crosses_boundary(z, z_new)                               # would cross a plate
            near = self.near_stop.test(z_new, self_ids[idx]) & ~other              # too close to a line
            stop_before = other | near
            near_end[idx[near]] = True
            ok = ~stop_before
            ok_idx = idx[ok]
            zn = z_new[ok]
            traj[step + 1, ok_idx] = zn
            cur[ok_idx] = zn
            length[ok_idx] += hz[ok]

            outside = (zn.real < bx0) | (zn.real > bx1) | (zn.imag < by0) | (zn.imag > by1)
            with np.errstate(invalid="ignore"):
                back_home = (~outside & (length[ok_idx] > 3.0 * d)
                             & (np.abs(zn - close_to[ok_idx]) < 0.75 * hz[ok]))
            left_box[ok_idx[outside]] = True
            closed[ok_idx[back_home]] = True
            alive[idx[stop_before]] = False
            alive[ok_idx[outside | back_home]] = False
        return traj, closed, near_end, left_box

    # ------------------------------------------------------------------ growing the picture
    def _yield_to_fresh_base(self):
        """The coarser level is primary: where one of its new (or lengthened) lines comes too close to
        a line of this level, this level's line is cut there; both pieces fade out at the cut and the
        gap is filled again by the usual seeding."""
        fresh, self._fresh_parts = self._fresh_parts, []
        if not fresh or not self.lines:
            return
        ns = self.near_stop
        probe = _Raster(ns.x0, ns.y0, ns.nx * ns.c, ns.ny * ns.c, ns.c)
        for part in fresh:
            probe.stamp(part, STOP_RATIO * self.d)
        kept = []
        for ln in self.lines:
            hit = probe.test(ln.pts)
            if not hit.any():
                kept.append(ln)
                continue
            edges = np.diff(np.concatenate([[0], (~hit).astype(int), [0]]))
            for a, b in zip(np.nonzero(edges == 1)[0], np.nonzero(edges == -1)[0]):
                piece = ln.pts[a:b]
                r0 = ln.start if a == 0 else "near"
                r1 = ln.end if b == ln.pts.size else "near"
                if "closed" in (r0, r1) and (r0, r1) != ("closed", "closed"):
                    r0 = "near" if r0 == "closed" else r0
                    r1 = "near" if r1 == "closed" else r1
                min_len = (MIN_LENGTH_RATIO + TAPER_RATIO * ((r0 == "near") + (r1 == "near"))) * self.d
                if piece.size >= 3 and float(np.sum(np.abs(np.diff(piece)))) >= min_len:
                    kept.append(_Line(next(_line_ids), piece, r0, r1))
        self.lines = kept

    def _continue_lines(self):
        """Lines of this level that ended at the old region border run on into the new region."""
        bx0, bx1, by0, by1 = self.box
        for which, sign in (("end", +1.0), ("start", -1.0)):
            todo = []
            for ln in self.lines:
                if getattr(ln, which) != "box":
                    continue
                p = ln.pts[-1] if which == "end" else ln.pts[0]
                if bx0 < p.real < bx1 and by0 < p.imag < by1:
                    todo.append(ln)
            for k in range(0, len(todo), BATCH_SIZE):
                part = todo[k:k + BATCH_SIZE]
                seeds = np.array([ln.pts[-1] if which == "end" else ln.pts[0] for ln in part])
                other_end = [(ln.pts[0] if which == "end" else ln.pts[-1])
                             if (ln.start if which == "end" else ln.end) == "box" else complex(np.nan, np.nan)
                             for ln in part]
                lines, closed, near_end, left_box = self._integrate(
                    seeds, sign, [ln.id for ln in part], other_end)
                for j, ln in enumerate(part):
                    cont = lines[j]
                    hit = self.near_stop.test(cont[1:], ln.id) if cont.size > 1 else np.zeros(0, bool)
                    cut = np.nonzero(hit)[0]
                    if cut.size:                                  # ran into a line continued just before
                        cont = cont[:cut[0] + 1]
                        reason = "near"
                    elif closed[j]:
                        reason = "closed"
                    elif near_end[j]:
                        reason = "near"
                    elif left_box[j]:
                        reason = "box"
                    else:
                        reason = "stop"
                    new = cont[1:]
                    if which == "end":
                        ln.pts = np.concatenate([ln.pts, new])
                        ln.end = reason
                    else:
                        ln.pts = np.concatenate([new[::-1], ln.pts])
                        ln.start = reason
                    if reason == "closed":
                        ln.start = ln.end = "closed"
                    if new.size:
                        self._stamp(new, ln.id)
                        self.queue.extend(_neighbour_seeds(np.concatenate([cont[:1], new]), self.d))

    def _pick(self, source: deque, limit: int):
        """Up to `limit` seeds from `source` that are usable now, at least 2d apart and (very
        probably) on different streamlines (different ψ). Seeds that only clash with this batch
        go back to the front of the queue; seeds that are no longer usable are dropped (the
        rasters only fill up, so they can never become usable again)."""
        d = self.d
        batch, b_psi, b_tol, deferred = [], [], [], []
        while source and len(batch) < limit:
            n = min(len(source), 8 * BATCH_SIZE)
            cand = np.array([source.popleft() for _ in range(n)])
            ok = self._seed_ok(cand)
            if not ok.any():
                continue
            cand = cand[ok]
            with np.errstate(all="ignore"):
                psi = complex_potential(self.flows, cand).imag
                speed = np.abs(complex_velocity(self.flows, cand))
            for z, p, v in zip(cand, psi, speed):
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

    def _fill(self, start, priority, grid):
        """Jobard–Lefer: integrate seeds batch by batch until no usable seed is left."""
        d = self.d
        first = start[self._seed_ok(start)] if start.size else start
        while True:
            self._check_cancel()
            if first is not None and first.size:
                seeds, first = first, None
            else:
                first = None
                seeds = None
                for source in (self.queue, priority, grid):
                    seeds = self._pick(source, BATCH_SIZE)
                    if seeds is not None:
                        break
                if seeds is None:
                    break
            fwd, closed, fwd_near, fwd_box = self._integrate(seeds, +1.0)
            bwd = [np.array([s]) for s in seeds]
            bwd_near = np.zeros(seeds.size, dtype=bool)
            bwd_box = np.zeros(seeds.size, dtype=bool)
            need_back = np.nonzero(~closed)[0]
            if need_back.size:
                back_lines, _, back_near, back_box = self._integrate(seeds[need_back], -1.0)
                for k, j in enumerate(need_back):
                    bwd[j] = back_lines[k]
                    bwd_near[j] = back_near[k]
                    bwd_box[j] = back_box[k]

            for j in range(seeds.size):
                if self.near_seed.test(seeds[j:j + 1])[0]:
                    continue                                          # a line from this batch passed nearby
                pts = np.concatenate([bwd[j][::-1], fwd[j][1:]])       # ordered along the flow
                s = bwd[j].size - 1                                    # index of the seed
                if pts.size < 3:
                    continue
                hit = self.near_stop.test(pts)                        # lines accepted earlier in this batch
                after = np.nonzero(hit[s + 1:])[0]
                end = s + 1 + after[0] if after.size else pts.size
                before = np.nonzero(hit[:s])[0]
                begin = before[-1] + 1 if before.size else 0
                seg = pts[begin:end]
                if seg.size < 3:
                    continue
                if closed[j] and begin == 0 and end == pts.size:
                    r0 = r1 = "closed"
                else:
                    r0 = "near" if (begin > 0 or bwd_near[j]) else ("box" if bwd_box[j] else "stop")
                    r1 = "near" if (end < pts.size or fwd_near[j]) else ("box" if fwd_box[j] else "stop")
                # every line needs a fully opaque middle part: a fading end costs TAPER_RATIO·d extra
                min_len = (MIN_LENGTH_RATIO + TAPER_RATIO * ((r0 == "near") + (r1 == "near"))) * d
                if float(np.sum(np.abs(np.diff(seg)))) < min_len:
                    continue
                ln = _Line(next(_line_ids), seg, r0, r1)
                self._stamp(seg, ln.id)
                self.lines.append(ln)
                self.queue.extend(_neighbour_seeds(seg, d))


def _refine(pts: np.ndarray, h: float, flows) -> np.ndarray:
    """Insert points into a streamline polyline so that no step is longer than h. Between two points
    the curve is a cubic Hermite spline using the flow direction at both points (exact tangents),
    so the refined line stays on the streamline to high accuracy."""
    if pts.size < 2:
        return pts
    chord = np.diff(pts)
    L = np.abs(chord)
    k = np.maximum(1, np.ceil(L / h - 1e-9).astype(int))
    if k.max() == 1:
        return pts
    with np.errstate(all="ignore"):
        vel = np.conj(complex_velocity(flows, pts))
        t = vel / np.abs(vel)
    # orient the tangents along the line; use the chord where the velocity is unusable
    ref = np.concatenate([chord, chord[-1:]])
    ref = ref / np.where(np.abs(ref) > 0, np.abs(ref), 1.0)
    t = np.where(np.isfinite(t), t, ref)
    t = np.where((t * np.conj(ref)).real < 0, -t, t)
    i = np.repeat(np.arange(chord.size), k)                    # segment of every new point
    s = (np.arange(i.size) - np.repeat(np.cumsum(k) - k, k)) / np.repeat(k, k)
    p0, p1, m0, m1 = pts[i], pts[i + 1], t[i] * L[i], t[i + 1] * L[i]
    h00, h10, h01, h11 = 2 * s**3 - 3 * s**2 + 1, s**3 - 2 * s**2 + s, -2 * s**3 + 3 * s**2, s**3 - s**2
    return np.concatenate([h00 * p0 + h10 * m0 + h01 * p1 + h11 * m1, pts[-1:]])


def _inside(inner, outer) -> bool:
    if outer is None:
        return False
    x0, x1, y0, y1 = inner
    a0, a1, b0, b1 = outer
    return a0 <= x0 and x1 <= a1 and b0 <= y0 and y1 <= b1


def _stagnation_speed(els, flows, region) -> float | None:
    """Speeds below 1e-4 × the typical speed in the region count as a stagnation point."""
    x0, x1, y0, y1 = region
    gx, gy = np.meshgrid(np.linspace(x0, x1, 17), np.linspace(y0, y1, 17))
    z = gx + 1j * gy
    with np.errstate(invalid="ignore"):
        sp = np.abs(complex_velocity(flows, z))
    sp = sp[fluid_mask(els, z)]
    sp = sp[np.isfinite(sp)]
    if sp.size == 0 or np.nanmedian(sp) == 0:
        return None
    return 1e-4 * float(np.nanmedian(sp))


def view_spacing(elements, xlim, ylim, density: float = 1.0) -> float:
    """Line spacing d for a view: BASE_LINES_ACROSS lines across the FLUID part of the view."""
    (x0, x1), (y0, y1) = xlim, ylim
    W, H = x1 - x0, y1 - y0
    gx, gy = np.meshgrid(np.linspace(x0, x1, 33), np.linspace(y0, y1, 33))
    fluid_fraction = max(float(np.mean(fluid_mask(active(elements), gx + 1j * gy))), 0.02)
    return math.sqrt(W * H * fluid_fraction) / (BASE_LINES_ACROSS * max(density, 0.05))


def trace_streamlines(elements: Sequence[FlowElement], xlim, ylim, density: float = 1.0,
                      arrow_density: float = 1.0, cancelled: Callable[[], bool] | None = None,
                      seeds: Sequence[complex] = (), use_kernel: bool = True, **_ignored) -> StreamlineSet:
    """Evenly spaced streamlines of one view (computed from scratch).
    density        1 = default spacing; 2 = twice as many lines
    arrow_density  1 = default spacing between arrows; 0 = no arrows
    cancelled      called now and then; returning True aborts with `Cancelled`
    seeds          points whose streamlines are drawn first (e.g. through a stagnation point)
    use_kernel     False = NumPy integrator even if the compiled kernel (kernel.py) is available"""
    x0, x1 = map(float, xlim)
    y0, y1 = map(float, ylim)
    if x1 <= x0 or y1 <= y0:
        return StreamlineSet()
    d = view_spacing(elements, (x0, x1), (y0, y1), density)
    f = StreamlineField(elements, d, use_kernel=use_kernel)
    f.extend((x0, x1, y0, y1), seeds=seeds, cancelled=cancelled)
    if f.domain is None:
        return StreamlineSet(separation=d)
    return f.result(arrow_density, (x0 + 0.5 * d, y0 + 0.5 * d, x1 - x0 - d, y1 - y0 - d))


# ---------------------------------------------------------------------- several levels (the plot)
class StreamlineCache:
    """Streamlines of one scene for the interactive plot.

    * Line spacing comes in levels d = 2^−L. The level follows the zoom with some hysteresis, so a
      small zoom does not change the picture; within a level the lines never move.
    * Optionally (COARSE_LEVELS > 0) a level starts from all lines of the next coarser level and fills
      the gaps (multi-level Jobard–Lefer), so when the level changes, half of the lines stay.
    * update(view) fills the visible region first, then a margin around it (overscan), so panning
      shows lines that already exist.
    """
    LEVEL_HYSTERESIS = 0.65            # change level when the ideal level is this far away (in levels)
    OVERSCAN = 0.5                     # margin computed around the view, as a fraction of its size
    TRIGGER = 0.15                     # ... computed again when less than this margin is left
    # How many coarser levels a level is built from (0 = every level on its own). With > 0 zooming
    # in keeps the coarser lines in place, but those lines end where the COARSER spacing makes them
    # end, which leaves gaps in spreading flows (e.g. around a source) -> off for now.
    COARSE_LEVELS = 0
    MAX_DOMAIN_FACTOR = 40.0           # start again when a level grew this much larger than the view

    def __init__(self, elements: Sequence[FlowElement], density: float = 1.0, use_kernel: bool = True):
        self.elements = list(elements)
        self.density = float(density)
        self.use_kernel = use_kernel
        self.fields: dict[int, StreamlineField] = {}
        self.level: int | None = None
        self.v_min: float | None = None
        self.features = None                       # stagnation points + dividing streamlines (FlowFeatures)
        self.with_features = True

    def _choose_level(self, view, current: int | None) -> int:
        (x0, x1), (y0, y1) = view
        ideal = -math.log2(view_spacing(self.elements, (x0, x1), (y0, y1), self.density))
        if current is None or abs(ideal - current) > self.LEVEL_HYSTERESIS:
            return int(round(ideal))
        return current

    def level_for(self, view) -> int:
        self.level = self._choose_level(view, self.level)
        return self.level

    def covers(self, view) -> bool:
        """True if the lines computed so far already fill `view` at the level it needs."""
        f = self.fields.get(self._choose_level(view, self.level))
        (x0, x1), (y0, y1) = view
        return f is not None and f.contains((x0, x1, y0, y1))

    def update(self, view, arrow_density: float = 1.0, cancelled: Callable[[], bool] | None = None,
               progress: Callable[[StreamlineSet], None] | None = None,
               force: bool = False) -> StreamlineSet | None:
        """Lines for `view` = ((x0, x1), (y0, y1)). Returns None if nothing changed since the last
        call (same level, view already filled) unless `force`. `progress` gets the picture once the
        visible part is done (before the margin around it)."""
        (x0, x1), (y0, y1) = map(lambda r: tuple(map(float, r)), view)
        if x1 <= x0 or y1 <= y0:
            return None
        previous = self.level
        L = self.level_for(((x0, x1), (y0, y1)))
        W, H = x1 - x0, y1 - y0
        o = self.OVERSCAN
        visible = (x0, x1, y0, y1)
        around = (x0 - o * W, x1 + o * W, y0 - o * H, y1 + o * H)
        f = self.fields.get(L)
        t = self.TRIGGER
        if f is not None and f.contains((x0 - t * W, x1 + t * W, y0 - t * H, y1 + t * H)) and L == previous:
            return self._with_features(f.result(arrow_density)) if force else None
        if f is not None and f.domain is not None:
            a0, a1, b0, b1 = f.domain
            grown = (max(a1, around[1]) - min(a0, around[0])) * (max(b1, around[3]) - min(b0, around[2]))
            if grown > self.MAX_DOMAIN_FACTOR * W * H:          # panned far away: start again
                self.fields.clear()
        changed = L != previous
        if self.with_features and (self.features is None or not _inside(visible, self.features.region)):
            self._update_features(visible, cancelled)
            changed = True
        for region in (visible, around):
            f = self.fields.get(L)
            if f is not None and f.contains(region):
                continue
            self._extend(L, region, 0, cancelled)
            changed = True
            if region is visible and progress is not None:
                progress(self._with_features(self.fields[L].result(arrow_density)))
        if not changed and not force:
            return None
        f = self.fields.get(L)
        res = f.result(arrow_density) if f is not None and f.domain is not None else StreamlineSet()
        return self._with_features(res)

    def _with_features(self, res: StreamlineSet) -> StreamlineSet:
        if self.features is not None:
            res.stagnation = list(self.features.points)
            res.dividing = list(self.features.dividing)
            res.dividing_owner = list(self.features.owners)
        return res

    def _update_features(self, visible, cancelled):
        """Stagnation points and dividing streamlines for 3× the view. A point on every dividing
        streamline (about one line spacing from its stagnation point) becomes a first seed of the
        streamline fields, so the regular lines are spaced from the dividing ones."""
        from .stagnation import flow_features
        x0, x1, y0, y1 = visible
        W, H = x1 - x0, y1 - y0
        region = (x0 - W, x1 + W, y0 - H, y1 + H)
        if cancelled is not None and cancelled():
            raise Cancelled()
        self.features = flow_features(self.elements, region, scale=max(W, H))
        d_view = view_spacing(self.elements, (x0, x1), (y0, y1), self.density)
        seeds = []
        stag = np.array([p.z for p in self.features.points], dtype=complex)
        for ln in self.features.dividing:
            z = ln[:, 0] + 1j * ln[:, 1]
            if stag.size and np.min(np.abs(stag - z[-1])) < np.min(np.abs(stag - z[0])):
                z = z[::-1]                              # measure from the stagnation point end
            s = np.concatenate([[0.0], np.cumsum(np.abs(np.diff(z)))])
            k = int(np.searchsorted(s, min(d_view, 0.5 * s[-1])))
            seeds.append(z[min(k, z.size - 1)])
        self._seeds = np.array(seeds, dtype=complex)
        for f in self.fields.values():                   # fields that exist get the new ones too
            f.special_seeds = np.concatenate([f.special_seeds, self._seeds])

    def _extend(self, L, region, depth, cancelled):
        d = 2.0 ** -L
        x0, x1, y0, y1 = region
        use_coarse = depth < self.COARSE_LEVELS and 2.0 * d < max(x1 - x0, y1 - y0) / 6.0
        if use_coarse:
            self._extend(L - 1, region, depth + 1, cancelled)
        f = self.fields.get(L)
        if f is None:
            f = self.fields[L] = StreamlineField(self.elements, d, self.v_min, self.use_kernel)
            f.special_seeds = getattr(self, "_seeds", np.zeros(0, complex)).copy()
        if use_coarse and (L - 1) in self.fields:
            f.set_base(self.fields[L - 1].all_lines)
        f.extend(region, cancelled=cancelled)
        if self.v_min is None:
            self.v_min = f.v_min


def _columns(traj, close_to, closed) -> list[np.ndarray]:
    """Trajectory columns (NaN after the end) -> list of point arrays; closed loops end exactly at
    the point they came back to (their seed, or the other end of a continued line)."""
    lines = []
    for j in range(close_to.size):
        col = traj[:, j]
        finite = np.isfinite(col)
        n = col.size if finite.all() else int(np.argmax(~finite))
        pts = col[:n]
        if closed[j]:
            pts = np.append(pts, close_to[j])        # close the loop exactly
        lines.append(pts)
    return lines


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


def _grid_seeds(x0, x1, y0, y1, d, center: complex | None = None) -> np.ndarray:
    """Regular grid (spacing d), ordered from `center` (default: the middle) outwards."""
    cx = np.arange(x0 + 0.5 * d, x1, d)
    cy = np.arange(y0 + 0.5 * d, y1, d)
    CX, CY = np.meshgrid(cx, cy)
    g = (CX + 1j * CY).ravel()
    c = complex(0.5 * (x0 + x1), 0.5 * (y0 + y1)) if center is None else center
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

    # nearest line point of every lattice point: look only in the 3 × 3 cells (size d) around it
    near = (P.real > bx - d) & (P.real < bx + bw + d) & (P.imag > by - d) & (P.imag < by + bh + d)
    P, T = P[near], T[near]
    if P.size == 0 or L.size == 0:
        return []
    kx = np.floor((P.real - bx) / d).astype(np.int64) + 2
    ky = np.floor((P.imag - by) / d).astype(np.int64) + 2
    ny_cells = int(ky.max()) + 3
    key = kx * ny_cells + ky
    order = np.argsort(key, kind="stable")
    skey = key[order]
    lx = np.floor((L.real - bx) / d).astype(np.int64) + 2
    ly = np.floor((L.imag - by) / d).astype(np.int64) + 2
    ranges = []
    for ox in (-1, 0, 1):
        for oy in (-1, 0, 1):
            k = (lx + ox) * ny_cells + (ly + oy)
            ranges.append((np.searchsorted(skey, k, "left"), np.searchsorted(skey, k, "right")))
    arrows = []
    for i in range(L.size):
        cand = [order[lo[i]:hi[i]] for lo, hi in ranges if hi[i] > lo[i]]
        if not cand:
            continue
        cand = np.concatenate(cand)
        dist = np.abs(P[cand] - L[i])
        k = int(np.argmin(dist))
        if dist[k] < 0.75 * d:
            j = cand[k]
            arrows.append((float(P[j].real), float(P[j].imag), float(np.angle(T[j]))))
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
    gap = np.array([[np.nan, np.nan]])
    out = []
    for parts in fade_piece_lists(lines, tapers, d, levels):
        out.append(np.vstack([x for p in parts for x in (p, gap)]) if parts else np.zeros((0, 2)))
    return out


def fade_piece_lists(lines: list[np.ndarray], tapers: list[tuple[bool, bool]], d: float,
                     levels: int = FADE_LEVELS) -> list[list[np.ndarray]]:
    """Like fade_pieces, but every opacity level is a list of separate (N, 2) pieces."""
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
