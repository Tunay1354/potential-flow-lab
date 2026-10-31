"""
stagnation_layer.py — stagnation points (⊗) and the dividing streamlines through them.

Both come with every streamline result. Clicking a point selects it: it glows, shows a box with its
coordinates and its dividing streamlines ("All dividing streamlines" shows those of every point).
Hidden while an element is dragged (they belong to the old position).
"""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainterPath

from ..theme import LAYOUT, MARKERS
from .layer import PlotLayer, glow_dots, set_box_text
from .scaled_curve import ScaledCurve

WHERE = {"flow": "in the flow", "wall": "on the wall", "vertex": "corner vertex", "body": "on the body surface"}


def stagnation_symbol() -> QPainterPath:
    """Marker of a stagnation point: a ring with a cross in it (⊗), unit size, centered."""
    path = QPainterPath()
    path.addEllipse(-0.5, -0.5, 1.0, 1.0)
    a = 0.5 / np.sqrt(2.0)
    path.moveTo(-a, -a)
    path.lineTo(a, a)
    path.moveTo(-a, a)
    path.lineTo(a, -a)
    return path


class StagnationLayer(PlotLayer):

    def __init__(self, plot, vb):
        super().__init__(plot, vb)
        self.dividing_item = ScaledCurve(connect="finite")
        self.dividing_item.setSegmentedLineMode("on")
        self.add_item(self.dividing_item, 1.6)
        self.symbol_item = self.add_item(
            pg.ScatterPlotItem(symbol=stagnation_symbol(), size=MARKERS["stagnation"]["size"]), 3.5)
        self.glow = []                           # glow of the selected point
        self.label = self.add_item(pg.TextItem(anchor=(0.0, 1.0)), 6)
        self.label.setVisible(False)
        self.points = []                         # StagnationPoint list (physics.stagnation)
        self.dividing_lines, self.dividing_owner = [], []     # lines and the index of their point
        self.selected = None                     # index of the selected point (or None)

    # ------------------------------------------------------------------ hooks
    def apply_theme(self, theme):
        super().apply_theme(theme)
        self.dividing_item.setPen(pg.mkPen(theme["dividing_streamline"], width=LAYOUT["dividing_streamline_width"]))
        self.symbol_item.setPen(pg.mkPen(theme["stagnation"], width=2))
        self.symbol_item.setBrush(pg.mkBrush(theme["plot_bg"]))
        self.draw()

    def view_changed(self):
        self._place_label()

    def visibility_changed(self):
        dragging = self.canvas.is_dragging()
        shown = self.canvas.layers["stagnation"] and not dragging
        self.dividing_item.setVisible(not dragging)       # (its lines are chosen in draw)
        self.symbol_item.setVisible(shown)
        for item in self.glow:
            item.setVisible(shown)
        self.label.setVisible(shown and self.selected is not None)

    def drag_finished(self):
        self.draw()

    # ------------------------------------------------------------------ data
    def set_result(self, result):
        """The stagnation points and dividing streamlines of a new streamline result; the selection is
        kept if the selected point is still there."""
        old = self.points[self.selected] if self.selected is not None else None
        # the vertex of a sector flow is a stagnation point too (w ∝ ζ^(n−1) = 0), but it is the corner
        # of the walls themselves: not marked (its dividing lines are the drawn walls)
        keep = [k for k, p in enumerate(result.stagnation) if p.kind != "vertex"]
        new_index = {k: i for i, k in enumerate(keep)}
        self.points = [result.stagnation[k] for k in keep]
        pairs = [(ln, new_index[o]) for ln, o in zip(result.dividing, result.dividing_owner) if o in new_index]
        self.dividing_lines = [ln for ln, _ in pairs]
        self.dividing_owner = [o for _, o in pairs]
        self.selected = None
        if old is not None:
            for k, p in enumerate(self.points):
                if abs(p.z - old.z) <= 1e-9 * (1.0 + abs(old.z)):
                    self.selected = k
        self.draw()

    def select(self, index):
        """Select a point (index in points) or none (None)."""
        if index is not None and not 0 <= index < len(self.points):
            index = None
        self.selected = index
        self.draw()

    # ------------------------------------------------------------------ drawing
    def draw(self):
        t = self.theme
        pts = self.points
        self.symbol_item.setData([p.x for p in pts], [p.y for p in pts])
        for item in self.glow:
            self.plot.removeItem(item)
        self.glow = []
        k = self.selected
        if k is not None:
            p = pts[k]
            self.glow = glow_dots(self.plot, [p.x], [p.y], t["stagnation"], MARKERS["stagnation"]["size"], 3.4)
            x, y = round(p.x, 4) + 0.0, round(p.y, 4) + 0.0
            set_box_text(self.label, t, f'<b>Stagnation point</b> <span style="color:{t["text_muted"]}">'
                                        f'({WHERE[p.kind]})</span><br>x = {x:.4f}<br>y = {y:.4f}')
            self._place_label()
        # dividing streamlines: all of them (layer) or only those of the selected point
        lines = [ln for ln, o in zip(self.dividing_lines, self.dividing_owner)
                 if self.canvas.layers["dividing"] or o == k]
        if lines:
            gap = np.array([[np.nan, np.nan]])
            xy = np.vstack([x for ln in lines for x in (ln, gap)])
            self.dividing_item.setData(xy[:, 0], xy[:, 1])
        else:
            self.dividing_item.setData([], [])
        self.canvas.apply_visibility()

    def _place_label(self):
        """The coordinate box sits a few pixels up-right of the selected point (at any zoom), on the
        side away from the nearest element symbol (not over the body)."""
        if self.selected is None:
            return
        p = self.points[self.selected]
        px, py = self.vb.viewPixelSize()
        off = LAYOUT["stagnation_label_offset_px"]
        marks = [m for e in self.canvas.elements if e.enabled for m in e.marker_points()]
        left = bool(marks) and min(marks, key=lambda m: abs(m - p.z)).real > p.x
        self.label.setAnchor((1.0, 1.0) if left else (0.0, 1.0))
        self.label.setPos(p.x + (-off if left else off) * px, p.y + off * py)

    # ------------------------------------------------------------------ picking
    def pick(self, scene_pos) -> list:
        """[(distance in pixels, index)] of the points under a scene position, nearest first."""
        if not self.canvas.layers["stagnation"]:
            return []
        click = complex(scene_pos.x(), scene_pos.y())
        out = []
        for k, p in enumerate(self.points):
            q = self.vb.mapViewToScene(QPointF(p.x, p.y))
            d = abs(complex(q.x(), q.y()) - click)
            if d <= LAYOUT["pick_radius_px"]:
                out.append((d, k))
        return sorted(out)

    def near(self, x: float, y: float):
        """The point within the pick radius (screen pixels) of the data position (x, y), or None."""
        if not self.canvas.layers["stagnation"] or not self.points:
            return None
        px, py = self.vb.viewPixelSize()
        r = LAYOUT["pick_radius_px"]
        best = min(self.points, key=lambda p: ((p.x - x) / px) ** 2 + ((p.y - y) / py) ** 2)
        return best if ((best.x - x) / px) ** 2 + ((best.y - y) / py) ** 2 <= r * r else None
