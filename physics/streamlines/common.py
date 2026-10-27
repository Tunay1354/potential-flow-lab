"""
common.py — the parameters of the streamline engine and the data it hands out (StreamlineSet).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import itertools

import numpy as np


BASE_LINES_ACROSS = 26          # ~ number of line spacings across the view at density 1
STOP_RATIO = 0.4                # a line stops at STOP_RATIO·d from another line
SEED_RATIO = 0.9                # a seed must be at least SEED_RATIO·d from every line
MIN_LENGTH_RATIO = 2.0          # lines shorter than this many d (+ fading ends) are not drawn
TAPER_RATIO = 1.5               # length (in d) over which a cut line end fades out (used by the plot)
MAX_TURN_COS = 0.7              # turning more than ~45° in one step = stagnation (saddle) point
FADE_LEVELS = 4                 # number of opacity steps in a fading line end
ARROW_SPACING_RATIO = 6.5       # distance between arrows (in d) at arrow density 1
BOX_MARGIN_RATIO = 0.6          # lines may run this many d beyond the region before they stop
BATCH_SIZE = 32

WALL_ID = 2 ** 30               # owner id of walls in the stop raster (never equal to a line id)
_line_ids = itertools.count()   # every line ever created gets its own id


class Cancelled(Exception):
    """Raised inside the computation when the `cancelled` callback returns True."""


@dataclass
class StreamlineSet:
    lines: list[np.ndarray] = field(default_factory=list)          # each (N, 2), ordered in flow direction
    arrows: list[tuple[float, float, float]] = field(default_factory=list)   # (x, y, angle_rad)
    tapers: list[tuple[bool, bool]] = field(default_factory=list)  # per line: (start cut, end cut)
    separation: float = 0.0                                        # line spacing d used
    domain: tuple[float, float, float, float] | None = None        # region filled with lines (x0, x1, y0, y1)
    stagnation: list = field(default_factory=list)                 # StagnationPoint (stagnation.py)
    dividing: list[np.ndarray] = field(default_factory=list)       # dividing streamlines, (N, 2) each
    dividing_owner: list[int] = field(default_factory=list)        # index in `stagnation` of each one
    scene_dividing: list[np.ndarray] = field(default_factory=list) # the whole scene's, coarser (bodies)
    inner: list[np.ndarray] = field(default_factory=list)          # branches into bodies: not drawn,
    scene_inner: list[np.ndarray] = field(default_factory=list)    # … borders for the Solid bodies layer
    scene_region: tuple[float, float, float, float] | None = None  # … the region they were found in


@dataclass
class _Line:
    """A streamline: points ordered along the flow and why each end stops:
    "near" (came too close to another line -> fades out), "box" (left the computed region; may be
    continued later), "stop" (wall, singular point, stagnation point ...), "closed" (a loop)."""
    id: int
    pts: np.ndarray
    start: str
    end: str

    @property
    def taper(self) -> tuple[bool, bool]:
        return self.start == "near", self.end == "near"



def _c128(z) -> np.ndarray:
    return np.ascontiguousarray(np.atleast_1d(z), dtype=np.complex128)
