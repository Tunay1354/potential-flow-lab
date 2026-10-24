"""
geometry.py — plane geometry for DRAWING walls (no Qt, no physics changes; unit-tested).

The physics treats every wall as an infinite line. On screen, a wall is drawn only where it
borders the fluid: the part of a wall that lies on the solid side of another wall has no fluid
next to it, so two walls meeting at a corner look like an "L" (or a wedge of any angle).

Points are complex numbers x + iy. A wall is anything with `point`, `direction` (unit complex)
and `signed_distance(z)` (> 0 on the fluid side), e.g. physics.SymmetryWall.
"""
from __future__ import annotations

import numpy as np


def clip_polygon(poly, value):
    """Part of a convex polygon (list of complex) where value(z) >= 0 (Sutherland–Hodgman, one edge)."""
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        va, vb = value(a), value(b)
        if va >= 0:
            out.append(a)
        if (va >= 0) != (vb >= 0):
            out.append(a + (b - a) * va / (va - vb))
    return out


def rect_polygon(xr, yr):
    return [complex(xr[0], yr[0]), complex(xr[1], yr[0]), complex(xr[1], yr[1]), complex(xr[0], yr[1])]


def fluid_polygon(walls, xr, yr):
    """The fluid part of the view rectangle (intersection with every wall's fluid half-plane)."""
    poly = rect_polygon(xr, yr)
    for w in walls:
        poly = clip_polygon(poly, lambda z, w=w: float(w.signed_distance(z)))
        if len(poly) < 3:
            return []
    return poly


def visible_wall_segment(wall, other_walls, xr, yr, tol=1e-12):
    """End points (complex, complex) of the part of `wall` that is inside the view AND borders the
    fluid (on the fluid side of every other wall), or None if no part of it is visible."""
    p, d = wall.point, wall.direction
    t0, t1 = -np.inf, np.inf
    # 1) inside the view rectangle (slab method)
    for pc, dc, lo, hi in ((p.real, d.real, xr[0], xr[1]), (p.imag, d.imag, yr[0], yr[1])):
        if abs(dc) < 1e-15:
            if pc < lo or pc > hi:
                return None
            continue
        a, b = (lo - pc) / dc, (hi - pc) / dc
        t0, t1 = max(t0, min(a, b)), min(t1, max(a, b))
    # 2) on the fluid side of every other wall:  s(t) = s0 + t * ds >= 0
    for o in other_walls:
        s0 = float(o.signed_distance(p))
        ds = float(o.signed_distance(p + d)) - s0
        if abs(ds) < 1e-15:                     # parallel walls
            if s0 < -tol:
                return None                     # this wall is entirely behind the other one
            continue
        t_zero = -s0 / ds
        if ds > 0:
            t0 = max(t0, t_zero)
        else:
            t1 = min(t1, t_zero)
    if t0 >= t1:
        return None
    return p + t0 * d, p + t1 * d


def ray_in_rect(origin, direction, xr, yr):
    """Visible part (two complex end points) of the ray origin + t·direction, t >= 0, or None."""
    p, d = complex(origin), complex(direction)
    t0, t1 = 0.0, np.inf
    for pc, dc, lo, hi in ((p.real, d.real, xr[0], xr[1]), (p.imag, d.imag, yr[0], yr[1])):
        if abs(dc) < 1e-15:
            if pc < lo or pc > hi:
                return None
            continue
        a, b = (lo - pc) / dc, (hi - pc) / dc
        t0, t1 = max(t0, min(a, b)), min(t1, max(a, b))
    if t0 >= t1:
        return None
    return p + t0 * d, p + t1 * d


def sector_shading(sector, xr, yr):
    """How to shade the solid (non-fluid) part of a sector flow in the view.
    Returns ("cut", fluid_polygon)   -> shade the view minus this polygon   (β <= 180°, convex wedge)
            ("fill", solid_polygon)  -> shade this polygon                  (180° < β < 360°)
            ("none", [])             -> nothing to shade                    (β = 360°, a plate)"""
    from physics import SymmetryWall
    beta = sector.beta_deg
    if beta >= 360.0 - 1e-9:
        return "none", []
    if beta <= 180.0 + 1e-9:
        return "cut", fluid_polygon(sector.implied_walls(), xr, yr)
    # the solid region is the convex wedge from θ2 to θ1 + 360°: left of θ2 and right of θ1
    solid = [SymmetryWall(xw=sector.x0, yw=sector.y0, theta_w=sector.theta2, side=0),
             SymmetryWall(xw=sector.x0, yw=sector.y0, theta_w=sector.theta1, side=1)]
    return "fill", fluid_polygon(solid, xr, yr)
