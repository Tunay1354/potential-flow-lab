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

_C = np.complex128
_EMPTY_C = np.zeros(0, _C)
_EMPTY_F = np.zeros(0, np.float64)


# ---------------------------------------------------------------------- scene -> arrays
def compile_scene(elements, flows):
    """Arrays describing the velocity (flows = resolve(elements)) and the fluid region (elements).
    Returns (F, R, W) or None if Numba is missing or some element has no kernel form.
      F = (c0, p1z, p1c, p2z, p2c, r1z, r1c, r1P, r2z, r2c, r2P, sz, srot, shalf, sn, sV)
      R = (hp_p, hp_n, wz, wrot, whalf, wbeta)          fluid region (walls, wedges)
      W = (wz, wrot, whalf)                              wedges whose cut a step must not cross"""
    if not HAVE_NUMBA:
        return None
    c0 = 0j
    p1, p2, r1, r2, sec = [], [], [], [], []
    for e in flows:
        terms = e.kernel_terms()
        if terms is None:
            return None
        for t in terms:
            kind = t[0]
            if kind == "const":
                c0 += t[1]
            elif kind == "pole1":
                p1.append(t[1:])
            elif kind == "pole2":
                p2.append(t[1:])
            elif kind == "row1":
                r1.append(t[1:])
            elif kind == "row2":
                r2.append(t[1:])
            elif kind == "sector":
                sec.append(t[1:])
            else:
                return None
    hp, wd = [], []
    for e in elements:
        if not e.enabled:
            continue
        reg = e.kernel_region()
        overrides = type(e).fluid_region is not _base_fluid_region()
        if reg is None:
            if overrides:
                return None                            # restricts the fluid but has no kernel form
            continue
        if reg[0] == "halfplane":
            hp.append(reg[1:])
        elif reg[0] == "wedge":
            wd.append(reg[1:])
        else:
            return None

    def col(rows, k, dtype=_C):
        return np.array([r[k] for r in rows], dtype=dtype) if rows else np.zeros(0, dtype)

    F = (complex(c0),
         col(p1, 0), col(p1, 1),
         col(p2, 0), col(p2, 1),
         col(r1, 0), col(r1, 1), col(r1, 2),
         col(r2, 0), col(r2, 1), col(r2, 2),
         col(sec, 0), col(sec, 1), col(sec, 2, np.float64), col(sec, 3, np.float64), col(sec, 4, np.float64))
    R = (col(hp, 0), col(hp, 1),
         col(wd, 0), col(wd, 1), col(wd, 2, np.float64), col(wd, 3, np.float64))
    W = (R[2], R[3], R[4])
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
    c0, p1z, p1c, p2z, p2c, r1z, r1c, r1P, r2z, r2c, r2P, sz, srot, shalf, sn, sV = F
    w = c0
    for k in range(p1z.size):
        w += p1c[k] / (z - p1z[k])
    for k in range(p2z.size):
        dz = z - p2z[k]
        w += -p2c[k] / (dz * dz)
    for k in range(r1z.size):
        P = r1P[k]
        w += r1c[k] * (math.pi / P) * _cot(math.pi * (z - r1z[k]) / P)
    for k in range(r2z.size):
        P = r2P[k]
        ct = _cot(math.pi * (z - r2z[k]) / P)
        w += -r2c[k] * (math.pi / P) ** 2 * (1.0 + ct * ct)
    for k in range(sz.size):
        zeta = (z - sz[k]) * srot[k]
        r = abs(zeta)
        half = shalf[k]
        th = cmath.phase(zeta * complex(math.cos(half), -math.sin(half))) + half
        n = sn[k]
        w += n * sV[k] * srot[k] * r ** (n - 1.0) * cmath.exp(1j * (n - 1.0) * th)
    return w


@njit(**JIT)
def _local_angle(z, z0, rot, half):
    zeta = (z - z0) * rot
    return cmath.phase(zeta * complex(math.cos(half), -math.sin(half))) + half


@njit(**JIT)
def _fluid(z, R):
    hp_p, hp_n, wz, wrot, whalf, wbeta = R
    for k in range(hp_p.size):
        if ((z - hp_p[k]) * hp_n[k].conjugate()).real < 0.0:
            return False
    for k in range(wz.size):
        th = _local_angle(z, wz[k], wrot[k], whalf[k])
        if not (th >= -ANGLE_TOL and th <= wbeta[k] + ANGLE_TOL):
            return False
    return True


@njit(**JIT)
def _crossed(za, zb, W):
    wz, wrot, whalf = W
    for k in range(wz.size):
        if abs(_local_angle(zb, wz[k], wrot[k], whalf[k]) - _local_angle(za, wz[k], wrot[k], whalf[k])) > math.pi:
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
    return vel / sp, sp


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

    Returns traj (n_max + 1, B) complex (NaN after the end), closed, near_end, left_box (B,).
    Stop rules (identical to the NumPy tracer in streamlines.py):
      the step is NOT taken when the new point is not finite / not in the fluid / closer than
      r_sing to a singular point / slower than v_min / turns more than allowed / makes no progress /
      crosses a plate, or lies in a cell of another line (then near_end = True);
      the line ends AFTER the step when it leaves the box (left_box) or comes back (closed)."""
    B = seeds.size
    ny, nx = raster.shape[1], raster.shape[2]
    traj = np.full((n_max + 1, B), np.nan + 0j)
    closed = np.zeros(B, np.bool_)
    near_end = np.zeros(B, np.bool_)
    left_box = np.zeros(B, np.bool_)
    for j in range(B):
        z = seeds[j]
        me = self_ids[j]
        target = close_to[j]
        traj[0, j] = z
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
            traj[step + 1, j] = z_new
            z = z_new
            length += hz
            if z_new.real < bx0 or z_new.real > bx1 or z_new.imag < by0 or z_new.imag > by1:
                left_box[j] = True
                break
            if length > 3.0 * d and abs(z_new - target) < 0.75 * hz:
                closed[j] = True
                break
    return traj, closed, near_end, left_box
