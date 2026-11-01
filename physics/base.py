"""
base.py — common base class for every flow element.

Notation (course notes):
    z = x + i y,   F(z) = phi + i psi   (complex potential)
    w = dF/dz = u - i v                 (complex velocity)

Every element only has to say what its w(z) is. Superposition (adding the
elements together) is done in field.py, so a new element type never needs
to touch any other file except its own (plus one import line in elements/__init__.py).

Boundaries (symmetry walls) are also elements, but they produce no velocity
themselves: they make images of the flow elements (images.py) and restrict
the fluid region.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
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
    choices: tuple[str, ...] = ()   # non-empty -> the value is an index into this tuple


@dataclass(frozen=True)
class Issue:
    """Something found when checking a scene.
    severity: 'error'   -> physically inconsistent (e.g. element behind a wall)
              'warning' -> allowed but probably not intended (e.g. strength 0)
              'info'    -> just a note (e.g. two singular points at the same place, as in a lifting cylinder)"""
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
    IS_BOUNDARY: ClassVar[bool] = False           # True for walls: no velocity of its own
    POSITION_KEYS: ClassVar[tuple[str, str] | None] = ("x0", "y0")   # parameters that place the element

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

    def marker_points(self) -> list[complex]:
        """Points where the GUI draws this element's marker (default: its singular points)."""
        return self.singular_points()

    def crosses_boundary(self, za: np.ndarray, zb: np.ndarray) -> np.ndarray | None:
        """True where the straight step za -> zb crosses a boundary that has fluid on BOTH sides
        (e.g. a thin plate). None = no such boundary. Used by the streamline tracer."""
        return None

    def implied_walls(self) -> list | None:
        """Straight walls that belong to this element's own geometry (e.g. the two sides of a wedge).
        None  -> the element has no walls (default).
        list  -> the walls; other elements get images in them (images.py).
        []    -> the element has walls, but they cannot be written as half-planes (no exact images)."""
        return None

    def mirrored(self, wall) -> "FlowElement | None":
        """Image of this element in a straight wall (method of images).
        Return None if the element needs no image (e.g. a freestream parallel to the wall).
        Element types that cannot be mirrored keep this default and are reported as an error."""
        raise NotImplementedError(f"{self.NAME} cannot be mirrored in a wall")

    def periodic_complex_velocity(self, z: np.ndarray, period: complex) -> np.ndarray:
        """Σ_n w(z − n·P) over all integers n (infinite row of copies, period P).
        Needed for the images between two parallel walls; elements that cannot do it keep this default."""
        raise NotImplementedError(f"{self.NAME} cannot be placed between parallel walls")

    def periodic_complex_potential(self, z: np.ndarray, period: complex) -> np.ndarray:
        raise NotImplementedError(f"{self.NAME} cannot be placed between parallel walls")

    # ------------------------------------------------------------------ compiled kernel (kernel.py)
    def kernel_terms(self) -> list[tuple] | None:
        """This element's velocity as terms of the compiled kernel (fast streamlines):
            ("const", w)                     w
            ("pole1", z0, c)                 c / (z − z0)
            ("pole2", z0, c)                 −c / (z − z0)²
            ("sector", z0, rot, half, n, V)  n V rot ζ^(n−1),  ζ = (z − z0)·rot  (see sector.py)
        None = not expressible -> the slower NumPy path is used for scenes with this element."""
        return None

    def kernel_region(self) -> tuple | None:
        """Fluid region for the kernel: ("halfplane", point, normal) or ("wedge", z0, rot, half, beta).
        None = no restriction. Elements that override fluid_region must override this too."""
        return None

    @classmethod
    def batch_complex_velocity(cls, elements: list, z: np.ndarray) -> np.ndarray:
        """Σ w_k(z) for several elements of THIS type. Subclasses may vectorise it
        (important when walls create many images); the default simply loops."""
        z = as_complex_array(z)
        w = np.zeros(z.shape, dtype=np.complex128)
        for e in elements:
            w += e.complex_velocity(z)
        return w

    # ------------------------------------------------------------------ checks
    def check(self) -> list[Issue]:
        """Generic checks from PARAMS (finite values, min/max). Subclasses add their own."""
        issues = []
        for p in self.PARAMS:
            val = getattr(self, p.key)
            if p.choices:
                if not (isinstance(val, (int, np.integer)) or float(val).is_integer()) \
                        or not 0 <= int(val) < len(p.choices):
                    issues.append(Issue("error", f"{p.name}: invalid choice {val!r}."))
                continue
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

    # ------------------------------------------------------------------ copies
    def to_dict(self) -> dict:
        """Type and every field (a comparable key of the element; scene files: model/scene_file.py)."""
        return {"type": self.TYPE, **asdict(self)}

    def copy(self, **changes) -> "FlowElement":
        """New element with some parameters changed (elements are never modified in place)."""
        return replace(self, **changes)

    def translated(self, dx: float, dy: float) -> "FlowElement":
        """Copy moved by (dx, dy). Elements without a position (uniform flow) are returned unchanged."""
        if not self.POSITION_KEYS:
            return self.copy()
        kx, ky = self.POSITION_KEYS
        return self.copy(**{kx: getattr(self, kx) + dx, ky: getattr(self, ky) + dy})

    # ------------------------------------------------------------------ display
    def summary(self) -> str:
        """Short text for the element list, e.g. 'm = 1, (0, 0)'."""
        parts = []
        keys = {p.key for p in self.PARAMS}
        for p in self.PARAMS:
            val = getattr(self, p.key)
            if p.key == "x0" and "y0" in keys:            # position shown as (x0, y0)
                parts.append(f"at ({short_number(val)}, {short_number(getattr(self, 'y0'))})")
            elif p.key == "y0" and "x0" in keys:
                continue
            elif p.choices:
                parts.append(f"{p.name.lower()}: {p.choices[int(val)]}")
            else:
                parts.append(f"{p.symbol} = {short_number(val)}{'°' if p.is_angle else ''}")
        return ",  ".join(parts)


def short_number(x: float) -> str:
    """A number for the element list: 4 significant digits."""
    return f"{x:.4g}"


def as_complex_array(z) -> np.ndarray:
    return np.asarray(z, dtype=np.complex128)


def stable_cot(u: np.ndarray) -> np.ndarray:
    """cot(u) for complex u without overflow when |Im u| is large (cot -> ∓i)."""
    u = as_complex_array(u)
    up = u.imag > 0
    q = np.exp(np.where(up, 2j * u, -2j * u))          # |q| <= 1
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(up, 1j * (q + 1) / (q - 1), 1j * (1 + q) / (1 - q))


def stable_log_sin(u: np.ndarray) -> np.ndarray:
    """log(sin u) for complex u without overflow (up to multiples of 2πi)."""
    u = as_complex_array(u)
    up = u.imag > 0
    q = np.exp(np.where(up, 2j * u, -2j * u))
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(up, -1j * u + np.log((q - 1) / 2j), 1j * u + np.log((1 - q) / 2j))


def normalize_angle(deg: float) -> float:
    """Angle in degrees mapped to (−180°, 180°]."""
    a = math.fmod(deg, 360.0)
    if a <= -180.0:
        a += 360.0
    elif a > 180.0:
        a -= 360.0
    return a
