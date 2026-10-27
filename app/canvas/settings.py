"""
settings.py — the plot settings of one scene (Plot settings panel; saved in the scene file).

A new setting is one field here: the canvas layers read it from `canvas.settings`, and it is saved
and opened with the scene (add its type to model.scene_file.SETTINGS as well).
"""
from dataclasses import asdict, dataclass, fields

from ..theme import LAYOUT

INT_FIELDS = ("particles", "anim_speed", "trail", "pulse_speed", "pulse_length", "pulse_spacing")


@dataclass
class PlotSettings:
    density: float = 1.0                        # streamlines: 1 = default spacing, 2 = twice as many
    arrow_density: float = 1.0                  # direction arrows along the lines
    show_arrows: bool = True
    line_width: float = LAYOUT["streamline_width"]
    field_quality: int = 2                      # grid of the field layers: 1 low, 2 medium, 3 high
    cp_reference: float | None = None           # Cp reference speed; None = V∞ of the uniform flow(s)
    particles: int = 1500                       # particles: number of tracer particles
    anim_speed: int = 5                         # particles: speed slider (5: a typical one crosses the view in 6 s)
    trail: int = 4                              # particles: trail length slider (0 = no trails)
    pulse_speed: int = 5                        # pulses: speed slider (as anim_speed)
    pulse_length: int = 4                       # pulses: length slider (0 = short dashes)
    pulse_spacing: int = 4                      # pulses: spacing slider (4: 4 streamline spacings apart)

    def to_document(self) -> dict:
        """The settings as stored in a scene file (no Cp reference = the uniform flow's V∞)."""
        out = asdict(self)
        for key in ("field_quality",) + INT_FIELDS:
            out[key] = float(getattr(self, key))
        if not self.cp_reference:
            del out["cp_reference"]
        return out

    def updated(self, saved: dict) -> "PlotSettings":
        """These settings with the values of a scene file. Missing values stay as they are, except the
        Cp reference (missing = V∞) and the grid quality (files older than the field layers)."""
        values = asdict(self)
        values.update({f.name: saved[f.name] for f in fields(self) if f.name in saved})
        values["field_quality"] = int(saved.get("field_quality", 2))
        for key in INT_FIELDS:
            values[key] = int(values[key])
        values["cp_reference"] = saved.get("cp_reference") or None
        return PlotSettings(**values)
