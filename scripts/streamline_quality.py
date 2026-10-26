"""
streamline_quality.py — measures how good the streamline picture is, for several scenes.

    python scripts/streamline_quality.py

Columns
  lines      number of streamlines
  gap_cv     uniform-flow scenes only: variation of the distance between neighbouring lines
             (std / mean; 0 = perfectly even)
  inner_ends line ends in the middle of the fluid: not at the view edge, not at a wall / wedge side,
             not at a singular point, not at a stagnation point, not a closed loop (lower = better)
  short      lines shorter than 3 d (d = line spacing)
  ms         computation time
"""
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from physics import (Doublet, SectorFlow, Source, SymmetryWall, Uniform, Vortex,  # noqa: E402
                     complex_velocity, resolve)
from physics.field import singular_points  # noqa: E402
from physics.streamlines import trace_streamlines  # noqa: E402

VIEW = ((-4.0, 4.0), (-3.0, 3.0))
SCENES = {
    "uniform α=0": ([Uniform()], VIEW),
    "uniform α=30°": ([Uniform(alpha=30.0)], VIEW),
    "cylinder": ([Uniform(), Doublet(mu=1.0)], VIEW),
    "lifting cylinder": ([Uniform(), Doublet(mu=1.0), Vortex(Gamma=-2.0)], VIEW),
    "Rankine oval": ([Uniform(), Source(m=3.0, x0=-1.0), Source(m=-3.0, x0=1.0)], VIEW),
    "corner 90°": ([SectorFlow(V=1.0)], ((-0.6, 3.4), (-0.6, 3.0))),
    "wedge 30°": ([SectorFlow(V=0.2, theta2=30.0)], ((-0.3, 2.7), (-0.4, 1.8))),
    "plate tip": ([SectorFlow(theta2=360.0)], ((-3.0, 3.0), (-2.4, 2.4))),
    "source near wall": ([SymmetryWall(yw=0.0), Source(m=2.0, y0=1.0)], ((-4.0, 4.0), (-1.0, 5.0))),
    "channel": ([SymmetryWall(yw=-1.0), SymmetryWall(yw=1.0, side=1), Uniform(),
                 Source(m=1.0, x0=-1.5, y0=0.3), Vortex(Gamma=1.0, x0=1.5, y0=-0.3)], ((-5.0, 5.0), (-1.6, 1.6))),
}


def measure(elements, view, **kw):
    t0 = time.perf_counter()
    res = trace_streamlines(elements, *view, **kw)
    ms = (time.perf_counter() - t0) * 1000.0
    d = res.separation
    (x0, x1), (y0, y1) = view
    flows = resolve(elements)
    sing = np.array(singular_points(elements))
    domains = [e for e in elements if e.enabled and (e.IS_BOUNDARY or e.implied_walls() is not None)]
    gx, gy = np.meshgrid(np.linspace(x0, x1, 17), np.linspace(y0, y1, 17))
    sp = np.abs(complex_velocity(flows, gx + 1j * gy))
    v_ref = float(np.nanmedian(sp[np.isfinite(sp)])) if np.isfinite(sp).any() else 1.0

    inner, short = 0, 0
    for ln in res.lines:
        z = ln[:, 0] + 1j * ln[:, 1]
        length = float(np.sum(np.abs(np.diff(z))))
        if length < 3.0 * d:
            short += 1
        if abs(z[0] - z[-1]) < 1e-9:
            continue                                            # closed loop
        for p in (z[0], z[-1]):
            near_edge = min(p.real - x0, x1 - p.real, p.imag - y0, y1 - p.imag) < 1.5 * d
            near_sing = sing.size and np.min(np.abs(sing - p)) < 2.0 * d
            near_wall = any(abs(float(e.signed_distance(np.array([p]))[0])) < 1.0 * d for e in domains)
            stagnant = abs(complex_velocity(flows, np.array([p]))[0]) < 0.08 * v_ref
            if not (near_edge or near_sing or near_wall or stagnant):
                inner += 1
    return res, {"lines": len(res.lines), "inner_ends": inner, "short": short, "ms": ms, "d": d}


def gap_cv(res):
    """Uniform flow: lines are straight; spacing between neighbours across the flow."""
    if not res.lines:
        return float("nan")
    first = res.lines[0]
    t = first[-1] - first[0]
    t = t / np.linalg.norm(t)
    nrm = np.array([-t[1], t[0]])
    offs = np.sort([float(np.mean(ln @ nrm)) for ln in res.lines])
    gaps = np.diff(offs)
    return float(np.std(gaps) / np.mean(gaps)) if gaps.size else float("nan")


def main():
    print(f"{'scene':<20}{'lines':>7}{'gap_cv':>9}{'inner_ends':>12}{'short':>8}{'ms':>8}")
    print("-" * 64)
    totals = {"inner_ends": 0, "short": 0, "ms": 0.0}
    for name, (els, view) in SCENES.items():
        res, m = measure(els, view)
        cv = gap_cv(res) if name.startswith("uniform") else float("nan")
        cv_txt = f"{cv:9.3f}" if np.isfinite(cv) else f"{'–':>9}"
        print(f"{name:<20}{m['lines']:>7}{cv_txt}{m['inner_ends']:>12}{m['short']:>8}{m['ms']:>8.0f}")
        for k in totals:
            totals[k] += m[k]
    print("-" * 64)
    print(f"{'total':<20}{'':>7}{'':>9}{totals['inner_ends']:>12}{totals['short']:>8}{totals['ms']:>8.0f}")


if __name__ == "__main__":
    main()
