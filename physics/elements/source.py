"""Source / sink:  F(z) = (m / 2π) log(z − z0),   w = (m / 2π) / (z − z0).
m > 0 source, m < 0 sink.  V_r = m / (2π r)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..base import FlowElement, Issue, ParamSpec, as_complex_array
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

    def check(self):
        issues = super().check()
        if self.m == 0:
            issues.append(Issue("warning", "m = 0: this element has no effect."))
        return issues
