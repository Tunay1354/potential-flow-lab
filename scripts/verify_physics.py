"""
verify_physics.py — prints a verification table (analytic vs numerical).
The same comparisons are checked automatically by `pytest`; this script shows the numbers
in a readable form for the report.

Run from the project folder:   python scripts/verify_physics.py
"""
import os
import sys

import numpy as np

if hasattr(sys.stdout, "reconfigure"):          # Γ, θ, ∮ on any Windows console / redirect
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from physics import Doublet, SectorFlow, Source, SymmetryWall, Uniform, Vortex, complex_potential, velocity  # noqa: E402
from physics.diagnostics import (circle_points, circulation_around_circle, flux_through_circle,  # noqa: E402
                                 polar_components, surface_forces)

rows = []


def add(case, quantity, analytic, numeric):
    rows.append((case, quantity, analytic, numeric, abs(numeric - analytic)))


# 1) Uniform flow ------------------------------------------------------------------
for alpha in (0.0, 45.0):
    u, v = velocity([Uniform(V=1.0, alpha=alpha)], 1.234, -0.567)
    a = np.radians(alpha)
    add(f"Uniform, α = {alpha:.0f}°", "u", np.cos(a), float(u))
    add(f"Uniform, α = {alpha:.0f}°", "v", np.sin(a), float(v))

# 2) Source, sink, vortex -------------------------------------------------------------
c = 0.5 + 0.5j
for m in (2.0, -2.0):
    name = "Source" if m > 0 else "Sink"
    el = [Source(m=m, x0=c.real, y0=c.imag)]
    add(f"{name}, m = {m:g}", "flux ∮V·n ds", m, flux_through_circle(el, c, 1.0))
    z, _ = circle_points(c, 1.0, 8)
    add(f"{name}, m = {m:g}", "V_r at r = 1", m / (2 * np.pi), float(polar_components(el, z, c)[0][0]))
for g in (1.5, -1.5):
    el = [Vortex(Gamma=g, x0=c.real, y0=c.imag)]
    add(f"Vortex, Γ = {g:g}", "circulation ∮V·ds", g, circulation_around_circle(el, c, 1.0))
    z, _ = circle_points(c, 1.0, 8)
    add(f"Vortex, Γ = {g:g}", "V_θ at r = 1", g / (2 * np.pi), float(polar_components(el, z, c)[1][0]))

# 3) Cylinder -------------------------------------------------------------------------
V, A, rho = 1.0, 1.0, 1.225
cyl = [Uniform(V=V), Doublet(mu=V * A**2)]
th = np.radians(90.0)
z = A * np.exp(1j * th)
vr, vt = polar_components(cyl, z)
add("Cylinder (U + doublet)", "V_r on r = a", 0.0, float(vr))
add("Cylinder (U + doublet)", "V_θ at θ = 90°", -2 * V, float(vt))
u, v = velocity(cyl, z.real, z.imag)
add("Cylinder (U + doublet)", "Cp at θ = 90°", -3.0, float(1 - (u**2 + v**2) / V**2))
u, v = velocity(cyl, A, 0.0)
add("Cylinder (U + doublet)", "|V| at θ = 0 (stag.)", 0.0, float(np.hypot(u, v)))
L, D = surface_forces(cyl, 0j, A, rho)
add("Cylinder (U + doublet)", "L' (d'Alembert)", 0.0, L)
add("Cylinder (U + doublet)", "D' (d'Alembert)", 0.0, D)

G = 2.0                                     # clockwise circulation (course example)
lcyl = cyl + [Vortex(Gamma=-G)]
s = -G / (4 * np.pi * V * A)
ts = np.arcsin(s)
u, v = velocity(lcyl, A * np.cos(ts), A * np.sin(ts))
add("Lifting cylinder, Γ_cw = 2", "|V| at sinθ = −Γ/(4πVa)", 0.0, float(np.hypot(u, v)))
L, D = surface_forces(lcyl, 0j, A, rho)
add("Lifting cylinder, Γ_cw = 2", "L' = ρ V∞ Γ", rho * V * G, L)
add("Lifting cylinder, Γ_cw = 2", "D'", 0.0, D)

# 4) Symmetry walls (method of images) ---------------------------------------------------
def max_vn(els, wall, half=8.0, n=801):
    t = np.linspace(-half, half, n)
    z = wall.point + t * wall.direction
    uu, vv = velocity(els, z.real, z.imag)
    return float(np.max(np.abs(((uu + 1j * vv) * np.conj(wall.normal)).real)))


wall = SymmetryWall(xw=0.0, yw=-1.0, theta_w=0.0)
scene = [wall, Uniform(V=1.0), Source(m=1.0, x0=-1.0, y0=0.5), Vortex(Gamma=1.5, x0=1.0),
         Doublet(mu=0.5, x0=0.0, y0=1.0, delta=30.0)]
add("Wall y = −1, mixed scene", "max |V·n| on wall (801 pts)", 0.0, max_vn(scene, wall))
tilted = SymmetryWall(xw=0.5, yw=-0.5, theta_w=35.0)
scene = [tilted, Uniform(V=1.0, alpha=35.0), Source(m=1.0, x0=0.0, y0=1.0), Vortex(Gamma=-1.0, x0=1.0, y0=2.0)]
add("Wall θ_w = 35°, mixed scene", "max |V·n| on wall", 0.0, max_vn(scene, tilted))
G, hh = 1.0, 0.8
u, v = velocity([SymmetryWall(yw=0.0), Vortex(Gamma=G, y0=hh)], 0.0, 0.0)
add("Vortex Γ = 1 at h = 0.8 above wall", "u on wall below vortex", G / (np.pi * hh), float(u))
m_, hh = 1.0, 0.8
u, v = velocity([SymmetryWall(yw=0.0), Source(m=m_, y0=hh)], hh, 0.0)
add("Source m = 1 at h = 0.8 above wall", "u on wall at x = h", m_ / (2 * np.pi * hh), float(u))
a_, b_ = SymmetryWall(yw=0.0, side=0), SymmetryWall(theta_w=90.0, side=1)
corner = [a_, b_, Source(m=1.0, x0=1.0, y0=1.0)]
add("90° corner + source (3 images)", "max |V·n| on both walls", 0.0, max(max_vn(corner, a_), max_vn(corner, b_)))
ca, cb = SymmetryWall(yw=0.0, side=0), SymmetryWall(yw=2.0, side=1)
channel = [ca, cb, Source(m=1.0, y0=0.7)]
add("Channel H = 2 + source (∞ images)", "max |V·n| on both walls", 0.0,
    max(max_vn(channel, ca, half=30), max_vn(channel, cb, half=30)))
u, v = velocity(channel, 80.0, 1.0)
add("Channel H = 2 + source (∞ images)", "u far downstream = m/(2H)", 0.25, float(u))

# 5) Sector (wedge) flow ------------------------------------------------------------------
sec = SectorFlow(V=1.0, theta1=0.0, theta2=90.0)
u, v = velocity([sec], 1.5, 0.5)
add("Sector β = 90° (n = 2), V = 1", "u = 2Vx at (1.5, 0.5)", 3.0, float(u))
add("Sector β = 90° (n = 2), V = 1", "v = −2Vy at (1.5, 0.5)", -1.0, float(v))
for beta in (30.0, 270.0):
    s_ = SectorFlow(V=1.0, x0=0.5, y0=-0.5, theta1=20.0, theta2=20.0 + beta)
    z = s_.z0 + np.linspace(0.05, 4.0, 200) * np.exp(1j * np.radians(20.0 + beta))
    F_ = complex_potential([s_], z)
    add(f"Sector β = {beta:.0f}° (n = {180 / beta:.4g})", "max |ψ| / max |F| on 2nd wall", 0.0,
        float(np.max(np.abs(F_.imag)) / np.max(np.abs(F_))))
r_ = 0.81
s_ = SectorFlow(V=2.0, theta1=0.0, theta2=360.0)
u, v = velocity([s_], r_ * np.cos(1.0), r_ * np.sin(1.0))
add("Plate tip β = 360° (n = 1/2), V = 2", "|V| = (V/2) r^(−1/2), r = 0.81", 1.0 / np.sqrt(r_), float(np.hypot(u, v)))
s_ = SectorFlow(V=1.0)
both = [s_, Source(m=1.0, x0=1.0, y0=1.0)]
worst = 0.0
for ang in (0.0, 90.0):
    z = np.linspace(0.05, 6.0, 400) * np.exp(1j * np.radians(ang))
    uu, vv = velocity(both, z.real, z.imag)
    worst = max(worst, float(np.max(np.abs(((uu + 1j * vv) * np.conj(1j * np.exp(1j * np.radians(ang)))).real))))
add("Sector β = 90° + source (3 images)", "max |V·n| on both walls", 0.0, worst)

# print -------------------------------------------------------------------------------
w = [34, 28, 12, 22, 10]
head = ["Case", "Quantity", "Analytic", "Numerical", "|Error|"]
print("  ".join(h.ljust(n) for h, n in zip(head, w)))
print("-" * (sum(w) + 8))
for case, q, a, n, e in rows:
    print(f"{case:<34}  {q:<28}  {a:>12.6f}  {n:>22.15f}  {e:>10.1e}")
worst = max(r[4] for r in rows)
print("-" * (sum(w) + 8))
print(f"{len(rows)} comparisons, largest error = {worst:.1e}  ->  {'OK' if worst < 1e-9 else 'CHECK!'}")
