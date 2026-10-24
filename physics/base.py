"""
base.py — common base class for every flow element.

Notation (course notes):
    z = x + i y,   F(z) = phi + i psi   (complex potential)
    w = dF/dz = u - i v                 (complex velocity)

Every element only has to say what its w(z) is. Superposition (adding the
elements together) is done in field.py, so a new element type never needs
to touch any other file except its own (plus one import line in elements/__init__.py).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, fields
from typing import ClassVar

import numpy as np


@dataclass(frozen=True)
class ParamSpec:
    """Describes one user-editable parameter (used by the GUI dialog and by validation)."""
    key: str                    # attribute name in the element class
    symbol: str                 # symbol in the notes, e.g. "m", "Γ"
    name: str                   # long name, e.g. "Strength"
    unit: str = ""
    default: float = 0.0
    minimum: float = -math.inf
    maximum: float = math.inf
    is_angle: bool = False      # stored in degrees


@dataclass(frozen=True)
class Issue:
    """A problem found when checking an element. severity: 'error' or 'warning'."""
    severity: str
    message: str

    @property
    def is_error(self) -> bool:
        return self.severity == "error"


@dataclass(kw_only=True)
class FlowElement:
    """Base class. Subclasses are dataclasses whose fields are the element parameters."""

    TYPE: ClassVar[str] = ""                      # unique key used in saved files, e.g. "source"
    NAME: ClassVar[str] = ""                      # human readable, e.g. "Source / sink"
    PARAMS: ClassVar[tuple[ParamSpec, ...]] = ()

    enabled: bool = True                          # unticked in the list -> ignored in the sum

    # ------------------------------------------------------------------ physics
    def complex_velocity(self, z: np.ndarray) -> np.ndarray:
        """w(z) = u - i v. Must accept a complex numpy array of any shape."""
        raise NotImplementedError

    def complex_potential(self, z: np.ndarray) -> np.ndarray:
        """F(z) = phi + i psi. Note: log terms have a branch cut (psi or phi jumps by 2π·const)."""
        raise NotImplementedError

    def singular_points(self) -> list[complex]:
        """Points where the velocity is infinite (element centers). Empty for regular elements."""
        return []

    def freestream_velocity(self) -> complex | None:
        """u + i v at infinity contributed by this element (only the uniform flow has one)."""
        return None

    def fluid_region(self, z: np.ndarray) -> np.ndarray | None:
        """Boolean array, True where fluid exists according to this element.
        None = no restriction (default). Walls (fluid on one side) and sector flow
        (fluid only inside the wedge) override this."""
        return None

    # ------------------------------------------------------------------ checks
    def check(self) -> list[Issue]:
        """Generic checks from PARAMS (finite values, min/max). Subclasses add their own."""
        issues = []
        for p in self.PARAMS:
            val = getattr(self, p.key)
            if not math.isfinite(val):
                issues.append(Issue("error", f"{p.name} ({p.symbol}) must be a finite number."))
            elif val < p.minimum or val > p.maximum:
                if math.isinf(p.maximum):
                    rule = f"≥ {p.minimum:g}"
                elif math.isinf(p.minimum):
                    rule = f"≤ {p.maximum:g}"
                else:
                    rule = f"between {p.minimum:g} and {p.maximum:g}"
                issues.append(Issue("error", f"{p.name} ({p.symbol}) must be {rule}."))
        return issues

    def is_valid(self) -> bool:
        return not any(i.is_error for i in self.check())

    # ------------------------------------------------------------------ save / load
    def to_dict(self) -> dict:
        return {"type": self.TYPE, **asdict(self)}

    @classmethod
    def from_dict(cls, data: dict) -> "FlowElement":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in names})

    @classmethod
    def with_defaults(cls, **overrides) -> "FlowElement":
        """New element with the default value of every parameter (used by the 'Add' dialog)."""
        values = {p.key: p.default for p in cls.PARAMS}
        values.update(overrides)
        return cls(**values)

    # ------------------------------------------------------------------ display
    def summary(self) -> str:
        """Short text for the element list, e.g. 'm = 1, (0, 0)'."""
        parts = []
        keys = {p.key for p in self.PARAMS}
        for p in self.PARAMS:
            val = getattr(self, p.key)
            if p.key == "x0" and "y0" in keys:            # position shown as (x0, y0)
                parts.append(f"at ({_fmt(val)}, {_fmt(getattr(self, 'y0'))})")
            elif p.key == "y0" and "x0" in keys:
                continue
            else:
                parts.append(f"{p.symbol} = {_fmt(val)}{'°' if p.is_angle else ''}")
        return ",  ".join(parts)


def _fmt(x: float) -> str:
    return f"{x:.4g}"


def as_complex_array(z) -> np.ndarray:
    return np.asarray(z, dtype=np.complex128)
