"""Sector (wedge) flow — course notes, item 7, generalised to any vertex and orientation.

    ζ = (z − z0) e^{−iθ1} = r e^{iθ'}           (local coordinates: first wall along θ' = 0)
    F(z) = V ζ^n,   n = π / β,   β = θ2 − θ1     (opening angle, measured counter-clockwise)

    w = dF/dz = n V e^{−iθ1} ζ^{n−1}
    V_r = n V r^{n−1} cos(nθ'),   V_θ = −n V r^{n−1} sin(nθ')
    ψ = V r^n sin(nθ') = 0  on  θ' = 0  and  θ' = β   (both walls are streamlines)

The flow is defined ONLY inside the wedge 0 ≤ θ' ≤ β (the fluid region).

Branch: ζ^n is multi-valued when n is not an integer. θ' is taken in (β/2 − π, β/2 + π], so the
branch cut lies on the bisector of the region OUTSIDE the wedge; the velocity is continuous along
and across both walls. For β = 360° (flow around the tip of a semi-infinite plate) the cut is the
plate itself, which is a wall with fluid on both sides; `crosses_boundary` stops streamlines there.

Direction: V > 0 -> fluid comes in along the θ2 wall and leaves along the θ1 wall
(e.g. β = 90°, θ1 = 0: F = Vz², u = 2Vx, v = −2Vy). V < 0 reverses the flow.

β is wrapped into (0°, 360°]: θ1 = 300°, θ2 = 30° gives β = 90°; θ1 = θ2 gives β = 360° (plate).
Special values: β = 180° -> n = 1, uniform flow along a straight wall;  β > 180° -> n < 1, the
velocity is infinite at the vertex (flow around a convex corner).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ..base import FlowElement, Issue, ParamSpec, as_complex_array
from ..registry import register
from .wall import SymmetryWall

ANGLE_TOL = 1e-9          # rad, points this close to a wall count as inside


@register
@dataclass(kw_only=True)
class SectorFlow(FlowElement):
    TYPE = "sector"
    NAME = "Sector (wedge) flow"
    PARAMS = (
        ParamSpec("V", "V", "Strength constant", "", default=1.0),
        ParamSpec("x0", "x₀", "Vertex x", "m", default=0.0),
        ParamSpec("y0", "y₀", "Vertex y", "m", default=0.0),
        ParamSpec("theta1", "θ₁", "First wall angle", "°", default=0.0, minimum=-360.0, maximum=360.0,
                  is_angle=True),
        ParamSpec("theta2", "θ₂", "Second wall angle", "°", default=90.0, minimum=-360.0, maximum=360.0,
                  is_angle=True),
    )

    V: float = 1.0
    x0: float = 0.0
    y0: float = 0.0
    theta1: float = 0.0          # degrees
    theta2: float = 90.0         # degrees

    # ------------------------------------------------------------------ geometry
    @property
    def z0(self) -> complex:
        return complex(self.x0, self.y0)

    @property
    def beta_deg(self) -> float:
        """Opening angle in degrees, counter-clockwise from θ1 to θ2, in (0, 360]."""
        b = math.fmod(self.theta2 - self.theta1, 360.0)
        if b < 0:
            b += 360.0
        if b <= 1e-9:
            b += 360.0
        return b

    @property
    def beta(self) -> float:
        return math.radians(self.beta_deg)

    @property
    def n(self) -> float:
        return math.pi / self.beta

    def _rot(self) -> complex:
        return complex(math.cos(math.radians(self.theta1)), -math.sin(math.radians(self.theta1)))  # e^{−iθ1}

    def local_angle(self, z) -> np.ndarray:
        """θ' in (β/2 − π, β/2 + π]: 0 on the first wall, β on the second, branch cut outside."""
        zeta = (as_complex_array(z) - self.z0) * self._rot()
        half = 0.5 * self.beta
        return np.angle(zeta * complex(math.cos(half), -math.sin(half))) + half

    def signed_distance(self, z) -> np.ndarray:
        """Distance to the wedge boundary (the two walls), positive inside the wedge."""
        z = as_complex_array(z)
        rel = z - self.z0
        dist = None
        for ang in (self.theta1, self.theta2):
            d = complex(math.cos(math.radians(ang)), math.sin(math.radians(ang)))
            q = rel * np.conj(d)                       # along / across the wall ray
            dk = np.where(q.real >= 0, np.abs(q.imag), np.abs(rel))
            dist = dk if dist is None else np.minimum(dist, dk)
        th = self.local_angle(z)
        inside = (th >= -ANGLE_TOL) & (th <= self.beta + ANGLE_TOL)
        return np.where(inside, dist, -dist)

    # ------------------------------------------------------------------ element interface
    def complex_velocity(self, z):
        z = as_complex_array(z)
        zeta = (z - self.z0) * self._rot()
        r = np.abs(zeta)
        th = self.local_angle(z)
        n = self.n
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            return n * self.V * self._rot() * r ** (n - 1.0) * np.exp(1j * (n - 1.0) * th)

    def complex_potential(self, z):
        z = as_complex_array(z)
        r = np.abs((z - self.z0) * self._rot())
        th = self.local_angle(z)
        n = self.n
        return self.V * r ** n * np.exp(1j * n * th)

    def singular_points(self):
        """For β > 180° (n < 1) the velocity ~ r^{n−1} is infinite at the vertex."""
        return [self.z0] if self.n < 1.0 - 1e-12 else []

    def marker_points(self):
        return [self.z0]

    def fluid_region(self, z):
        th = self.local_angle(z)
        return (th >= -ANGLE_TOL) & (th <= self.beta + ANGLE_TOL)

    def crosses_boundary(self, za, zb):
        """A step crossing the branch cut changes θ' by about 2π (inside the fluid θ' is continuous)."""
        return np.abs(self.local_angle(zb) - self.local_angle(za)) > math.pi

    def implied_walls(self):
        """The wedge sides as walls. For β ≤ 180° the wedge is the intersection of two half-planes:
        left of the θ1 direction and right of the θ2 direction. For β > 180° it is not: []."""
        b = self.beta_deg
        if b > 180.0 + 1e-9:
            return []
        w1 = SymmetryWall(xw=self.x0, yw=self.y0, theta_w=self.theta1, side=0)
        if abs(b - 180.0) <= 1e-9:
            return [w1]                                   # both sides lie on one straight wall
        return [w1, SymmetryWall(xw=self.x0, yw=self.y0, theta_w=self.theta2, side=1)]

    def mirrored(self, wall):
        """Not imaged: the sector flow already satisfies its own walls (imaging it would double it)."""
        return None

    def check(self):
        issues = super().check()
        if self.V == 0:
            issues.append(Issue("warning", "V = 0: this element has no effect."))
        return issues

    def summary(self) -> str:
        return (f"V = {self.V:.4g},  vertex ({self.x0:.4g}, {self.y0:.4g}),  θ₁ = {self.theta1:.4g}°,  "
                f"θ₂ = {self.theta2:.4g}°  (β = {self.beta_deg:.4g}°, n = {self.n:.4g})")
