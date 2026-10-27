"""
canvas — the plot card of the main window.

    canvas.py            PlotCanvas: bar + plot + title block; shared state; passes events to the layers
    layer.py             PlotLayer: the interface every layer implements (+ small drawing helpers)
    streamline_layer.py  streamlines and arrows, computed in a background thread
    stagnation_layer.py  stagnation points and dividing streamlines
    field_layer.py       equipotential lines, |V| and Cp color bands (contours.py, legend.py)
    element_layer.py     element symbols, walls, selection glow, picking
    animation_layer.py   what the animated views share; particle_layer.py (particles with trails),
                         pulse_layer.py (pulses along the streamlines)
    body_layer.py        "Solid bodies": the inside of cylinders / Rankine bodies filled (physics/bodies.py)
    interaction.py       mouse modes, dragging elements, dropping palette elements
    settings.py          PlotSettings (saved with the scene)
    bar.py               the bar above the plot
"""
from .bar import CanvasBar
from .canvas import LAYERS, LIVE_DRAG_DEFAULT, VIEW_MODES, PlotCanvas
from .interaction import ELEMENT_MIME, MOUSE_MODES, snap_step, snapped
from .settings import PlotSettings

__all__ = ["CanvasBar", "PlotCanvas", "PlotSettings", "LAYERS", "LIVE_DRAG_DEFAULT", "VIEW_MODES", "ELEMENT_MIME", "MOUSE_MODES",
           "snap_step", "snapped"]
