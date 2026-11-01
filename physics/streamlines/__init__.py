"""
streamlines — evenly spaced streamlines with direction arrows
(Jobard & Lefer, "Creating evenly-spaced streamlines of arbitrary density", 1997).

How it works
1. d is the desired distance between neighbouring streamlines (smaller d = higher density).
2. The FIRST lines start on the border where the flow enters the region, exactly d apart. Every
   accepted line then proposes new seeds on both sides of it, d away (neighbour seeding), so the
   picture grows outwards with an even spacing. When no neighbour seed is left, the next seeds come
   from rings around singular points and points along walls, and finally from a regular grid.
3. Seeds are integrated with RK4 forwards and backwards along the direction field V/|V|
   (step = arc length). The compiled kernel (kernel.py) is used when available, else NumPy.
4. A line stops when it comes closer than STOP_RATIO·d to another line, leaves the region, comes
   close to a singular point, leaves the fluid, reaches a stagnation point, or closes on itself.
   Ends caused by "too close to another line" fade out in the plot (`tapers`).

"Distance to existing lines" is looked up in rasters (cell size d/4) in which every line is stamped
with a disk of radius STOP_RATIO·d (stop test) and SEED_RATIO·d (seed test).

Interactive use (the plot): StreamlineField keeps its lines. When the visible region grows
(pan / zoom out) the old lines stay exactly where they are: lines that ended at the old region border
are continued, and only the new area gets new seeds. StreamlineCache keeps one field per spacing
level d = 2^−L (the level changes only after a clear zoom).

The velocity always comes from the analytic superposition, never from a picture, so the streamlines
are exact up to the integration error.

    common.py   parameters (STOP_RATIO …), StreamlineSet
    level.py    StreamlineField (one spacing level), trace_streamlines(), view_spacing()
    cache.py    StreamlineCache (the plot: levels, filled around the view, stagnation features)
    seeds.py    where lines start          rasters.py  distance to the lines drawn so far
    arrows.py   direction arrows           drawing.py  fading line ends for the plot
"""
from .cache import StreamlineCache
from .common import FADE_LEVELS, STOP_RATIO, TAPER_RATIO, Cancelled, StreamlineSet
from .drawing import fade_piece_boxes
from .level import StreamlineField, trace_streamlines, view_spacing

__all__ = ["StreamlineSet", "StreamlineField", "StreamlineCache", "Cancelled", "trace_streamlines", "view_spacing",
           "fade_piece_boxes", "FADE_LEVELS", "STOP_RATIO", "TAPER_RATIO"]
