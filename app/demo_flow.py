"""
demo_flow.py — TEMPORARY. Only exists so the prototype shows a realistic picture.

Lifting cylinder from the course notes:
    F(z) = V∞ (z + a²/z) + i (Γ_cw / 2π) log(z/a)
In the program's convention (Γ > 0 ccw) this is a vortex with Γ = −Γ_cw.
The real physics engine (physics/ package) will replace this file.
"""
import numpy as np

V_INF = 1.0
A = 1.0
GAMMA_CW = 2.0          # clockwise circulation -> lift upwards


def velocity(x, y):
    z = np.asarray(x, dtype=float) + 1j * np.asarray(y, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        w = V_INF * (1.0 - A**2 / z**2) + 1j * GAMMA_CW / (2.0 * np.pi * z)
    return w.real, -w.imag          # w = u - i v


def inside_body(x, y):
    return x * x + y * y < A * A


def trace_streamlines(x_range, y_range, n_seeds=27, ds=0.02, max_steps=1500):
    """Very simple RK4 tracer (arc-length parametrised). Returns list of (xs, ys)."""
    lines = []
    x_start = x_range[0] - 0.3
    for y0 in np.linspace(y_range[0] - 0.4, y_range[1] + 0.4, n_seeds):
        pts = [(x_start, y0)]
        x, y = x_start, y0

        def f(px, py):
            u, v = velocity(px, py)
            sp = np.hypot(u, v)
            return (u / sp, v / sp) if sp > 1e-6 else (0.0, 0.0)

        for _ in range(max_steps):
            k1 = f(x, y)
            k2 = f(x + 0.5 * ds * k1[0], y + 0.5 * ds * k1[1])
            k3 = f(x + 0.5 * ds * k2[0], y + 0.5 * ds * k2[1])
            k4 = f(x + ds * k3[0], y + ds * k3[1])
            dx = ds * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]) / 6
            dy = ds * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]) / 6
            if dx == 0 and dy == 0:
                break
            x, y = x + dx, y + dy
            if inside_body(x, y) or x > x_range[1] + 0.3 or abs(y) > max(abs(y_range[0]), abs(y_range[1])) + 1:
                break
            pts.append((x, y))
        if len(pts) > 5:
            arr = np.array(pts)
            lines.append((arr[:, 0], arr[:, 1]))
    return lines
