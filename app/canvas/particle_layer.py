"""
particle_layer.py — the "Particles" view: tracer particles carried by the flow (physics.particles),
with fading trails, colored by speed.

Trails: every frame the picture fades a little (integer arithmetic that rounds down, so old trails
really disappear), then each particle's step since the last frame is drawn on top as a short line. The
trail length is how fast the picture fades. Zoom / pan start the picture again (the old trails would be
in the wrong place).
"""
import math

import numpy as np

from physics import kernel
from physics.particles import Particles

from .animation_layer import LINE_PX, MAX_STEP_PX, AnimatedLayer, speed_factor


def trail_seconds(slider: int) -> float:
    """Trail length slider 0 … 10 -> how long a trail takes to fade (0 = no trail: dots only)."""
    return 0.0 if slider <= 0 else 0.05 * 1.45 ** slider


class ParticleLayer(AnimatedLayer):
    """Style "Particles": tracer particles with fading trails."""

    def __init__(self, plot, vb):
        super().__init__(plot, vb)
        self.particles = Particles()

    def start(self):
        self.particles.set_scene(self.canvas.shown_elements())
        self.particles.set_view(self._box(), restart=True)

    def typical(self) -> float:
        return self.particles.v_typ

    # ------------------------------------------------------------------ hooks
    def scene_changed(self):
        if self.animated:
            self.particles.set_scene(self.canvas.elements)
            self._colors()

    def view_changed(self):
        if self.animated:
            self.particles.set_view(self._box())
            self._colors()
            self._clear()

    def drag_moved(self):
        if self.animated:                                     # the particles flow around the moved element
            self.particles.set_scene(self.canvas.shown_elements())

    def drag_finished(self):
        self.scene_changed()

    def set_count(self, n: int):
        self.particles.set_count(n)

    def bodies_changed(self):
        """The solid bodies changed (BodyLayer): no particles inside them."""
        bodies = self.canvas.bodies
        self.particles.set_excluded(bodies.contains if bodies.mask is not None else None)

    # ------------------------------------------------------------------ one frame
    def render(self, image, dt):
        p = self.particles
        p.step(dt, speed_factor(self.speed_slider))
        tau = trail_seconds(self.trail_slider)
        bits = np.frombuffer(image.bits(), np.uint8)
        if tau > 0:
            keep = int(256 * math.exp(-dt / tau))
            if kernel.HAVE_NUMBA:
                kernel.fade_bytes(bits, keep)
            else:
                bits[:] = (bits.astype(np.uint16) * keep >> 8).astype(np.uint8)
        else:
            bits[:] = 0
        self._draw_steps(image, tau > 0)

    def _draw_steps(self, image, trails: bool):
        """Each particle's step since the last frame as a short line (a dot without trails), in its
        speed color."""
        p = self.particles
        a, b = (p.prev, p.pos) if trails else (p.pos, p.pos)
        ax, ay = self._to_pixels(image, a)
        bx, by = self._to_pixels(image, b)
        dpr = self.pixel_scale()
        draw = ~p.fresh if trails else np.ones(p.pos.size, bool)
        draw &= np.hypot(bx - ax, by - ay) <= MAX_STEP_PX * dpr
        band = np.where(draw, self._band(p.speed), -1)
        self._draw(image, ax, ay, bx, by, band, np.ones(band.size), LINE_PX, False)
