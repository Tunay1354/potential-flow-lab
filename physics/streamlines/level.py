"""
level.py — the evenly spaced streamlines of one spacing level (StreamlineField): seeding, RK4
integration (compiled kernel or NumPy), stop rules; trace_streamlines() for one picture.
"""
from __future__ import annotations

import math
from collections import deque
from typing import Callable, Sequence

import numpy as np

from .. import kernel, parallel
from ..base import FlowElement
from ..field import active, complex_potential, complex_velocity, fluid_mask, singular_points
from ..images import resolve
from .arrows import _place_arrows
from .common import (BASE_LINES_ACROSS, BATCH_SIZE, BOX_MARGIN_RATIO, Cancelled, MAX_TURN_COS,
                     MIN_LENGTH_RATIO, SEED_RATIO, STOP_RATIO, StreamlineSet, TAPER_RATIO, WALL_ID,
                     _Line, _line_ids)
from .rasters import _OwnerRaster, _Raster
from .seeds import _boundary_lines, _grid_seeds, _inflow_seeds, _line_range, _neighbour_seeds, _priority_seeds

PARALLEL_MIN_SEEDS = 3                 # seeds per core at least (fewer: not worth a thread)


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
        self.lines: list[_Line] = []
        self.queue: deque = deque()
        self.special_seeds = np.zeros(0, complex)   # e.g. points on dividing streamlines: used first
        self._cancelled: Callable[[], bool] | None = None
        self._barriers = [e for e in self.els
                          if e.crosses_boundary(np.zeros(1, complex), np.zeros(1, complex)) is not None]

    # ------------------------------------------------------------------ public
    def contains(self, region) -> bool:
        if self.domain is None:
            return False
        x0, x1, y0, y1 = region
        a0, a1, b0, b1 = self.domain
        return a0 <= x0 and x1 <= a1 and b0 <= y0 and y1 <= b1

    def extend(self, region, seeds: Sequence[complex] = (),
               cancelled: Callable[[], bool] | None = None) -> bool:
        """Fill `region` = (x0, x1, y0, y1) with lines. Returns False if it was filled already."""
        if self.contains(region) and not len(seeds):
            return False
        old_domain, old_special = self.domain, self.special_seeds
        try:
            return self._extend(region, seeds, cancelled)
        except Cancelled:
            self.domain = old_domain          # the new area is not complete: fill it again next time
            self.special_seeds = old_special  # (with its first seeds: those already used are refused then)
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
        for ln in self.lines:
            self._stamp(ln.pts, ln.id)

        if not first:                                       # a grown region: old lines run on into it,
            self._continue_lines()                          # gaps along them are seeded (d away)
            for ln in self.lines:
                self.queue.extend(_neighbour_seeds(ln.pts, d))
            self.queue = deque(self._usable(np.array(self.queue, dtype=complex)))
        rx0, rx1, ry0, ry1 = map(float, region)
        priority = deque(self._usable(_priority_seeds(self.els, x0, x1, y0, y1, d, self.sing, self.r_sing)))
        grid = deque(self._usable(_grid_seeds(x0, x1, y0, y1, d,
                                              center=complex(0.5 * (rx0 + rx1), 0.5 * (ry0 + ry1)))))
        # the first lines start on the inflow border; a grown region continues from the existing lines
        inflow = (_inflow_seeds(self.els, self.flows, x0, x1, y0, y1, d) if first
                  else np.zeros(0, complex))
        sp = self.special_seeds
        inside = (sp.real > x0) & (sp.real < x1) & (sp.imag > y0) & (sp.imag < y1)
        special, self.special_seeds = sp[inside], sp[~inside]          # each special seed is used once
        start = np.concatenate([np.asarray(seeds, dtype=complex).ravel(), special, inflow])
        self._fill(start, priority, grid)
        return True

    def result(self, arrow_density: float = 1.0, arrow_box=None) -> StreamlineSet:
        """All lines for drawing; arrows inside `arrow_box` (x, y, width, height), default: the whole region."""
        out = StreamlineSet(lines=[np.column_stack([ln.pts.real, ln.pts.imag]) for ln in self.lines],
                            tapers=[ln.taper for ln in self.lines], separation=self.d, domain=self.domain)
        if arrow_box is None and self.domain is not None:
            x0, x1, y0, y1 = self.domain
            arrow_box = (x0 + 0.5 * self.d, y0 + 0.5 * self.d, x1 - x0 - self.d, y1 - y0 - self.d)
        if arrow_box is not None:
            out.arrows = _place_arrows(out.lines, out.tapers, self.d, arrow_density, arrow_box)
        return out

    def free_trace(self, seeds, sign: float, box, slowest: float | None = None):
        """Streamlines from `seeds` in one direction inside `box` = (x0, x1, y0, y1), WITHOUT avoiding
        other lines (used for dividing streamlines and the 'inside a body?' test). `slowest`: a lower
        "too slow = stopped" speed for these lines only (default: the region's, v_min).
        Returns (point arrays, closed, left_box) — left_box True = the line reached the box border."""
        x0, x1, y0, y1 = map(float, box)
        if self.v_min is None:
            self.v_min = _stagnation_speed(self.els, self.flows, (x0, x1, y0, y1)) or 0.0
        if slowest is not None and slowest < self.v_min:
            saved, self.v_min = self.v_min, slowest
            try:
                return self.free_trace(seeds, sign, box)
            finally:
                self.v_min = saved
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
        seeds, self_ids, close_to = self._trace_args(seeds, self_ids, close_to)
        self._check_cancel()
        if self.compiled is not None:
            tasks, combine = self._trace_tasks(seeds, sign, self_ids, close_to)
            return combine(parallel.run(tasks))
        traj, closed, near_end, left_box = self._integrate_numpy(seeds, sign, self_ids, close_to)
        return self._finish(_columns(traj), closed, near_end, left_box, close_to)

    def _integrate_both(self, seeds):
        """Both directions of every seed at once (several cores): (forward, backward), each as _integrate
        returns it. The backward lines of seeds whose forward line closed are not needed (the caller
        drops them); tracing them anyway costs nothing extra in time on several cores, and every line
        is exactly the one _integrate would trace."""
        seeds, self_ids, close_to = self._trace_args(seeds, None, None)
        self._check_cancel()
        t_fwd, c_fwd = self._trace_tasks(seeds, +1.0, self_ids, close_to)
        t_bwd, c_bwd = self._trace_tasks(seeds, -1.0, self_ids, close_to)
        res = parallel.run(t_fwd + t_bwd)
        return c_fwd(res[:len(t_fwd)]), c_bwd(res[len(t_fwd):])

    def _trace_args(self, seeds, self_ids, close_to):
        seeds = np.asarray(seeds, dtype=np.complex128)
        B = seeds.size
        self_ids = np.full(B, -1, np.int32) if self_ids is None else np.asarray(self_ids, np.int32)
        close_to = seeds.copy() if close_to is None else np.asarray(close_to, np.complex128)
        return seeds, self_ids, close_to

    def _trace_tasks(self, seeds, sign, self_ids, close_to):
        """The compiled tracer for pieces of the seeds (tasks for parallel.run) and the function that puts
        the pieces' results together. The seeds are independent (the raster of the other lines is only
        read): pieces on different cores give exactly the lines of one call."""
        F, R, W = self.compiled
        ns = self.near_stop
        bx0, bx1, by0, by1 = self.box

        def trace(a, b):
            pts, offsets, closed, near_end, left_box = kernel.trace_batch(
                seeds[a:b], float(sign), F, R, W, self.sing, self.r_sing, self.h, self.n_max, self.v_min,
                MAX_TURN_COS, self.d, ns.a, self_ids[a:b], close_to[a:b], bx0, bx1, by0, by1,
                ns.x0, ns.y0, ns.c)
            return [pts[offsets[j]:offsets[j + 1]] for j in range(b - a)], closed, near_end, left_box

        def combine(parts):
            lines = [ln for p in parts for ln in p[0]]
            closed, near_end, left_box = (np.concatenate([p[k] for p in parts]) for k in (1, 2, 3))
            return self._finish(lines, closed, near_end, left_box, close_to)

        tasks = [lambda a=a, b=b: trace(a, b) for a, b in parallel.chunks(seeds.size, PARALLEL_MIN_SEEDS)]
        return tasks, combine

    @staticmethod
    def _finish(lines, closed, near_end, left_box, close_to):
        # closed loops end exactly at the point they came back to (their seed, or the other end of a
        # continued line)
        lines = [np.append(ln, close_to[j]) if closed[j] else ln for j, ln in enumerate(lines)]
        return lines, closed, near_end, left_box

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
            if kernel.HAVE_NUMBA:
                status, zb, pb, tb = kernel.pick_seeds(cand, np.asarray(psi, float), np.asarray(speed, float),
                                                       np.array(batch, complex), np.array(b_psi, float),
                                                       np.array(b_tol, float), limit, d)
                batch, b_psi, b_tol = zb.tolist(), pb.tolist(), tb.tolist()
                deferred += cand[status == 1].tolist()
            else:
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
            bwd = [np.array([s]) for s in seeds]
            bwd_near = np.zeros(seeds.size, dtype=bool)
            bwd_box = np.zeros(seeds.size, dtype=bool)
            if self.compiled is not None and parallel.workers() > 1 and seeds.size >= PARALLEL_MIN_SEEDS:
                (fwd, closed, fwd_near, fwd_box), (back_all, _, back_near, back_box) = self._integrate_both(seeds)
                need_back = np.nonzero(~closed)[0]
                for j in need_back:
                    bwd[j], bwd_near[j], bwd_box[j] = back_all[j], back_near[j], back_box[j]
            else:
                fwd, closed, fwd_near, fwd_box = self._integrate(seeds, +1.0)
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


def _columns(traj) -> list[np.ndarray]:
    """Trajectory columns of the NumPy tracer (NaN after the end) -> list of point arrays."""
    lines = []
    for j in range(traj.shape[1]):
        col = traj[:, j]
        finite = np.isfinite(col)
        lines.append(col[:col.size if finite.all() else int(np.argmax(~finite))])
    return lines
