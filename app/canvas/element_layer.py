"""
element_layer.py — the elements themselves on the plot: their symbols (source, vortex, doublet,
sector vertex), the symmetry walls and sector sides with hatch marks and shaded solid region, the glow
of the selected element, and picking (which element is under the mouse).

Walls are drawn for a region 3× the view, so a pan does not need a redraw at once. While an element
is dragged, its moved copy is drawn instead (canvas.shown_elements()).
"""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsPathItem

from ..geometry import (fluid_polygon, point_segment_distance, rect_polygon, sector_shading,
                        sector_sides, visible_wall_segment)
from ..theme import LAYOUT, MARKERS
from .layer import PlotLayer, glow_dots


class ElementLayer(PlotLayer):

    def __init__(self, plot, vb):
        super().__init__(plot, vb)
        self.markers, self.walls = [], []        # plot items (rebuilt on every change)
        self._wall_rect = None                   # region the walls were drawn for (x0, x1, y0, y1, view width)
        self._hatch_spacing = 1.0

    # ------------------------------------------------------------------ hooks
    def apply_theme(self, theme):
        super().apply_theme(theme)
        self.draw()

    def scene_changed(self):
        self.draw()

    def selection_changed(self):
        self.draw()

    def view_changed(self):
        if self._walls_need_redraw():
            self._draw_walls_around_view()
            self.canvas.apply_visibility()

    def visibility_changed(self):
        for item in self.markers:
            item.setVisible(self.canvas.layers["markers"])
        for item in self.walls:
            item.setVisible(self.canvas.layers["walls"])

    # ------------------------------------------------------------------ drawing
    def draw(self):
        """Symbols and walls of the elements as shown now."""
        self._draw_markers()
        self._draw_walls_around_view()
        self.canvas.apply_visibility()

    def _selected(self):
        cv = self.canvas
        return cv.shown_elements()[cv.selected] if 0 <= cv.selected < len(cv.elements) else None

    def _draw_markers(self):
        for it in self.markers:
            self.plot.removeItem(it)
        self.markers = []
        t, sel = self.theme, self._selected()
        for e in self.canvas.shown_elements():
            pts = e.marker_points() if e.enabled else []
            if not pts:
                continue
            xs, ys = [p.real for p in pts], [p.imag for p in pts]
            style = MARKERS.get(e.TYPE, MARKERS["default"])
            color = t.get("el_sink" if getattr(e, "is_sink", False) else f"el_{e.TYPE}", t["plot_axis"])
            if style["filled"]:
                brush, pen = pg.mkBrush(color), pg.mkPen(t["plot_bg"], width=1.5)
            else:
                brush, pen = pg.mkBrush(None), pg.mkPen(color, width=2)
            if e is sel:                                  # selected: soft glow in the element's own color
                self.markers += glow_dots(self.plot, xs, ys, color, style["size"], 2.9)
            item = pg.ScatterPlotItem(xs, ys, size=style["size"], symbol=style["symbol"], brush=brush, pen=pen)
            self.markers.append(self.add_item(item, 3))

    def _walls_need_redraw(self) -> bool:
        if self._wall_rect is None:
            return True
        (x0, x1), (y0, y1) = self.canvas.view()
        a0, a1, b0, b1, w = self._wall_rect
        return not (a0 <= x0 and x1 <= a1 and b0 <= y0 and y1 <= b1) or not 0.7 < (x1 - x0) / w < 1.4

    def _draw_walls_around_view(self):
        """Walls for a region 3× the view; the hatch spacing follows the view size."""
        (x0, x1), (y0, y1) = self.canvas.view()
        W, H = x1 - x0, y1 - y0
        self._wall_rect = (x0 - W, x1 + W, y0 - H, y1 + H, W)
        self._hatch_spacing = abs(complex(W, H)) / LAYOUT["wall_hatch_count"]
        self._draw_walls((x0 - W, x1 + W), (y0 - H, y1 + H))

    def _draw_walls(self, xr, yr):
        """Symmetry walls and the sides of a sector flow inside the rectangle xr × yr.
        Solid region shaded once; each wall drawn only where it borders the fluid (corners look like
        an L or a wedge); hatch marks on the solid side. A plate (β = 360°) has fluid on both sides."""
        for it in self.walls:
            self.plot.removeItem(it)
        self.walls = []
        shown = self.canvas.shown_elements()
        walls = [e for e in shown if e.enabled and e.IS_BOUNDARY]
        sectors = [e for e in shown if e.enabled and e.TYPE == "sector"]
        t, sel = self.theme, self._selected()
        # 1) shading of the solid region
        if walls:
            self._add_shading("cut", fluid_polygon(walls, xr, yr), xr, yr, t["el_wall"])
        for sec in sectors:
            self._add_shading(*sector_shading(sec, xr, yr), xr, yr, t["el_sector"])
        # 2) symmetry walls: the part that borders the fluid
        for w in walls:
            seg = visible_wall_segment(w, [o for o in walls if o is not w], xr, yr)
            if seg is not None:
                self._add_wall_line(seg, w.normal, t["el_wall"], glow=w is sel)
        # 3) sector sides: two rays from the vertex (fluid normal points into the wedge)
        for sec in sectors:
            plate = sec.beta_deg >= 360.0 - 1e-9
            for seg, normal in sector_sides(sec, xr, yr):
                self._add_wall_line(seg, normal, t["el_sector"], hatch=not plate, glow=sec is sel)

    def _add_shading(self, mode, poly, xr, yr, color):
        if mode == "none":
            return
        path = QPainterPath()
        if mode == "cut":                                   # view minus the fluid polygon
            path.setFillRule(Qt.OddEvenFill)
            path.addPolygon(QPolygonF([QPointF(z.real, z.imag) for z in rect_polygon(xr, yr)]))
        if len(poly) >= 3:
            path.addPolygon(QPolygonF([QPointF(z.real, z.imag) for z in poly]))
        elif mode == "fill":
            return
        fill = QColor(color)
        fill.setAlpha(38 if self.theme["name"] == "light" else 55)
        shade = QGraphicsPathItem(path)
        shade.setBrush(QBrush(fill))
        shade.setPen(QPen(Qt.NoPen))
        self.walls.append(self.add_item(shade, 0.5))

    def _add_wall_line(self, seg, fluid_normal, color, hatch=True, glow=False):
        """Thick line from seg[0] to seg[1]; hatch marks on the side opposite to `fluid_normal`.
        glow=True (selected): wide, semi-transparent lines of the same color underneath."""
        a, b = seg
        xs, ys = [a.real, b.real], [a.imag, b.imag]
        if glow:
            for extra, alpha in LAYOUT["selection_glow"]:
                gc = QColor(color)
                gc.setAlpha(alpha)
                g = pg.PlotCurveItem(xs, ys, pen=pg.mkPen(gc, width=LAYOUT["wall_width"] + 0.6 * extra))
                self.walls.append(self.add_item(g, 3.9))
        line = pg.PlotCurveItem(xs, ys, pen=pg.mkPen(QColor(color), width=LAYOUT["wall_width"]))
        self.walls.append(self.add_item(line, 4))
        length = abs(b - a)
        n = int(length / self._hatch_spacing)
        if not hatch or n < 1:
            return
        d = (b - a) / length
        left = 1 if (np.conj(d) * fluid_normal).imag > 0 else -1      # fluid on the left of d?
        tick = 0.6 * self._hatch_spacing * (-fluid_normal * np.exp(1j * np.pi / 4 * left))
        base = a + (np.arange(n) + 0.5) * self._hatch_spacing * d
        mx = np.column_stack([base.real, (base + tick).real, np.full(n, np.nan)]).ravel()
        my = np.column_stack([base.imag, (base + tick).imag, np.full(n, np.nan)]).ravel()
        marks = pg.PlotCurveItem(mx, my, connect="finite", pen=pg.mkPen(color, width=1.2))
        self.walls.append(self.add_item(marks, 4))

    # ------------------------------------------------------------------ picking
    def pick(self, scene_pos) -> list[int]:
        """Indices of the elements under a scene (pixel) position, nearest first.
        Markers (source, vortex, doublet, sector vertex) and drawn lines (walls, sector sides) can be
        picked; the uniform flow has no symbol on the plot and is selected from the list."""
        cv = self.canvas
        xr, yr = cv.view()
        click = complex(scene_pos.x(), scene_pos.y())

        def to_scene(z):
            q = self.vb.mapViewToScene(QPointF(z.real, z.imag))
            return complex(q.x(), q.y())

        hits = []
        for i, e in enumerate(cv.elements):
            if not e.enabled:
                continue
            dists = [abs(to_scene(p) - click) for p in e.marker_points()]
            # + 0.5 px: a marker wins a tie with a line
            dists += [point_segment_distance(click, to_scene(a), to_scene(b)) + 0.5
                      for a, b in self._pick_segments(e, xr, yr)]
            if dists and min(dists) <= LAYOUT["pick_radius_px"]:
                hits.append((min(dists), i))
        return [i for _, i in sorted(hits)]

    def _pick_segments(self, e, xr, yr):
        """Visible straight pieces of an element (same as drawn): walls and the sides of a sector."""
        if e.IS_BOUNDARY:
            walls = [w for w in self.canvas.elements if w.enabled and w.IS_BOUNDARY]
            seg = visible_wall_segment(e, [o for o in walls if o is not e], xr, yr)
            return [seg] if seg else []
        if e.TYPE == "sector":
            return [seg for seg, _ in sector_sides(e, xr, yr)]
        return []
