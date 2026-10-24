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

from physics import Doublet, Source, Uniform, Vortex, velocity  # noqa: E402
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

# print -------------------------------------------------------------------------------
w = [30, 26, 12, 22, 10]
head = ["Case", "Quantity", "Analytic", "Numerical", "|Error|"]
print("  ".join(h.ljust(n) for h, n in zip(head, w)))
print("-" * (sum(w) + 8))
for case, q, a, n, e in rows:
    print(f"{case:<30}  {q:<26}  {a:>12.6f}  {n:>22.15f}  {e:>10.1e}")
worst = max(r[4] for r in rows)
print("-" * (sum(w) + 8))
print(f"{len(rows)} comparisons, largest error = {worst:.1e}  ->  {'OK' if worst < 1e-9 else 'CHECK!'}")
