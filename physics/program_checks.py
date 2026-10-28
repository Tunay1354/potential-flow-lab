"""
program_checks.py — what the PROGRAM computes, checked against the theory (Paket V, `--verify`):

  scene_checks(title, elements, view)   the checks that fit a scene, chosen by what it contains:
      uniform flow only       the drawn streamlines are straight lines at the angle α
      one source / sink       the drawn streamlines are radial; the flow goes out of a source, into a sink
      one vortex              the drawn streamlines are circles; the sense of rotation
      (lifting) cylinder      stagnation points found by the program at sin θ = Γ/(4πV∞a); the body surface
                              is the circle r = a; Cp on it; lift and drag from the pressure integral
                              against Kutta–Joukowski and d'Alembert
      source above a wall     no flow through the wall; the stagnation point on the wall under the source
  accuracy_checks()       the numerical methods on their own: ψ constant along the drawn streamlines,
                          the stagnation point search, body shapes from the surfaces, lift for several Γ

Each row has its own tolerance: the streamlines are integrated (RK4) and the surfaces are traced, so
these are not exact to round-off like the velocity formulas (physics/verification.py).
"""
from __future__ import annotations

import numpy as np

from .elements import Doublet, SectorFlow, Source, SymmetryWall, Uniform, Vortex
from .field import active, complex_potential, complex_velocity, reference_speed
from .images import resolve
from .stagnation import find_stagnation_points
from .streamlines import StreamlineCache
from .surface import body_surfaces, cylinder_cp, pressure_force
from .verification import Check

RHO = 1.225
SCENES = "The program's results for the scene"
ACCURACY = "Accuracy of the numerical methods"


def _lines(elements, view):
    res = StreamlineCache(tuple(active(elements))).update(view, force=True)
    return res, [ln[:, 0] + 1j * ln[:, 1] for ln in res.lines if len(ln) >= 3]


def _velocity(elements, z):
    return np.conj(complex_velocity(resolve(active(elements)), z))


# ---------------------------------------------------------------------- one scene
def scene_checks(title, elements, view) -> list[Check]:
    """The checks that fit this scene (see the module docstring); [] if none does."""
    els = active(elements)
    kinds = sorted(e.TYPE for e in els)
    rows: list[Check] = []

    def add(quantity, analytic, numerical, tol):
        rows.append(Check(title, quantity, float(analytic), float(numerical), tol, SCENES))

    if kinds == ["uniform"]:
        (u,) = els
        _res, lines = _lines(els, view)
        seg = np.concatenate([np.diff(z) for z in lines])
        ang = np.degrees(np.angle(seg[np.abs(seg) > 0])) - u.alpha
        ang = (ang + 90.0) % 180.0 - 90.0                         # a line drawn either way round
        add(f"drawn streamlines: largest angle to α = {u.alpha:g}° [°]", 0.0, np.max(np.abs(ang)), 1e-6)
        z = np.concatenate(lines)
        vel = _velocity(els, z)
        add("flow direction along them: mean cos(angle to α)", 1.0,
            np.mean((vel * np.exp(-1j * np.radians(u.alpha))).real / np.abs(vel)), 1e-9)
    elif kinds == ["source"]:
        (s,) = els
        _res, lines = _lines(els, view)
        worst = 0.0
        for z in lines:
            mid = 0.5 * (z[1:] + z[:-1])
            d = np.diff(z)
            ok = (np.abs(d) > 0) & (np.abs(mid - s.z0) > 1e-9)
            a = np.degrees(np.angle(d[ok] / (mid[ok] - s.z0)))
            a = (a + 90.0) % 180.0 - 90.0
            worst = max(worst, float(np.max(np.abs(a))) if a.size else 0.0)
        add("drawn streamlines: largest angle to the radial direction [°]", 0.0, worst, 1e-6)
        z = np.concatenate(lines)
        vel = _velocity(els, z)
        radial = (vel * np.conj(z - s.z0)).real / (np.abs(vel) * np.abs(z - s.z0))
        sign = 1.0 if s.m > 0 else -1.0
        add(f"flow {'out of the source' if s.m > 0 else 'into the sink'}: V·r̂ / |V| on the lines", sign,
            float(np.mean(radial)), 1e-9)
    elif kinds == ["vortex"]:
        (v,) = els
        _res, lines = _lines(els, view)
        dev = max(float(np.ptp(np.abs(z - v.z0)) / np.mean(np.abs(z - v.z0))) for z in lines)
        add("drawn streamlines are circles: largest (r_max − r_min)/r", 0.0, dev, 1e-4)
        z = np.concatenate(lines)
        vel = _velocity(els, z)
        tang = (vel * np.conj(1j * (z - v.z0))).real / (np.abs(vel) * np.abs(z - v.z0))
        add(f"sense of rotation: V_θ / |V| ({'counter-clockwise' if v.Gamma > 0 else 'clockwise'} = "
            f"{'+' if v.Gamma > 0 else '−'}1)", np.sign(v.Gamma), float(np.mean(tang)), 1e-9)
    elif kinds in (["doublet", "uniform"], ["doublet", "uniform", "vortex"]):
        rows += _cylinder_rows(title, els, view)
    elif kinds == ["source", "wall"]:
        w = next(e for e in els if e.TYPE == "wall")
        s = next(e for e in els if e.TYPE == "source")
        t = np.linspace(-20.0, 20.0, 2001)
        z = w.point + t * w.direction
        vel = _velocity(els, z)
        add("no flow through the wall: max |V·n| on the wall (2001 points)", 0.0,
            float(np.max(np.abs((vel * np.conj(w.normal)).real))), 1e-9)
        foot = w.point + ((s.z0 - w.point) * np.conj(w.direction)).real * w.direction
        res, _lines_ = _lines(els, view)
        found = [p.z for p in res.stagnation]
        add("stagnation point on the wall under the source: distance to it [m]", 0.0,
            min(abs(p - foot) for p in found) if found else np.inf, 1e-8)
    return rows


def _cylinder_rows(title, els, view) -> list[Check]:
    rows = []

    def add(quantity, analytic, numerical, tol):
        rows.append(Check(title, quantity, float(analytic), float(numerical), tol, SCENES))

    u = next(e for e in els if e.TYPE == "uniform")
    d = next(e for e in els if e.TYPE == "doublet")
    vortices = [e for e in els if e.TYPE == "vortex"]
    gamma = vortices[0].Gamma if vortices else 0.0
    if vortices and abs(vortices[0].z0 - d.z0) > 1e-12:
        return rows                                    # not a (lifting) cylinder
    V, a = u.V, float(np.sqrt(d.mu / u.V))
    alpha = np.radians(u.alpha)
    s = gamma / (4.0 * np.pi * V * a)
    if abs(s) <= 1.0:
        th = np.arcsin(s)
        exact = [d.z0 + a * np.exp(1j * (alpha + th)), d.z0 + a * np.exp(1j * (alpha + np.pi - th))]
        res, _lines_ = _lines(els, view)
        found = [p.z for p in res.stagnation]
        err = max(min(abs(p - q) for q in found) for p in exact) if found else np.inf
        add(f"stagnation points found at sin θ = Γ/(4πV∞a) = {s:.4f}: largest distance [m]", 0.0, err, 1e-8)
    (surf,) = [b for b in body_surfaces(els) if b.closed]
    if abs(gamma) <= 4.0 * np.pi * V * a:
        add("body surface traced by the program is r = a: max |r − a| [m]", 0.0,
            float(np.max(np.abs(np.abs(surf.z - d.z0) - a))), 2e-3)
        exact = cylinder_cp(els, surf)
        add("Cp on that surface vs 1 − (2 sin θ − Γ/(2πaV∞))²: max |error|", 0.0,
            float(np.max(np.abs(exact - surf.cp(V)))), 5e-3)
    f = pressure_force(surf, els, V)
    kj = -RHO * V * gamma
    add("lift L′ = −∮ p n ds vs Kutta–Joukowski ρV∞Γ_cw [N/m, ρ = 1.225]", kj, RHO * f.lift,
        1e-3 * max(1.0, abs(kj)))
    add("drag D′ = −∮ p n ds vs d'Alembert 0 [N/m]", 0.0, RHO * f.drag, 1e-3 * max(1.0, abs(kj)))
    return rows


# ---------------------------------------------------------------------- the numerical methods
def accuracy_checks() -> list[Check]:
    rows: list[Check] = []

    def add(case, quantity, analytic, numerical, tol):
        rows.append(Check(case, quantity, float(analytic), float(numerical), tol, ACCURACY))

    # ψ along the drawn streamlines (RK4 integration): constant, in units of the ψ step between lines
    view = ((-4.0, 4.0), (-3.0, 3.0))
    for name, els in (("Cylinder", [Uniform(), Doublet(mu=1.0)]),
                      ("Lifting cylinder, Γ = −2", [Uniform(), Doublet(mu=1.0), Vortex(Gamma=-2.0)]),
                      ("Two cylinders in a row", [Uniform(), Doublet(mu=0.5, x0=-1.5), Doublet(mu=0.5, x0=1.5)]),
                      ("Cylinder above the ground", [SymmetryWall(yw=0.0), Uniform(), Doublet(mu=1.0, y0=1.5)]),
                      ("Vortex near a wall", [SymmetryWall(yw=0.0), Vortex(Gamma=2.0, y0=1.0)])):
        res, lines = _lines(els, view if "ground" not in name and "wall" not in name else ((-4.0, 4.0), (-0.5, 4.5)))
        step = _psi_step(els, lines, res)
        worst = 0.0
        for z in lines:
            psi = complex_potential(els, z).imag
            worst = max(worst, float(np.ptp(psi)) / step)
        add(name, "ψ along each drawn line: max (ψ_max − ψ_min) / Δψ between lines (≤ 1 %)", 0.0, worst, 1e-2)

    # the stagnation point search (Newton) against closed-form positions
    m = 2.0
    pts = find_stagnation_points([Uniform(), Source(m=m)], (-4.0, 4.0, -3.0, 3.0))
    add("Rankine half-body, m = 2", "nose x = −m/(2πV∞) [m]", -m / (2 * np.pi),
        min((p.x for p in pts), key=lambda x: abs(x + m / (2 * np.pi))), 1e-9)
    m = 2 * np.pi
    pts = find_stagnation_points([Uniform(), Source(m=m, x0=-1.0), Source(m=-m, x0=1.0)], (-4.0, 4.0, -3.0, 3.0))
    L = np.sqrt(1.0 + m / (np.pi * 1.0 * 1.0))
    add("Rankine oval, m = 2π, a = 1", "stagnation points x = ±a√(1 + m/(πaV∞)) [m]", L,
        max(abs(p.x) for p in pts), 1e-9)
    g = -4.0 * np.pi
    pts = find_stagnation_points([Uniform(), Doublet(mu=1.0), Vortex(Gamma=g)], (-4.0, 4.0, -3.0, 3.0))
    add("Lifting cylinder, Γ = −4πV∞a", "the two points meet at the bottom (0, −a): distance [m]", 0.0,
        min(abs(p.z + 1j) for p in pts), 1e-6)
    pts = find_stagnation_points([SymmetryWall(yw=0.0, side=0), SymmetryWall(theta_w=90.0, side=1),
                                  Source(m=2.0, x0=1.0, y0=1.0)], (-0.5, 4.0, -0.5, 4.0))
    add("Source in a 90° corner (walls)", "stagnation point in the corner (a double zero of w): distance [m]",
        0.0, min(abs(p.z) for p in pts), 1e-5)
    pts = find_stagnation_points([SectorFlow(V=1.0), Source(m=2.0, x0=1.0, y0=1.0)], (-0.5, 4.0, -0.5, 4.0))
    add("Source in a 90° corner flow", "|V| at the stagnation point found", 0.0,
        min(abs(_velocity([SectorFlow(V=1.0), Source(m=2.0, x0=1.0, y0=1.0)], np.array([p.z]))[0])
            for p in pts if p.kind != "vertex"), 1e-9)

    # body shapes traced by the program
    (cyl,) = body_surfaces([Uniform(), Doublet(mu=1.0)])
    z = cyl.z
    area = 0.5 * np.sum(z.real * np.roll(z.imag, -1) - np.roll(z.real, -1) * z.imag)
    add("Cylinder, a = 1", "area inside the traced surface = πa² [m²]", np.pi, area, 2e-3)
    (half,) = body_surfaces([Uniform(), Source(m=2.0)])
    z = half.z[np.abs(half.z.imag) > 1e-3]
    th = np.mod(np.angle(z), 2 * np.pi)
    th = np.where(z.imag > 0, th, 2 * np.pi - th)
    exact = 1.0 * (1.0 - th / np.pi)                           # |y| = (m/2V∞)(1 − θ/π), m = 2
    add("Rankine half-body, m = 2", "surface |y| = (m/2V∞)(1 − θ/π): max |error| [m]", 0.0,
        float(np.max(np.abs(np.abs(z.imag) - exact))), 2e-3)
    (oval,) = body_surfaces([Uniform(), Source(m=2 * np.pi, x0=-1.0), Source(m=-2 * np.pi, x0=1.0)])
    add("Rankine oval, m = 2π, a = 1", "half-length of the traced surface = √3 [m]", np.sqrt(3.0),
        float(np.max(np.abs(oval.z.real))), 2e-3)

    # lift from the pressure integral for several Γ (also Γ > 4πV∞a: the body with its turning ring)
    for g in (-2.0, -6.0, -15.0, 3.0):
        els = [Uniform(), Doublet(mu=1.0), Vortex(Gamma=g)]
        (surf,) = [b for b in body_surfaces(els) if b.closed]
        f = pressure_force(surf, els, 1.0)
        add(f"Lifting cylinder, Γ = {g:g}", "L′/ρ from −∮ p n ds vs −V∞Γ [m³/s²]", -g, f.lift, 1e-3 * max(1.0, abs(g)))
    return rows


def _psi_step(els, lines, res) -> float:
    """ψ between two neighbouring streamlines ≈ typical speed × line spacing."""
    z = np.concatenate(lines)
    speed = np.abs(_velocity(els, z))
    v = reference_speed(active(els)) or float(np.median(speed[np.isfinite(speed)]))
    return v * float(res.separation)
