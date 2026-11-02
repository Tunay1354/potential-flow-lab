"""
random_test.py — the exhaustive random test (ROADMAP 23): hundreds of random, also strange, scenes and random
user actions, each checked against the physics and for crashes. The program itself is not changed; nothing of
yours is touched (Qt test folders, a temporary settings file, exports into a temporary folder).

    python scripts/random_test.py                    about 25 minutes (physics ~60 %, the window ~40 %)
    python scripts/random_test.py --minutes 60       longer: more scenes and more actions
    python scripts/random_test.py --quick            ~3 minutes (to see that it runs; a slow scene makes it longer)
    python scripts/random_test.py --seed 7           another set of random scenes (the seed is in the report)
    python scripts/random_test.py --replay random_test_results/<run>/failures/0003-psi.pflow
                                                     one saved failing scene again, every check, with details
    python scripts/random_test.py --no-gui           only the physics part

Results: random_test_results/<date-time>/ — summary.md (read this first), results.json (every number),
failures/ (each failing scene as a .pflow you can open in the program, and a .txt with what went wrong). Send the
whole folder (or zip it) to the assistant.

While it runs, one line shows: the part (physics / window), the bar and %, time gone and left, the clock time it
ends, what it is doing now and the failures so far. The clock on that line moves every second; a long scene shows
"working N s" — still moving = still working; after 2 minutes on one thing it writes where every thread is to
failures/STACK-….txt by itself. If the line does not change at all for 5 minutes: frozen (Ctrl+C, send the folder).

PART 1 — physics (no window). Random scenes of six kinds:
    free      a uniform flow (any angle) + 1–5 sources / sinks / vortices / doublets (aligned or turned)
    classic   cylinder, lifting cylinder (also |Γ| > 4πV∞a), Rankine oval, half-body, two bodies close together
    walls     one wall, a corner (π/k), a channel (also closed at one end, or a rectangle of 4 walls, turned),
              with elements on the fluid side and (open ones) a parallel uniform flow
    sector    sector flows (β = 90°, 60°, 45°, 180°, 360°, any) alone or with a source / vortex inside
    edge      the strange ones: tiny and huge strengths and coordinates, elements almost on top of each other,
              an element on / behind a wall, zero strengths, hidden elements, crowded scenes (8–16 elements)
    chaos     what the scene check calls errors, mixed freely: 1–3 walls at any angle and place, a uniform flow
              at any angle (not parallel to the walls), sources / vortices / doublets / sector flows anywhere, also
              several sector flows or a sector flow with walls
  Each valid scene is computed in four views (the Fit view, 50× closer at a random point, 100× wider, panned) and
  checked:
    no-crash     streamlines, stagnation points, dividing streamlines, bodies, surfaces, forces, particles,
                 field grid, travel times: nothing raises
    slow         one scene (all its views and checks) takes less than 2 minutes; a scene that does not end is
                 written to failures/RUNNING-slow.* while it still runs (stuck? Ctrl+C and send the folder)
    stagnation   |V| at every stagnation point found ≈ 0 (relative to the typical speed of the view)
    tangent      every drawn streamline runs along the velocity (angle between a segment and V at its middle)
    psi          ψ is constant along every drawn streamline (scenes without sources / sector flows, whose ψ has a
                 branch cut): how far a line strays from its own ψ level, δψ/|V|, in units of the line spacing
                 (tangent and psi skip flow slower than 5 % of the view's speed scale, which is never below
                 1e-6 × the flow round the elements: far out in a corner or down a closed channel the flow is
                 ~nothing and a line's exact place there does not matter)
    crossing     no two drawn streamlines cross (away from stagnation and singular points)
    bodies-zoom  the Solid bodies map is the same in the Fit view and 4× closer (zoom-independent bodies)
    forces       a closed body alone in a uniform stream: lift = −ρV∞Γ (Kutta–Joukowski), drag = 0 (d'Alembert)
    save-open    saved and opened again: the same elements, and the same streamlines bit for bit
    particles    tracer particles stay in the fluid (never behind a wall, never inside a body)
  Invalid scenes (the scene check reports an error: the window still draws them, under the red strip) are
  computed too, in the Fit view and 50× closer: no-crash and slow only (the physics checks do not hold there).

PART 2 — the window (offscreen: nothing appears on the screen). The program's own window gets random actions:
  add (walls at any angle, uniform flows at any angle, sector flows of any β) / edit / move / hide / delete
  elements, undo / redo, presets, clear, layers on and off, Static / Particles / Pulses with frames, zoom (also to
  the limits), Fit, pan, theme, sliders, the beaver dropped on the plot, export (PNG / SVG / CSV), save and open
  again — and the fast ones, with real mouse and wheel events: a wheel burst (5–80 notches at once, often to a zoom
  limit), panning with the mouse, dragging an element with the mouse, a wall storm (2–3 walls at random angles
  added at once, maybe a uniform flow across them), flipping Static / Particles / Pulses quickly. About one action
  in three does not wait for the window to finish computing (the next one comes while it still computes).
  After every action: no error (anything that reaches the error window or the log counts), the window is done
  computing within 30 s (slow (window): how long it took in the end), and every few actions: undo all the way back
  gives exactly the scene of the start, redo all the way gives exactly the scene of the end.
"""
from __future__ import annotations

import argparse
import datetime
import json
import logging
import math
import os
import platform
import sys
import tempfile
import threading
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np  # noqa: E402

from app_info import APP_NAME, APP_VERSION, LOGGER  # noqa: E402
from model.scene_file import SceneDocument, _element_to_data, dumps, load_scene, loads, save_scene  # noqa: E402
from physics import Doublet, SectorFlow, Source, SymmetryWall, Uniform, Vortex, check_scene  # noqa: E402
from physics.bodies import body_map, scene_map  # noqa: E402
from physics.field import (active, complex_potential, complex_velocity, compute_field, fluid_mask,  # noqa: E402
                           reference_speed, singular_points)
from physics.images import resolve  # noqa: E402
from physics.particles import Particles, travel_times  # noqa: E402
from physics.stagnation import _scene_speed, find_stagnation_points, flow_features  # noqa: E402
from physics.streamlines import StreamlineCache  # noqa: E402
from physics.surface import body_surfaces, pressure_force  # noqa: E402

KINDS = ("free", "classic", "walls", "sector", "edge", "chaos")
CHECKS = ("no-crash", "slow", "stagnation", "tangent", "psi", "crossing", "bodies-zoom", "forces", "save-open",
          "particles")
TOL = {"stagnation": 1e-5,            # |V| / typical speed at a stagnation point
       "tangent_deg": 3.0,            # largest angle between a drawn segment and V at its middle
       "psi": 0.02,                   # largest distance of a line from its own ψ level (δψ/|V|) / line spacing
       "bodies": 0.02,                # share of sample points classified differently in the two views
       "force": 0.01,                 # |L′ − KJ| and |D′| / max(1, |V∞Γ|)
       "particles": 0.005,            # share of particles outside the fluid / inside a body
       "slow_scene_s": 120.0,         # one scene, all its views and checks (PART 1)
       "slow_window_s": 30.0}         # the window still computing this long after an action (PART 2)
DEFAULT_VIEW = ((-4.0, 4.0), (-2.6, 2.6))


# ====================================================================== random scenes
def _log_uniform(rng, lo, hi):
    return float(math.exp(rng.uniform(math.log(lo), math.log(hi))))


def _strength(rng, lo=0.3, hi=4.0):
    return float(rng.choice([-1.0, 1.0]) * rng.uniform(lo, hi))


def _point(rng, r=3.0):
    return float(rng.uniform(-r, r)), float(rng.uniform(-0.7 * r, 0.7 * r))


def random_scene(rng, kind: str) -> list:
    """A list of elements of one of the five kinds (see the module text)."""
    if kind == "free":
        alpha = float(rng.choice([0.0, rng.uniform(-60, 60)]))
        els = [Uniform(V=float(rng.uniform(0.3, 3.0)), alpha=alpha)]
        for _ in range(int(rng.integers(1, 6))):
            x, y = _point(rng)
            t = int(rng.integers(4))
            if t == 0:
                els.append(Source(m=_strength(rng), x0=x, y0=y))
            elif t == 1:
                els.append(Vortex(Gamma=_strength(rng, 0.3, 8.0), x0=x, y0=y))
            elif t == 2:
                els.append(Doublet(mu=float(rng.uniform(0.2, 4.0)), x0=x, y0=y, delta=alpha))
            else:
                els.append(Doublet(mu=float(rng.uniform(0.2, 4.0)), x0=x, y0=y, delta=float(rng.uniform(-180, 180))))
        return els
    if kind == "classic":
        V, a = float(rng.uniform(0.5, 3.0)), float(rng.uniform(0.3, 2.0))
        alpha = float(rng.choice([0.0, rng.uniform(-45, 45)]))
        which = int(rng.integers(5))
        u = Uniform(V=V, alpha=alpha)
        if which == 0:
            return [u, Doublet(mu=V * a * a, delta=alpha)]
        if which == 1:
            g = float(rng.choice([-1, 1]) * rng.uniform(0.1, 1.6) * 4 * math.pi * V * a)     # also beyond 4πV∞a
            return [u, Doublet(mu=V * a * a, delta=alpha), Vortex(Gamma=g)]
        if which == 2:
            m, s = float(rng.uniform(0.5, 8.0)), float(rng.uniform(0.3, 2.0))
            c, sn = math.cos(math.radians(alpha)), math.sin(math.radians(alpha))
            return [u, Source(m=m, x0=-s * c, y0=-s * sn), Source(m=-m, x0=s * c, y0=s * sn)]
        if which == 3:
            return [u, Source(m=float(rng.uniform(0.2, 6.0)), x0=float(rng.uniform(-1, 1)))]
        gap = float(rng.uniform(0.05, 1.5))
        return [Uniform(V=V), Doublet(mu=0.5, x0=-gap - 0.7), Doublet(mu=0.5, x0=gap + 0.7)]
    if kind == "walls":
        which = int(rng.integers(5))
        if which == 0:                                            # one wall
            th = float(rng.choice([0.0, 90.0, rng.uniform(-80, 80)]))
            walls = [SymmetryWall(xw=0.0, yw=-1.0, theta_w=th, side=0)]
        elif which == 1:                                          # a corner of π/k
            k = int(rng.choice([2, 3, 4]))
            walls = [SymmetryWall(yw=0.0, theta_w=0.0, side=0), SymmetryWall(theta_w=180.0 / k, side=1)]
        elif which == 2:                                          # a channel
            h = float(rng.uniform(1.0, 4.0))
            walls = [SymmetryWall(yw=0.0, side=0), SymmetryWall(yw=h, side=1)]
        else:                                                     # a channel closed at one end / a rectangle
            h, w, th = float(rng.uniform(1.0, 4.0)), float(rng.uniform(1.0, 6.0)), float(rng.choice([0.0, rng.uniform(-90, 90)]))
            t = complex(math.cos(math.radians(th)), math.sin(math.radians(th)))
            at = lambda x, y: t * complex(x, y)                   # noqa: E731
            walls = [SymmetryWall(xw=at(0, -h / 2).real, yw=at(0, -h / 2).imag, theta_w=th, side=0),
                     SymmetryWall(xw=at(0, h / 2).real, yw=at(0, h / 2).imag, theta_w=th, side=1),
                     SymmetryWall(xw=at(-w / 2, 0).real, yw=at(-w / 2, 0).imag, theta_w=th + 90.0, side=1)]
            if which == 4:
                walls.append(SymmetryWall(xw=at(w / 2, 0).real, yw=at(w / 2, 0).imag, theta_w=th + 90.0, side=0))
        els = list(walls)
        if which < 3 and which != 1 and rng.random() < 0.7:
            els.append(Uniform(V=float(rng.uniform(0.3, 2.0)), alpha=walls[0].theta_w))
        for _ in range(int(rng.integers(1, 4))):
            for _try in range(20):                                # a point on the fluid side of every wall
                z = complex(*_point(rng, 3.0))
                if all(w.signed_distance(z) > 0.2 for w in walls):
                    break
            t = int(rng.integers(3))
            if t == 0:
                els.append(Source(m=_strength(rng), x0=z.real, y0=z.imag))
            elif t == 1:
                els.append(Vortex(Gamma=_strength(rng, 0.3, 6.0), x0=z.real, y0=z.imag))
            else:
                els.append(Doublet(mu=float(rng.uniform(0.1, 1.0)), x0=z.real, y0=z.imag, delta=walls[0].theta_w))
        return els
    if kind == "sector":
        beta = float(rng.choice([90.0, 60.0, 45.0, 180.0, 360.0, rng.uniform(20, 340)]))
        th1 = float(rng.choice([0.0, rng.uniform(-90, 90)]))
        sec = SectorFlow(V=float(rng.uniform(0.3, 3.0)), x0=0.0, y0=0.0, theta1=th1, theta2=th1 + beta)
        els = [sec]
        if rng.random() < 0.6:
            mid = math.radians(th1 + beta / 2)
            r = float(rng.uniform(0.5, 2.5))
            z = r * complex(math.cos(mid), math.sin(mid))
            els.append((Source(m=_strength(rng), x0=z.real, y0=z.imag) if rng.random() < 0.5
                        else Vortex(Gamma=_strength(rng), x0=z.real, y0=z.imag)))
        return els
    if kind == "chaos":
        els = [SymmetryWall(xw=float(rng.uniform(-3, 3)), yw=float(rng.uniform(-2, 2)),
                            theta_w=float(rng.uniform(-180, 180)), side=int(rng.integers(2)))
               for _ in range(int(rng.integers(1, 4)))]
        if rng.random() < 0.8:
            els.append(Uniform(V=float(rng.uniform(0.3, 3.0)), alpha=float(rng.uniform(-180, 180))))
        for _ in range(int(rng.integers(1, 5))):
            x, y = _point(rng)
            th = float(rng.uniform(-180, 180))
            choice = [Source(m=_strength(rng), x0=x, y0=y), Vortex(Gamma=_strength(rng, 0.3, 8.0), x0=x, y0=y),
                      Doublet(mu=float(rng.uniform(0.2, 4.0)), x0=x, y0=y, delta=th),
                      SectorFlow(V=float(rng.uniform(0.3, 3.0)), x0=x, y0=y, theta1=th,
                                 theta2=th + float(rng.uniform(20, 360)))]
            els.append(choice[int(rng.integers(4))])
        rng.shuffle(els)
        return els
    # edge
    which = int(rng.integers(7))
    if which == 0:                                                # tiny / huge strengths
        s = _log_uniform(rng, 1e-6, 1e6)
        return [Uniform(V=float(rng.choice([1.0, s]))), Doublet(mu=s), Vortex(Gamma=-s, x0=0.0)]
    if which == 1:                                                # tiny / huge coordinates
        L = _log_uniform(rng, 1e-5, 1e5)
        return [Uniform(V=1.0), Source(m=L, x0=-L), Source(m=-L, x0=L), Vortex(Gamma=L, y0=2 * L)]
    if which == 2:                                                # almost on top of each other
        e = _log_uniform(rng, 1e-9, 1e-3)
        return [Uniform(V=1.0), Source(m=1.0), Source(m=-1.0, x0=e), Vortex(Gamma=1.0, y0=e)]
    if which == 3:                                                # on / behind a wall, a non-parallel stream
        return [SymmetryWall(yw=0.0), Source(m=1.0, y0=float(rng.choice([0.0, -0.5, 1e-9]))),
                Uniform(V=1.0, alpha=float(rng.choice([0.0, 30.0])))]
    if which == 4:                                                # zero strengths
        return [Uniform(V=0.0), Source(m=0.0, x0=1.0), Vortex(Gamma=0.0), Doublet(mu=0.0, x0=-1.0)]
    if which == 5:                                                # hidden elements
        els = random_scene(rng, "free")
        return [e.copy(enabled=bool(rng.random() < 0.6)) for e in els]
    els = random_scene(rng, "free")                               # crowded
    for _ in range(int(rng.integers(6, 14))):
        x, y = _point(rng, 5.0)
        els.append([Source(m=_strength(rng), x0=x, y0=y), Vortex(Gamma=_strength(rng), x0=x, y0=y)][int(rng.integers(2))])
    return els


# ====================================================================== views
def fit_view(els):
    """The view Fit would show (the same rule as PlotCanvas.fit_range), shaped like the plot (3 : 2)."""
    pts = [p for e in els if e.enabled for p in e.marker_points()]
    pts = [p for p in pts if math.isfinite(p.real) and math.isfinite(p.imag)]
    if not pts:
        return DEFAULT_VIEW
    xs, ys = [p.real for p in pts], [p.imag for p in pts]
    span = max(max(xs) - min(xs), max(ys) - min(ys))
    pad = max(2.5, 0.6 * span)
    (x0, x1), (y0, y1) = (min(xs) - pad, max(xs) + pad), (min(ys) - pad, max(ys) + pad)
    cx, cy, w = 0.5 * (x0 + x1), 0.5 * (y0 + y1), max(x1 - x0, 1.5 * (y1 - y0))
    return (cx - w / 2, cx + w / 2), (cy - w / 3, cy + w / 3)


def scaled(view, factor, rng=None):
    (x0, x1), (y0, y1) = view
    w, h = x1 - x0, y1 - y0
    if rng is None:
        cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
    else:
        cx, cy = x0 + w * float(rng.uniform(0.2, 0.8)), y0 + h * float(rng.uniform(0.2, 0.8))
    return (cx - factor * w / 2, cx + factor * w / 2), (cy - factor * h / 2, cy + factor * h / 2)


def panned(view, fx, fy):
    (x0, x1), (y0, y1) = view
    w, h = x1 - x0, y1 - y0
    return (x0 + fx * w, x1 + fx * w), (y0 + fy * h, y1 + fy * h)


def box(view):
    (x0, x1), (y0, y1) = view
    return (x0, x1, y0, y1)


# ====================================================================== the checks of one scene
class Findings:
    """What went wrong in one scene: [(check, view, message, detail)]."""

    def __init__(self):
        self.items = []
        self.counts = {c: [0, 0] for c in CHECKS}            # check -> [run, failed]

    def ran(self, check):
        self.counts[check][0] += 1

    def fail(self, check, view, message, detail=""):
        self.counts[check][1] += 1
        self.items.append((check, view, message, detail))


def _typical_speed(els, flows, view, v_scene):
    """A speed scale of the view: the median |V| of its fluid — but not below 1e-6 × the flow round the
    elements (far down a closed channel the flow dies out like e^(−πx/H): a median there is ~1e-50)."""
    (x0, x1), (y0, y1) = view
    X, Y = np.meshgrid(np.linspace(x0, x1, 31), np.linspace(y0, y1, 21))
    z = (X + 1j * Y).ravel()
    with np.errstate(all="ignore"):
        sp = np.abs(complex_velocity(flows, z))
    ok = np.isfinite(sp) & fluid_mask(els, z)
    return max(float(np.median(sp[ok])) if ok.any() else 0.0, 1e-6 * v_scene)


def _guard(f, check, view, fn):
    """Run fn(); an exception is a no-crash failure (with the traceback). Returns fn()'s result or None."""
    f.ran("no-crash")
    try:
        return fn()
    except Exception as exc:                                     # noqa: BLE001 - that is what we look for
        f.fail("no-crash", view, f"{check}: {type(exc).__name__}: {exc}", traceback.format_exc())
        return None


def check_scene_physics(els, rng, f: Findings, quick=False):
    """Every check of PART 1 for one scene (see the module text)."""
    issues = _guard(f, "scene check", "-", lambda: check_scene(els))
    if not active(els):
        return "skipped"
    if issues is None or any(s.severity == "error" for s in issues):
        _compute_only(els, rng, f, quick)
        return "invalid"
    flows = resolve(active(els))
    v_scene = _scene_speed(active(els), flows, np.array(singular_points(els), complex))
    fit = fit_view(els)
    views = {"fit": fit, "closer": scaled(fit, 0.02, rng), "wider": scaled(fit, 100.0), "panned": panned(fit, 0.6, -0.3)}
    if quick:
        views = {"fit": fit, "closer": views["closer"]}
    results = {}
    for name, view in views.items():
        cache = StreamlineCache(tuple(active(els)), 1.0)
        res = _guard(f, "streamlines", name, lambda: cache.update(view, 1.0, force=True))
        if res is None:
            continue
        results[name] = res
        W = view[0][1] - view[0][0]
        v_typ = _typical_speed(els, flows, view, v_scene)
        _guard(f, "flow features", name, lambda: flow_features(els, box(view), scale=W))
        _guard(f, "field grid", name, lambda: compute_field(els, view[0], view[1], 60, 40))
        _guard(f, "travel times", name, lambda: travel_times(res.lines[:40], els, 0.01 * W, 1e-3 * max(v_typ, 1e-12)))
        pts = _guard(f, "stagnation points", name, lambda: find_stagnation_points(els, box(view), scale=W))
        if pts and v_typ > 0:
            f.ran("stagnation")
            z = np.array([p.z for p in pts if p.kind != "vertex"], complex)
            if z.size:
                with np.errstate(all="ignore"):
                    sp = np.abs(complex_velocity(flows, z)) / v_typ
                bad = np.nonzero(~(sp < TOL["stagnation"]))[0]
                if bad.size:
                    k = int(bad[0])
                    f.fail("stagnation", name, f"|V|/V_typ = {sp[k]:.2e} at a stagnation point ({z[k].real:.6g}, "
                                               f"{z[k].imag:.6g}) (tolerance {TOL['stagnation']:g})")
        if v_typ > 0 and res.lines:
            _check_lines(els, flows, res, view, name, v_typ, f)
    if "fit" in results:
        res = results["fit"]
        _check_crossings(els, res, "fit", f)
        _check_bodies_zoom(els, res, fit, rng, f)
        _check_save_open(els, fit, f)
        _check_particles(els, res, fit, f)
    _check_forces(els, f)
    return "valid"


def _compute_only(els, rng, f, quick):
    """A scene with errors is still drawn by the window: everything it computes must end without an exception
    (and in time — the slow check around the scene). Accuracy is not checked: it does not hold there."""
    fit = fit_view(els)
    views = {"fit": fit} if quick else {"fit": fit, "closer": scaled(fit, 0.02, rng)}
    for name, view in views.items():
        W = view[0][1] - view[0][0]
        res = _guard(f, "streamlines", name, lambda: StreamlineCache(tuple(active(els)), 1.0).update(view, 1.0, force=True))
        _guard(f, "stagnation points", name, lambda: find_stagnation_points(els, box(view), scale=W))
        _guard(f, "field grid", name, lambda: compute_field(els, view[0], view[1], 60, 40))
        if res is not None:
            bmap = _guard(f, "solid bodies", name, lambda: _map(els, view, res))
            _guard(f, "travel times", name, lambda: travel_times(res.lines[:40], els, 0.01 * W, 1e-9))
            _guard(f, "particles", name, lambda: _moved_particles(els, view, bmap))
    surfs = _guard(f, "body surfaces", "scene", lambda: body_surfaces(els))
    for srf in surfs or []:
        _guard(f, "pressure force", srf.name, lambda: pressure_force(srf, els, reference_speed(els) or 1.0))


def _moved_particles(els, view, bmap, count=600, steps=40):
    """Tracer particles as the Particles mode moves them: 40 frames of 1/30 s."""
    p = Particles(count, seed=1)
    p.set_scene(els)
    p.set_view(box(view), restart=True)
    if bmap is not None:
        p.set_excluded(bmap.contains)
    for _ in range(steps):
        p.step(1 / 30)
    return p


def _away(els, z, view, res):
    """Points far enough from singular points and stagnation points for the line checks."""
    W = view[0][1] - view[0][0]
    keep = np.ones(z.shape, bool)
    r_sing = max(3.0 * res.separation, 0.01 * W)
    for s in singular_points(els):
        keep &= np.abs(z - s) > r_sing
    for p in res.stagnation:
        keep &= np.abs(z - p.z) > max(1.0 * res.separation, 0.005 * W)
    keep &= fluid_mask(els, z)
    return keep


def _check_lines(els, flows, res, view, name, v_typ, f):
    (x0, x1), (y0, y1) = view
    worst_angle, where = 0.0, None
    worst_psi, psi_where = 0.0, None
    has_cut = any(e.TYPE in ("source", "sector") for e in active(els))
    for ln in res.lines:
        if len(ln) < 3:
            continue
        z = ln[:, 0] + 1j * ln[:, 1]
        inside = (z.real > x0) & (z.real < x1) & (z.imag > y0) & (z.imag < y1)
        if not inside.any():
            continue
        mid, d = 0.5 * (z[1:] + z[:-1]), np.diff(z)
        keep = _away(els, mid, view, res) & (np.abs(d) > 0) & inside[1:] & inside[:-1]
        if not keep.any():
            continue
        with np.errstate(all="ignore"):
            v = np.conj(complex_velocity(flows, mid[keep]))
            ok = np.abs(v) > 0.05 * v_typ
            ang = np.degrees(np.abs(np.angle(d[keep][ok] / v[ok]))) if ok.any() else np.zeros(0)
        ang = np.minimum(ang, 180.0 - ang) if ang.size else ang          # a line may be stored either way round
        if ang.size and float(ang.max()) > worst_angle:
            k = int(np.argmax(ang))
            worst_angle, where = float(ang.max()), mid[keep][ok][k]
        if not has_cut:
            zk = z[inside & _away(els, z, view, res)]
            if zk.size >= 3:
                with np.errstate(all="ignore"):
                    psi = complex_potential(els, zk).imag
                    sp = np.abs(complex_velocity(flows, zk))
                good = np.isfinite(psi) & (sp > 0.05 * v_typ)
                if good.sum() >= 3:                               # distance from the line's own ψ level
                    off = np.abs(psi[good] - np.median(psi[good])) / sp[good] / res.separation
                    k = int(np.argmax(off))
                    if off[k] > worst_psi:
                        worst_psi, psi_where = float(off[k]), zk[good][k]
    f.ran("tangent")
    if worst_angle > TOL["tangent_deg"]:
        f.fail("tangent", name, f"a drawn streamline is {worst_angle:.2f}° off the velocity at "
                                f"({where.real:.6g}, {where.imag:.6g}) (tolerance {TOL['tangent_deg']}°)")
    if not has_cut:
        f.ran("psi")
        if worst_psi > TOL["psi"]:
            f.fail("psi", name, f"a streamline strays {100 * worst_psi:.2f} % of the line spacing from its ψ level "
                                f"at ({psi_where.real:.6g}, {psi_where.imag:.6g}) (tolerance {100 * TOL['psi']:g} %)")


def _segments_cross(a, b, c, d):
    """Do the segments a–b and c–d cross properly (complex end points)? Touching ends do not count."""
    def orient(p, q, r):
        return ((q - p).conjugate() * (r - p)).imag
    o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    return o1 * o2 < 0 and o3 * o4 < 0


def _check_crossings(els, res, name, f, max_hits=3):
    """No two drawn streamlines cross: segments of different lines in the same grid cell are tested."""
    f.ran("crossing")
    cell = max(res.separation, 1e-12)
    grid = {}
    segs = []
    for li, ln in enumerate(res.lines):
        z = ln[:, 0] + 1j * ln[:, 1]
        for k in range(len(z) - 1):
            a, b = z[k], z[k + 1]
            if not (np.isfinite(a) and np.isfinite(b)):
                continue
            i = len(segs)
            segs.append((li, a, b))
            for cx in range(int(math.floor(min(a.real, b.real) / cell)), int(math.floor(max(a.real, b.real) / cell)) + 1):
                for cy in range(int(math.floor(min(a.imag, b.imag) / cell)), int(math.floor(max(a.imag, b.imag) / cell)) + 1):
                    grid.setdefault((cx, cy), []).append(i)
    if len(segs) > 400_000:
        return                                                    # (too many for this check: skipped)
    avoid = [p.z for p in res.stagnation] + list(singular_points(els))
    r = 1.5 * res.separation
    seen, hits = set(), []
    for members in grid.values():
        if len(members) < 2:
            continue
        for ii in range(len(members)):
            li, a, b = segs[members[ii]]
            for jj in range(ii + 1, len(members)):
                lj, c, d = segs[members[jj]]
                if li == lj or (members[ii], members[jj]) in seen:
                    continue
                seen.add((members[ii], members[jj]))
                if _segments_cross(a, b, c, d):
                    m = 0.5 * (a + b)
                    if all(abs(m - p) > r for p in avoid) and bool(fluid_mask(els, np.array([m]))[0]):
                        hits.append(m)
                        if len(hits) >= max_hits:
                            break
    if hits:
        f.fail("crossing", name, f"{len(hits)}+ crossing of two streamlines, e.g. at ({hits[0].real:.6g}, "
                                 f"{hits[0].imag:.6g})")


def _map(els, view, res, shape=(160, 240)):
    hint = (scene_map(els, res) or None) if res.scene_dividing else None
    return body_map(els, box(view), shape, list(res.dividing) + list(res.inner), hint=hint)


def _check_bodies_zoom(els, res_fit, fit, rng, f):
    """The bodies of the Fit view and of a view 4× closer agree where both see them (not right at an edge)."""
    if not any(e.TYPE in ("source", "doublet") for e in active(els)):
        return
    f.ran("bodies-zoom")
    closer = scaled(fit, 0.25, rng)
    res_c = StreamlineCache(tuple(active(els)), 1.0).update(closer, 1.0, force=True)
    a = _map(els, fit, res_fit)
    b = _map(els, closer, res_c)
    (x0, x1), (y0, y1) = closer
    z = (x0 + (x1 - x0) * rng.random(3000)) + 1j * (y0 + (y1 - y0) * rng.random(3000))
    z = z[fluid_mask(els, z)]
    if not z.size:
        return
    in_a = a.contains(z) if a is not None else np.zeros(z.size, bool)
    in_b = b.contains(z) if b is not None else np.zeros(z.size, bool)
    # within 3 pixels of the coarse map from an edge of EITHER map: an edge (a body thinner than that — the far
    # tail of a half-body — is absorbed by the coarse map on purpose, and shows when zoomed in)
    px = (fit[0][1] - fit[0][0]) / 240.0 * 3.0
    edge = np.zeros(z.size, bool)
    for m, inside in ((a, in_a), (b, in_b)):
        if m is not None:
            for dz in (px, -px, 1j * px, -1j * px):
                edge |= m.contains(z + dz) != inside
    diff = (in_a != in_b) & ~edge
    share = float(diff.mean())
    if share > TOL["bodies"]:
        k = int(np.argmax(diff))
        f.fail("bodies-zoom", "fit / 4× closer", f"{100 * share:.1f} % of the points are body in one view and fluid "
                                                 f"in the other, e.g. ({z[k].real:.6g}, {z[k].imag:.6g})")


def _check_forces(els, f):
    """Closed bodies alone in a uniform stream: lift = −V∞Γ, drag = 0 (per unit ρ)."""
    if any(e.TYPE in ("wall", "sector") for e in active(els)):
        return
    surfs = _guard(f, "body surfaces", "scene", lambda: body_surfaces(els))
    if not surfs:
        return
    v_inf = reference_speed(els)
    for s in surfs:
        if not (s.closed and s.alone) or not v_inf:
            continue
        force = _guard(f, "pressure force", "scene", lambda: pressure_force(s, els, v_inf))
        if force is None:
            continue
        f.ran("forces")
        kj = -v_inf * s.gamma
        scale = max(1.0, abs(kj))
        if abs(force.lift - kj) > TOL["force"] * scale or abs(force.drag) > TOL["force"] * scale:
            f.fail("forces", s.name, f"L′/ρ = {force.lift:.6g} vs −V∞Γ = {kj:.6g}, D′/ρ = {force.drag:.3g} "
                                     f"(tolerance {100 * TOL['force']:g} % of max(1, |V∞Γ|))")


def _check_save_open(els, view, f):
    f.ran("save-open")
    try:
        back = loads(dumps(SceneDocument(list(els), "random", view)), "random")
    except Exception as exc:                                     # noqa: BLE001
        f.fail("save-open", "-", f"cannot save / open: {type(exc).__name__}: {exc}", traceback.format_exc())
        return
    a, b = [_element_to_data(e) for e in els], [_element_to_data(e) for e in back.elements]
    if a != b or back.view != view:
        f.fail("save-open", "-", "the reopened scene differs (elements or view)")
        return
    la = StreamlineCache(tuple(active(els)), 1.0).update(view, force=True).lines
    lb = StreamlineCache(tuple(active(back.elements)), 1.0).update(view, force=True).lines
    if len(la) != len(lb) or any(p.shape != q.shape or not np.array_equal(p, q) for p, q in zip(la, lb)):
        f.fail("save-open", "-", "the reopened scene gives other streamlines")


def _check_particles(els, res, view, f):
    f.ran("particles")
    bmap = _map(els, view, res)
    p = _moved_particles(els, view, bmap)
    keep = ~p.fresh & np.isfinite(p.pos)
    if not keep.any():
        return
    # a new particle gets 16 tries to land in the fluid: with only a share f of the view in the fluid, about
    # (1 − f)^16 of them land in a body anyway (a view almost all inside a body) — that is allowed
    (x0, x1), (y0, y1) = view
    g = (x0 + (x1 - x0) * np.random.default_rng(2).random(4000)) + 1j * (y0 + (y1 - y0) * np.random.default_rng(3).random(4000))
    free = fluid_mask(els, g) & ~(bmap.contains(g) if bmap is not None else np.zeros(g.size, bool))
    allowed = max(TOL["particles"], 3.0 * (1.0 - float(free.mean())) ** 16)
    z = p.pos[keep]
    outside = ~fluid_mask(els, z)
    in_body = np.zeros(z.size, bool)
    if bmap is not None:                                          # deeper than 3 pixels of the map: a real miss
        px = 3.0 * (view[0][1] - view[0][0]) / 240.0
        in_body = bmap.contains(z)
        for dz in (px, -px, 1j * px, -1j * px):
            in_body &= bmap.contains(z + dz)
    share = float((outside | in_body).mean())
    if share > allowed:
        k = int(np.argmax(outside | in_body))
        f.fail("particles", "fit", f"{100 * share:.2f} % of the particles are outside the fluid or inside a body, "
                                   f"e.g. ({z[k].real:.6g}, {z[k].imag:.6g})")


# ====================================================================== PART 2: the window
class _Errors(logging.Handler):
    """Collects every error: uncaught exceptions (sys.excepthook) and ERROR records of the program's log."""

    def __init__(self):
        super().__init__(logging.ERROR)
        self.items = []

    def emit(self, record):
        self.items.append(f"log: {record.getMessage()}")

    def hook(self, exc_type, exc, tb):
        self.items.append("".join(traceback.format_exception(exc_type, exc, tb)))


def gui_part(seconds, rng, out_dir, status, failures_before=0):
    """Random actions in the real window (offscreen). Returns a dict with counts and failures."""
    from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
    from PySide6.QtGui import QMouseEvent, QWheelEvent
    from PySide6.QtWidgets import QApplication, QDialog
    from app.main_window import MainWindow
    from app.scene import list_presets
    from app.theme import DARK, LIGHT
    app = QApplication.instance()
    errors = _Errors()
    logging.getLogger(LOGGER).addHandler(errors)
    old_hook = sys.excepthook
    sys.excepthook = errors.hook
    MainWindow.START_SCENE = None
    win = MainWindow()
    win._ask_save_changes = lambda: "discard"
    win._notify_user = lambda kind, title, text: errors.items.append(f"message box: {title}: {text}") \
        if kind == "warning" else None
    win._run_dialog = lambda dlg: True
    old_exec = QDialog.exec
    QDialog.exec = lambda dlg: QDialog.Rejected                   # (a double click must not open a modal dialog)
    win.resize(1536, 830)
    win.show()
    presets = [p for _g, items in list_presets() for p in items]
    tmp = tempfile.mkdtemp(prefix="flowy-random-")
    stats = {"actions": 0, "by_action": {}, "undo_checks": 0, "failures": []}

    def pump(s=0.05):
        """Events for s seconds, then until the background computation is done. False: still computing
        after TOL['slow_window_s'] (it goes on in the background; the test goes on too)."""
        t = time.perf_counter()
        while time.perf_counter() - t < s:
            app.processEvents()
        t = time.perf_counter()
        idle = False
        while not idle and time.perf_counter() - t < TOL["slow_window_s"]:
            idle = win.canvas.wait_idle(500)
            app.processEvents()
        app.processEvents()
        return idle

    def snapshot():
        return [_element_to_data(e) for e in win.elements]

    def random_element(kind=None):
        kind = kind or rng.choice(["uniform", "source", "vortex", "doublet", "wall", "sector"])
        x, y = _point(rng)
        th = float(rng.choice([0.0, 90.0, rng.uniform(-180, 180)]))
        return {"uniform": lambda: Uniform(V=float(rng.uniform(0.2, 3)), alpha=th),
                "source": lambda: Source(m=_strength(rng), x0=x, y0=y),
                "vortex": lambda: Vortex(Gamma=_strength(rng, 0.3, 8), x0=x, y0=y),
                "doublet": lambda: Doublet(mu=float(rng.uniform(0.2, 3)), x0=x, y0=y, delta=th),
                "wall": lambda: SymmetryWall(xw=x, yw=y, theta_w=th, side=int(rng.integers(2))),
                "sector": lambda: SectorFlow(V=1.0, x0=x, y0=y, theta1=th,
                                             theta2=th + float(rng.choice([90, 180, 360, rng.uniform(20, 360)])))}[kind]()

    vp = win.canvas.plot.viewport()

    def vp_point(x, y):
        """Data point → viewport pixel."""
        return QPointF(win.canvas.plot.mapFromScene(win.canvas.vb.mapViewToScene(QPointF(x, y))))

    def random_pixel():
        return QPointF(float(rng.uniform(0.05, 0.95)) * vp.width(), float(rng.uniform(0.05, 0.95)) * vp.height())

    def mouse(kind, pos, buttons):
        app.sendEvent(vp, QMouseEvent(kind, pos, QPointF(vp.mapToGlobal(pos.toPoint())), Qt.LeftButton, buttons,
                                      Qt.NoModifier))

    def mouse_drag(a, b, steps):
        """Press, move in steps without waiting, release — a fast hand (after a pause: never a double click)."""
        t = time.perf_counter()
        while time.perf_counter() - t < 0.45:
            app.processEvents()
        mouse(QEvent.MouseButtonPress, a, Qt.LeftButton)
        for k in range(1, steps + 1):
            mouse(QEvent.MouseMove, a + (b - a) * (k / steps), Qt.LeftButton)
            app.processEvents()
        mouse(QEvent.MouseButtonRelease, b, Qt.NoButton)
        app.processEvents()

    def act_add():
        win.model.add(random_element())

    def act_edit():
        if win.elements:
            i = int(rng.integers(len(win.elements)))
            e = win.elements[i]
            p = e.PARAMS[int(rng.integers(len(e.PARAMS)))]
            if p.choices:
                v = int(rng.integers(len(p.choices)))
            else:
                v = float(getattr(e, p.key)) * float(rng.uniform(0.5, 1.5)) + float(rng.normal(0, 0.3))
                v = min(max(v, p.minimum), p.maximum)
            win.model.replace(i, e.copy(**{p.key: v}))

    def act_move():
        movable = [i for i, e in enumerate(win.elements) if e.POSITION_KEYS]
        if movable:
            i = int(rng.choice(movable))
            e = win.elements[i]
            kx, ky = e.POSITION_KEYS
            for _ in range(int(rng.integers(1, 6))):              # a drag: several small moves, one undo step
                e = e.copy(**{kx: getattr(e, kx) + float(rng.normal(0, 0.3)), ky: getattr(e, ky) + float(rng.normal(0, 0.3))})
                win.model.replace(i, e, merge_key="move")

    def act_hide():
        if win.elements:
            i = int(rng.integers(len(win.elements)))
            win.model.set_enabled(i, not win.elements[i].enabled)

    def act_delete():
        if win.elements:
            win.delete_element(int(rng.integers(len(win.elements))))

    def act_undo_redo():
        for _ in range(int(rng.integers(1, 4))):
            (win.model_undo if rng.random() < 0.6 else win.model_redo)()

    def act_preset():
        if presets:
            win.load_preset(presets[int(rng.integers(len(presets)))])

    def act_clear():
        win.clear_all()

    def act_layer():
        boxes = win.settings_panel.layer_boxes
        key = list(boxes)[int(rng.integers(len(boxes)))]
        boxes[key].setChecked(not boxes[key].isChecked())

    def act_view_mode():
        mode = str(rng.choice(["static", "particles", "pulses"]))
        win.canvas.set_view_mode(mode)
        if mode != "static":
            for _ in range(int(rng.integers(5, 40))):
                win.canvas.animation.advance(1 / 30)

    def act_zoom():
        cv = win.canvas
        r = rng.random()
        if r < 0.15:                                              # to a limit, then back
            lo, hi = cv.scene_zoom_limits()
            w = lo * 1.01 if rng.random() < 0.5 else hi * 0.99
            (x0, x1), (y0, y1) = cv.view()
            cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
            cv.set_view((cx - w / 2, cx + w / 2), (cy - w / 3, cy + w / 3))
        elif r < 0.3:
            cv.fit_view()
        else:
            cv.set_view(*scaled(cv.view(), float(math.exp(rng.uniform(-2.5, 2.5))), rng))
        if cv.animated:
            for _ in range(5):
                cv.animation.advance(1 / 30)

    def act_pan():
        win.canvas.set_view(*panned(win.canvas.view(), float(rng.uniform(-1, 1)), float(rng.uniform(-1, 1))))

    def act_theme():
        win.apply_theme(DARK if win.theme is LIGHT else LIGHT)

    def act_slider():
        sl = win.settings_panel.sliders
        key = list(sl)[int(rng.integers(len(sl)))]
        s = sl[key]
        s.setValue(int(rng.integers(s.minimum(), s.maximum() + 1)))

    def act_beaver():
        b = win.beaver
        r = b.plot_rect()
        b.state = "held"
        b.drop(r.center())
        for _ in range(int(rng.integers(10, 80))):
            b.advance(1 / 30)

    def act_export():
        from app.export import export_data, render_figure
        cv = win.canvas
        fmt = str(rng.choice(["png", "svg", "csv"]))
        path = os.path.join(tmp, f"export.{fmt}")
        if fmt == "csv":
            export_data(path, ["elements", "stagnation", "streamlines"], win.elements, cv.view(), cv.stagnation_points,
                        cv.last_result.lines if cv.last_result else [], cv.settings.cp_reference, 41, ",", None)
        else:
            render_figure(cv, path, fmt, 1.0, "paper")

    def act_wheel_burst():
        c = random_pixel()
        notch = int(rng.choice([120, -120]))
        for _ in range(int(rng.integers(5, 81))):                # mostly one way, now and then back
            d = notch if rng.random() < 0.85 else -notch
            app.sendEvent(vp, QWheelEvent(c, QPointF(vp.mapToGlobal(c.toPoint())), QPoint(0, 0), QPoint(0, d),
                                          Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False))
            app.processEvents()

    def act_pan_drag():
        win.canvas.set_mode("pan")
        mouse_drag(random_pixel(), random_pixel(), int(rng.integers(2, 41)))
        win.canvas.set_mode("select")

    def act_drag_element():
        (x0, x1), (y0, y1) = win.canvas.view()
        seen = [e for e in win.elements if e.POSITION_KEYS and x0 < getattr(e, e.POSITION_KEYS[0]) < x1
                and y0 < getattr(e, e.POSITION_KEYS[1]) < y1]
        if not seen:
            return act_move()
        e = seen[int(rng.integers(len(seen)))]
        win.canvas.set_mode("move")
        mouse_drag(vp_point(getattr(e, e.POSITION_KEYS[0]), getattr(e, e.POSITION_KEYS[1])), random_pixel(),
                   int(rng.integers(2, 41)))
        win.canvas.set_mode("select")

    def act_wall_storm():
        for _ in range(int(rng.integers(2, 4))):
            win.model.add(random_element("wall"))
            app.processEvents()
        if rng.random() < 0.5:
            win.model.add(random_element("uniform"))

    def act_mode_flip():
        for _ in range(int(rng.integers(4, 13))):
            win.canvas.set_view_mode(str(rng.choice(["static", "particles", "pulses"])))
            for _ in range(int(rng.integers(0, 6))):
                if win.canvas.animated:
                    win.canvas.animation.advance(1 / 30)
            app.processEvents()

    def act_save_open():
        path = os.path.join(tmp, "scene.pflow")
        before = snapshot()
        if win._write(path) and win.open_scene(path):
            if snapshot() != before:
                stats["failures"].append({"check": "save-open (window)", "message": "the reopened scene differs"})

    actions = {"add": (act_add, 6), "edit": (act_edit, 5), "move": (act_move, 4), "hide": (act_hide, 2),
               "delete": (act_delete, 3), "undo/redo": (act_undo_redo, 4), "preset": (act_preset, 2),
               "clear": (act_clear, 1), "layer": (act_layer, 4), "view mode": (act_view_mode, 3),
               "zoom": (act_zoom, 4), "pan": (act_pan, 2), "theme": (act_theme, 1), "slider": (act_slider, 2),
               "beaver": (act_beaver, 1), "export": (act_export, 1), "save/open": (act_save_open, 1),
               "wheel burst": (act_wheel_burst, 3), "pan drag": (act_pan_drag, 2), "drag element": (act_drag_element, 3),
               "wall storm": (act_wall_storm, 2), "mode flip": (act_mode_flip, 1)}
    names = list(actions)
    weights = np.array([w for _f, w in actions.values()], float)
    weights /= weights.sum()
    t0 = time.perf_counter()
    try:
        pump(1.0)
        while time.perf_counter() - t0 < seconds:
            # one sequence: from a known scene, 6–20 actions, then undo all / redo all must give back exactly
            win.model.reset([random_element() for _ in range(int(rng.integers(0, 4)))])
            pump()
            start, seq = snapshot(), []
            for _ in range(int(rng.integers(6, 21))):
                name = str(rng.choice(names, p=weights))
                if name == "undo/redo" or name == "save/open":
                    name = "edit"                                # (inside a sequence: the history must stay intact)
                n_before = len(errors.items)
                idle = True
                t_act = time.perf_counter()
                status.set("window", f"action {stats['actions'] + 1}: {name}",
                           failures=failures_before + len(stats["failures"]))
                try:
                    actions[name][0]()
                    if rng.random() < 0.3:                       # the next action while it still computes
                        app.processEvents()
                    else:
                        idle = pump()
                except Exception as exc:                         # noqa: BLE001
                    errors.items.append(f"{name}: {type(exc).__name__}: {exc}\n{traceback.format_exc()}")
                stats["actions"] += 1
                stats["by_action"][name] = stats["by_action"].get(name, 0) + 1
                seq.append(name)
                if not idle:                                     # the scene now (saved before waiting longer)
                    k = _gui_failure(stats, out_dir, win, "slow (window)", f"still computing {TOL['slow_window_s']:g} s "
                                     f"after '{name}'", "", seq)
                    done = False                                 # wait for its end (≤ 10 min): the next actions
                    while not done and time.perf_counter() - t_act < 600:     # would all be slow behind it
                        done = win.canvas.wait_idle(1000)
                        app.processEvents()
                    took = time.perf_counter() - t_act
                    stats["failures"][k]["message"] = (f"the window computed {took:.0f} s after '{name}'" if done else
                                                       f"the window still computed after {took:.0f} s ('{name}'): a hang?")
                if len(errors.items) > n_before:
                    _gui_failure(stats, out_dir, win, "no-crash (window)", f"after '{name}'",
                                 "\n\n".join(errors.items[n_before:]), seq)
            pump()
            end = snapshot()
            n_before = len(errors.items)
            status.set(item="undo all / redo all")
            while win.model.can_undo:
                win.model.undo()
            pump()
            stats["undo_checks"] += 1
            if snapshot() != start:
                _gui_failure(stats, out_dir, win, "undo", "undo all the way back did not give the start scene", "", seq)
            while win.model.can_redo:
                win.model.redo()
            pump()
            if snapshot() != end:
                _gui_failure(stats, out_dir, win, "redo", "redo all the way did not give the end scene", "", seq)
            if len(errors.items) > n_before:
                _gui_failure(stats, out_dir, win, "no-crash (window)", "during undo / redo",
                             "\n\n".join(errors.items[n_before:]), seq)
            # the actions that are not model commands, between sequences
            for name in ("undo/redo", "save/open"):
                n_before = len(errors.items)
                try:
                    actions[name][0]()
                    pump()
                except Exception as exc:                         # noqa: BLE001
                    errors.items.append(f"{name}: {type(exc).__name__}: {exc}\n{traceback.format_exc()}")
                stats["actions"] += 1
                stats["by_action"][name] = stats["by_action"].get(name, 0) + 1
                if len(errors.items) > n_before:
                    _gui_failure(stats, out_dir, win, "no-crash (window)", f"after '{name}'",
                                 "\n\n".join(errors.items[n_before:]), seq + [name])
    finally:
        QDialog.exec = old_exec
        sys.excepthook = old_hook
        logging.getLogger(LOGGER).removeHandler(errors)
        win.model.mark_clean()
        win.hide()                     # (not closed: close() waits for a computation still running; run() ends
        app.processEvents()            #  the process with os._exit once the report is written)
    return stats


def _gui_failure(stats, out_dir, win, check, message, detail, seq):
    k = len(stats["failures"]) + 1
    stem = os.path.join(out_dir, "failures", f"window-{k:03d}-{check.split()[0]}")
    try:
        save_scene(stem + ".pflow", SceneDocument(list(win.elements), f"window failure {k}", win.canvas.view()))
    except Exception:                                            # noqa: BLE001
        pass
    with open(stem + ".txt", "w", encoding="utf-8") as fh:
        fh.write(f"{check}: {message}\nactions of this sequence: {', '.join(seq)}\n\n{detail}\n")
    stats["failures"].append({"check": check, "message": message, "actions": list(seq), "file": os.path.basename(stem)})
    return len(stats["failures"]) - 1


# ====================================================================== running, the report
def _settings_sandbox():
    """Qt's test folders and a temporary settings file: the user's settings and data are never touched."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QSettings, QStandardPaths, qInstallMessageHandler
    from PySide6.QtWidgets import QApplication
    QStandardPaths.setTestModeEnabled(True)
    qInstallMessageHandler(lambda mode, ctx, msg: None if "propagateSizeHints" in msg else print(msg))
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, tempfile.mkdtemp(prefix="flowy-random-settings-"))
    app = QApplication.instance() or QApplication([sys.argv[0]])
    from app.startup import setup_application
    setup_application(app)
    QSettings().setValue("beaver/tour_offered", True)
    QSettings().setValue("beaver/enabled", True)
    return app


class _Watchdog:
    """A scene that does not end (a hang) would leave nothing behind: after TOL['slow_scene_s'] its elements are
    written to failures/RUNNING-slow.txt / .pflow at once (removed again when the scene ends after all; then the
    slow check records it as usual). If the test seems stuck: Ctrl+C and send the folder."""

    def __init__(self, out_dir):
        self.stem = os.path.join(out_dir, "failures", "RUNNING-slow")
        self.job, self.lock = None, threading.Lock()
        threading.Thread(target=self._run, name="random-test-watchdog", daemon=True).start()

    def start(self, kind, seed, els):
        with self.lock:
            self.job = [kind, seed, list(els), time.perf_counter(), False]

    def stop(self):
        with self.lock:
            written, self.job = self.job and self.job[4], None
        if written:
            for ext in (".txt", ".pflow"):
                try:
                    os.remove(self.stem + ext)
                except OSError:
                    pass

    def _run(self):
        while True:
            time.sleep(2.0)
            with self.lock:
                job = self.job
                if not job or job[4] or time.perf_counter() - job[3] < TOL["slow_scene_s"]:
                    continue
                job[4] = True
            kind, seed, els = job[:3]
            try:
                save_scene(self.stem + ".pflow", SceneDocument(els, f"random {kind} {seed} (still running)", fit_view(els)))
            except Exception:                                    # noqa: BLE001
                pass
            with open(self.stem + ".txt", "w", encoding="utf-8") as fh:
                fh.write(f"still running after {TOL['slow_scene_s']:g} s\nkind: {kind}\nscene seed: {seed}\n\nelements:\n")
                for e in els:
                    fh.write(f"  {_element_to_data(e)}\n")


def _bar(frac, width=20):
    n = int(round(min(max(frac, 0.0), 1.0) * width))
    return "[" + "#" * n + "." * (width - n) + "]"


def _clock(seconds):
    m, s = divmod(int(max(seconds, 0)), 60)
    return f"{m}:{s:02d}"


class _Status:
    """The one line that shows what the test does, rewritten every second by a thread of its own: its clock keeps
    moving while a long scene is computed, so a still-moving line means still working. One thing busy for
    STACK_AFTER_S: where every thread is right then goes to failures/STACK-….txt (where it hangs)."""

    WIDTH = 116                                                   # (a longer line would wrap and break the \r)
    STACK_AFTER_S = 120.0

    def __init__(self, total_s, out_dir):
        self.t0, self.total, self.out_dir = time.perf_counter(), total_s, out_dir
        self.phase, self.item, self.t_item, self.failures = "start", "", self.t0, 0
        self.dumped = None                                        # t_item of the last stack written
        self._stop = threading.Event()
        threading.Thread(target=self._run, name="random-test-status", daemon=True).start()

    def set(self, phase=None, item=None, failures=None):
        if phase is not None:
            self.phase = phase
        if item is not None and item != self.item:
            self.item, self.t_item = item, time.perf_counter()
        if failures is not None:
            self.failures = failures

    def _run(self):
        while not self._stop.wait(1.0):
            self.show()
            t_item = self.t_item
            if time.perf_counter() - t_item > self.STACK_AFTER_S and self.dumped != t_item:
                self.dumped = t_item
                self._write_stacks()

    def _write_stacks(self):
        names = {t.ident: t.name for t in threading.enumerate()}
        path = os.path.join(self.out_dir, "failures", f"STACK-{datetime.datetime.now():%H%M%S}.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"{self.phase}: {self.item} — busy for {time.perf_counter() - self.t_item:.0f} s\n")
            for ident, frame in sys._current_frames().items():
                fh.write(f"\n--- thread {names.get(ident, ident)}\n{''.join(traceback.format_stack(frame))}")

    def show(self):
        now = time.perf_counter()
        gone = now - self.t0
        left = self.total - gone
        end = (datetime.datetime.now() + datetime.timedelta(seconds=max(left, 0))).strftime("%H:%M")
        busy = now - self.t_item
        when = f"~{_clock(left)} left (ends ~{end})" if left > 0 else "finishing the last one"
        line = (f"{self.phase:<7} {_bar(gone / self.total)} {min(100, 100 * gone / self.total):3.0f} %  "
                f"{_clock(gone)} gone, {when}  failures {self.failures}  | {self.item}"
                + (f" — working {busy:.0f} s" if busy >= 10 else ""))
        print("\r" + line[:self.WIDTH].ljust(self.WIDTH), end="", flush=True)

    def stop(self):
        self._stop.set()
        self.show()
        print()


def run(args):
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = os.path.abspath(args.out or os.path.join(ROOT, "random_test_results", stamp))
    os.makedirs(os.path.join(out_dir, "failures"), exist_ok=True)
    minutes = 3.0 if args.quick else float(args.minutes)
    phys_s = minutes * 60.0 * (1.0 if args.no_gui else 0.6)
    gui_s = 0.0 if args.no_gui else minutes * 60.0 * 0.4
    seed = int(args.seed)
    print(f"{APP_NAME} {APP_VERSION} — random test, seed {seed}, about {minutes:.0f} min "
          f"(physics {phys_s / 60:.0f} min, window {gui_s / 60:.0f} min)\nresults: {out_dir}\n")
    app = _settings_sandbox() if not args.no_gui else None
    from physics import warmup
    status = _Status(phys_s + gui_s, out_dir)
    status.set("prepare", "compiling the fast kernels (once per installation)")
    for _label, fn in warmup.steps():
        fn()
    t_start = time.perf_counter()
    total = {c: [0, 0] for c in CHECKS}
    by_kind = {k: {"scenes": 0, "valid": 0, "invalid": 0, "failed": 0} for k in KINDS}
    failures = []
    n = 0
    watch = _Watchdog(out_dir)
    while time.perf_counter() - t_start < phys_s:
        kind = KINDS[n % len(KINDS)]
        scene_seed = seed * 1_000_003 + n
        rng = np.random.default_rng(scene_seed)
        els = random_scene(rng, kind)
        status.set("physics", f"scene {n + 1} ({kind}, {len(els)} elements)")
        f = Findings()
        t = time.perf_counter()
        watch.start(kind, scene_seed, els)
        try:
            outcome = check_scene_physics(els, rng, f, quick=args.quick)
        except Exception as exc:                                 # noqa: BLE001 - a bug of this script or the program
            f.fail("no-crash", "-", f"{type(exc).__name__}: {exc}", traceback.format_exc())
            outcome = "valid"
        watch.stop()
        f.ran("slow")
        if time.perf_counter() - t > TOL["slow_scene_s"]:
            f.fail("slow", "-", f"the scene took {time.perf_counter() - t:.0f} s (all views and checks; tolerance "
                                f"{TOL['slow_scene_s']:g} s)")
        by_kind[kind]["scenes"] += 1
        by_kind[kind][outcome if outcome in ("valid", "invalid") else "invalid"] += 1
        for c in CHECKS:
            total[c][0] += f.counts[c][0]
            total[c][1] += f.counts[c][1]
        if f.items:
            by_kind[kind]["failed"] += 1
            failures += _save_failure(out_dir, len(failures), kind, scene_seed, els, f, time.perf_counter() - t)
        n += 1
        status.set(failures=len(failures))
    gui = None
    if gui_s > 0:
        gui = gui_part(gui_s, np.random.default_rng(seed + 1), out_dir, status, len(failures))
    status.stop()
    elapsed = time.perf_counter() - t_start
    report = {"program": f"{APP_NAME} {APP_VERSION}", "seed": seed, "minutes": round(elapsed / 60, 1),
              "computer": f"{platform.platform()} · Python {platform.python_version()} · {os.cpu_count()} threads",
              "scenes": n, "by_kind": by_kind, "checks": {c: {"run": r, "failed": fl} for c, (r, fl) in total.items()},
              "tolerances": TOL, "failures": failures, "window": gui}
    with open(os.path.join(out_dir, "results.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, default=str)
    _write_summary(out_dir, report)
    bad = len(failures) + (len(gui["failures"]) if gui else 0)
    print(f"\n{'ALL OK' if bad == 0 else f'{bad} FAILURE(S)'} — {n} scenes"
          + (f", {gui['actions']} window actions" if gui else "") + f", {elapsed / 60:.1f} min")
    print(f"Report: {os.path.join(out_dir, 'summary.md')}\nSend the folder {out_dir} to the assistant.")
    del app
    sys.stdout.flush()
    os._exit(0 if bad == 0 else 1)     # (not sys.exit: a computation still running in the window would keep it waiting)


def _save_failure(out_dir, k0, kind, scene_seed, els, f, seconds):
    out = []
    by_check = {}
    for check, view, message, detail in f.items:
        by_check.setdefault(check, []).append((view, message, detail))
    for check, items in by_check.items():
        k = k0 + len(out) + 1
        stem = os.path.join(out_dir, "failures", f"{k:04d}-{check}")
        try:
            save_scene(stem + ".pflow", SceneDocument(list(els), f"random {kind} {scene_seed} ({check})", fit_view(els)))
        except Exception:                                        # noqa: BLE001 - e.g. a NaN value: the .txt has it
            pass
        with open(stem + ".txt", "w", encoding="utf-8") as fh:
            fh.write(f"check: {check}\nkind: {kind}\nscene seed: {scene_seed}\ntime: {seconds:.1f} s\n\nelements:\n")
            for e in els:
                fh.write(f"  {_element_to_data(e)}\n")
            for view, message, detail in items:
                fh.write(f"\n[{view}] {message}\n{detail}\n")
        out.append({"check": check, "kind": kind, "seed": scene_seed, "file": os.path.basename(stem),
                    "views": [v for v, _m, _d in items], "message": items[0][1]})
    return out


def _write_summary(out_dir, r):
    lines = [f"# Random test — {r['program']}", "",
             f"- seed **{r['seed']}**, {r['minutes']} min, {r['computer']}",
             f"- scenes: **{r['scenes']}**" + (f", window actions: **{r['window']['actions']}**" if r["window"] else ""),
             "", "## Physics checks", "", "| check | run | failed |", "|---|---:|---:|"]
    for c, v in r["checks"].items():
        lines.append(f"| {c} | {v['run']} | {v['failed']} |")
    lines += ["", "## Scenes by kind", "", "| kind | scenes | valid | invalid (scene check error) | with a failure |",
              "|---|---:|---:|---:|---:|"]
    for k, v in r["by_kind"].items():
        lines.append(f"| {k} | {v['scenes']} | {v['valid']} | {v['invalid']} | {v['failed']} |")
    if r["window"]:
        w = r["window"]
        lines += ["", "## The window", "", f"- actions: {w['actions']}, undo / redo round trips: {w['undo_checks']}",
                  "- actions done: " + ", ".join(f"{k} {v}" for k, v in sorted(w["by_action"].items()))]
    fails = list(r["failures"]) + (list(r["window"]["failures"]) if r["window"] else [])
    lines += ["", f"## Failures ({len(fails)})", ""]
    if not fails:
        lines.append("None.")
    for x in fails[:200]:
        lines.append(f"- **{x['check']}** — {x.get('message', '')}  (`failures/{x.get('file', '')}`)")
    with open(os.path.join(out_dir, "summary.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def replay(path):
    """One saved scene again, every check, everything printed."""
    doc = load_scene(path)
    els = doc.elements
    print(f"{os.path.basename(path)}: {len(els)} elements")
    for e in els:
        print("  ", _element_to_data(e))
    f = Findings()
    outcome = check_scene_physics(els, np.random.default_rng(0), f)
    print(f"scene: {outcome}")
    for c in CHECKS:
        print(f"  {c:<12} run {f.counts[c][0]:>3}  failed {f.counts[c][1]}")
    for check, view, message, detail in f.items:
        print(f"\n[{check} · {view}] {message}\n{detail}")
    return 0 if not f.items else 1


def main():
    p = argparse.ArgumentParser(description="The exhaustive random test (see the text at the top of this file).")
    p.add_argument("--minutes", type=float, default=25.0, help="how long (default 25)")
    p.add_argument("--quick", action="store_true", help="~3 minutes, fewer views per scene")
    p.add_argument("--seed", type=int, default=1, help="which random scenes (default 1)")
    p.add_argument("--no-gui", action="store_true", help="only the physics part")
    p.add_argument("--out", help="the results folder (default random_test_results/<date-time>)")
    p.add_argument("--replay", metavar="FILE", help="one saved failing scene (.pflow) again, with details")
    args = p.parse_args()
    if args.replay:
        sys.exit(replay(args.replay))
    sys.exit(run(args))


if __name__ == "__main__":
    main()
