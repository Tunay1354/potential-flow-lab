"""
surface.py — pressure on the surfaces of a scene (Paket S): the surfaces of the solid bodies and the
walls, Cp along them, and the force on a closed body from the pressure integral.

Surfaces
  * bodies (bodies.find_bodies, found once for the whole scene, independent of the view): a closed
    body (cylinder, Rankine oval …) has one closed surface, counter-clockwise (body on the left); an
    open body (Rankine half-body) has a surface that ends where the search region ends (its body goes
    on to x → ∞ downstream).
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

from .bodies import find_bodies
from .field import active, complex_velocity, fluid_mask, reference_speed, singular_points
from .images import resolve
from .stagnation import bodies_box, body_size, flow_features, has_free_stream

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
    """The surfaces of all bodies of the scene (whole scene: does not depend on the view)."""
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
    bodies = find_bodies(els, feats.dividing, box, cells=600, inner=feats.inner)
    flows = resolve(els)
    sing = singular_points(els)
    fs = complex(sum((e.freestream_velocity() or 0j) for e in els))
    walls = any(e.fluid_region(np.zeros(1, complex)) is not None for e in els)
    out = []
    size = min(sizes)
    for b in sorted(bodies, key=_first_x):
        chains = [c[:, 0] + 1j * c[:, 1] for c in b.surface]
        for z in chains:
            if z.size < 4:
                continue
            z = _resample(z, b.closed, size / POINTS_PER_SIZE)
            surf = Surface("body", "", z, _arc(z), _velocity(flows, z), closed=bool(b.closed), inside=list(b.singular))
            surf.gamma = float(sum(e.Gamma for e in els if e.TYPE == "vortex"
                                   and any(_same(p, q) for p in e.singular_points() for q in b.singular)))
            if b.closed:
                surf.center = _centroid(z)
                others = [p for p in sing if not any(_same(p, q) for q in b.singular)]
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
