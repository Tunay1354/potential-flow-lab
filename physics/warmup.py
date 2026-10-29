"""
warmup.py — compiles (or loads from the cache) every Numba kernel once, with tiny inputs.

The streamline kernels are compiled by the first streamline computation (in the background, the window
says "Preparing…"). The others — particles, their trails, pulses, solid bodies — would otherwise be
compiled the first time the user presses Particles / Pulses or switches Solid bodies on, and the window
would stop for a second or two then (only after installing / updating; later starts load them from the
cache in milliseconds). The window calls warm_up_in_background() when the first streamlines are drawn.

The loading screen (app/splash.py, main.py) runs steps() before the window opens: the streamline engine
on the starting scene, then warm_up(); afterwards the window has nothing left to compile.
"""
from __future__ import annotations

import threading

import numpy as np

from . import kernel

_started = False


def mark_done():
    """The loading screen did it already: warm_up_in_background() has nothing to do."""
    global _started
    _started = True


def streamline_engine() -> float:
    """The streamline computation of the starting scene (lifting cylinder) as the window does it: compiles
    every kernel it uses (tracing, rasters, seeds, arrows, line ends, stagnation points). Returns ms."""
    import time

    from .elements import Doublet, Uniform, Vortex
    from .streamlines import StreamlineCache, fade_piece_boxes
    t = time.perf_counter()
    r = StreamlineCache((Uniform(), Doublet(mu=1.0), Vortex(Gamma=-2.0)), 1.0).update(((-4.0, 4.0), (-3.0, 3.0)),
                                                                                     1.0, force=True)
    fade_piece_boxes(r.lines, r.tapers, r.separation)         # the fading line ends, as the plot draws them
    return (time.perf_counter() - t) * 1000.0


def steps() -> list[tuple[str, object]]:
    """(text for the loading screen, function) — everything that is compiled, in the order it is needed."""
    if not kernel.HAVE_NUMBA:
        return []
    return [("Preparing the streamline engine…", streamline_engine),
            ("Preparing particles, pulses and solid bodies…", warm_up)]


def warm_up_in_background():
    """warm_up() in a background thread, once per program run."""
    global _started
    if _started or not kernel.HAVE_NUMBA:
        return
    _started = True
    threading.Thread(target=_quietly, name="numba-warm-up", daemon=True).start()


def _quietly():
    try:
        warm_up()
    except Exception:                                  # noqa: BLE001 - only a head start, never an error
        pass


def warm_up() -> bool:
    """Run every kernel the plot uses once (same argument types as the plot). False without Numba."""
    if not kernel.HAVE_NUMBA:
        return False
    from .bodies import body_map
    from .elements import Doublet, Uniform
    from .particles import Particles, travel_times
    scene = [Uniform(), Doublet(mu=1.0)]
    box = (-3.0, 3.0, -2.0, 2.0)
    th = np.linspace(0.0, 2.0 * np.pi, 65)
    circle = np.column_stack([np.cos(th), np.sin(th)])              # the cylinder's surface r = 1
    axis = np.column_stack([np.linspace(-3.0, -1.0, 9), np.zeros(9)])
    p = Particles(64)                                               # particles (advect, respawn)
    p.set_scene(scene)
    p.set_view(box)
    p.step(1 / 60)
    img = np.zeros((8, 8, 4), np.uint8)                             # trails and pulses
    x = np.linspace(1.0, 6.0, 4)
    kernel.fade_bytes(img.reshape(-1), 200)
    kernel.draw_segments(img, x, x, x[::-1].copy(), x, np.zeros(4, np.int64), np.ones((1, 4)), 1.0,
                         np.ones(4), False)
    for keep in (False, True):                                       # (the bands of the parallel version)
        kernel.draw_segments_rows(img, x, x, x[::-1].copy(), x, np.zeros(4, np.int64), np.ones((1, 4)), 1.0,
                                  np.ones(4), keep, 0, 4)
    travel_times([axis, circle], scene, 0.1, 1e-3)
    body_map(scene, box, (24, 36), [circle, axis])                   # solid bodies
    return True
