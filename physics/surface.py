"""
surface.py — pressure on the surfaces of a scene (Paket S): the surfaces of the solid bodies and the
walls, Cp along them, and the force on a closed body from the pressure integral.

Surfaces
  * bodies (found once for the whole scene, independent of the view): the parts of the dividing
    streamlines with body fluid on one side and other fluid on the other, joined into outlines (through
    the stagnation points). A thin channel of free stream between two bodies, too thin for the grid of
    cells, is told by tracing the streamlines just beside the line. A closed body (cylinder, Rankine
    oval …) has one closed surface, counter-clockwise (body on the left); an open body (Rankine
    half-body) has a surface that ends where the search region ends (its body goes on downstream).
  * walls: symmetry walls and the two sides of a sector flow, only where fluid touches them, over the
    view (they are infinite).
The points are spaced evenly along the surface and the velocity is evaluated exactly there (on the
body surface and on a wall it is tangential).

Force on a closed body (per unit span; p∞ drops out of a closed integral):
    F′ = −∮ p n ds = −½ ρ V_ref² ∮ Cp n ds,      n = outward normal
Lift L′ is the component across the free stream (90° counter-clockwise from it), drag D′ the
component along it. For a body alone in a uniform stream the theory gives
    L′ = −ρ V∞ Γ   (Kutta–Joukowski; Γ = circulation inside the body, counter-clockwise positive
                    as in this program, so a clockwise Γ < 0 gives lift upwards)
    D′ = 0          (d'Alembert's paradox)
The pressure integral is computed from the surface and compared with these values. With walls or
other elements outside the body the force is still the pressure integral, but there is no such
closed-form value to compare with.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .field import active, complex_velocity, fluid_mask, reference_speed, singular_points
from .images import resolve
from .bodies import PROBE_CELLS, body_map
from .stagnation import BODY, _encloses, bodies_box, body_size, flow_features, has_free_stream, trace_ends

POINTS_PER_SIZE = 240           # surface points per body size (cylinder radius, half-body width …)
MAX_POINTS = 4000
WALL_POINTS = 600               # points along the visible part of a wall


@dataclass
class Surface:
    """One surface: points along it (complex), arc length s from its start, velocity there."""
    kind: str                    # "body" | "wall"
    name: str                    # "Body 1", "Wall 1", "Sector flow: wall at θ₁ = 0°"
    z: np.ndarray                # points (complex), bodies: counter-clockwise (body on the left)
    s: np.ndarray                # arc length from z[0]
    vel: np.ndarray              # u + i v at the points
    closed: bool = False         # a closed body (z[-1] is next to z[0]; not repeated)
    center: complex = 0j         # closed bodies: center of the area; θ is measured round it
    inside: list = field(default_factory=list)       # singular points inside (bodies)
    gamma: float = 0.0           # circulation of the vortices inside (counter-clockwise positive)
    alone: bool = False          # closed body alone in a uniform stream (Kutta–Joukowski applies)
    note: str = ""               # why there is no comparison with the theory (walls, other elements)

    @property
    def speed(self) -> np.ndarray:
        return np.abs(self.vel)

    def cp(self, v_ref: float | None) -> np.ndarray:
        """Cp = 1 − (V / V_ref)² (NaN without a reference speed)."""
        if not v_ref:
            return np.full(self.z.shape, np.nan)
        return 1.0 - (self.speed / v_ref) ** 2

    def theta(self, alpha_deg: float = 0.0) -> np.ndarray:
        """Angle round the center in degrees, 0 … 360, measured counter-clockwise from the direction
        of the free stream (Anderson: the front stagnation point of a cylinder is at θ = 180°)."""
        a = np.degrees(np.angle(self.z - self.center)) - alpha_deg
        return np.mod(a, 360.0)

    def along_flow(self, alpha_deg: float = 0.0) -> np.ndarray:
        """Distance along the free stream from the most upstream point of the surface."""
        x = (self.z * np.exp(-1j * np.radians(alpha_deg))).real
        return x - np.nanmin(x)


@dataclass
class Force:
    """Pressure integral over a closed surface, per unit span and divided by ρ (m³/s² = (N/m)/(kg/m³))."""
    fx: float
    fy: float
    lift: float | None           # across / along the free stream (None without a uniform flow)
    drag: float | None
    kj_lift: float | None        # −V∞ Γ for a body alone in a uniform stream, else None


# ---------------------------------------------------------------------- bodies
def body_surfaces(elements) -> list[Surface]:
    """The surfaces of all bodies of the scene (whole scene: does not depend on the view).

    The parts of the dividing streamlines with a body on one side (bodies.surface_pieces, body on the
    left) are joined end to start into outlines; next to a stagnation point a part stops a little short
    of it, so two parts that both end there are joined through the point. Parts of the same body region
    go together first (where two bodies meet at one stagnation point — a thin channel of free stream
    between two half-bodies — each keeps its own outline). One outline = one body: closed (a cylinder,
    an oval) or open (a half-body; it ends where the search region ends)."""
    els = active(elements)
    if not has_free_stream(els):
        return []
    box = bodies_box(els)
    if box is None:
        return []
    sizes = [body_size(els, e, p) for e in els if e.TYPE in ("source", "doublet")
             for p in e.singular_points()]
    sizes = [s for s in sizes if s]
    if not sizes:
        return []
    x0, x1, y0, y1 = box
    L = max(x1 - x0, y1 - y0)
    scale = min(L, 8.0 * max(sizes))            # tracer step ≪ the bodies, stagnation search over the box
    feats = flow_features(els, box, scale=scale)
    cells = 700
    shape = (max(8, int(round(cells * (y1 - y0) / L))), max(8, int(round(cells * (x1 - x0) / L))))
    bmap = body_map(els, box, shape, list(feats.dividing) + list(feats.inner))
    if bmap is None or bmap.count == 0:
        return []
    cell = L / cells
    pieces = _surface_parts(els, bmap, list(feats.dividing), box, scale, cell)
    if not pieces:
        return []
    stag = np.array([p.z for p in feats.points], dtype=complex)
    outlines = _outlines(pieces, stag, 4.0 * cell, 0.04 * L + 6.0 * cell)
    flows = resolve(els)
    sing = singular_points(els)
    fs = complex(sum((e.freestream_velocity() or 0j) for e in els))
    walls = any(e.fluid_region(np.zeros(1, complex)) is not None for e in els)
    size = min(sizes)
    out = []
    for z, closed in sorted(outlines, key=lambda o: float(np.min(o[0].real))):
        if z.size < 4 or np.sum(np.abs(np.diff(z))) < max(16.0 * cell, 0.5 * min(sizes)):
            continue                                    # a scrap (a wedge next to a stagnation point)
        z = _resample(z, closed, size / POINTS_PER_SIZE)
        inside = [complex(p) for p in sing if closed and _encloses(z, np.array([p]))[0]]
        surf = Surface("body", "", z, _arc(z), _velocity(flows, z), closed=closed, inside=inside)
        surf.gamma = float(sum(e.Gamma for e in els if e.TYPE == "vortex"
                               and any(_same(p, q) for p in e.singular_points() for q in inside)))
        if closed:
            surf.center = _centroid(z)
            others = [p for p in sing if not any(_same(p, q) for q in inside)]
            if walls:
                surf.note = "Walls take part in the flow (ground effect): no closed-form value to compare with."
            elif abs(fs) == 0:
                surf.note = "No uniform flow: no Kutta–Joukowski value to compare with."
            elif others:
                surf.note = ("Other elements outside the body also push on it: the Kutta–Joukowski "
                             "value holds for a body alone in a uniform stream.")
            else:
                surf.alone = True
        else:
            surf.note = "Open body (it goes on downstream without end): no closed surface, no force."
        out.append(surf)
    for k, srf in enumerate(out, 1):
        srf.name = f"Body {k}" + ("" if srf.closed else " (open)")
    return out


SIDE_SAMPLES = 80               # side tests along a dividing streamline (at most)
MIN_GAP = 1e-3                  # … not where another dividing streamline is closer (× the search region)


def _surface_parts(els, bmap, lines, box, scale, cell):
    """The parts of the dividing streamlines that are a body surface, with the body on their left:
    [(body region, points)]. Each side of a line is looked up in the body map a few cells away; where
    BOTH sides are body of two different regions, the map cannot tell a thin channel of free stream
    between two bodies (two half-bodies close together: a hair of free stream runs between them, which
    no grid of cells resolves) from two bodies that touch (two sources side by side). There the sides
    are tested by tracing the streamline just beside the line back to where it starts
    (stagnation.trace_ends): a point less than half way to the next dividing streamline, traced with
    steps much shorter than that (its streamline passes close to a stagnation point)."""
    x0, x1, y0, y1 = box
    L = max(x1 - x0, y1 - y0)
    probe = PROBE_CELLS * cell
    zs = [ln[:, 0] + 1j * ln[:, 1] for ln in lines]
    flags = []
    ask = []                                         # (line, point, left id, right id, normal): traced
    ambiguous = {}                                   # line -> all its points with body of two regions
    for li, z in enumerate(zs):
        if z.size < 2:
            flags.append(np.zeros(0, int))
            continue
        t = np.gradient(z)
        n = 1j * t / np.where(np.abs(t) > 0, np.abs(t), 1.0)              # left normal
        left, right = bmap.body_at(z + probe * n), bmap.body_at(z - probe * n)
        f = np.where((left > 0) & (right == 0), left, np.where((right > 0) & (left == 0), -right, 0))
        both = np.nonzero((left > 0) & (right > 0) & (left != right))[0]
        if both.size:
            ambiguous[li] = both
            for k in both[np.unique(np.linspace(0, both.size - 1, min(SIDE_SAMPLES, both.size)).astype(int))]:
                ask.append((li, int(k), int(left[k]), int(right[k]), n[k]))
        flags.append(f.astype(int))
    if ask:
        every = [z[::max(1, z.size // 300)] for z in zs]
        probes, eps_all, keep = [], [], []
        for q, (li, k, _l, _r, nk) in enumerate(ask):
            others = np.concatenate([w for lj, w in enumerate(every) if lj != li] or [np.zeros(0, complex)])
            gap = float(np.min(np.abs(others - zs[li][k]))) if others.size else L
            if gap < MIN_GAP * L:
                continue                       # where the lines meet (a stagnation point): the neighbours tell
            eps = float(np.clip(0.3 * gap, 1e-4 * L, 4e-3 * L))
            probes += [zs[li][k] + eps * nk, zs[li][k] - eps * nk]
            eps_all += [eps, eps]
            keep.append(q)
        if probes:
            probes, eps_all = np.array(probes), np.array(eps_all)
            kinds = np.empty(probes.size, np.int8)
            level = np.round(np.log2(np.minimum(40.0 * eps_all, scale))).astype(int)   # tracer ≈ 40 × offset
            for lev in np.unique(level):
                sel = level == lev
                kinds[sel] = trace_ends(els, probes[sel], box, float(2.0 ** lev), -1.0)[0]
            body = (kinds == BODY).reshape(-1, 2)
            decided = {}                                      # line -> [(point, flag)]
            for q, b in zip(keep, body):
                li, k, lid, rid, _n = ask[q]
                decided.setdefault(li, []).append((k, lid if b[0] and not b[1] else -rid if b[1] and not b[0] else 0))
            for li, items in decided.items():                 # each ambiguous point: its nearest test
                f = flags[li]
                ks = np.array([k for k, _v in items])
                vs = np.array([v for _k, v in items])
                amb = ambiguous[li]
                f[amb] = vs[np.abs(amb[:, None] - ks[None, :]).argmin(axis=1)]
    out = []
    for z, f in zip(zs, flags):
        if not f.size:
            continue
        k = 0
        while k < z.size:
            if f[k] == 0:
                k += 1
                continue
            j = k
            while j + 1 < z.size and f[j + 1] == f[k]:
                j += 1
            if j > k:
                out.append((abs(int(f[k])), z[k:j + 1] if f[k] > 0 else z[k:j + 1][::-1]))
            k = j + 1
    return _drop_repeats(out, 2.0 * probe)


def _drop_repeats(pieces, tol):
    """A surface traced from both of its stagnation points is there twice: keep the longer copy."""
    pieces = sorted(pieces, key=lambda p: -np.sum(np.abs(np.diff(p[1]))))
    kept = []
    for b, z in pieces:
        sub = z[::max(1, z.size // 200)]
        if any(kb == b and np.median(np.min(np.abs(sub[:, None] - w[None, ::max(1, w.size // 400)]), axis=1)) < tol
               for kb, w in kept):
            continue
        kept.append((b, z))
    return kept


def _outlines(pieces, stag, tol, reach):
    """Join pieces (body number, points with the body on the left) end to start into outlines:
    [(points, closed)]. A link from the end of a piece to the start of another (or of itself: a closed
    outline) is possible when they are less than `tol` apart, or both within `reach` of one stagnation
    point (then the point is put between them). Cheapest links first; a link inside one body region costs
    less than one between two regions (that only joins the regions of one body split by a branch)."""
    n = len(pieces)
    links = []
    for i, (bi, zi) in enumerate(pieces):
        e = zi[-1]
        for j, (bj, zj) in enumerate(pieces):
            st = zj[0]
            d = abs(e - st)
            via = None
            if d > tol or bi != bj:          # two regions meet only at a stagnation point (not at the
                                             # far end of a thin channel, where their surfaces are close)
                if not stag.size:
                    continue
                ds = np.abs(stag - e) + np.abs(stag - st)
                k = int(np.argmin(ds))
                if abs(stag[k] - e) > reach or abs(stag[k] - st) > reach:
                    continue
                via, d = stag[k], float(ds[k])
            cost = d + (0.0 if bi == bj else 2.0 * reach)
            links.append((cost, i, j, via))
    links.sort(key=lambda t: t[0])
    nxt, prev = {}, {}
    for _cost, i, j, via in links:
        if i in nxt or j in prev:
            continue
        nxt[i], prev[j] = (j, via), i
    out, seen = [], set()
    starts = [i for i in range(n) if i not in prev] + list(range(n))     # open outlines first
    for s0 in starts:
        if s0 in seen:
            continue
        parts, i, closed = [], s0, False
        while True:
            seen.add(i)
            parts.append(pieces[i][1])
            if i not in nxt:
                break
            j, via = nxt[i]
            if via is not None:
                parts.append(np.array([via]))
            if j == s0:
                closed = True
                break
            if j in seen:
                break
            i = j
        z = np.concatenate(parts)
        out.append((z, closed))
    return out


def _first_x(b) -> float:
    return float(min(np.min(c[:, 0]) for c in b.surface))


def _resample(z, closed, ds):
    """Points evenly spaced along the polyline, about ds apart (at most MAX_POINTS)."""
    zz = np.append(z, z[0]) if closed else z
    seg = np.abs(np.diff(zz))
    s = np.concatenate([[0.0], np.cumsum(seg)])
    total = s[-1]
    n = int(np.clip(total / max(ds, 1e-12), 64, MAX_POINTS))
    t = np.linspace(0.0, total, n, endpoint=not closed)
    return np.interp(t, s, zz.real) + 1j * np.interp(t, s, zz.imag)


def _same(p, q) -> bool:
    return abs(p - q) < 1e-9 * (1.0 + abs(p))


def _arc(z):
    return np.concatenate([[0.0], np.cumsum(np.abs(np.diff(z)))])


def _velocity(flows, z):
    with np.errstate(all="ignore"):
        return np.conj(complex_velocity(flows, z))


def _centroid(z) -> complex:
    """Center of the area inside the closed polygon z."""
    a, b = z, np.roll(z, -1)
    cross = a.real * b.imag - b.real * a.imag
    area = 0.5 * cross.sum()
    if abs(area) < 1e-15:
        return complex(np.mean(z))
    cx = ((a.real + b.real) * cross).sum() / (6.0 * area)
    cy = ((a.imag + b.imag) * cross).sum() / (6.0 * area)
    return complex(cx, cy)


def rotate_to_theta0(surf: Surface, alpha_deg: float = 0.0) -> Surface:
    """A closed surface with its first point at θ = 0 (so a plot over θ does not jump)."""
    if not surf.closed:
        return surf
    k = int(np.argmin(surf.theta(alpha_deg)))
    z, vel = np.roll(surf.z, -k), np.roll(surf.vel, -k)
    out = Surface(surf.kind, surf.name, z, _arc(z), vel, True, surf.center, surf.inside, surf.gamma,
                  surf.alone, surf.note)
    return out


# ---------------------------------------------------------------------- walls
def wall_surfaces(elements, view) -> list[Surface]:
    """The walls where fluid touches them, over the view ((x0, x1), (y0, y1)) and a little beyond."""
    els = active(elements)
    (x0, x1), (y0, y1) = view
    W, H = x1 - x0, y1 - y0
    box = (x0 - 0.05 * W, x1 + 0.05 * W, y0 - 0.05 * H, y1 + 0.05 * H)
    flows = resolve(els)
    eps = 1e-6 * max(W, H)
    lines = []                                   # (name, start point, direction, ray?, normal into fluid)
    n_wall = 0
    for e in els:
        if e.TYPE == "wall":
            n_wall += 1
            lines.append((f"Wall {n_wall}", e.point, e.direction, False, e.normal))
        elif e.TYPE == "sector":
            for ang, name, sgn in ((e.theta1, "θ₁", 1j), (e.theta2, "θ₂", -1j)):
                d = np.exp(1j * np.radians(ang))
                lines.append((f"Sector wall {name} = {ang:.4g}°", e.z0, d, True, d * sgn))
    out = []
    for name, p, d, ray, nrm in lines:
        first = len(out)
        t0, t1 = _clip_line(p, d, box)
        if ray:
            t0 = max(t0, 0.0)
        if not t1 > t0:
            continue
        t = np.linspace(t0, t1, WALL_POINTS)
        z = p + t * d
        wet = np.asarray(fluid_mask(els, z + eps * nrm), bool)
        for run in _runs(wet):
            if run.size < 8:
                continue
            zr = z[run]
            vel = _velocity(flows, zr)
            out.append(Surface("wall", name, zr, t[run], vel))
        if len(out) - first > 1:                        # a wall wetted in several parts
            for j, srf in enumerate(out[first:], 1):
                srf.name = f"{name} (part {j})"
    return out


def _clip_line(p, d, box):
    """Parameters t0 < t1 where p + t·d is inside the box (−inf, −inf if it misses)."""
    x0, x1, y0, y1 = box
    t0, t1 = -np.inf, np.inf
    for a, da, lo, hi in ((p.real, d.real, x0, x1), (p.imag, d.imag, y0, y1)):
        if abs(da) < 1e-15:
            if not lo <= a <= hi:
                return -np.inf, -np.inf
            continue
        ta, tb = (lo - a) / da, (hi - a) / da
        t0, t1 = max(t0, min(ta, tb)), min(t1, max(ta, tb))
    return t0, t1


def _runs(mask):
    idx = np.nonzero(mask)[0]
    if not idx.size:
        return []
    return np.split(idx, np.nonzero(np.diff(idx) > 1)[0] + 1)


# ---------------------------------------------------------------------- force
def pressure_force(surf: Surface, elements, v_ref: float | None) -> Force | None:
    """Force per unit span / ρ on a closed body from the pressure integral (None for open surfaces or
    without a reference speed)."""
    if not surf.closed or not v_ref:
        return None
    cp = surf.cp(v_ref)
    z = surf.z
    dz = np.roll(z, -1) - z                                    # closed polygon, counter-clockwise
    cp_mid = 0.5 * (cp + np.roll(cp, -1))
    # outward normal n = −i t (body on the left of the way round): F/ρ = −½V² ∮ Cp n ds = ½V² ∮ Cp i dz
    F = 0.5 * v_ref ** 2 * np.sum(cp_mid * 1j * dz)
    els = active(elements)
    fs = complex(sum((e.freestream_velocity() or 0j) for e in els))
    lift = drag = kj = None
    if abs(fs) > 0:
        ed = fs / abs(fs)
        el = 1j * ed
        drag = float((F * np.conj(ed)).real)
        lift = float((F * np.conj(el)).real)
        if surf.alone:
            kj = -abs(fs) * surf.gamma
    return Force(float(F.real), float(F.imag), lift, drag, kj)


def cylinder_cp(elements, surf: Surface) -> np.ndarray | None:
    """Analytic Cp on the surface when the scene is exactly a (lifting) cylinder: uniform flow +
    doublet along it + optionally a vortex at its center (Γ ≤ 4πV∞a: the surface is the circle r = a).
        Cp = 1 − (2 sin θ − Γ / (2π a V∞))²     (θ from the free stream, Γ counter-clockwise > 0)
    None for any other scene."""
    els = active(elements)
    uni = [e for e in els if e.TYPE == "uniform"]
    dbl = [e for e in els if e.TYPE == "doublet"]
    vor = [e for e in els if e.TYPE == "vortex"]
    if len(uni) != 1 or len(dbl) != 1 or len(vor) > 1 or len(els) != 1 + 1 + len(vor) or not surf.closed:
        return None
    u, d = uni[0], dbl[0]
    if u.V <= 0 or d.mu <= 0 or abs(((d.delta - u.alpha) + 180.0) % 360.0 - 180.0) > 1e-9:
        return None
    gamma = 0.0
    if vor:
        if abs(vor[0].z0 - d.z0) > 1e-9 * (1 + abs(d.z0)):
            return None
        gamma = vor[0].Gamma
    a = np.sqrt(d.mu / u.V)
    if abs(gamma) > 4.0 * np.pi * u.V * a:
        return None
    th = np.angle(surf.z - d.z0) - np.radians(u.alpha)
    return 1.0 - (2.0 * np.sin(th) - gamma / (2.0 * np.pi * a * u.V)) ** 2


def free_stream_angle(elements) -> float:
    """α of the uniform flow(s) in degrees (0 without one)."""
    fs = complex(sum((e.freestream_velocity() or 0j) for e in active(elements)))
    return float(np.degrees(np.angle(fs))) if abs(fs) > 0 else 0.0


def scene_reference_speed(elements):
    return reference_speed(active(elements))
