"""
pulse_layer.py — the "Pulses along streamlines" view.

Every drawn streamline is cut into ~2 pixel pieces with the travel time τ from the start of its line
(physics.particles.travel_times). With the animation time t and the pulse period T, a piece is lit
when s = frac((t − τ) / T) < L (L = the lit part of a period, Pulse length slider), brightest at the
head (s = 0); T follows from the Spacing slider. Equal spacing in TIME: pulses stretch where the flow is
fast and crowd where it is slow. The picture is drawn anew every frame.
"""
import numpy as np

from physics.field import active
from physics.images import resolve
from physics.particles import time_scale, travel_times, typical_speed

from .animation_layer import MAX_STEP_PX, AnimatedLayer, GLFrame, speed_factor

PULSE_PX = 3.0                   # width of a pulse (screen pixels)
PULSE_STEP_PX = 2.0              # pulses: streamlines cut into pieces of about this length


def pulse_length(slider: int) -> float:
    """Pulse length slider 0 … 10 -> lit part of a pulse period (0: short dashes … 10: long comets)."""
    return 0.06 + 0.064 * min(max(slider, 0), 10)


def pulse_spacing(slider: int) -> float:
    """Spacing slider 1 … 10 -> distance between pulses at the typical speed, in streamline spacings
    (4 -> 4)."""
    return 1.0 + 0.75 * min(max(slider, 1), 10)


class PulseLayer(AnimatedLayer):
    """Style "Pulses along streamlines" (see the module docstring)."""
    DRAW_WHILE_PAUSED = True

    def __init__(self, plot, vb):
        super().__init__(plot, vb)
        self.result = None                    # the StreamlineSet drawn (StreamlineLayer)
        self.t = 0.0                          # animation time
        self.period = 1.0                     # T
        self.v_typ = 0.0
        self._pieces = None                   # (a, b, tau, speed) of the drawn lines (data coordinates)
        self._piece_step = None               # piece length they were cut with
        self._px = None                       # the pieces near the view, in picture pixels
        self._px_key = None
        self._px_serial = 0                   # _px recomputed (the graphics card gets the new pieces)
        self._gl_serial = -1                  # _px_serial of the pieces sent to the card
        self.spacing_slider = 4

    def gl_resend(self):
        self._gl_serial = -1

    def gpu_changed(self):
        super().gpu_changed()
        self._gl_serial = -1

    def set_spacing(self, slider: int):
        self.spacing_slider = int(slider)
        self._pieces = None                   # a new period

    # ------------------------------------------------------------------ the lines
    def set_lines(self, result):
        """New streamlines are drawn (also the previews while an element is dragged)."""
        self.result = result
        self._pieces = None
        self._px_key = None

    def start(self):
        self.t = 0.0
        self._pieces = None
        self._px_key = None
        self._update_speed()

    def typical(self) -> float:
        return self.v_typ

    def _update_speed(self):
        els = active(self.canvas.shown_elements())
        self.v_typ = typical_speed(els, resolve(els), self._box())

    def _prepare(self, image):
        """Travel times along the lines (again when they or the zoom changed), and the pieces near the
        view in picture pixels (again when the view changed)."""
        res = self.result
        if res is None or not res.lines or not self.v_typ > 0:
            self._px = None
            return
        (x0, x1), _ = self._view
        step = PULSE_STEP_PX * (x1 - x0) / image.width()
        if self._pieces is None or not 0.6 < step / self._piece_step < 1.6:
            self._piece_step = step
            self._pieces = travel_times(res.lines, self.canvas.shown_elements(), step, 1e-3 * self.v_typ)
            sep = res.separation if res.separation > 0 else 0.05 * (x1 - x0)
            self.period = pulse_spacing(self.spacing_slider) * sep / self.v_typ
            self._px_key = None
        if self._px_key == self._view_key:
            return
        self._px_key = self._view_key
        a, b, tau, speed = self._pieces
        ax, ay = self._to_pixels(image, a)
        bx, by = self._to_pixels(image, b)
        m = PULSE_PX * 2
        w, h = image.width(), image.height()
        near = (np.maximum(ax, bx) > -m) & (np.minimum(ax, bx) < w + m) & \
               (np.maximum(ay, by) > -m) & (np.minimum(ay, by) < h + m)
        near &= np.hypot(bx - ax, by - ay) <= MAX_STEP_PX * self.pixel_scale()
        near[near] &= ~self.canvas.bodies.contains(0.5 * (a[near] + b[near]))
        idx = np.nonzero(near)[0]
        self._px = (ax[idx], ay[idx], bx[idx], by[idx], tau[idx] / self.period, self._band(speed[idx]))
        self._px_serial += 1

    # ------------------------------------------------------------------ hooks
    def scene_changed(self):
        if self.animated:
            self._update_speed()
            self._colors()
            self._px_key = None

    def bodies_changed(self):
        self._px_key = None                   # (pieces inside a body are not drawn)

    def view_changed(self):
        if self.animated:
            self._update_speed()
            self._colors()
            self._px_key = None

    def drag_finished(self):
        self.scene_changed()

    # ------------------------------------------------------------------ one frame
    def render(self, image, dt):
        self.t += dt * time_scale(self._box(), self.v_typ, speed_factor(self.speed_slider))
        if isinstance(image, GLFrame):
            # the graphics card: the pieces are sent once (when they change), each frame only the time;
            # the shader decides which pieces are lit (the same rule as below)
            self._prepare(image)
            image.ops.append(("clear",))
            if self._px is not None:
                ax, ay, bx, by, phase, band = self._px
                fresh = self._gl_serial != self._px_serial
                segs = np.column_stack([ax, ay, bx, by, band, phase]) if fresh else None
                self._gl_serial = self._px_serial
                image.ops.append(("pulses", segs, self._px_serial, self.t / self.period,
                                  pulse_length(self.trail_slider), 0.5 * PULSE_PX * self.pixel_scale()))
            return
        bits = np.frombuffer(image.bits(), np.uint8)
        bits[:] = 0
        self._prepare(image)
        if self._px is None:
            return
        ax, ay, bx, by, phase, band = self._px
        s = np.mod(self.t / self.period - phase, 1.0)
        L = pulse_length(self.trail_slider)
        lit = np.nonzero(s < L)[0]
        if lit.size:
            alpha = 1.0 - s[lit] / L                             # bright head, fading tail
            self._draw(image, ax[lit], ay[lit], bx[lit], by[lit], band[lit], alpha, PULSE_PX, True)
