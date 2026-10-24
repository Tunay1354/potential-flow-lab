"""Source / sink:  F(z) = (m / 2π) log(z − z0),   w = (m / 2π) / (z − z0).
m > 0 source, m < 0 sink.  V_r = m / (2π r)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..base import FlowElement, Issue, ParamSpec, as_complex_array, stable_cot, stable_log_sin
from ..registry import register


@register
@dataclass(kw_only=True)
class Source(FlowElement):
    TYPE = "source"
    NAME = "Source / sink"
    PARAMS = (
        ParamSpec("m", "m", "Strength", "m²/s", default=1.0),
        ParamSpec("x0", "x₀", "Position x", "m", default=0.0),
        ParamSpec("y0", "y₀", "Position y", "m", default=0.0),
    )

    m: float = 1.0
    x0: float = 0.0
    y0: float = 0.0

    @property
    def z0(self) -> complex:
        return complex(self.x0, self.y0)

    @property
    def is_sink(self) -> bool:
        return self.m < 0

    def complex_velocity(self, z):
        with np.errstate(divide="ignore", invalid="ignore"):
            return (self.m / (2.0 * np.pi)) / (as_complex_array(z) - self.z0)

    def complex_potential(self, z):
        with np.errstate(divide="ignore", invalid="ignore"):
            return (self.m / (2.0 * np.pi)) * np.log(as_complex_array(z) - self.z0)

    def singular_points(self):
        return [self.z0]

    def mirrored(self, wall):
        """Image in a wall: source of the SAME strength at the mirror point."""
        z = complex(wall.reflect(self.z0))
        return Source(m=self.m, x0=z.real, y0=z.imag)

    def periodic_complex_velocity(self, z, period):
        """Row of copies every P:  Σ 1/(z − z0 − nP) = (π/P) cot(π(z − z0)/P)."""
        u = np.pi * (as_complex_array(z) - self.z0) / period
        return self.m / (2.0 * np.pi) * (np.pi / period) * stable_cot(u)

    def periodic_complex_potential(self, z, period):
        u = np.pi * (as_complex_array(z) - self.z0) / period
        return self.m / (2.0 * np.pi) * stable_log_sin(u)

    @classmethod
    def batch_complex_velocity(cls, elements, z):
        z = as_complex_array(z)
        z0 = np.array([e.z0 for e in elements])
        c = np.array([e.m for e in elements]) / (2.0 * np.pi)
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.sum(c / (z[..., None] - z0), axis=-1)

    def check(self):
        issues = super().check()
        if self.m == 0:
            issues.append(Issue("warning", "m = 0: this element has no effect."))
        return issues
