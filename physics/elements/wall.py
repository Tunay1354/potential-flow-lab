"""Straight symmetry wall (impermeable, V·n = 0), enforced with the method of images.

The wall is the infinite straight line through z_w = x_w + i y_w with direction angle θ_w.
Fluid exists only on one side of it ("left" or "right" of the direction e^{iθ_w}).

Reflection of a point in the wall:
    z* = z_w + e^{2iθ_w} conj(z − z_w)

Milne-Thomson plane theorem: for flow elements F(z) on the fluid side,
    F_total(z) = F(z) + conj(F(z*))
makes the wall a streamline (ψ = const, so V·n = 0). Each element type turns this into an
image rule in its own `mirrored()` method; images.py applies them.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ..base import FlowElement, ParamSpec, short_number, as_complex_array
from ..registry import register

SIDES = ("left", "right")


@register
@dataclass(kw_only=True)
class SymmetryWall(FlowElement):
    TYPE = "wall"
    NAME = "Symmetry wall"
    IS_BOUNDARY = True
    POSITION_KEYS = ("xw", "yw")
    PARAMS = (
        ParamSpec("xw", "x_w", "Point on wall x", "m", default=0.0),
        ParamSpec("yw", "y_w", "Point on wall y", "m", default=-1.5),
        ParamSpec("theta_w", "θ_w", "Wall angle", "°", default=0.0, minimum=-360.0, maximum=360.0,
                  is_angle=True),
        ParamSpec("side", "", "Fluid side", default=0, minimum=0, maximum=1,
                  choices=("left of wall direction", "right of wall direction")),
    )

    xw: float = 0.0
    yw: float = -1.5
    theta_w: float = 0.0        # degrees
    side: int = 0               # 0: fluid on the left of e^{iθ_w}, 1: on the right

    # ------------------------------------------------------------------ geometry
    @property
    def point(self) -> complex:
        return complex(self.xw, self.yw)

    @property
    def direction(self) -> complex:
        """Unit vector along the wall."""
        return complex(math.cos(math.radians(self.theta_w)), math.sin(math.radians(self.theta_w)))

    @property
    def normal(self) -> complex:
        """Unit normal pointing INTO the fluid."""
        return self.direction * (1j if self.side == 0 else -1j)

    def signed_distance(self, z) -> np.ndarray:
        """Distance from the wall, positive on the fluid side."""
        z = as_complex_array(z)
        return ((z - self.point) * np.conj(self.normal)).real

    def reflect(self, z) -> np.ndarray:
        """Mirror image of point(s) z in the wall line."""
        z = as_complex_array(z)
        e2 = self.direction ** 2
        return self.point + e2 * np.conj(z - self.point)

    # ------------------------------------------------------------------ element interface
    def complex_velocity(self, z):
        return np.zeros(as_complex_array(z).shape, dtype=np.complex128)   # a wall has no velocity itself

    def complex_potential(self, z):
        return np.zeros(as_complex_array(z).shape, dtype=np.complex128)

    def kernel_terms(self):
        return []                                      # no velocity of its own

    def kernel_region(self):
        return ("halfplane", self.point, self.normal)

    def fluid_region(self, z):
        return self.signed_distance(z) >= 0.0          # points ON the wall count as fluid

    def mirrored(self, wall):
        return None                                    # walls are not imaged (see images.py)

    def summary(self) -> str:
        return f"through ({short_number(self.xw)}, {short_number(self.yw)}),  θ_w = {short_number(self.theta_w)}°,  fluid: {SIDES[int(self.side)]}"
