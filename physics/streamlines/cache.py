"""
cache.py — the streamlines of the interactive plot (StreamlineCache): one field per spacing level
d = 2^−L, filled around the view, plus the stagnation points / dividing streamlines of the view.
"""
from __future__ import annotations

import math
from typing import Callable, Sequence

import numpy as np

from ..base import FlowElement
from ..field import active
from .common import Cancelled, StreamlineSet
from .level import StreamlineField, _inside, view_spacing


# ---------------------------------------------------------------------- several levels (the plot)
class StreamlineCache:
    """Streamlines of one scene for the interactive plot.

    * Line spacing comes in levels d = 2^−L. The level follows the zoom with some hysteresis, so a
      small zoom does not change the picture; within a level the lines never move.
    * Optionally (COARSE_LEVELS > 0) a level starts from all lines of the next coarser level and fills
      the gaps (multi-level Jobard–Lefer), so when the level changes, half of the lines stay.
    * update(view) fills the visible region first, then a margin around it (overscan), so panning
      shows lines that already exist.
    """
    LEVEL_HYSTERESIS = 0.65            # change level when the ideal level is this far away (in levels)
    OVERSCAN = 0.5                     # margin computed around the view, as a fraction of its size
    TRIGGER = 0.15                     # ... computed again when less than this margin is left
    # How many coarser levels a level is built from (0 = every level on its own). With > 0 zooming
    # in keeps the coarser lines in place, but those lines end where the COARSER spacing makes them
    # end, which leaves gaps in spreading flows (e.g. around a source) -> off for now.
    COARSE_LEVELS = 0
    MAX_DOMAIN_FACTOR = 40.0           # start again when a level grew this much larger than the view
    FEATURES_ZOOM = 2.5                # stagnation points searched again after zooming in this much

    def __init__(self, elements: Sequence[FlowElement], density: float = 1.0, use_kernel: bool = True):
        self.elements = list(elements)
        self.density = float(density)
        self.use_kernel = use_kernel
        self.fields: dict[int, StreamlineField] = {}
        self.level: int | None = None
        self.v_min: float | None = None
        self.features = None                       # stagnation points + dividing streamlines (FlowFeatures)
        self.features_scale = 0.0                  # size of the view they were searched for
        self._context = None                       # features of the whole scene (bodies), at its own scale
        self.with_features = True

    def _choose_level(self, view, current: int | None) -> int:
        (x0, x1), (y0, y1) = view
        ideal = -math.log2(view_spacing(self.elements, (x0, x1), (y0, y1), self.density))
        if current is None or abs(ideal - current) > self.LEVEL_HYSTERESIS:
            return int(round(ideal))
        return current

    def level_for(self, view) -> int:
        self.level = self._choose_level(view, self.level)
        return self.level

    def covers(self, view) -> bool:
        """True if the lines computed so far already fill `view` at the level it needs."""
        f = self.fields.get(self._choose_level(view, self.level))
        (x0, x1), (y0, y1) = view
        return f is not None and f.contains((x0, x1, y0, y1))

    def update(self, view, arrow_density: float = 1.0, cancelled: Callable[[], bool] | None = None,
               progress: Callable[[StreamlineSet], None] | None = None,
               force: bool = False, margin: bool = True) -> StreamlineSet | None:
        """Lines for `view` = ((x0, x1), (y0, y1)). Returns None if nothing changed since the last
        call (same level, view already filled) unless `force`. `progress` gets the picture once the
        visible part is done (before the margin around it); margin=False: the visible part only."""
        (x0, x1), (y0, y1) = map(lambda r: tuple(map(float, r)), view)
        if x1 <= x0 or y1 <= y0:
            return None
        previous = self.level
        L = self.level_for(((x0, x1), (y0, y1)))
        W, H = x1 - x0, y1 - y0
        o = self.OVERSCAN
        visible = (x0, x1, y0, y1)
        around = (x0 - o * W, x1 + o * W, y0 - o * H, y1 + o * H)
        f = self.fields.get(L)
        t = self.TRIGGER
        stale = self.with_features and self._features_stale(visible)
        if f is not None and f.contains((x0 - t * W, x1 + t * W, y0 - t * H, y1 + t * H)) and L == previous \
                and not stale:
            return self._with_features(f.result(arrow_density)) if force else None
        if f is not None and f.domain is not None:
            a0, a1, b0, b1 = f.domain
            grown = (max(a1, around[1]) - min(a0, around[0])) * (max(b1, around[3]) - min(b0, around[2]))
            if grown > self.MAX_DOMAIN_FACTOR * W * H:          # panned far away: start again
                self.fields.clear()
        changed = L != previous
        if stale:
            self._update_features(visible, cancelled)
            changed = True
        for region in (visible, around) if margin else (visible,):
            f = self.fields.get(L)
            if f is not None and f.contains(region):
                continue
            self._extend(L, region, 0, cancelled)
            changed = True
            if region is visible and progress is not None:
                progress(self._with_features(self.fields[L].result(arrow_density)))
        if not changed and not force:
            return None
        f = self.fields.get(L)
        res = f.result(arrow_density) if f is not None and f.domain is not None else StreamlineSet()
        return self._with_features(res)

    def _features_stale(self, visible) -> bool:
        """The stagnation points must be searched again: the view left their region, or it is much
        smaller than the view they were searched for (a point found only at a finer scale — next to a
        weak source, two points close together — would stay missing after a big zoom in)."""
        if self.features is None or not _inside(visible, self.features.region):
            return True
        x0, x1, y0, y1 = visible
        return max(x1 - x0, y1 - y0) < self.features_scale / self.FEATURES_ZOOM

    def _with_features(self, res: StreamlineSet) -> StreamlineSet:
        if self.features is not None:
            res.stagnation = list(self.features.points)
            res.dividing = list(self.features.dividing)
            res.dividing_owner = list(self.features.owners)
            res.inner = list(self.features.inner)
        if self._context:
            res.scene_dividing, res.scene_region = self._context.dividing, self._context.region
            res.scene_inner = self._context.inner
        return res

    def _update_features(self, visible, cancelled):
        """Stagnation points and dividing streamlines for 3× the view. A point on every dividing
        streamline (about one line spacing from its stagnation point) becomes a first seed of the
        streamline fields, so the regular lines are spaced from the dividing ones."""
        from ..stagnation import bodies_box, features_with_context, flow_features
        x0, x1, y0, y1 = visible
        W, H = x1 - x0, y1 - y0
        region = (x0 - W, x1 + W, y0 - H, y1 + H)
        if cancelled is not None and cancelled():
            raise Cancelled()
        box = bodies_box(active(self.elements))
        context = None
        if box is not None and not _inside(box, region):  # the bodies reach beyond the searched region
            if self._context is None:                     # the whole scene, once, at its own scale
                self._context = flow_features(self.elements, box, scale=max(box[1] - box[0], box[3] - box[2]))
            context = self._context
        self.features = features_with_context(self.elements, region, max(W, H), context)
        self.features_scale = max(W, H)
        d_view = view_spacing(self.elements, (x0, x1), (y0, y1), self.density)
        seeds = []
        stag = np.array([p.z for p in self.features.points], dtype=complex)
        for ln in self.features.dividing:
            z = ln[:, 0] + 1j * ln[:, 1]
            if stag.size and np.min(np.abs(stag - z[-1])) < np.min(np.abs(stag - z[0])):
                z = z[::-1]                              # measure from the stagnation point end
            s = np.concatenate([[0.0], np.cumsum(np.abs(np.diff(z)))])
            k = int(np.searchsorted(s, min(d_view, 0.5 * s[-1])))
            seeds.append(z[min(k, z.size - 1)])
        self._seeds = np.array(seeds, dtype=complex)
        for f in self.fields.values():                   # fields that exist get the new ones too
            f.special_seeds = _merge_seeds(f.special_seeds, self._seeds, 0.25 * f.d)

    def _extend(self, L, region, depth, cancelled):
        d = 2.0 ** -L
        x0, x1, y0, y1 = region
        use_coarse = depth < self.COARSE_LEVELS and 2.0 * d < max(x1 - x0, y1 - y0) / 6.0
        if use_coarse:
            self._extend(L - 1, region, depth + 1, cancelled)
        f = self.fields.get(L)
        if f is None:
            f = self.fields[L] = StreamlineField(self.elements, d, self.v_min, self.use_kernel)
            f.special_seeds = getattr(self, "_seeds", np.zeros(0, complex)).copy()
        if use_coarse and (L - 1) in self.fields:
            f.set_base(self.fields[L - 1].all_lines)
        f.extend(region, cancelled=cancelled)
        if self.v_min is None:
            self.v_min = f.v_min


def _merge_seeds(pending: np.ndarray, new: np.ndarray, tol: float) -> np.ndarray:
    """The pending seeds plus those new ones that are not (within tol) there yet: the features are
    found again whenever the view leaves their region, mostly with the same dividing streamlines, and
    the list would otherwise grow with every pan."""
    out = list(pending)
    for z in new:
        if not out or np.min(np.abs(np.asarray(out) - z)) > tol:
            out.append(z)
    return np.asarray(out, dtype=complex)
