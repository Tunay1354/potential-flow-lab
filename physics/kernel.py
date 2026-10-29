"""
kernel.py — compiled (Numba) velocity field and streamline integrator.

The NumPy code in field.py / streamlines.py works on whole arrays; for tracing streamlines that
means thousands of small NumPy calls, which is slow and keeps Python's global interpreter lock
(GIL) busy, so the window stutters while a background thread computes. Here the same mathematics
is compiled to machine code with Numba:

  * the velocity is a sum of simple terms that every element describes in `kernel_terms()`
    (pole1 = source / vortex, pole2 = doublet, row1 / row2 = their infinite image rows in a
    channel, sector = wedge flow, const = uniform flow);
  * the fluid region is a list of half-planes (walls) and wedges (sector flow);
  * `trace_batch` integrates streamlines with exactly the rules of the NumPy tracer
    (RK4 on the unit direction field, same stop conditions), and releases the GIL (nogil).

If Numba is not installed, or a scene contains an element without kernel terms, `compile_scene`
returns None and streamlines.py uses its NumPy path. Set the environment variable
PFL_NO_NUMBA=1 to force the NumPy path (for comparison).

The first call compiles the functions (a few seconds); the machine code is cached on disk
(__pycache__), so later starts are fast.
"""
from __future__ import annotations

import cmath
import math
import os

import numpy as np

try:                                                  # pragma: no cover - depends on installation
    if os.environ.get("PFL_NO_NUMBA"):
        raise ImportError
    from numba import njit
    HAVE_NUMBA = True
except ImportError:                                   # pragma: no cover
    HAVE_NUMBA = False

    def njit(*args, **kwargs):
        if args and callable(args[0]):
            return args[0]
        return lambda f: f

ANGLE_TOL = 1e-9          # same as sector.py: points this close to a wedge side count as inside
JIT = dict(cache=True, nogil=True, error_model="numpy")   # numpy error model: 1/0 -> inf (no exception)
# short helpers (microseconds) keep the interpreter lock: releasing and taking it back would cost more
# than they do (the window thread may hold it for a while), see the Jobard–Lefer bookkeeping below
QUICK = dict(cache=True, nogil=False, error_model="numpy")

# ---------------------------------------------------------------------- scene -> arrays
# The scene is ONE table per purpose (a tuple of many small arrays would cost a reference-count update
# per array on every velocity evaluation — several times the arithmetic itself):
#   F  velocity terms (n, 6) complex, rows sorted by kind (the sum keeps the same order):
#        CONST  [kind, c]                     uniform flows (summed)
#        POLE1  [kind, z, c]                  c / (z − z_k)            source, vortex
#        POLE2  [kind, z, c]                  −c / (z − z_k)²          doublet
#        ROW1   [kind, z, c, P]               infinite image rows of poles in a channel (period P, complex)
#        ROW2   [kind, z, c, P]               ... of doublets
#        SECTOR [kind, z, rot, half, n, V]    wedge flow
#   R  fluid region (m, 6) complex: HALFPLANE [kind, p, normal], WEDGE [kind, z, rot, half, beta]
#   W  the wedges of R (a step must not cross their cut)
CONST, POLE1, POLE2, ROW1, ROW2, SECTOR = range(6)
HALFPLANE, WEDGE = 0, 1
_TERM_KINDS = {"const": CONST, "pole1": POLE1, "pole2": POLE2, "row1": ROW1, "row2": ROW2, "sector": SECTOR}


def _table(rows) -> np.ndarray:
    out = np.zeros((len(rows), 6), np.complex128)
    for i, r in enumerate(rows):
        out[i, :len(r)] = r
    return out


def compile_scene(elements, flows):
    """Tables of the velocity (flows = resolve(elements)) and of the fluid region (elements).
    Returns (F, R, W) (see above) or None if Numba is missing or some element has no kernel form."""
    if not HAVE_NUMBA:
        return None
    c0 = 0j
    rows = {k: [] for k in _TERM_KINDS.values() if k != CONST}
    for e in flows:
        terms = e.kernel_terms()
        if terms is None:
            return None
        for t in terms:
            kind = _TERM_KINDS.get(t[0])
            if kind is None:
                return None
            if kind == CONST:
                c0 += t[1]
            else:
                rows[kind].append((kind,) + tuple(t[1:]))
    F = _table([(CONST, c0)] + [r for k in (POLE1, POLE2, ROW1, ROW2, SECTOR) for r in rows[k]])
    region = []
    for e in elements:
        if not e.enabled:
            continue
        reg = e.kernel_region()
        if reg is None:
            if type(e).fluid_region is not _base_fluid_region():
                return None                            # restricts the fluid but has no kernel form
            continue
        if reg[0] == "halfplane":
            region.append((HALFPLANE,) + tuple(reg[1:]))
        elif reg[0] == "wedge":
            region.append((WEDGE,) + tuple(reg[1:]))
        else:
            return None
    R = _table(region)
    W = R[R[:, 0].real == WEDGE].copy()
    return F, R, W


def _base_fluid_region():
    from .base import FlowElement
    return FlowElement.fluid_region


# ---------------------------------------------------------------------- compiled pieces
@njit(**JIT)
def _cot(u):
    """cot(u) without overflow for large |Im u| (same as base.stable_cot)."""
    if u.imag > 0:
        q = cmath.exp(2j * u)
        return 1j * (q + 1) / (q - 1)
    q = cmath.exp(-2j * u)
    return 1j * (1 + q) / (1 - q)


@njit(**JIT)
def _w(z, F):
    """Complex velocity w = u − i v at one point."""
    w = 0j
    for k in range(F.shape[0]):
        kind = int(F[k, 0].real)
        if kind == CONST:
            w = F[k, 1]                                      # first row; the others add to it
        elif kind == POLE1:
            w += F[k, 2] / (z - F[k, 1])
        elif kind == POLE2:
            dz = z - F[k, 1]
            w += -F[k, 2] / (dz * dz)
        elif kind == ROW1:
            P = F[k, 3]                                      # complex: the period may point along y
            w += F[k, 2] * (math.pi / P) * _cot(math.pi * (z - F[k, 1]) / P)
        elif kind == ROW2:
            P = F[k, 3]
            ct = _cot(math.pi * (z - F[k, 1]) / P)
            w += -F[k, 2] * (math.pi / P) ** 2 * (1.0 + ct * ct)
        else:                                                # SECTOR
            rot = F[k, 2]
            zeta = (z - F[k, 1]) * rot
            r = abs(zeta)
            half = F[k, 3].real
            th = cmath.phase(zeta * complex(math.cos(half), -math.sin(half))) + half
            n = F[k, 4].real
            w += n * F[k, 5].real * rot * r ** (n - 1.0) * cmath.exp(1j * (n - 1.0) * th)
    return w


@njit(**JIT)
def _local_angle(z, z0, rot, half):
    zeta = (z - z0) * rot
    return cmath.phase(zeta * complex(math.cos(half), -math.sin(half))) + half


@njit(**JIT)
def _fluid(z, R):
    for k in range(R.shape[0]):
        if int(R[k, 0].real) == HALFPLANE:
            if ((z - R[k, 1]) * R[k, 2].conjugate()).real < 0.0:
                return False
        else:
            th = _local_angle(z, R[k, 1], R[k, 2], R[k, 3].real)
            if not (th >= -ANGLE_TOL and th <= R[k, 4].real + ANGLE_TOL):
                return False
    return True


@njit(**JIT)
def _crossed(za, zb, W):
    for k in range(W.shape[0]):
        z0, rot, half = W[k, 1], W[k, 2], W[k, 3].real
        if abs(_local_angle(zb, z0, rot, half) - _local_angle(za, z0, rot, half)) > math.pi:
            return True
    return False


@njit(**JIT)
def _min_dist(z, pts):
    best = np.inf
    for k in range(pts.size):
        dd = abs(z - pts[k])
        if dd < best:
            best = dd
    return best


@njit(**JIT)
def _direction(z, F):
    """Unit direction (u + i v)/|V| and speed |V|."""
    vel = _w(z, F).conjugate()
    sp = abs(vel)
    if sp == 0.0:                     # exactly on a stagnation point (e.g. the corner of two walls):
        return complex(math.nan, math.nan), 0.0       # no direction (callers stop there); no ZeroDivisionError
    return vel / sp, sp


@njit(**JIT)
def newton_zeros(z, F, L, x0, x1, y0, y1, iterations):
    """Newton's method for w(z) = 0 from every starting point (see stagnation._newton): w' from a
    central difference, steps limited to L/10; NaN when a point leaves the box or w' = 0."""
    hc = 1e-7 * L
    out = z.copy()
    for i in range(z.size):
        zi = out[i]
        for _ in range(iterations):
            w = _w(zi, F)
            dw = (_w(zi + hc, F) - _w(zi - hc, F)) / (2.0 * hc)
            if dw.real == 0.0 and dw.imag == 0.0:
                zi = complex(np.nan, zi.imag)
                break
            step = w / dw
            a = abs(step)
            if a > 0.1 * L:
                step *= 0.1 * L / a
            if not _isfinite_c(step):
                zi = complex(np.nan, zi.imag)
                break
            zi = zi - step
            if zi.real < x0 or zi.real > x1 or zi.imag < y0 or zi.imag > y1:
                zi = complex(np.nan, np.nan)                     # ran away from the region
                break
            if not abs(step) > 1e-13 * L:
                break                                            # converged
        out[i] = zi
    return out


@njit(**JIT)
def _isfinite_c(z):
    return math.isfinite(z.real) and math.isfinite(z.imag)


@njit(**JIT)
def velocity_many(z, F):
    """w at many points (used by the tests to compare with the NumPy field)."""
    out = np.empty(z.size, np.complex128)
    for i in range(z.size):
        out[i] = _w(z[i], F)
    return out


@njit(**JIT)
def fluid_many(z, R):
    out = np.empty(z.size, np.bool_)
    for i in range(z.size):
        out[i] = _fluid(z[i], R)
    return out


@njit(**JIT)
def trace_batch(seeds, sign, F, R, W, sing, r_sing, h, n_max, v_min, max_turn_cos, d,
                raster, self_ids, close_to, bx0, bx1, by0, by1, rx0, ry0, cell):
    """Integrate every seed in one direction (sign = +1 with the flow, −1 against it).

    raster      (2, ny, nx) int32: ids of the lines near each cell (−1 = none), see _OwnerRaster
    self_ids    (B,) id of the line being continued (its own cells do not stop it), −1 for new lines
    close_to    (B,) the line is closed when it comes back to this point (NaN = never)

    Returns pts (all points of all lines, one after the other), offsets (B + 1: line j is
    pts[offsets[j]:offsets[j + 1]], starting with its seed), closed, near_end, left_box (B,).
    Stop rules (identical to the NumPy tracer in streamlines.py):
      the step is NOT taken when the new point is not finite / not in the fluid / closer than
      r_sing to a singular point / slower than v_min / turns more than allowed / makes no progress /
      crosses a plate, or lies in a cell of another line (then near_end = True);
      the line ends AFTER the step when it leaves the box (left_box) or comes back (closed)."""
    B = seeds.size
    ny, nx = raster.shape[1], raster.shape[2]
    pts = np.empty(max(64 * B, 16), np.complex128)
    n = 0
    offsets = np.zeros(B + 1, np.int64)
    closed = np.zeros(B, np.bool_)
    near_end = np.zeros(B, np.bool_)
    left_box = np.zeros(B, np.bool_)
    for j in range(B):
        offsets[j] = n
        z = seeds[j]
        me = self_ids[j]
        target = close_to[j]
        if n == pts.size:
            pts = _grown(pts, n)
        pts[n] = z
        n += 1
        k0, _ = _direction(z, F)
        if not _isfinite_c(k0):
            continue
        length = 0.0
        for step in range(n_max):
            if sing.size:
                hz = min(max(0.2 * _min_dist(z, sing), h / 8.0), h)
            else:
                hz = h
            k1 = _direction(z, F)[0] * sign
            k2 = _direction(z + 0.5 * hz * k1, F)[0] * sign
            k3 = _direction(z + 0.5 * hz * k2, F)[0] * sign
            k4 = _direction(z + hz * k3, F)[0] * sign
            z_new = z + hz * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
            k_new, speed_new = _direction(z_new, F)
            k_new = k_new * sign

            other = not (_isfinite_c(z_new) and _isfinite_c(k_new))
            if not other:
                other = not _fluid(z_new, R)
            if not other and sing.size:
                other = _min_dist(z_new, sing) < r_sing
            if not other:
                other = (speed_new < v_min
                         or (k1.real * k_new.real + k1.imag * k_new.imag) < max_turn_cos
                         or abs(z_new - z) < 0.5 * hz
                         or _crossed(z, z_new, W))
            if other:
                break
            ix = min(max(int((z_new.real - rx0) / cell), 0), nx - 1)
            iy = min(max(int((z_new.imag - ry0) / cell), 0), ny - 1)
            r0 = raster[0, iy, ix]
            r1 = raster[1, iy, ix]
            if (r0 >= 0 and r0 != me) or (r1 >= 0 and r1 != me):
                near_end[j] = True
                break
            if n == pts.size:
                pts = _grown(pts, n)
            pts[n] = z_new
            n += 1
            z = z_new
            length += hz
            if z_new.real < bx0 or z_new.real > bx1 or z_new.imag < by0 or z_new.imag > by1:
                left_box[j] = True
                break
            if length > 3.0 * d and abs(z_new - target) < 0.75 * hz:
                closed[j] = True
                break
    offsets[B] = n
    return pts[:n], offsets, closed, near_end, left_box


@njit(**JIT)
def _grown(a, n):
    out = np.empty(2 * a.size, a.dtype)
    out[:n] = a[:n]
    return out


# ---------------------------------------------------------------------- Jobard–Lefer bookkeeping
# Rasters over the computed region (cell size d/4): "is there a line within radius r?". A bool raster
# for the seed test; an owner raster (2, ny, nx) of line ids for the stop test (see _OwnerRaster in
# streamlines.py, which falls back to the same operations in NumPy when Numba is missing).
@njit(**QUICK)
def _cell_index(v, origin, c, n):
    """Cell of coordinate v, clipped to 0 … n − 1 (like int() + clip in NumPy; not finite -> 0)."""
    if not math.isfinite(v):
        return 0
    q = (v - origin) / c
    if not math.isfinite(q) or q < 0.0:
        return 0
    i = int(q)
    return i if i < n - 1 else n - 1


@njit(**QUICK)
def raster_test(a, z, x0, y0, c):
    """Bool raster a (ny, nx): value at every point."""
    ny, nx = a.shape
    out = np.empty(z.size, np.bool_)
    for k in range(z.size):
        out[k] = a[_cell_index(z[k].imag, y0, c, ny), _cell_index(z[k].real, x0, c, nx)]
    return out


@njit(**QUICK)
def raster_stamp(a, z, radius, x0, y0, c):
    """Bool raster: set every cell within `radius` of every point."""
    ny, nx = a.shape
    r = int(math.ceil(radius / c))
    lim = radius ** 2
    cc = c ** 2
    for k in range(z.size):
        iy = _cell_index(z[k].imag, y0, c, ny)
        ix = _cell_index(z[k].real, x0, c, nx)
        for oy in range(-r, r + 1):
            for ox in range(-r, r + 1):
                if (ox * ox + oy * oy) * cc <= lim:
                    a[min(max(iy + oy, 0), ny - 1), min(max(ix + ox, 0), nx - 1)] = True


@njit(**QUICK)
def owner_test(a, z, self_id, x0, y0, c):
    """Owner raster a (2, ny, nx): is a line OTHER than self_id near every point?"""
    ny, nx = a.shape[1], a.shape[2]
    out = np.empty(z.size, np.bool_)
    for k in range(z.size):
        iy = _cell_index(z[k].imag, y0, c, ny)
        ix = _cell_index(z[k].real, x0, c, nx)
        r0, r1 = a[0, iy, ix], a[1, iy, ix]
        out[k] = (r0 >= 0 and r0 != self_id) or (r1 >= 0 and r1 != self_id)
    return out


@njit(**QUICK)
def owner_stamp(a, z, radius, owner, x0, y0, c):
    """Owner raster: note `owner` in every cell within `radius` of every point (first slot if free,
    else the second slot, unless the first already is `owner`)."""
    ny, nx = a.shape[1], a.shape[2]
    r = int(math.ceil(radius / c))
    lim = radius ** 2
    cc = c ** 2
    for k in range(z.size):
        iy = _cell_index(z[k].imag, y0, c, ny)
        ix = _cell_index(z[k].real, x0, c, nx)
        for oy in range(-r, r + 1):
            for ox in range(-r, r + 1):
                if (ox * ox + oy * oy) * cc <= lim:
                    yy = min(max(iy + oy, 0), ny - 1)
                    xx = min(max(ix + ox, 0), nx - 1)
                    cur = a[0, yy, xx]
                    if cur == -1:
                        a[0, yy, xx] = owner
                    elif cur != owner:
                        a[1, yy, xx] = owner


@njit(**QUICK)
def neighbour_seeds(seg, d):
    """Points at distance d on both sides of a line, every d along it (see streamlines.py)."""
    m = seg.size
    s = np.empty(m, np.float64)
    s[0] = 0.0
    for i in range(1, m):
        s[i] = s[i - 1] + abs(seg[i] - seg[i - 1])
    total = s[m - 1] if m else 0.0
    if not total > 0.0:
        return np.zeros(0, np.complex128)
    start = 0.5 * d
    count = int(math.ceil((total - start) / d)) if total > start else 0
    delta = (start + d) - start                      # as np.arange(start, total, d)
    out = np.empty(2 * count, np.complex128)
    n = 0
    for i in range(count):
        target = start + d if i == 1 else start + i * delta
        k = np.searchsorted(s, target)
        k = min(max(k, 1), m - 1)
        t = seg[k] - seg[k - 1]
        if abs(t) == 0:
            continue
        nrm = 1j * t / abs(t)
        out[n] = seg[k] + d * nrm
        out[n + 1] = seg[k] - d * nrm
        n += 2
    return out[:n]


@njit(**QUICK)
def pick_seeds(cand, psi, speed, batch, b_psi, b_tol, limit, d):
    """Which candidates join the batch (status 0) or wait for a later one (status 1): at most
    `limit` seeds, at least 2d apart and on different streamlines (ψ farther apart than 0.3·d·|V|).
    Returns status and the batch (seeds, ψ, ψ tolerance) after these candidates."""
    status = np.ones(cand.size, np.int8)
    nb = batch.size
    zb = np.empty(nb + cand.size, np.complex128)
    pb = np.empty(nb + cand.size, np.float64)
    tb = np.empty(nb + cand.size, np.float64)
    zb[:nb], pb[:nb], tb[:nb] = batch, b_psi, b_tol
    for i in range(cand.size):
        if nb >= limit:
            continue
        z, p = cand[i], psi[i]
        clash = False
        for k in range(nb):
            if abs(z - zb[k]) < 2.0 * d:
                clash = True
                break
        if not clash and math.isfinite(p):
            for k in range(nb):
                if abs(p - pb[k]) < tb[k]:
                    clash = True
                    break
        if clash:
            continue
        status[i] = 0
        zb[nb] = z
        pb[nb] = p if math.isfinite(p) else np.inf
        v = speed[i]
        tb[nb] = 0.3 * d * v if math.isfinite(v) else 0.0
        nb += 1
    return status, zb[:nb], pb[:nb], tb[:nb]


@njit(**JIT)
def nearest_line_points(P, L, skey, order, lx, ly, ny_cells, max_dist):
    """For every lattice point L[i]: index (in P) of the nearest line point within max_dist, looking
    only in the 3 × 3 cells around it (cell keys of the points sorted in skey / order); −1 = none."""
    out = np.full(L.size, -1, np.int64)
    for i in range(L.size):
        best, best_j = np.inf, -1
        for ox in range(-1, 2):
            for oy in range(-1, 2):
                k = (lx[i] + ox) * ny_cells + (ly[i] + oy)
                lo = np.searchsorted(skey, k)
                hi = np.searchsorted(skey, k, side="right")
                for q in range(lo, hi):
                    j = order[q]
                    dist = abs(P[j] - L[i])
                    if dist < best:
                        best, best_j = dist, j
        if best < max_dist:
            out[i] = best_j
    return out


@njit(**QUICK)
def _interp(x, s, f, lo, hi):
    """np.interp(x, s[lo:hi], f[lo:hi]) for one x (s non-decreasing)."""
    if x <= s[lo]:
        return f[lo]
    if x >= s[hi - 1]:
        return f[hi - 1]
    j = lo + np.searchsorted(s[lo:hi], x, side="right") - 1
    slope = (f[j + 1] - f[j]) / (s[j + 1] - s[j])
    r = slope * (x - s[j]) + f[j]
    if not math.isfinite(r):
        r = slope * (x - s[j + 1]) + f[j + 1]
        if not math.isfinite(r) and f[j] == f[j + 1]:
            r = f[j]
    return r


@njit(**QUICK)
def fade_cut(xy, offs, cut0, cut1, d, levels, taper_ratio):
    """Lines (points xy, line i = xy[offs[i]:offs[i + 1]]) cut into pieces for drawing with fading ends
    (see streamlines.fade_piece_lists). Returns the points of all pieces (one after the other),
    offsets (pieces + 1), the opacity level of every piece and its bounding box (x0, x1, y0, y1)."""
    nl = offs.size - 1
    P = nl * (1 + 2 * levels)
    pts = np.empty((xy.shape[0] + 2 * P + 2 * nl * levels * 2 + 16, 2))
    po = np.zeros(P + 1, np.int64)
    plev = np.empty(P, np.int64)
    boxes = np.empty((P, 4))
    s = np.empty(xy.shape[0])
    npc, n = 0, 0
    for i in range(nl):
        lo, hi = offs[i], offs[i + 1]
        if hi - lo < 2:
            continue
        s[lo] = 0.0
        for k in range(lo + 1, hi):
            s[k] = s[k - 1] + math.hypot(xy[k, 0] - xy[k - 1, 0], xy[k, 1] - xy[k - 1, 1])
        total = s[hi - 1]
        n_cut = int(cut0[i]) + int(cut1[i])
        Lt = min(taper_ratio * d, total / n_cut) if n_cut else 0.0
        a = Lt if cut0[i] else 0.0
        b = total - Lt if cut1[i] else total
        for piece in range(1 + 2 * levels):
            if piece == 0:
                if not b > a:
                    continue
                pa, pb, lev = a, b, 0
            else:
                k = (piece + 1) // 2
                start = piece % 2 == 1
                if (start and not cut0[i]) or (not start and not cut1[i]):
                    continue
                l0, l1 = Lt * (levels - k) / levels, Lt * (levels - k + 1) / levels
                pa, pb, lev = (l0, l1, k) if start else (total - l1, total - l0, k)
            if n + (hi - lo) + 2 > pts.shape[0]:
                grown = np.empty((2 * pts.shape[0] + hi - lo + 2, 2))
                grown[:n] = pts[:n]
                pts = grown
            po[npc] = n
            pts[n, 0] = _interp(pa, s, xy[:, 0], lo, hi)
            pts[n, 1] = _interp(pa, s, xy[:, 1], lo, hi)
            n += 1
            for k2 in range(lo, hi):
                if s[k2] > pa and s[k2] < pb:
                    pts[n, 0], pts[n, 1] = xy[k2, 0], xy[k2, 1]
                    n += 1
            pts[n, 0] = _interp(pb, s, xy[:, 0], lo, hi)
            pts[n, 1] = _interp(pb, s, xy[:, 1], lo, hi)
            n += 1
            seg = pts[po[npc]:n]
            boxes[npc, 0], boxes[npc, 1] = seg[:, 0].min(), seg[:, 0].max()
            boxes[npc, 2], boxes[npc, 3] = seg[:, 1].min(), seg[:, 1].max()
            plev[npc] = lev
            npc += 1
    po[npc] = n
    return pts[:n], po[:npc + 1], plev[:npc], boxes[:npc]


# ---------------------------------------------------------------------- tracer particles (animation)
@njit(**QUICK)
def seed_random(seed):
    np.random.seed(seed)


@njit(**JIT)
def _spawn_point(F, R, sing, guard, x0, x1, y0, y1):
    """A random point of the box in the fluid, away from singular points (16 tries)."""
    z = complex(x0 + (x1 - x0) * np.random.random(), y0 + (y1 - y0) * np.random.random())
    for _ in range(16):
        if _fluid(z, R) and (sing.size == 0 or _min_dist(z, sing) >= guard):
            break
        z = complex(x0 + (x1 - x0) * np.random.random(), y0 + (y1 - y0) * np.random.random())
    return z


@njit(**JIT)
def advect_particles(pos, age, speed, fresh, F, R, W, sing, guard, dt, age_dt, max_step, max_sub,
                     x0, x1, y0, y1, max_age):
    """Move every particle by dt (midpoint RK2, split into sub-steps no longer than max_step, at most
    max_sub of them). A particle starts again at a random point (fresh = True) when it leaves the box,
    the fluid, comes within `guard` of a singular point, crosses a plate, would need more sub-steps than
    allowed (next to a singular point), or is older than max_age (ages grow by age_dt)."""
    for i in range(pos.size):
        z = pos[i]
        v = _w(z, F).conjugate()
        travel = abs(v) * dt
        ok = math.isfinite(travel) and travel <= max_step * max_sub
        if ok:
            n = min(max(int(math.ceil(travel / max_step)), 1), max_sub)
            h = dt / n
            k2 = v
            for k in range(n):
                k1 = v if k == 0 else _w(z, F).conjugate()
                k2 = _w(z + 0.5 * h * k1, F).conjugate()
                z_new = z + h * k2
                if _crossed(z, z_new, W):
                    ok = False
                    break
                z = z_new
            v = k2
        age[i] += age_dt
        if ok:
            ok = (_isfinite_c(z) and x0 <= z.real <= x1 and y0 <= z.imag <= y1 and _fluid(z, R)
                  and (sing.size == 0 or _min_dist(z, sing) >= guard) and age[i] <= max_age)
        if ok:
            pos[i] = z
            speed[i] = abs(v)
            fresh[i] = False
        else:
            z = _spawn_point(F, R, sing, guard, x0, x1, y0, y1)
            pos[i] = z
            age[i] = 0.0
            speed[i] = abs(_w(z, F))
            fresh[i] = True


@njit(**QUICK)
def fade_bytes(buf, keep):
    """Trail picture: every byte × keep / 256, rounded DOWN (so faint pixels really reach 0; Qt's
    rounding would leave ghost trails). keep = 0 … 256."""
    for i in range(buf.size):
        buf[i] = (buf[i] * keep) >> 8


@njit(**QUICK)
def draw_segments(img, ax, ay, bx, by, color_index, palette, radius, alpha, keep_max):
    """Antialiased lines of half-width `radius` with round ends into a premultiplied BGRA picture
    img (rows, columns, 4) uint8. Line k goes from (ax, ay) to (bx, by) in pixels (row = y) and has
    the color palette[color_index[k]] = (r, g, b, alpha 0…1) with its alpha × alpha[k];
    index < 0: not drawn. keep_max: a pixel keeps the more opaque color instead of blending (pieces of
    one line that overlap at their round ends then do not show darker beads)."""
    draw_segments_rows(img, ax, ay, bx, by, color_index, palette, radius, alpha, keep_max, 0, img.shape[0])


@njit(**JIT)
def draw_segments_rows(img, ax, ay, bx, by, color_index, palette, radius, alpha, keep_max, r0, r1):
    """draw_segments, only into the picture rows r0 … r1 − 1 (without the interpreter lock): bands of rows
    drawn on several cores at once give exactly the same picture (every pixel sees the lines in the same
    order), see draw_segments_parallel."""
    rows, cols = min(img.shape[0], r1), img.shape[1]
    for k in range(ax.size):
        ci = color_index[k]
        if ci < 0:
            continue
        x0, y0, x1, y1 = ax[k], ay[k], bx[k], by[k]
        if not (math.isfinite(x0) and math.isfinite(y0) and math.isfinite(x1) and math.isfinite(y1)):
            continue
        cr, cg, cb, ca = palette[ci, 0], palette[ci, 1], palette[ci, 2], palette[ci, 3] * alpha[k]
        if ca <= 0.0:
            continue
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy
        i0 = max(int(math.floor(min(x0, x1) - radius - 1.0)), 0)
        i1 = min(int(math.ceil(max(x0, x1) + radius + 1.0)), cols - 1)
        j0 = max(int(math.floor(min(y0, y1) - radius - 1.0)), r0)
        j1 = min(int(math.ceil(max(y0, y1) + radius + 1.0)), rows - 1)
        if j1 < j0:
            continue
        for j in range(j0, j1 + 1):
            py = j + 0.5
            for i in range(i0, i1 + 1):
                px = i + 0.5
                t = 0.0
                if L2 > 0.0:
                    t = ((px - x0) * dx + (py - y0) * dy) / L2
                    t = min(max(t, 0.0), 1.0)
                qx, qy = x0 + t * dx - px, y0 + t * dy - py
                cov = radius + 0.5 - math.sqrt(qx * qx + qy * qy)
                if cov <= 0.0:
                    continue
                a = ca * min(cov, 1.0)
                if keep_max:
                    if 255.0 * a > img[j, i, 3]:
                        img[j, i, 0] = int(cb * a + 0.5)
                        img[j, i, 1] = int(cg * a + 0.5)
                        img[j, i, 2] = int(cr * a + 0.5)
                        img[j, i, 3] = int(255.0 * a + 0.5)
                    continue
                inv = 1.0 - a
                img[j, i, 0] = int(cb * a + img[j, i, 0] * inv + 0.5)
                img[j, i, 1] = int(cg * a + img[j, i, 1] * inv + 0.5)
                img[j, i, 2] = int(cr * a + img[j, i, 2] * inv + 0.5)
                img[j, i, 3] = int(255.0 * a + img[j, i, 3] * inv + 0.5)


def draw_segments_parallel(img, ax, ay, bx, by, color_index, palette, radius, alpha, keep_max):
    """draw_segments on all cores: the picture is cut into bands of rows (physics.parallel), each band drawn
    by one core. The same picture as draw_segments, bit for bit."""
    from . import parallel
    rows = img.shape[0]
    bands = parallel.chunks(rows, 48)
    if len(bands) <= 1:
        draw_segments(img, ax, ay, bx, by, color_index, palette, radius, alpha, keep_max)
        return
    parallel.run([lambda a=a, b=b: draw_segments_rows(img, ax, ay, bx, by, color_index, palette, radius, alpha,
                                                       keep_max, a, b) for a, b in bands])


@njit(**QUICK)
def label_regions(free):
    """Connected regions (4-neighbour) of the True cells of a 2-D bool array. Returns (labels, n):
    labels 1 … n, 0 for False cells. A barrier drawn as an 8-connected line separates regions."""
    rows, cols = free.shape
    labels = np.zeros((rows, cols), np.int32)
    stack = np.empty(rows * cols, np.int64)
    n = 0
    for j0 in range(rows):
        for i0 in range(cols):
            if not free[j0, i0] or labels[j0, i0] != 0:
                continue
            n += 1
            labels[j0, i0] = n
            top = 0
            stack[0] = j0 * cols + i0
            top = 1
            while top > 0:
                top -= 1
                k = stack[top]
                j, i = k // cols, k % cols
                if j > 0 and free[j - 1, i] and labels[j - 1, i] == 0:
                    labels[j - 1, i] = n
                    stack[top] = k - cols
                    top += 1
                if j < rows - 1 and free[j + 1, i] and labels[j + 1, i] == 0:
                    labels[j + 1, i] = n
                    stack[top] = k + cols
                    top += 1
                if i > 0 and free[j, i - 1] and labels[j, i - 1] == 0:
                    labels[j, i - 1] = n
                    stack[top] = k - 1
                    top += 1
                if i < cols - 1 and free[j, i + 1] and labels[j, i + 1] == 0:
                    labels[j, i + 1] = n
                    stack[top] = k + 1
                    top += 1
    return labels, n
