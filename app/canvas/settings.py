"""
settings.py — the plot settings of one scene (Plot settings panel; saved in the scene file).

A new setting is one field here: the canvas layers read it from `canvas.settings`, and it is saved
and opened with the scene (add its type to model.scene_file.SETTINGS as well).
"""
from dataclasses import asdict, dataclass, fields

from ..theme import LAYOUT


@dataclass
class PlotSettings:
    density: float = 1.0                        # streamlines: 1 = default spacing, 2 = twice as many
    arrow_density: float = 1.0                  # direction arrows along the lines
    show_arrows: bool = True
    line_width: float = LAYOUT["streamline_width"]
    field_quality: int = 2                      # grid of the field layers: 1 low, 2 medium, 3 high
    cp_reference: float | None = None           # Cp reference speed; None = V∞ of the uniform flow(s)
    particles: int = 1500                       # animation: number of tracer particles
    anim_speed: int = 5                         # animation speed slider (5: a typical particle crosses the view in 6 s)
    trail: int = 4                              # trail length slider (0 = no trails)

    def to_document(self) -> dict:
        """The settings as stored in a scene file (no Cp reference = the uniform flow's V∞)."""
        out = asdict(self)
        for key in ("field_quality", "particles", "anim_speed", "trail"):
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
        for key in ("particles", "anim_speed", "trail"):
            values[key] = int(values[key])
        values["cp_reference"] = saved.get("cp_reference") or None
        return PlotSettings(**values)
