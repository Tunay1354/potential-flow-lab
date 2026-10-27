"""
plot_settings.py — the plot settings of one scene (Plot settings panel; saved in the scene file).

Pure Python: the scene file (scene_file.py) checks and stores them by these fields, the plot uses them
through app/canvas/settings.py. A new setting:
    1. a field here (metadata zero=True if 0 is a valid value; int fields are slider positions),
    2. its slider in app/canvas/settings.SLIDERS (label, range, tooltip) — if it has one,
    3. PlotCanvas.set_<name>(value), which applies it to the plot.
The panel, the window wiring and the scene file follow from these.
"""
from dataclasses import asdict, dataclass, field, fields


def _zero_ok(default):
    return field(default=default, metadata={"zero": True})


@dataclass
class PlotSettings:
    density: float = 1.0                        # streamlines: 1 = default spacing, 2 = twice as many
    arrow_density: float = 1.0                  # direction arrows along the lines
    show_arrows: bool = True
    line_width: float = 1.4                     # streamline width (screen pixels)
    field_quality: int = 2                      # grid of the field layers: 1 low, 2 medium, 3 high
    cp_reference: float | None = None           # Cp reference speed; None = V∞ of the uniform flow(s)
    particles: int = 1500                       # particles: number of tracer particles
    anim_speed: int = 5                         # particles: speed slider (5: a typical one crosses the view in 6 s)
    trail: int = _zero_ok(4)                    # particles: trail length slider (0 = no trails)
    pulse_speed: int = 5                        # pulses: speed slider (as anim_speed)
    pulse_length: int = _zero_ok(4)             # pulses: length slider (0 = short dashes)
    pulse_spacing: int = 4                      # pulses: spacing slider (4: 4 streamline spacings apart)

    def to_document(self) -> dict:
        """The settings as stored in a scene file (numbers as floats; no Cp reference = V∞)."""
        out = asdict(self)
        for key in INT_FIELDS:
            out[key] = float(getattr(self, key))
        if not self.cp_reference:
            del out["cp_reference"]
        return out

    def updated(self, saved: dict) -> "PlotSettings":
        """These settings with the values of a scene file. Missing values stay as they are, except the
        Cp reference (missing = V∞) and the grid quality (files older than the field layers)."""
        values = asdict(self)
        values.update({f.name: saved[f.name] for f in fields(self) if f.name in saved})
        values["field_quality"] = saved.get("field_quality", 2)
        for key in INT_FIELDS:
            values[key] = int(values[key])
        values["cp_reference"] = saved.get("cp_reference") or None
        return PlotSettings(**values)


_FIELDS = fields(PlotSettings)
INT_FIELDS = tuple(f.name for f in _FIELDS if f.type in (int, "int"))
# as stored in a scene file: name -> type (numbers are floats in the file)
SETTING_TYPES = {f.name: bool if f.type in (bool, "bool") else float for f in _FIELDS}
ZERO_ALLOWED = frozenset(f.name for f in _FIELDS if f.metadata.get("zero"))
