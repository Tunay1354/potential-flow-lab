"""
warmup.py — compiles (or loads from the cache) every Numba kernel once, with tiny inputs.

The streamline kernels are compiled by the first streamline computation (in the background, the window
says "Preparing…"). The others — particles, their trails, pulses, solid bodies — would otherwise be
compiled the first time the user presses Particles / Pulses or switches Solid bodies on, and the window
would stop for a second or two then (only after installing / updating; later starts load them from the
cache in milliseconds). The window calls warm_up_in_background() when the first streamlines are drawn.
"""
from __future__ import annotations

import threading

import numpy as np

from . import kernel

_started = False


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
    from .streamlines import StreamlineCache
    scene = [Uniform(), Doublet(mu=1.0)]
    box = (-3.0, 3.0, -2.0, 2.0)
    res = StreamlineCache(tuple(scene), 1.0).update(((box[0], box[1]), (box[2], box[3])), force=True)
    p = Particles(64)                                               # particles (advect, respawn)
    p.set_scene(scene)
    p.set_view(box)
    p.step(1 / 60)
    img = np.zeros((8, 8, 4), np.uint8)                             # trails and pulses
    x = np.linspace(1.0, 6.0, 4)
    kernel.fade_bytes(img.reshape(-1), 200)
    kernel.draw_segments(img, x, x, x[::-1].copy(), x, np.zeros(4, np.int64), np.ones((1, 4)), 1.0,
                         np.ones(4), False)
    travel_times(res.lines[:2], scene, 0.1, 1e-3)
    body_map(scene, box, (24, 36), res.dividing)                     # solid bodies
    return True
