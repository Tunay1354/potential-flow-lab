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
  "body"    on the border of a body: with a free stream, the fluid that does not come from far
            upstream (inside a cylinder, a Rankine body, or the ring of fluid that turns with a
            fast-spinning cylinder) is the body; points with fluid of both kinds around them lie on
            the body surface / dividing streamline.
Points with only body fluid around them (e.g. the second root inside the cylinder when
Γ > 4πV∞a) are not physical and are not returned.

Dividing streamlines (separatrices) leave a stagnation point in the directions where the velocity
is radial; they are traced outwards (along the flow) or inwards (against it) until they leave the
region, reach a singular point or another stagnation point. Branches that run into a body are left out.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .field import active, complex_velocity, fluid_mask, reference_speed, singular_points
from .images import resolve


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
    v_scale = _typical_speed(els, flows, region)
    if v_scale is None:
        return []
    sing = np.array(singular_points(els), dtype=complex)

    # starting points: a grid over the region (~16 per view size) and small rings around singular points
    m = 0.05 * L
    nx = int(np.clip(16 * (x1 - x0) / L, 12, 80))
    ny = int(np.clip(16 * (y1 - y0) / L, 10, 80))
    gx, gy = np.meshgrid(np.linspace(x0 - m, x1 + m, nx), np.linspace(y0 - m, y1 + m, ny))
    z = (gx + 1j * gy).ravel()
    z = z[_in_fluid(els, z, 2 * m)]                                    # no starts deep in the solid
    for s in sing:
        z = np.concatenate([z, s + 0.05 * L * np.exp(2j * np.pi * (np.arange(12) + 0.5) / 12)])
    z = _newton(_velocity_function(els, flows), z, L, (x0 - L, x1 + L, y0 - L, y1 + L))

    with np.errstate(invalid="ignore"):
        w = np.abs(complex_velocity(flows, z))
    ok = np.isfinite(z) & np.isfinite(w) & (w < 1e-8 * v_scale)
    ok &= (z.real >= x0) & (z.real <= x1) & (z.imag >= y0) & (z.imag <= y1)
    z = z[ok]
    if sing.size and z.size:
        z = z[np.min(np.abs(z[:, None] - sing[None, :]), axis=1) > 1e-6 * L]
    z = z[_in_fluid(els, z, 1e-7 * L)]                               # zeros behind walls (images): out
    z = _unique(z, 1e-6 * L)

    vertices = [e.z0 for e in els if e.TYPE == "sector" and e.n > 1.0 + 1e-12
                and x0 <= e.x0 <= x1 and y0 <= e.y0 <= y1]
    if vertices:
        z = np.array([p for p in z if min(abs(p - v) for v in vertices) > 1e-4 * L], dtype=complex)

    bdist = _boundary_distance(els, z)
    points = [StagnationPoint(complex(v), "vertex") for v in vertices]
    points += [StagnationPoint(complex(p), "wall" if b < 1e-6 * L else "flow") for p, b in zip(z, bdist)]
    if classify and reference_speed(els) is not None:
        points = _classify_bodies(els, points, region, L)
    points.sort(key=lambda p: (round(p.x, 9), round(p.y, 9)))
    return points


def _typical_speed(els, flows, region):
    x0, x1, y0, y1 = region
    gx, gy = np.meshgrid(np.linspace(x0, x1, 17), np.linspace(y0, y1, 17))
    zz = gx + 1j * gy
    with np.errstate(invalid="ignore"):
        sp = np.abs(complex_velocity(flows, zz))
    sp = sp[fluid_mask(els, zz) & np.isfinite(sp)]
    if sp.size == 0 or np.median(sp) == 0:
        return None
    return float(np.median(sp))


def _velocity_function(els, flows):
    """w(z) for many points: the compiled kernel when available (much faster with image rows)."""
    from . import kernel
    compiled = kernel.compile_scene(els, flows)
    if compiled is not None:
        F = compiled[0]
        return lambda z: kernel.velocity_many(np.ascontiguousarray(z, dtype=complex), F)
    return lambda z: complex_velocity(flows, z)


def _newton(w_of, z, L, box, iterations: int = 80):
    """Newton's method for w(z) = 0 on many starting points at once. w' from a central difference
    (w is analytic, so the derivative is the same in every direction); steps limited to L/10.
    Points stop iterating once their step is negligible."""
    hc = 1e-7 * L
    z = z.astype(complex)
    active = np.ones(z.size, bool)
    with np.errstate(all="ignore"):
        for _ in range(iterations):
            idx = np.nonzero(active)[0]
            if idx.size == 0:
                break
            za = z[idx]
            w = w_of(za)
            dw = (w_of(za + hc) - w_of(za - hc)) / (2.0 * hc)
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
    out = []
    for p in z:
        if all(abs(p - q) > tol for q in out):
            out.append(p)
    return np.array(out, dtype=complex)


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


# ---------------------------------------------------------------------- bodies
def _far_field_box(region):
    x0, x1, y0, y1 = region
    L = max(x1 - x0, y1 - y0)
    return (x0 - L, x1 + L, y0 - L, y1 + L)


def _tracer(els, scale):
    from .streamlines import StreamlineField
    return StreamlineField(els, scale / 80.0)


def comes_from_far_upstream(els, z, region, scale=None) -> np.ndarray:
    """True where the streamline through z, followed BACKWARDS, reaches the far field (a box 3×
    the region). With a free stream, False marks fluid that belongs to a body."""
    z = np.atleast_1d(np.asarray(z, complex))
    if z.size == 0:
        return np.zeros(0, bool)
    x0, x1, y0, y1 = region
    tracer = _tracer(els, scale or max(x1 - x0, y1 - y0))
    _lines, _closed, left = tracer.free_trace(z, -1.0, _far_field_box(region))
    return np.asarray(left, bool)


def _probe_radius(p, others, sing, L):
    r = 0.01 * L
    near = [abs(p - q) for q in others if q != p] + [abs(p - s) for s in sing]
    if near:
        r = min(r, 0.3 * min(near))
    return r


def _classify_bodies(els, points, region, L):
    sing = [complex(s) for s in singular_points(els)]
    zs = [p.z for p in points]
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
        free = comes_from_far_upstream(els, ring, region, L)
        if not free.any():
            continue                                        # inside a body: not physical
        if free.all() or p.kind == "wall":
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
    has_stream = reference_speed(els) is not None
    tracer = _tracer(els, L)
    box = (x0, x1, y0, y1)
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
            # fluid. A branch along the body surface (e.g. the cylinder surface) has free-stream
            # fluid on one side and is kept.
            u = (starts - p.z) / r
            probes = np.concatenate([starts, starts + 0.3 * r * 1j * u, starts - 0.3 * r * 1j * u])
            free = comes_from_far_upstream(els, probes, region, L).reshape(3, -1)
            keep = free.any(axis=0)
            starts, signs = starts[keep], signs[keep]
            if not starts.size:
                continue
        for sgn in (1.0, -1.0):
            sel = signs == sgn
            if not sel.any():
                continue
            lines, _closed, _left = tracer.free_trace(starts[sel], sgn, box)
            for s, ln in zip(starts[sel], lines):
                pts = np.concatenate([[p.z], ln]) if sgn > 0 else np.concatenate([ln[::-1], [p.z]])
                if pts.size >= 3:
                    feats.dividing.append(np.column_stack([pts.real, pts.imag]))
                    feats.owners.append(k)
    return feats
