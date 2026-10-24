"""Uniform flow:  F(z) = V∞ e^{-iα} z,   w = V∞ e^{-iα}   ->  u = V∞ cos α,  v = V∞ sin α."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ..base import FlowElement, Issue, ParamSpec, as_complex_array
from ..registry import register


@register
@dataclass(kw_only=True)
class Uniform(FlowElement):
    TYPE = "uniform"
    NAME = "Uniform flow"
    POSITION_KEYS = None
    PARAMS = (
        ParamSpec("V", "V∞", "Speed", "m/s", default=1.0, minimum=0.0),
        ParamSpec("alpha", "α", "Angle", "°", default=0.0, minimum=-360.0, maximum=360.0, is_angle=True),
    )

    V: float = 1.0
    alpha: float = 0.0          # degrees, measured counter-clockwise from +x

    def _w(self) -> complex:
        return self.V * np.exp(-1j * math.radians(self.alpha))

    def complex_velocity(self, z):
        z = as_complex_array(z)
        return np.full(z.shape, self._w(), dtype=np.complex128)

    def complex_potential(self, z):
        return self._w() * as_complex_array(z)

    def freestream_velocity(self) -> complex:
        return np.conj(self._w())             # u + i v

    def mirrored(self, wall):
        """A freestream is not imaged: it must be parallel to the wall (checked in images.py).
        (Applying the plane theorem to it would double its tangential part and cancel its normal part.)"""
        return None

    def check(self):
        issues = super().check()
        if self.V == 0:
            issues.append(Issue("warning", "V∞ = 0: this element has no effect."))
        return issues
