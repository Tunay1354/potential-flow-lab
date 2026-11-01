"""
diagnostics.py — measurements on a flow for the verification table (verification.py) and the tests:
polar velocity components, flux and circulation around a circle, pressure force on a circular body.

The integrals are taken on a circle of radius R around `center`, sampled uniformly in θ (for smooth
periodic integrands this is exact up to round-off). The elements are used as given: the images of
walls are not added here.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np

from .base import FlowElement
from .field import complex_velocity, reference_speed


def circle_points(center: complex, radius: float, n: int = 4096) -> tuple[np.ndarray, np.ndarray]:
    """Points on a circle and their angles θ (counter-clockwise, endpoint excluded)."""
    theta = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    return center + radius * np.exp(1j * theta), theta


def polar_components(elements: Sequence[FlowElement], z, center: complex = 0j):
    """(V_r, V_θ) relative to `center`:  w = e^{-iθ}(V_r − i V_θ)  ->  V_r − i V_θ = w e^{iθ}."""
    z = np.asarray(z, dtype=np.complex128)
    theta = np.angle(z - center)
    q = complex_velocity(elements, z) * np.exp(1j * theta)
    return q.real, -q.imag


def flux_through_circle(elements, center: complex, radius: float, n: int = 4096) -> float:
    """Volume flow rate per unit depth leaving the circle:  ∮ V·n ds  (equals m for a source inside)."""
    z, _ = circle_points(center, radius, n)
    v_r, _ = polar_components(elements, z, center)
    return float(np.mean(v_r) * 2.0 * np.pi * radius)


def circulation_around_circle(elements, center: complex, radius: float, n: int = 4096) -> float:
    """Γ = ∮ V·ds, counter-clockwise (equals Γ of a vortex inside, course convention)."""
    z, _ = circle_points(center, radius, n)
    _, v_t = polar_components(elements, z, center)
    return float(np.mean(v_t) * 2.0 * np.pi * radius)


def surface_forces(elements, center: complex, radius: float, rho: float = 1.0, n: int = 4096):
    """Force per unit span on a circular body by pressure integration:
        F' = −∮ (p − p∞) n ds,   p − p∞ = ½ ρ V∞² Cp = ½ ρ (V∞² − V²).
    Returns (lift, drag) relative to the freestream direction (lift = +90° from freestream)."""
    z, theta = circle_points(center, radius, n)
    w = complex_velocity(elements, z)
    v_inf = reference_speed(elements)
    if v_inf is None:
        raise ValueError("No uniform flow: lift and drag are undefined.")
    dp = 0.5 * rho * (v_inf ** 2 - np.abs(w) ** 2)
    ds = 2.0 * np.pi * radius / n
    fx = -np.sum(dp * np.cos(theta)) * ds
    fy = -np.sum(dp * np.sin(theta)) * ds
    # freestream direction
    fs = sum((e.freestream_velocity() or 0j) for e in elements if e.enabled)
    e_d = fs / abs(fs)                 # unit vector along freestream (drag)
    e_l = 1j * e_d                     # +90° (lift)
    force = complex(fx, fy)
    drag = (force * np.conj(e_d)).real
    lift = (force * np.conj(e_l)).real
    return float(lift), float(drag)
