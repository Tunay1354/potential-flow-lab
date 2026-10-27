"""
particles.py — the animated view: tracer particles carried by the flow (style "Particles"), and travel
times along streamlines for pulses that run along them (style "Pulses").

Every particle moves with the local velocity (midpoint RK2; where the flow is fast a step is split so
that no sub-step is longer than about 1/300 of the view). A particle starts again at a random point of
the view when it leaves the view or the fluid, comes close to a singular point, crosses a plate, or is
older than its lifetime; the lifetimes start staggered, so particles never all restart at once and the
density stays even (also around sources and sinks).

Time runs so that a particle at the TYPICAL speed of the view (median |V|) crosses the view in about
CROSSING_S seconds, whatever the zoom; `speed` multiplies this (the Speed slider).
The compiled kernel (kernel.py) is used when available, else the same rules in NumPy.

Pulses: along every streamline the travel time τ(s) = ∫ ds / |V| is computed once; a pulse is where
(t − τ) is close to a multiple of the pulse period, so pulses run at the local speed and, being evenly
spaced in TIME, spread out where the flow is fast and crowd where it is slow (like puffs of dye).
"""
from __future__ import annotations

import math

import numpy as np

from . import kernel
from .field import active, complex_velocity, fluid_mask, singular_points
from .images import resolve

CROSSING_S = 6.0          # a particle at the typical speed crosses the view in this many seconds
LIFETIME_S = 6.0          # ... and starts again after at most this long
STEPS_ACROSS = 300        # sub-steps are at most 1/300 of the view width
MAX_SUBSTEPS = 16
GUARD_ACROSS = 150        # particles keep 1/150 of the view width away from singular points


class Particles:
    """Positions, ages and speeds of `count` tracer particles in one scene and view."""

    def __init__(self, count: int = 1500, seed: int = 1):
        self.rng = np.random.default_rng(seed)
        if kernel.HAVE_NUMBA:
            kernel.seed_random(seed)
        self.count = int(count)
        self.pos = np.zeros(0, complex)
        self.prev = np.zeros(0, complex)
        self.age = np.zeros(0)
        self.speed = np.zeros(0)
        self.fresh = np.zeros(0, bool)          # started again in the last step (no trail segment)
        self.els, self.flows, self.compiled = [], [], None
        self.sing = np.zeros(0, complex)
        self.box = None                          # view (x0, x1, y0, y1)
        self.v_typ = 0.0                         # typical speed of the view

    # ------------------------------------------------------------------ scene and view
    def set_scene(self, elements):
        """New elements (the particles keep their places; those now in the solid start again)."""
        self.els = active(elements)
        self.flows = resolve(self.els)
        self.compiled = kernel.compile_scene(self.els, self.flows)
        self.sing = np.array(singular_points(self.els), dtype=complex)
        if self.box is not None:
            self.v_typ = self._typical_speed()

    def set_view(self, box, restart: bool = False):
        """The visible region (x0, x1, y0, y1). restart = scatter every particle again."""
        self.box = tuple(map(float, box))
        self.v_typ = self._typical_speed()
        if restart or self.pos.size != self.count:
            self.scatter()

    def set_count(self, count: int):
        self.count = int(count)
        if self.box is not None:
            self.scatter()

    def scatter(self):
        """Every particle at a random point, with random ages (they will not all restart together)."""
        x0, x1, y0, y1 = self.box
        n = self.count
        self.pos = np.zeros(n, complex)
        self.age = self.rng.uniform(0.0, LIFETIME_S, n)
        self.speed = np.zeros(n)
        self.fresh = np.ones(n, bool)
        self.pos[:] = self._spawn(n)
        with np.errstate(all="ignore"):
            self.speed[:] = np.abs(complex_velocity(self.flows, self.pos)) if self.flows else 0.0
        self.prev = self.pos.copy()

    # ------------------------------------------------------------------ time
    def time_scale(self, speed: float = 1.0) -> float:
        """Animation time per real second."""
        return time_scale(self.box, self.v_typ, speed)

    def step(self, dt_real: float, speed: float = 1.0):
        """Advance by dt_real seconds of real time (scaled by time_scale)."""
        if self.box is None or not self.flows or self.pos.size == 0:
            return
        dt = dt_real * self.time_scale(speed)
        if not dt > 0:
            return
        x0, x1, y0, y1 = self.box
        width = x1 - x0
        self.prev = self.pos.copy()
        if self.compiled is not None:
            F, R, W = self.compiled
            kernel.advect_particles(self.pos, self.age, self.speed, self.fresh, F, R, W, self.sing,
                                    width / GUARD_ACROSS, dt, dt_real, width / STEPS_ACROSS, MAX_SUBSTEPS,
                                    x0, x1, y0, y1, LIFETIME_S)
        else:
            self._step_numpy(dt, dt_real, width)

    # ------------------------------------------------------------------ helpers
    def _typical_speed(self) -> float:
        return typical_speed(self.els, self.flows, self.box, self.sing)

    def _usable(self, z):
        ok = fluid_mask(self.els, z)
        if self.sing.size:
            x0, x1 = self.box[:2]
            ok &= np.min(np.abs(z[:, None] - self.sing[None, :]), axis=1) >= (x1 - x0) / GUARD_ACROSS
        return ok

    def _spawn(self, n):
        x0, x1, y0, y1 = self.box
        z = self.rng.uniform(x0, x1, n) + 1j * self.rng.uniform(y0, y1, n)
        for _ in range(16):                                   # a few tries for points in the solid
            bad = ~self._usable(z)
            if not bad.any():
                break
            z[bad] = self.rng.uniform(x0, x1, bad.sum()) + 1j * self.rng.uniform(y0, y1, bad.sum())
        return z

    def _velocity(self, z):
        with np.errstate(all="ignore"):
            return np.conj(complex_velocity(self.flows, z))

    def _step_numpy(self, dt, dt_real, width):
        """The kernel's rules with NumPy (installations without Numba)."""
        x0, x1, y0, y1 = self.box
        max_step = width / STEPS_ACROSS
        z = self.pos.copy()
        v = self._velocity(z)
        travel = np.abs(v) * dt
        ok = np.isfinite(travel) & (travel <= max_step * MAX_SUBSTEPS)
        n = np.clip(np.ceil(np.where(ok, travel, 0) / max_step), 1, MAX_SUBSTEPS).astype(int)
        h = dt / n
        k2 = v.copy()
        for k in range(int(n.max()) if n.size else 0):
            act = ok & (k < n)
            if not act.any():
                break
            k1 = v[act] if k == 0 else self._velocity(z[act])
            k2a = self._velocity(z[act] + 0.5 * h[act] * k1)
            z_new = z[act] + h[act] * k2a
            for e in self.els:
                crossed = e.crosses_boundary(z[act], z_new)
                if crossed is not None:
                    ok[np.nonzero(act)[0][crossed]] = False
            z[act] = z_new
            k2[act] = k2a
        self.age += dt_real
        with np.errstate(invalid="ignore"):
            ok &= np.isfinite(z) & (z.real >= x0) & (z.real <= x1) & (z.imag >= y0) & (z.imag <= y1)
        ok[ok] &= self._usable(z[ok])
        ok &= self.age <= LIFETIME_S
        self.pos[ok] = z[ok]
        self.speed[ok] = np.abs(k2[ok])
        bad = ~ok
        self.fresh = bad
        if bad.any():
            self.pos[bad] = self._spawn(int(bad.sum()))
            self.age[bad] = 0.0
            self.speed[bad] = np.abs(self._velocity(self.pos[bad]))


def typical_speed(els, flows, box, sing=None) -> float:
    """Median |V| in the fluid part of the box (x0, x1, y0, y1), away from singular points."""
    x0, x1, y0, y1 = box
    if not flows:
        return 0.0
    gx, gy = np.meshgrid(np.linspace(x0, x1, 24), np.linspace(y0, y1, 24))
    z = (gx + 1j * gy).ravel()
    ok = fluid_mask(els, z)
    sing = np.array(singular_points(els), dtype=complex) if sing is None else sing
    if sing.size:
        ok &= np.min(np.abs(z[:, None] - sing[None, :]), axis=1) > 0.02 * max(x1 - x0, y1 - y0)
    with np.errstate(all="ignore"):
        sp = np.abs(complex_velocity(flows, z[ok]))
    sp = sp[np.isfinite(sp)]
    return float(np.median(sp)) if sp.size else 0.0


def time_scale(box, v_typ: float, speed: float = 1.0) -> float:
    """Animation time per real second: a particle at the typical speed v_typ crosses the box in
    CROSSING_S / speed seconds."""
    if not box or not v_typ > 0:
        return 0.0
    return speed * (box[1] - box[0]) / (CROSSING_S * v_typ)


def travel_times(lines, elements, step: float, v_floor: float):
    """Streamlines cut into short pieces (about `step` long) with the travel time τ to the middle of
    every piece from the start of its line (lines are ordered along the flow) and the speed there.
    Returns (a, b, tau, speed): piece start / end points (complex) and τ, |V| per piece. Speeds below
    v_floor count as v_floor (near a stagnation point τ would grow without limit)."""
    els = active(elements)
    flows = resolve(els)
    starts, ends = [], []
    for xy in lines:
        if len(xy) < 2:
            continue
        z = xy[:, 0] + 1j * xy[:, 1]
        s = np.concatenate([[0.0], np.cumsum(np.abs(np.diff(z)))])
        if not s[-1] > 0:
            continue
        n = max(2, int(math.ceil(s[-1] / step)) + 1)
        t = np.linspace(0.0, s[-1], n)
        zz = np.interp(t, s, z.real) + 1j * np.interp(t, s, z.imag)
        starts.append(zz[:-1])
        ends.append(zz[1:])
    if not starts:
        empty = np.zeros(0, complex)
        return empty, empty, np.zeros(0), np.zeros(0)
    a, b = np.concatenate(starts), np.concatenate(ends)
    mid = np.ascontiguousarray(0.5 * (a + b))
    compiled = kernel.compile_scene(els, flows) if flows else None
    with np.errstate(all="ignore"):
        if compiled is not None:
            v = np.abs(kernel.velocity_many(mid, compiled[0]))
        else:
            v = np.abs(complex_velocity(flows, mid)) if flows else np.zeros(a.size)
    v = np.where(np.isfinite(v), v, np.inf)
    dt = np.abs(b - a) / np.maximum(v, v_floor)
    # cumulative time per line: restart the sum at every line's first piece
    first = np.cumsum([0] + [len(p) for p in starts[:-1]])
    total = np.cumsum(dt)
    base = np.repeat(total[first] - dt[first], [len(p) for p in starts])
    tau = total - base - 0.5 * dt
    return a, b, tau, np.where(np.isfinite(v), v, 0.0)


def nice_top(value: float) -> float:
    """A round number ≥ value (1, 2, 2.5, 5 × 10^k)."""
    if not value > 0:
        return 1.0
    k = 10.0 ** math.floor(math.log10(value))
    for m in (1.0, 2.0, 2.5, 5.0, 10.0):
        if value <= m * k * 1.0001:
            return m * k
    return 10.0 * k
