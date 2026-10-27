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
            a doublet or turns round one (inside a cylinder or a Rankine body, see trace_origin) is
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


# ---------------------------------------------------------------------- bodies
def has_free_stream(els) -> bool:
    """Fluid comes from far away: a uniform flow, or a sector flow (corner flow …). Without it there
    are no bodies (all fluid comes out of the sources)."""
    return reference_speed(els) is not None or any(e.TYPE == "sector" and e.V != 0 for e in els)


def _stream_speed(els, p) -> float | None:
    """Speed of the free stream at the point p: |V∞|, or the speed of the sector flow(s) there."""
    v = reference_speed(els)
    if v:
        return v
    far = resolve([e for e in els if e.TYPE == "sector"])
    if not far:
        return None
    for z in (p, p + abs(p) + 1.0):                       # (at a corner vertex the speed is 0)
        with np.errstate(all="ignore"):
            w = abs(complex_velocity(far, np.array([z], complex))[0])
        if np.isfinite(w) and w > 0:
            return float(w)
    return None


def body_size(els, e, p) -> float | None:
    """Size of the body (or ring of turning fluid) an element would make in the free stream at its
    point p: cylinder radius √(μ/V), half-body width m/V, stagnation distance Γ/(2πV)."""
    v = _stream_speed(els, p)
    if not v:
        return None
    if e.TYPE == "doublet":
        return float(np.sqrt(abs(e.mu) / v))
    if e.TYPE == "source":
        return abs(e.m) / v
    if e.TYPE == "vortex":
        return abs(e.Gamma) / (2.0 * np.pi * v)
    return None


def bodies_box(els, margin: float = 4.0):
    """A box round every source, doublet and vortex, `margin` × the size of its body (body_size);
    None without a free stream or such elements."""
    if not els or not has_free_stream(els):
        return None
    box = None
    for e in els:
        for p in (e.singular_points() if e.TYPE in ("doublet", "source", "vortex") else ()):
            size = body_size(els, e, p)
            if not size:
                continue
            r = margin * size
            b = (p.real - r, p.real + r, p.imag - r, p.imag + r)
            box = b if box is None else (min(box[0], b[0]), max(box[1], b[1]), min(box[2], b[2]), max(box[3], b[3]))
    return box


def _union(a, b):
    return a if b is None else (min(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), max(a[3], b[3]))


def _far_field_box(region, els=()):
    """Where a traced line counts as "from / to the far field": 3× the region, and wide enough round
    every source, doublet and vortex for its body (or ring of turning fluid) to fit inside — else, in
    a view zoomed into part of a body, a line turning inside the body would leave the box and count
    as free stream."""
    x0, x1, y0, y1 = region
    L = max(x1 - x0, y1 - y0)
    return _union((x0 - L, x1 + L, y0 - L, y1 + L), bodies_box(els))


def _tracer(els, scale):
    from .streamlines import StreamlineField
    return StreamlineField(els, scale / 80.0)


# where the fluid at a point comes from (the streamline through it, followed backwards)
FAR, LOOP, BODY, STOPPED, OPEN = 0, 1, 2, 3, 4
MASS_TYPES = ("source", "doublet")            # elements that make bodies (a vortex alone does not)


def trace_origin(elements, z, region, scale=None) -> np.ndarray:
    """For every point z, where its streamline comes from, followed BACKWARDS:
        FAR   the far field (a box 3× the region): fluid of the free stream
        BODY  it starts at a source or a doublet, or turns in a closed loop round one: fluid of a
              body (inside a cylinder or a Rankine oval / half-body; with a fast-spinning cylinder
              also the ring of fluid that turns with it)
        OPEN  it starts at a source or a doublet that the free stream passes THROUGH (open_elements:
              a doublet not along the flow at it, a tilted source–sink pair): real flow, no body
        LOOP  any other closed loop (e.g. round a free vortex in a uniform flow): real flow, no body
        STOPPED the line stopped anywhere else (e.g. next to a stagnation point, where the flow is
              too slow to follow): unknown
    This is THE definition of a body (stagnation point kinds, which dividing lines are drawn,
    bodies.py)."""
    return trace_ends(elements, z, region, scale, -1.0)[0]


def trace_ends(elements, z, region, scale=None, sign: float = -1.0):
    """The streamline through every point z followed backwards (sign −1, see trace_origin) or forwards
    (+1: where the fluid GOES; BODY = into a sink or a doublet). Returns (kinds, element): element =
    index (in active(elements)) of the source / doublet the line ends at, −1 if none."""
    els = active(elements)
    out, which, loops = _trace_raw(els, z, region, scale, sign)
    if not ((out == BODY).any()):
        return out, which
    opened = open_elements(els)
    if opened:
        for k in np.nonzero(out == BODY)[0]:
            owners = loops.get(k)                       # closed loop: the mass elements it goes round
            if owners is not None:
                if all(i in opened for i in owners):
                    out[k] = OPEN
            elif which[k] in opened:
                out[k] = OPEN
    return out, which


def _trace_raw(els, z, region, scale, sign):
    """trace_ends without open_elements: (kinds, element, {line: elements a BODY loop goes round})."""
    z = np.atleast_1d(np.asarray(z, complex))
    out = np.full(z.size, STOPPED, dtype=np.int8)
    which = np.full(z.size, -1, dtype=np.int64)
    loops = {}
    if z.size == 0:
        return out, which, loops
    x0, x1, y0, y1 = region
    tracer = _tracer(els, scale or max(x1 - x0, y1 - y0))
    lines, closed, left = tracer.free_trace(z, sign, _far_field_box(region, els))
    left, closed = np.asarray(left, bool), np.asarray(closed, bool)
    out[left] = FAR
    out[~left & closed] = LOOP
    owner = [(i, p) for i, e in enumerate(els) if e.TYPE in MASS_TYPES for p in e.singular_points()]
    if not owner:
        return out, which, loops
    mass = np.array([p for _i, p in owner], dtype=complex)
    reach = 4.0 * tracer.r_sing                         # lines stop r_sing before a singular point
    for k in np.nonzero(~left)[0]:
        ln = lines[k]
        if closed[k]:
            if len(ln) > 2:
                inside = _encloses(ln, mass)
                if inside.any():
                    out[k] = BODY
                    loops[k] = {owner[j][0] for j in np.nonzero(inside)[0]}
        else:
            end = ln[-1] if len(ln) else z[k]
            d = np.abs(mass - end)
            if np.min(d) < reach:
                out[k] = BODY
                which[k] = owner[int(np.argmin(d))][0]
    return out, which, loops


# ---------------------------------------------------------------------- free stream through a body?
RING_POINTS = 64                 # open_elements: points round every source / doublet
_OPEN_CACHE: dict = {}


def open_elements(elements) -> frozenset:
    """The sources / doublets (indices in active(elements)) the free stream passes THROUGH, which
    therefore make no body. A real body cannot swallow the free stream: free-stream fluid flowing into
    a sink or a doublet (a doublet not along the flow at it — δ ≠ α, or a vortex beside it turns the
    flow there —, a source–sink pair across the flow) means that what looks like a body has the free
    stream going in at one place and out at another.
    Test: streamlines from a small ring round every source / doublet, followed both ways. Elements
    whose fluid reaches each other form a group; a group is open when free-stream fluid flows into
    one of its sinks / doublets, or when its fluid goes off to the far field although its sources do
    not give more than its sinks take in. (A source with more outflow — the Rankine half-body — is no
    such case: its body is open downstream.) Depends on the scene only, not on the view: the same
    answer at every zoom (cached per scene)."""
    els = active(elements)
    if not has_free_stream(els):
        return frozenset()
    import json
    key = tuple(json.dumps(e.to_dict(), sort_keys=True) for e in els)
    hit = _OPEN_CACHE.get(key)
    if hit is not None:
        return hit
    mass = [(i, complex(p)) for i, e in enumerate(els) if e.TYPE in MASS_TYPES for p in e.singular_points()]
    sing = np.array(singular_points(els), dtype=complex)
    parent = {i: i for i, _p in mass}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    takes_far, sends_far = set(), set()
    for i, p in mass:
        e = els[i]
        if (e.TYPE == "source" and e.m == 0) or (e.TYPE == "doublet" and e.mu == 0):
            continue
        size = body_size(els, e, p)
        if not size:
            continue
        # well inside the fluid the element owns: 0.3 × the cylinder radius, 0.2 × the distance of a
        # half-body's stagnation point m/(2πV)
        r = 0.3 * size if e.TYPE == "doublet" else 0.2 * size / (2.0 * np.pi)
        others = np.abs(sing - p)
        others = others[others > 1e-9 * (1.0 + abs(p))]
        if others.size:
            r = min(r, 0.3 * float(others.min()))
        ring = p + r * np.exp(2j * np.pi * (np.arange(RING_POINTS) + 0.5) / RING_POINTS)
        ring = ring[fluid_mask(els, ring)]
        if not ring.size:
            continue
        region = (p.real - r, p.real + r, p.imag - r, p.imag + r)
        for sign, far_set in ((-1.0, takes_far), (1.0, sends_far)):
            kinds, ends, _loops = _trace_raw(els, ring, region, 20.0 * r, sign)
            if (kinds == FAR).any():
                far_set.add(i)
            for j in set(ends[ends >= 0].tolist()):
                if j in parent:
                    parent[find(j)] = find(i)
    groups: dict = {}
    for i, _p in mass:
        groups.setdefault(find(i), set()).add(i)
    opened = set()
    for members in groups.values():
        net = sum(els[i].m for i in members if els[i].TYPE == "source")
        scale = sum(abs(els[i].m) for i in members if els[i].TYPE == "source")
        takes = any(i in takes_far and not (els[i].TYPE == "source" and els[i].m > 0) for i in members)
        through = net <= 1e-9 * (1.0 + scale) and any(i in sends_far for i in members)
        if takes or through:
            opened |= members
    out = frozenset(opened)
    if len(_OPEN_CACHE) > 16:
        _OPEN_CACHE.clear()
    _OPEN_CACHE[key] = out
    return out


def _encloses(ring, pts) -> np.ndarray:
    """True for the points inside the closed polyline `ring` (complex), even-odd rule."""
    a, b = ring, np.roll(ring, -1)
    inside = np.zeros(pts.size, bool)
    for k, p in enumerate(pts):
        up = (a.imag > p.imag) != (b.imag > p.imag)
        with np.errstate(divide="ignore", invalid="ignore"):
            x = a.real + (p.imag - a.imag) * (b.real - a.real) / (b.imag - a.imag)
        inside[k] = np.count_nonzero(up & (p.real < x)) % 2 == 1
    return inside


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
        origin = trace_origin(els, ring, region, L)
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
        new = []
        for ln, owner in zip(context.dividing, context.owners):
            if owner != k:
                continue
            z = ln[:, 0] + 1j * ln[:, 1]
            inside = (z.real > x0) & (z.real < x1) & (z.imag > y0) & (z.imag < y1)
            for run in _runs(inside):
                if run.size < 2:
                    continue
                if tracer is None:
                    tracer = _tracer(els, scale)
                seed = z[run[run.size // 2]]
                fwd, _c, _l = tracer.free_trace(np.array([seed]), 1.0, region)
                bwd, _c, _l = tracer.free_trace(np.array([seed]), -1.0, region)
                pts = np.concatenate([bwd[0][::-1], [seed], fwd[0]])            # along the flow
                if pts.size >= 3:
                    new.append(np.column_stack([pts.real, pts.imag]))
        if new:
            feats.points.append(p)
            feats.dividing += new
            feats.owners += [len(feats.points) - 1] * len(new)
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
            # fluid. A branch along the body surface (e.g. the cylinder surface) has other fluid on
            # one side and is kept.
            u = (starts - p.z) / r
            probes = np.concatenate([starts, starts + 0.3 * r * 1j * u, starts - 0.3 * r * 1j * u])
            origin = trace_origin(els, probes, region, L).reshape(3, -1)
            keep = ((origin == FAR) | (origin == LOOP) | (origin == OPEN)).any(axis=0)
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
