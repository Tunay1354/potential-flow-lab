"""
settings.py — the plot settings (model/plot_settings.py) and the sliders that show them.

SLIDERS lists every setting with a slider in Plot settings: its section, label, range, tooltip and how
the slider position maps to the value (value = offset + step × position). The panel builds the
sliders from it, a moved slider calls PlotCanvas.set_<key>(value), and an opened scene puts the
sliders back with position(). A new setting: see model/plot_settings.py.
"""
from dataclasses import dataclass

from model.plot_settings import INT_FIELDS, PlotSettings

__all__ = ["PlotSettings", "INT_FIELDS", "Slider", "SLIDERS", "slider"]


@dataclass(frozen=True)
class Slider:
    key: str                     # PlotSettings field
    section: str                 # Plot settings section
    label: str
    lo: int                      # slider positions
    hi: int
    tip: str = ""
    offset: float = 0.0          # value = offset + step × position
    step: float = 1.0

    def value(self, position: int):
        if self.key in INT_FIELDS:
            return int(position)
        return round(self.offset + self.step * position, 9)    # 1.4, not 1.4000000000000001 (saved)

    def position(self, value) -> int:
        return min(max(int(round((value - self.offset) / self.step)), self.lo), self.hi)


SLIDERS = (
    Slider("density", "streamlines", "Density", 1, 10, "Number of streamlines", 0.0, 0.2),     # 0.2 … 2
    Slider("line_width", "streamlines", "Line width", 1, 5, "", 0.6, 0.4),                     # 1.0 … 2.6 px
    Slider("arrow_density", "streamlines", "Arrow density", 1, 5, "", 0.5, 0.5),               # 1 … 3
    Slider("particles", "particles", "Count", 200, 5000, "Number of tracer particles"),
    Slider("anim_speed", "particles", "Speed", 1, 10,
           "How fast the particles move (5: a typical one crosses the view in 6 s)"),
    Slider("trail", "particles", "Trail length", 0, 10, "How long the particles' trails are (0: dots only)"),
    Slider("pulse_speed", "pulses", "Speed", 1, 10,
           "How fast the pulses run (5: at the typical speed they cross the view in 6 s)"),
    Slider("pulse_length", "pulses", "Pulse length", 0, 10,
           "How long each pulse is (0: short dashes, 10: long comets)"),
    Slider("pulse_spacing", "pulses", "Spacing", 1, 10,
           "How far apart the pulses are (4: four streamline spacings at the typical speed)"),
)
_BY_KEY = {s.key: s for s in SLIDERS}


def slider(key: str) -> Slider:
    return _BY_KEY[key]
