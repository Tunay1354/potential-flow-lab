"""
rasters.py — "how far is the nearest line?" looked up in rasters (cell size d/4): every line is
stamped with a disk of radius STOP_RATIO·d (stop test) and SEED_RATIO·d (seed test).
"""
from __future__ import annotations

import math

import numpy as np

from .. import kernel
from .common import _c128


class _Raster:
    """Boolean raster over a region: 'is there a line within radius r?'"""

    def __init__(self, x0, y0, W, H, cell):
        self.x0, self.y0, self.c = x0, y0, cell
        self.nx, self.ny = max(1, math.ceil(W / cell)), max(1, math.ceil(H / cell))
        self.a = np.zeros((self.ny, self.nx), dtype=bool)

    def index(self, z):
        ix = np.clip(((z.real - self.x0) / self.c).astype(int), 0, self.nx - 1)
        iy = np.clip(((z.imag - self.y0) / self.c).astype(int), 0, self.ny - 1)
        return iy, ix

    def _disk(self, z, radius):
        r = int(math.ceil(radius / self.c))
        oy, ox = np.mgrid[-r:r + 1, -r:r + 1]
        keep = (ox**2 + oy**2) * self.c**2 <= radius**2
        oy, ox = oy[keep], ox[keep]
        iy, ix = self.index(z)
        yy = np.clip(iy[:, None] + oy[None, :], 0, self.ny - 1)
        xx = np.clip(ix[:, None] + ox[None, :], 0, self.nx - 1)
        return yy, xx

    def test(self, z):
        if kernel.HAVE_NUMBA:
            return kernel.raster_test(self.a, _c128(z), self.x0, self.y0, self.c)
        iy, ix = self.index(z)
        return self.a[iy, ix]

    def stamp(self, z, radius):
        if kernel.HAVE_NUMBA:
            kernel.raster_stamp(self.a, _c128(z), float(radius), self.x0, self.y0, self.c)
            return
        yy, xx = self._disk(z, radius)
        self.a[yy, xx] = True


class _OwnerRaster(_Raster):
    """Stop raster that remembers WHICH lines are near a cell (two ids per cell, −1 = none), so a
    line that is being continued is not stopped by itself. Two slots are enough: a cell near two or
    more lines always holds at least one id that is not the testing line's own."""

    def __init__(self, x0, y0, W, H, cell):
        super().__init__(x0, y0, W, H, cell)
        self.a = np.full((2, self.ny, self.nx), -1, dtype=np.int32)

    def test(self, z, self_id=-1):
        if kernel.HAVE_NUMBA and np.ndim(self_id) == 0:
            return kernel.owner_test(self.a, _c128(z), int(self_id), self.x0, self.y0, self.c)
        iy, ix = self.index(z)
        r0, r1 = self.a[0, iy, ix], self.a[1, iy, ix]
        return ((r0 >= 0) & (r0 != self_id)) | ((r1 >= 0) & (r1 != self_id))

    def stamp(self, z, radius, owner=0):
        if kernel.HAVE_NUMBA:
            kernel.owner_stamp(self.a, _c128(z), float(radius), int(owner), self.x0, self.y0, self.c)
            return
        yy, xx = self._disk(z, radius)
        lin = np.unique(yy.ravel() * self.nx + xx.ravel())
        l0, l1 = self.a[0].reshape(-1), self.a[1].reshape(-1)        # views
        cur = l0[lin]
        l0[lin[cur == -1]] = owner
        l1[lin[(cur != -1) & (cur != owner)]] = owner
