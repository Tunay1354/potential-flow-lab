"""
verification.py — the physics checked against the analytic solutions of the course: a table of
(case, quantity, analytic value, numerical value, |error|) for the report (scripts/verify_physics.py,
the command line `--verify`) and for the tests (tests/test_verification.py). The velocity formulas
are exact to round-off; physics/program_checks.py adds what the program computes numerically (drawn
streamlines, stagnation point search, body surfaces, surface pressure), each with its own tolerance.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .diagnostics import (circle_points, circulation_around_circle, flux_through_circle, polar_components,
                          surface_forces)
from .elements import Doublet, SectorFlow, Source, SymmetryWall, Uniform, Vortex
from .field import complex_potential, velocity

TOLERANCE = 1e-9                  # largest error accepted (the comparisons are exact up to round-off)


@dataclass(frozen=True)
class Check:
    case: str
    quantity: str
    analytic: float
    numerical: float
    tolerance: float = TOLERANCE      # largest |error| accepted for this row (numerical methods: larger)
    section: str = "Analytic formulas"
    how: str = ""                     # how it is computed: "Theory: …" / "Program: …" / "Tolerance: …" lines

    @property
    def error(self) -> float:
        return abs(self.numerical - self.analytic)

    @property
    def ok(self) -> bool:
        return bool(self.error < self.tolerance)


def _max_vn(els, wall, half=8.0, n=801):
    """Largest normal velocity on a wall (should be 0)."""
    t = np.linspace(-half, half, n)
    z = wall.point + t * wall.direction
    uu, vv = velocity(els, z.real, z.imag)
    return float(np.max(np.abs(((uu + 1j * vv) * np.conj(wall.normal)).real)))


# How each comparison is made (shown under a check in Help → Run verification and in the HTML report).
# Lines starting with "Theory:", "Program:" or "Tolerance:" are the parts of the explanation.
_SAME_CODE = ("The velocity comes from the same code the plot uses: every element's own formula, the images "
              "of the walls added (physics/images.resolve), all summed (superposition, physics/field.velocity).")
HOW = {
    "uniform": "Theory: uniform flow at the angle α: F(z) = V∞ e^(−iα) z, so w = dF/dz = u − iv = V∞ e^(−iα): "
               "u = V∞ cos α, v = V∞ sin α, the same everywhere.\n"
               "Program: the velocity at the sample point (1.234, −0.567). " + _SAME_CODE,
    "flux": "Theory: a source of strength m: V_r = m/(2πr), V_θ = 0. The volume flow (per unit span) out of any "
            "circle around it is ∮ V·n ds = V_r · 2πr = m (a sink: m < 0, the flow goes in).\n"
            "Program: 4096 points on the circle r = 1 around the source; at each the velocity is split into "
            "the radial component V_r; flux = mean(V_r) × 2πr (the trapezoid rule — for a periodic integrand "
            "exact up to round-off). " + _SAME_CODE,
    "V_r": "Theory: V_r = m/(2πr) → m/(2π) on r = 1.\n"
           "Program: the velocity at a point of the circle r = 1, split into radial and tangential components "
           "(physics/diagnostics.polar_components). " + _SAME_CODE,
    "circulation": "Theory: a point vortex: V_θ = Γ/(2πr), V_r = 0. The circulation on any circle around it is "
                   "∮ V·ds = V_θ · 2πr = Γ (Γ > 0: counter-clockwise).\n"
                   "Program: 4096 points on r = 1, the tangential component V_θ at each; Γ = mean(V_θ) × 2πr. "
                   + _SAME_CODE,
    "V_θ vortex": "Theory: V_θ = Γ/(2πr) → Γ/(2π) on r = 1.\n"
                  "Program: the velocity at a point of the circle r = 1, split into polar components. " + _SAME_CODE,
    "cylinder": "Theory: uniform flow + doublet μ = V∞a² (a = 1): V_r = V∞(1 − a²/r²) cos θ, "
                "V_θ = −V∞(1 + a²/r²) sin θ. On r = a: V_r = 0 (the circle is a streamline: the body surface) and "
                "V_θ = −2V∞ sin θ, so Cp = 1 − (V/V∞)² = 1 − 4 sin²θ: −3 at θ = 90°, and the stagnation points "
                "are at θ = 0° and 180°.\n"
                "Program: the velocity at that point of the circle r = a from the uniform-flow and doublet elements; "
                "Cp = 1 − |V|²/V∞². " + _SAME_CODE,
    "dalembert": "Theory: d'Alembert's paradox — in steady inviscid flow without circulation the force on a closed "
                 "body is zero: no lift, no drag.\n"
                 "Program: the pressure from Bernoulli, p − p∞ = ½ρ(V∞² − V²), at 4096 points of the circle r = a "
                 "(velocity from the elements); force F = −∮ (p − p∞) n ds summed around the circle; L′ is its "
                 "component across the free stream, D′ along it (ρ = 1.225 kg/m³).",
    "lifting stag": "Theory: uniform + doublet + a vortex Γ at the center: on r = a, V_r = 0 and "
                    "V_θ = −2V∞ sin θ + Γ/(2πa). V_θ = 0 where sin θ = Γ/(4πV∞a) (Γ counter-clockwise > 0; here "
                    "Γ_cw = 2 clockwise, Γ = −2: the stagnation points move down).\n"
                    "Program: |V| at that point from the elements — zero if the formula and the program agree. "
                    + _SAME_CODE,
    "kutta": "Theory: Kutta–Joukowski: the lift per unit span on any closed body with circulation is L′ = ρ V∞ Γ "
             "(clockwise Γ gives lift up); the drag is still zero.\n"
             "Program: the same pressure integral as for d'Alembert — Bernoulli at 4096 points of r = a, "
             "F = −∮ (p − p∞) n ds — now with the vortex in the scene (ρ = 1.225 kg/m³, V∞ = 1, Γ_cw = 2: "
             "L′ = 2.45 N/m).",
    "wall": "Theory: a symmetry wall is a streamline: no flow through it, V·n = 0. The method of images puts a mirror "
            "image of every element behind the wall (source → same m, vortex → opposite Γ, doublet → mirrored "
            "axis, uniform flow along the wall → itself); on the wall the normal components cancel.\n"
            "Program: the images are made by physics/images.resolve (repeated reflection); the velocity is "
            "evaluated at points all along the wall and the largest |V·n| is shown.",
    "vortex wall": "Theory: the image of a vortex Γ at height h is a vortex −Γ at depth h. At the wall point under "
                   "the vortex both give Γ/(2πh) in the same direction: u = Γ/(πh).\n"
                   "Program: the velocity at (0, 0) with the wall y = 0 (image added by the program). " + _SAME_CODE,
    "source wall": "Theory: the image of a source m at height h is the same source at depth h. At (h, 0) each is "
                   "h√2 away: speed m/(2π h√2) at ±45°; the vertical parts cancel, the horizontal ones add: "
                   "u = m/(2πh).\n"
                   "Program: the velocity at (h, 0) with the wall y = 0 (image added by the program). " + _SAME_CODE,
    "corner": "Theory: two walls at 90° (π/k with k = 2): the reflections close after 2k − 1 = 3 images (mirror in "
              "each wall and in both), and then both walls are streamlines.\n"
              "Program: physics/images.resolve reflects until no new image appears (here 3), the velocity is "
              "evaluated at 801 points along each wall; the largest |V·n| is shown.",
    "channel": "Theory: two parallel walls H apart: the images repeat without end with the period 2H along the "
               "normal. The infinite rows are summed in closed form, Σ 1/(z − a − 2nH) = (π/2H) cot(π(z − a)/2H), "
               "so the channel is exact too. Far from the source all of its flow m goes along the channel, half "
               "each way: u = (m/2)/H = 0.25 for m = 1, H = 2.\n"
               "Program: max |V·n| at 801 points along each wall (|x| ≤ 30), and u at x = 80 in the middle of the "
               "channel.",
    "sector": "Theory: flow in a corner (sector, wedge) of angle β: F = V z^n with n = π/β. For β = 90°, n = 2: "
              "F = V z², w = 2Vz → u = 2Vx, v = −2Vy.\n"
              "Program: the velocity of the Sector flow element at (1.5, 0.5). " + _SAME_CODE,
    "sector psi": "Theory: F = V (z e^(−iθ₁))^n with n = π/β; on the second side θ = θ₁ + β the power is r^n e^(iπ), "
                  "a real number → ψ = Im F = 0: both sides of the sector are streamlines for any β.\n"
                  "Program: F at 200 points along the second side; the largest |ψ| relative to the largest |F|.",
    "plate tip": "Theory: β = 360° (flow around the tip of a flat plate): n = 1/2, |w| = V n r^(n−1) = (V/2) r^(−1/2) "
                 "→ 1/√0.81 for V = 2, r = 0.81 (infinite at the tip).\n"
                 "Program: |V| of the Sector flow element at r = 0.81. " + _SAME_CODE,
    "sector source": "Theory: a source inside a 90° sector flow: the sides of the sector are walls for the source, "
                     "so it gets the 3 corner images; the sector flow already satisfies its walls.\n"
                     "Program: max |V·n| at 400 points along each side (sector flow + source + images).",
}


def verification_checks() -> list[Check]:
    """All comparisons (uniform flow, source / sink / vortex, cylinder with and without circulation,
    symmetry walls and the method of images, sector flows)."""
    rows = []

    def add(case, quantity, analytic, numeric, how):
        rows.append(Check(case, quantity, float(analytic), float(numeric), how=HOW[how]))

    # 1) Uniform flow ------------------------------------------------------------------
    for alpha in (0.0, 45.0):
        u, v = velocity([Uniform(V=1.0, alpha=alpha)], 1.234, -0.567)
        a = np.radians(alpha)
        add(f"Uniform, α = {alpha:.0f}°", "u", np.cos(a), float(u), "uniform")
        add(f"Uniform, α = {alpha:.0f}°", "v", np.sin(a), float(v), "uniform")

    # 2) Source, sink, vortex -------------------------------------------------------------
    c = 0.5 + 0.5j
    for m in (2.0, -2.0):
        name = "Source" if m > 0 else "Sink"
        el = [Source(m=m, x0=c.real, y0=c.imag)]
        add(f"{name}, m = {m:g}", "flux ∮V·n ds", m, flux_through_circle(el, c, 1.0), "flux")
        z, _ = circle_points(c, 1.0, 8)
        add(f"{name}, m = {m:g}", "V_r at r = 1", m / (2 * np.pi), float(polar_components(el, z, c)[0][0]), "V_r")
    for g in (1.5, -1.5):
        el = [Vortex(Gamma=g, x0=c.real, y0=c.imag)]
        add(f"Vortex, Γ = {g:g}", "circulation ∮V·ds", g, circulation_around_circle(el, c, 1.0), "circulation")
        z, _ = circle_points(c, 1.0, 8)
        add(f"Vortex, Γ = {g:g}", "V_θ at r = 1", g / (2 * np.pi), float(polar_components(el, z, c)[1][0]),
            "V_θ vortex")

    # 3) Cylinder -------------------------------------------------------------------------
    V, A, rho = 1.0, 1.0, 1.225
    cyl = [Uniform(V=V), Doublet(mu=V * A**2)]
    th = np.radians(90.0)
    z = A * np.exp(1j * th)
    vr, vt = polar_components(cyl, z)
    add("Cylinder (U + doublet)", "V_r on r = a", 0.0, float(vr), "cylinder")
    add("Cylinder (U + doublet)", "V_θ at θ = 90°", -2 * V, float(vt), "cylinder")
    u, v = velocity(cyl, z.real, z.imag)
    add("Cylinder (U + doublet)", "Cp at θ = 90°", -3.0, float(1 - (u**2 + v**2) / V**2), "cylinder")
    u, v = velocity(cyl, A, 0.0)
    add("Cylinder (U + doublet)", "|V| at θ = 0 (stag.)", 0.0, float(np.hypot(u, v)), "cylinder")
    L, D = surface_forces(cyl, 0j, A, rho)
    add("Cylinder (U + doublet)", "L' (d'Alembert)", 0.0, L, "dalembert")
    add("Cylinder (U + doublet)", "D' (d'Alembert)", 0.0, D, "dalembert")

    G = 2.0                                     # clockwise circulation (course example)
    lcyl = cyl + [Vortex(Gamma=-G)]
    s = -G / (4 * np.pi * V * A)
    ts = np.arcsin(s)
    u, v = velocity(lcyl, A * np.cos(ts), A * np.sin(ts))
    add("Lifting cylinder, Γ_cw = 2", "|V| at sinθ = −Γ/(4πVa)", 0.0, float(np.hypot(u, v)), "lifting stag")
    L, D = surface_forces(lcyl, 0j, A, rho)
    add("Lifting cylinder, Γ_cw = 2", "L' = ρ V∞ Γ", rho * V * G, L, "kutta")
    add("Lifting cylinder, Γ_cw = 2", "D'", 0.0, D, "kutta")

    # 4) Symmetry walls (method of images) ---------------------------------------------------
    wall = SymmetryWall(xw=0.0, yw=-1.0, theta_w=0.0)
    scene = [wall, Uniform(V=1.0), Source(m=1.0, x0=-1.0, y0=0.5), Vortex(Gamma=1.5, x0=1.0),
             Doublet(mu=0.5, x0=0.0, y0=1.0, delta=30.0)]
    add("Wall y = −1, mixed scene", "max |V·n| on wall (801 pts)", 0.0, _max_vn(scene, wall), "wall")
    tilted = SymmetryWall(xw=0.5, yw=-0.5, theta_w=35.0)
    scene = [tilted, Uniform(V=1.0, alpha=35.0), Source(m=1.0, x0=0.0, y0=1.0), Vortex(Gamma=-1.0, x0=1.0, y0=2.0)]
    add("Wall θ_w = 35°, mixed scene", "max |V·n| on wall", 0.0, _max_vn(scene, tilted), "wall")
    G, hh = 1.0, 0.8
    u, v = velocity([SymmetryWall(yw=0.0), Vortex(Gamma=G, y0=hh)], 0.0, 0.0)
    add("Vortex Γ = 1 at h = 0.8 above wall", "u on wall below vortex", G / (np.pi * hh), float(u), "vortex wall")
    m_, hh = 1.0, 0.8
    u, v = velocity([SymmetryWall(yw=0.0), Source(m=m_, y0=hh)], hh, 0.0)
    add("Source m = 1 at h = 0.8 above wall", "u on wall at x = h", m_ / (2 * np.pi * hh), float(u), "source wall")
    a_, b_ = SymmetryWall(yw=0.0, side=0), SymmetryWall(theta_w=90.0, side=1)
    corner = [a_, b_, Source(m=1.0, x0=1.0, y0=1.0)]
    add("90° corner + source (3 images)", "max |V·n| on both walls", 0.0,
        max(_max_vn(corner, a_), _max_vn(corner, b_)), "corner")
    ca, cb = SymmetryWall(yw=0.0, side=0), SymmetryWall(yw=2.0, side=1)
    channel = [ca, cb, Source(m=1.0, y0=0.7)]
    add("Channel H = 2 + source (∞ images)", "max |V·n| on both walls", 0.0,
        max(_max_vn(channel, ca, half=30), _max_vn(channel, cb, half=30)), "channel")
    u, v = velocity(channel, 80.0, 1.0)
    add("Channel H = 2 + source (∞ images)", "u far downstream = m/(2H)", 0.25, float(u), "channel")

    # 5) Sector (wedge) flow ------------------------------------------------------------------
    sec = SectorFlow(V=1.0, theta1=0.0, theta2=90.0)
    u, v = velocity([sec], 1.5, 0.5)
    add("Sector β = 90° (n = 2), V = 1", "u = 2Vx at (1.5, 0.5)", 3.0, float(u), "sector")
    add("Sector β = 90° (n = 2), V = 1", "v = −2Vy at (1.5, 0.5)", -1.0, float(v), "sector")
    for beta in (30.0, 270.0):
        s_ = SectorFlow(V=1.0, x0=0.5, y0=-0.5, theta1=20.0, theta2=20.0 + beta)
        z = s_.z0 + np.linspace(0.05, 4.0, 200) * np.exp(1j * np.radians(20.0 + beta))
        F_ = complex_potential([s_], z)
        add(f"Sector β = {beta:.0f}° (n = {180 / beta:.4g})", "max |ψ| / max |F| on 2nd wall", 0.0,
            float(np.max(np.abs(F_.imag)) / np.max(np.abs(F_))), "sector psi")
    r_ = 0.81
    s_ = SectorFlow(V=2.0, theta1=0.0, theta2=360.0)
    u, v = velocity([s_], r_ * np.cos(1.0), r_ * np.sin(1.0))
    add("Plate tip β = 360° (n = 1/2), V = 2", "|V| = (V/2) r^(−1/2), r = 0.81", 1.0 / np.sqrt(r_),
        float(np.hypot(u, v)), "plate tip")
    s_ = SectorFlow(V=1.0)
    both = [s_, Source(m=1.0, x0=1.0, y0=1.0)]
    worst = 0.0
    for ang in (0.0, 90.0):
        z = np.linspace(0.05, 6.0, 400) * np.exp(1j * np.radians(ang))
        uu, vv = velocity(both, z.real, z.imag)
        worst = max(worst, float(np.max(np.abs(((uu + 1j * vv) * np.conj(1j * np.exp(1j * np.radians(ang)))).real))))
    add("Sector β = 90° + source (3 images)", "max |V·n| on both walls", 0.0, worst, "sector source")
    return rows


def format_table(checks: list[Check]) -> str:
    """The checks as a plain-text table with a summary line."""
    w = [34, 28, 12, 22, 10]
    head = ["Case", "Quantity", "Analytic", "Numerical", "|Error|"]
    out = ["  ".join(h.ljust(n) for h, n in zip(head, w)), "-" * (sum(w) + 8)]
    for c in checks:
        out.append(f"{c.case:<34}  {c.quantity:<28}  {c.analytic:>12.6f}  {c.numerical:>22.15f}  {c.error:>10.1e}")
    worst = max(c.error for c in checks)
    out.append("-" * (sum(w) + 8))
    out.append(f"{len(checks)} comparisons, largest error = {worst:.1e}  ->  "
               f"{'OK' if all(c.ok for c in checks) else 'CHECK!'}")
    return "\n".join(out)
