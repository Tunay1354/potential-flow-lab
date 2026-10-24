"""Doublet:  F(z) = μ e^{iδ} / (z − z0),   w = −μ e^{iδ} / (z − z0)².

Course notes: source m at −ε and sink −m at +ε, ε → 0 with μ = m ε / π  ->  F = μ / z  (δ = 0).
δ rotates the doublet axis. Uniform flow V∞ + doublet μ (δ = 0) gives a cylinder of radius a = √(μ / V∞)."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ..base import FlowElement, Issue, ParamSpec, as_complex_array, normalize_angle, stable_cot
from ..registry import register


@register
@dataclass(kw_only=True)
class Doublet(FlowElement):
    TYPE = "doublet"
    NAME = "Doublet"
    PARAMS = (
        ParamSpec("mu", "μ", "Strength", "m³/s", default=1.0),
        ParamSpec("x0", "x₀", "Position x", "m", default=0.0),
        ParamSpec("y0", "y₀", "Position y", "m", default=0.0),
        ParamSpec("delta", "δ", "Orientation", "°", default=0.0, minimum=-360.0, maximum=360.0,
                  is_angle=True),
    )

    mu: float = 1.0
    x0: float = 0.0
    y0: float = 0.0
    delta: float = 0.0          # degrees

    @property
    def z0(self) -> complex:
        return complex(self.x0, self.y0)

    def _c(self) -> complex:
        return self.mu * np.exp(1j * math.radians(self.delta))

    def complex_velocity(self, z):
        with np.errstate(divide="ignore", invalid="ignore"):
            return -self._c() / (as_complex_array(z) - self.z0) ** 2

    def complex_potential(self, z):
        with np.errstate(divide="ignore", invalid="ignore"):
            return self._c() / (as_complex_array(z) - self.z0)

    def singular_points(self):
        return [self.z0]

    def mirrored(self, wall):
        """Image in a wall: same μ at the mirror point, axis mirrored: δ* = 2θ_w − δ."""
        z = complex(wall.reflect(self.z0))
        return Doublet(mu=self.mu, x0=z.real, y0=z.imag, delta=normalize_angle(2.0 * wall.theta_w - self.delta))

    def periodic_complex_velocity(self, z, period):
        """Σ −c/(z − z0 − nP)² = −c (π/P)² csc²(π(z − z0)/P),   csc² = 1 + cot²."""
        u = np.pi * (as_complex_array(z) - self.z0) / period
        return -self._c() * (np.pi / period) ** 2 * (1.0 + stable_cot(u) ** 2)

    def periodic_complex_potential(self, z, period):
        u = np.pi * (as_complex_array(z) - self.z0) / period
        return self._c() * (np.pi / period) * stable_cot(u)

    @classmethod
    def batch_complex_velocity(cls, elements, z):
        z = as_complex_array(z)
        z0 = np.array([e.z0 for e in elements])
        c = np.array([e._c() for e in elements])
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.sum(-c / (z[..., None] - z0) ** 2, axis=-1)

    def check(self):
        issues = super().check()
        if self.mu == 0:
            issues.append(Issue("warning", "μ = 0: this element has no effect."))
        return issues
