"""
stagnation.py — stagnation points (V = 0) and the dividing streamlines through them.

Stagnation points are the zeros of the complex velocity w(z) = u − i v in the fluid. w is an
analytic function (a sum of poles, their image rows and power terms), so Newton's method
    z ← z − w(z) / w'(z)
converges fast from nearby starting points. Starting points cover the region; results that
converge to the same point are merged, zeros outside the fluid (e.g. behind a wall, created by the
images) are dropped, and the vertex of a sector flow with n > 1 (where w ∝ ζ^(n−1) = 0) is added.

Kinds of points
  "flow"    in the open flow
  "wall"    on a symmetry wall or a side of a sector flow
  "vertex"  the vertex of a sector flow (corner flow, n > 1)
  "body"    on the border of a body: with a free stream, fluid whose streamline starts at a source or
            a doublet or turns round one (inside a cylinder or a Rankine body, see origin.py) is
            the body; points with body fluid and other fluid around them lie on the body surface /
            dividing streamline. (Fluid turning round a free vortex is no body.)
Points with only body fluid around them (e.g. the second root inside the cylinder when
Γ > 4πV∞a) are not physical and are not returned.

Dividing streamlines (separatrices) leave a stagnation point in the directions where the velocity
is radial; they are traced outwards (along the flow) or inwards (against it) until they leave the
region, reach a singular point or another stagnation point. Branches that run into a body are left out.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .field import active, complex_velocity, fluid_mask, singular_points
from .images import resolve
from .origin import (BODY, FAR, LOOP, OPEN, STOPPED, bodies_box, box_union, has_free_stream, make_tracer,
                     speed_at, trace_origin)

NOISE_FLOOR = 1e-12             # speeds below this × the region's highest regular speed: rounding noise


@dataclass(frozen=True)
class StagnationPoint:
    z: complex
    kind: str                      # "flow" | "wall" | "vertex" | "body"

    @property
    def x(self) -> float:
        return self.z.real

    @property
    def y(self) -> float:
        return self.z.imag

    def describe(self) -> str:
        where = {"flow": "in the flow", "wall": "on the wall", "vertex": "corner vertex",
                 "body": "on the body surface"}[self.kind]
        x, y = round(self.x, 4) + 0.0, round(self.y, 4) + 0.0          # + 0.0: no "−0.0000"
        return f"Stagnation point ({x:.4f}, {y:.4f}), {where}"


@dataclass
class FlowFeatures:
    points: list[StagnationPoint] = field(default_factory=list)
    dividing: list[np.ndarray] = field(default_factory=list)      # (N, 2) arrays
    owners: list[int] = field(default_factory=list)              # index (in points) of each line's point
    region: tuple[float, float, float, float] | None = None
    # branches that run INTO a body (not drawn): the Solid bodies layer still needs them as borders —
    # e.g. a hair of free stream through a nearly closed body runs between such branches
    inner: list[np.ndarray] = field(default_factory=list)
    inner_owners: list[int] = field(default_factory=list)


# ---------------------------------------------------------------------- finding the points
def find_stagnation_points(elements, region, classify: bool = True, scale: float | None = None
                           ) -> list[StagnationPoint]:
    """Stagnation points inside `region` = (x0, x1, y0, y1). `scale` = size of the detail of
    interest (the view size; default: the region size): sets the start-point spacing, probe radius
    and tracing step."""
    els = active(elements)
    flows = resolve(els)
    x0, x1, y0, y1 = map(float, region)
    if not flows or x1 <= x0 or y1 <= y0:
        return []
    L = scale or max(x1 - x0, y1 - y0)
    sing = np.array(singular_points(els), dtype=complex)
    v_view, v_peak = _typical_speed(els, flows, region, sing)
    v_scene = _scene_speed(els, flows, sing)
    # (far down a channel closed at one end the flow dies out like e^(−πx/H): there the view's median can be
    #  ~0, and the flow round the elements sets the scale)
    v_scale, v_peak = max(v_view, 1e-6 * v_scene), max(v_peak, v_scene)
    if not v_scale > 0:
        return []

    # starting points: a grid over the region (~16 per view size) and small rings around singular points
    m = 0.05 * L
    nx = int(np.clip(16 * (x1 - x0) / L, 12, 80))
    ny = int(np.clip(16 * (y1 - y0) / L, 10, 80))
    gx, gy = np.meshgrid(np.linspace(x0 - m, x1 + m, nx), np.linspace(y0 - m, y1 + m, ny))
    z = (gx + 1j * gy).ravel()
    z = z[_in_fluid(els, z, 2 * m)]                                    # no starts deep in the solid
    for s in sing:
        z = np.concatenate([z, s + 0.05 * L * np.exp(2j * np.pi * (np.arange(12) + 0.5) / 12)])
    # … and at the distance where each element's own stagnation points are (its size in the flow AT it:
    # m/(2πU), √(μ/U), Γ/(2πU)). A weak source in a fast flow has its point much closer than 0.05·L;
    # Newton from the ring above then ran to another root and the point (with its dividing
    # streamlines, the half-body's surface) was missing at most zooms.
    for r in _own_scales(els, flows, sing, L):
        z = np.concatenate([z, r[0] + r[1] * np.exp(2j * np.pi * (np.arange(12) + 0.25) / 12)])
    z = _newton(els, flows, z, L, (x0 - L, x1 + L, y0 - L, y1 + L))

    with np.errstate(invalid="ignore"):
        w = np.abs(complex_velocity(flows, z))
    ok = np.isfinite(z) & np.isfinite(w) & (w < 1e-8 * v_scale)
    ok &= (z.real >= x0) & (z.real <= x1) & (z.imag >= y0) & (z.imag <= y1)
    z = z[ok]
    if sing.size and z.size:
        z = z[np.min(np.abs(z[:, None] - sing[None, :]), axis=1) > 1e-6 * L]
    z = z[_in_fluid(els, z, 1e-7 * L)]                               # zeros behind walls (images): out
    z = _unique(z, 1e-6 * L)
    z = z[_above_noise(flows, z, v_peak, L)]

    vertices = [e.z0 for e in els if e.TYPE == "sector" and e.n > 1.0 + 1e-12
                and x0 <= e.x0 <= x1 and y0 <= e.y0 <= y1]
    if vertices:
        z = np.array([p for p in z if min(abs(p - v) for v in vertices) > 1e-4 * L], dtype=complex)

    bdist = _boundary_distance(els, z)
    points = [StagnationPoint(complex(v), "vertex") for v in vertices]
    points += [StagnationPoint(complex(p), "wall" if b < 1e-6 * L else "flow") for p, b in zip(z, bdist)]
    if classify and has_free_stream(els):
        points = _classify_bodies(els, points, region, L)
    points.sort(key=lambda p: (round(p.x, 9), round(p.y, 9)))
    return points


def _own_scales(els, flows, sing, L):
    """(point, radius) of the extra Newton start rings: 0.5, 1 and 2 × the size each source / doublet /
    vortex has in the flow at it (only those between 1e-4·L and L: the others are not of this view)."""
    out = []
    for e in els:
        if e.TYPE not in ("source", "doublet", "vortex"):
            continue
        for p in e.singular_points():
            U = speed_at(flows, sing, p)
            if not U:
                continue
            if e.TYPE == "source":
                size = abs(e.m) / (2.0 * np.pi * U)
            elif e.TYPE == "vortex":
                size = abs(e.Gamma) / (2.0 * np.pi * U)
            else:
                size = float(np.sqrt(abs(e.mu) / U))
            for k in (0.5, 1.0, 2.0):
                if 1e-4 * L < k * size < L:
                    out.append((complex(p), k * size))
    return out


def _typical_speed(els, flows, region, sing):
    """(median |V|, highest |V| away from singular points) on a coarse grid of the region's fluid
    ((0, 0) without fluid)."""
    x0, x1, y0, y1 = region
    gx, gy = np.meshgrid(np.linspace(x0, x1, 17), np.linspace(y0, y1, 17))
    zz = (gx + 1j * gy).ravel()
    with np.errstate(invalid="ignore"):
        sp = np.abs(complex_velocity(flows, zz))
    ok = fluid_mask(els, zz) & np.isfinite(sp)
    if not ok.any():
        return 0.0, 0.0
    regular = ok if not sing.size else ok & (np.min(np.abs(zz[:, None] - sing[None, :]), axis=1)
                                             > 0.02 * max(x1 - x0, y1 - y0))
    return float(np.median(sp[ok])), float(np.max(sp[regular if regular.any() else ok]))


def _scene_speed(els, flows, sing) -> float:
    """The speed of the flow round the elements, whatever the view: the free stream and the flow each
    singular point sits in (made by the others); 0 when there is neither (one vortex alone)."""
    speeds = [abs(v) for v in (e.freestream_velocity() for e in els) if v is not None]
    return max(speeds + [speed_at(flows, sing, p) for p in sing], default=0.0)


def _above_noise(flows, z, v_peak, L) -> np.ndarray:
    """False for zeros whose whole neighbourhood is slower than NOISE_FLOOR × the region's highest regular
    speed: there the computed velocity is rounding noise with zeros of its own (far down a channel closed at
    one end the flow dies out like e^(−πx/H): dozens of false points when zoomed out, found by the random
    test). A real stagnation point has speed around it."""
    if not z.size:
        return np.ones(0, bool)
    ring = z[:, None] + 1e-3 * L * np.exp(0.5j * np.pi * np.arange(4))
    with np.errstate(all="ignore"):
        near = np.abs(complex_velocity(flows, ring))
    near[~np.isfinite(near)] = np.inf                                # (next to a singular point: keep)
    return ~(near.max(axis=1) < NOISE_FLOOR * v_peak)


def _newton(els, flows, z, L, box, iterations: int = 80):
    """Newton's method for w(z) = 0 on many starting points. w' from a central difference (w is
    analytic, so the derivative is the same in every direction); steps limited to L/10. A point
    stops once its step is negligible; points that leave `box` become NaN. Compiled when possible."""
    from . import kernel
    compiled = kernel.compile_scene(els, flows)
    if compiled is not None:
        return kernel.newton_zeros(np.ascontiguousarray(z, dtype=complex), compiled[0], float(L),
                                   *map(float, box), iterations)
    hc = 1e-7 * L
    z = z.astype(complex)
    active = np.ones(z.size, bool)
    with np.errstate(all="ignore"):
        for _ in range(iterations):
            idx = np.nonzero(active)[0]
            if idx.size == 0:
                break
            za = z[idx]
            w = complex_velocity(flows, za)
            dw = (complex_velocity(flows, za + hc) - complex_velocity(flows, za - hc)) / (2.0 * hc)
            step = w / dw
            big = np.abs(step) > 0.1 * L
            step[big] *= 0.1 * L / np.abs(step[big])
            step[~np.isfinite(step)] = np.nan
            z[idx] = za - step
            zn = z[idx]
            gone = (zn.real < box[0]) | (zn.real > box[1]) | (zn.imag < box[2]) | (zn.imag > box[3])
            z[idx[gone]] = np.nan                                       # ran away from the region
            active[idx[gone | ~(np.abs(step) > 1e-13 * L)]] = False     # converged (or NaN)
    return z


def _unique(z, tol):
    """The points without repeats (a point within `tol` of an earlier one is dropped)."""
    out = np.zeros(0, complex)
    for p in z:
        if not out.size or np.min(np.abs(out - p)) > tol:
            out = np.append(out, p)
    return out


def _in_fluid(els, z, tol) -> np.ndarray:
    """In the fluid, counting points up to `tol` outside a wall / sector side as inside (a zero ON a
    wall is a stagnation point; but not one on the extension of a wall into the solid)."""
    z = np.atleast_1d(np.asarray(z, complex))
    ok = np.ones(z.shape, bool)
    for e in els:
        if e.IS_BOUNDARY or e.TYPE == "sector":
            ok &= e.signed_distance(z) >= -tol
        else:
            region = e.fluid_region(z)
            if region is not None:
                ok &= region
    return ok


def _boundary_distance(els, z) -> np.ndarray:
    """Distance to the nearest symmetry wall or sector side (inf if there is none)."""
    z = np.atleast_1d(np.asarray(z, complex))
    d = np.full(z.shape, np.inf)
    for e in els:
        if e.IS_BOUNDARY or e.TYPE == "sector":
            d = np.minimum(d, np.abs(e.signed_distance(z)))
    return d


def _probe_radius(p, others, sing, L):
    r = 0.01 * L
    near = [abs(p - q) for q in others if q != p] + [abs(p - s) for s in sing]
    if near:
        r = min(r, 0.3 * min(near))
    return r


def _tracer_near(els, z, sing, L, tracer):
    """The tracer for lines from the point z: the view's, unless a singular point is so close that the
    view's tracer would stop the lines at once (it stops them L/160 before one; e.g. the nose of a small
    half-body seen at the scale of the whole scene) — then a finer one."""
    if not len(sing):
        return tracer
    d = float(np.min(np.abs(np.asarray(sing) - z)))
    return tracer if d >= 20.0 * tracer.r_sing else make_tracer(els, max(20.0 * d, 1e-9))


def _probe_scale(r, L):
    """Tracing scale for probes at distance r round a stagnation point: the tracer stops lines
    scale/160 before a singular point and counts 4× that as 'reached it'; at most the view's scale."""
    return min(L, 20.0 * r)


PROBE_REGION_SCENES = 20.0      # probes: a region at most this many times the scene's own size


def _probe_region(els, points, region):
    """The region whose far-field box (3× it) decides "from the free stream" for probe lines. Normally the
    view's region; zoomed far out (the view ≫ the scene: its singular points, stagnation points and body
    boxes) a square PROBE_REGION_SCENES × the scene's size round it — the same answer as a view of that
    size, but the probes are traced with their own small step, and across a box 3× a view 10³–10⁴× the
    scene they took millions of steps (fans at full speed, no lines for a minute)."""
    zs = [complex(s) for s in singular_points(els)] + [complex(getattr(p, "z", p)) for p in points]
    if not zs:
        return region
    xs, ys = [z.real for z in zs], [z.imag for z in zs]
    box = box_union((min(xs), max(xs), min(ys), max(ys)), bodies_box(els))
    size = max(box[1] - box[0], box[3] - box[2])
    x0, x1, y0, y1 = region
    if not size > 0 or max(x1 - x0, y1 - y0) <= PROBE_REGION_SCENES * size:
        return region
    cx, cy, h = 0.5 * (box[0] + box[1]), 0.5 * (box[2] + box[3]), 0.5 * PROBE_REGION_SCENES * size
    return (cx - h, cx + h, cy - h, cy + h)


def _classify_bodies(els, points, region, L):
    sing = [complex(s) for s in singular_points(els)]
    zs = [p.z for p in points]
    region = _probe_region(els, zs, region)
    out = []
    for p in points:
        if p.kind == "vertex":
            out.append(p)
            continue
        r = _probe_radius(p.z, zs, sing, L)
        ring = p.z + r * np.exp(2j * np.pi * (np.arange(12) + 0.25) / 12)
        ring = ring[fluid_mask(els, ring)]
        if ring.size == 0:
            out.append(p)
            continue
        # traced at the probe's scale: at the view's scale the tracer stops lines a whole step before a
        # singular point and counts everything that close as body — a point next to a weak source
        # (closer than that) was dropped as 'inside a body' when zoomed out
        origin = trace_origin(els, ring, region, _probe_scale(r, L))
        body = origin == BODY
        known = origin != STOPPED
        if known.any() and body[known].all():
            continue                                        # inside a body: not physical
        if not body.any() or p.kind == "wall":
            out.append(p)
        else:
            out.append(StagnationPoint(p.z, "body"))
    return out


# ---------------------------------------------------------------------- dividing streamlines
def separatrix_directions(flows, z0, r, count: int = 360):
    """Directions θ in which the velocity at z0 + r·e^{iθ} is radial, with +1 (flow goes out) or
    −1 (flow comes in). These are the starting directions of the dividing streamlines."""
    th = 2 * np.pi * (np.arange(count) + 0.5) / count
    zs = z0 + r * np.exp(1j * th)
    with np.errstate(all="ignore"):
        vel = np.conj(complex_velocity(flows, zs)) * np.exp(-1j * th)     # (radial, tangential)
    tang, rad = vel.imag, vel.real
    out = []
    for k in range(count):
        a, b = tang[k], tang[(k + 1) % count]
        if not (np.isfinite(a) and np.isfinite(b)) or a == b or np.sign(a) == np.sign(b):
            continue
        t = a / (a - b)
        ang = th[k] + t * (2 * np.pi / count)
        radial = rad[k] + t * (rad[(k + 1) % count] - rad[k])
        if abs(radial) > 2.0 * max(abs(a), abs(b)):                        # really radial, not a swirl
            out.append((ang, 1.0 if radial > 0 else -1.0))
    return out


def _psi(flows, z):
    from .field import complex_potential
    with np.errstate(all="ignore"):
        return complex(complex_potential(flows, np.array([z]))[0]).imag


def _onto_separatrix(flows, s, u, psi0, r):
    """Move the starting point s sideways (normal to the direction u) until ψ(s) = ψ at the
    stagnation point: the start then lies on the dividing streamline itself (not on its tangent,
    which is off by ~r²/2R). Left unchanged if ψ is not usable there (e.g. near a branch cut)."""
    n = 1j * u
    t = 0.0
    for _ in range(4):
        f0 = _psi(flows, s + t * n) - psi0
        h = 1e-4 * r
        df = (_psi(flows, s + (t + h) * n) - _psi(flows, s + (t - h) * n)) / (2 * h)
        if not (np.isfinite(f0) and np.isfinite(df)) or df == 0:
            return s
        t -= f0 / df
        if abs(t) > 0.2 * r:
            return s
    return s + t * n


def features_with_context(elements, region, scale, context: FlowFeatures | None) -> FlowFeatures:
    """flow_features of `region` at the view `scale`, plus the dividing streamlines of the points
    OUTSIDE it that `context` (the features of the whole scene, searched once at a coarser scale) has:
    zoomed into part of a body, the stagnation points of its surface are far away, but the surface
    still runs through the view. Those lines are traced again in the region at the view's scale,
    from a point of the coarse line; their points are added to the list (outside the region)."""
    feats = flow_features(elements, region, scale=scale)
    if context is None:
        return feats
    els = active(elements)
    x0, x1, y0, y1 = region
    tracer = None
    for k, p in enumerate(context.points):
        if x0 <= p.x <= x1 and y0 <= p.y <= y1:
            continue                                     # searched here at the finer scale
        new, new_inner = [], []
        for ln, owner, inner in ([(a, b, False) for a, b in zip(context.dividing, context.owners)]
                                 + [(a, b, True) for a, b in zip(context.inner, context.inner_owners)]):
            if owner != k:
                continue
            z = ln[:, 0] + 1j * ln[:, 1]
            inside = (z.real > x0) & (z.real < x1) & (z.imag > y0) & (z.imag < y1)
            for run in _runs(inside):
                if run.size < 2:
                    continue
                if tracer is None:
                    tracer = make_tracer(els, scale)
                seed = z[run[run.size // 2]]
                fwd, _c, _l = tracer.free_trace(np.array([seed]), 1.0, region)
                bwd, _c, _l = tracer.free_trace(np.array([seed]), -1.0, region)
                pts = np.concatenate([bwd[0][::-1], [seed], fwd[0]])            # along the flow
                if pts.size >= 3:
                    (new_inner if inner else new).append(np.column_stack([pts.real, pts.imag]))
        if new or new_inner:
            feats.points.append(p)
            feats.dividing += new
            feats.owners += [len(feats.points) - 1] * len(new)
            feats.inner += new_inner
            feats.inner_owners += [len(feats.points) - 1] * len(new_inner)
    return feats


def _runs(mask) -> list:
    """Index arrays of the runs of True in a bool array."""
    idx = np.nonzero(mask)[0]
    if not idx.size:
        return []
    cuts = np.nonzero(np.diff(idx) > 1)[0] + 1
    return np.split(idx, cuts)


def flow_features(elements, region, dividing: bool = True, scale: float | None = None) -> FlowFeatures:
    """Stagnation points and dividing streamlines for a region (x0, x1, y0, y1); `scale` = view size."""
    els = active(elements)
    points = find_stagnation_points(els, region, scale=scale)
    feats = FlowFeatures(points=points, region=tuple(map(float, region)))
    if not dividing or not points:
        return feats
    flows = resolve(els)
    x0, x1, y0, y1 = region
    L = scale or max(x1 - x0, y1 - y0)
    sing = [complex(s) for s in singular_points(els)]
    zs = [p.z for p in points]
    has_stream = has_free_stream(els)
    tracer = make_tracer(els, L)
    box = (x0, x1, y0, y1)
    probe_region = _probe_region(els, zs, region)
    for k, p in enumerate(points):
        r = _probe_radius(p.z, zs, sing, L)
        starts, signs = [], []
        psi0 = _psi(flows, p.z)
        for ang, sgn in separatrix_directions(flows, p.z, r):
            s = _onto_separatrix(flows, p.z + r * np.exp(1j * ang), np.exp(1j * ang), psi0, r)
            if not fluid_mask(els, np.array([s]))[0] or _boundary_distance(els, s)[0] < 0.3 * r:
                continue                                    # into the solid or along a wall (drawn already)
            starts.append(s)
            signs.append(sgn)
        if not starts:
            continue
        starts = np.array(starts)
        signs = np.array(signs)
        if has_stream:
            # leave out branches that run INTO a body: the start and both points beside it are body
            # fluid. A branch along the body surface (e.g. the cylinder surface) has other fluid on
            # one side and is kept.
            u = (starts - p.z) / r
            probes = np.concatenate([starts, starts + 0.3 * r * 1j * u, starts - 0.3 * r * 1j * u])
            origin = trace_origin(els, probes, probe_region, _probe_scale(r, L)).reshape(3, -1)
            keep = ((origin == FAR) | (origin == LOOP) | (origin == OPEN)).any(axis=0)
        else:
            keep = np.ones(starts.size, bool)
        for sgn in (1.0, -1.0):
            sel = signs == sgn
            if not sel.any():
                continue
            # (lines start next to a stagnation point, where the flow is slow: in a corner of a sector flow
            #  with n > 1 slower than the region's "too slow = stopped" — then they would stop at once,
            #  and a body in the corner was missing in a view 4× wider; the random test)
            with np.errstate(all="ignore"):
                slowest = 0.01 * float(np.min(np.abs(complex_velocity(flows, starts[sel]))))
            lines, _closed, _left = _tracer_near(els, p.z, sing, L, tracer).free_trace(starts[sel], sgn, box,
                                                                                     slowest)
            for shown, ln in zip(keep[sel], lines):
                pts = np.concatenate([[p.z], ln]) if sgn > 0 else np.concatenate([ln[::-1], [p.z]])
                if pts.size >= 3:
                    (feats.dividing if shown else feats.inner).append(np.column_stack([pts.real, pts.imag]))
                    (feats.owners if shown else feats.inner_owners).append(k)
    return feats
