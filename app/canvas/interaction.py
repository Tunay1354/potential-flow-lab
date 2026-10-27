"""
interaction.py — what the mouse does on the plot.

  * Mouse modes: Select (a click selects an element or a stagnation point), Move (drag an element to a
    new place), Pan (dragging moves the view, nothing is selected). In every mode the wheel zooms and
    dragging an empty place pans.
  * Move mode: the dragged element is a preview (the field layers fade, the stagnation points hide; the
    streamlines fade too, or follow it live with "Live update while dragging"); on release it goes to
    the model as one undo step and everything is computed again. Shift snaps to a grid, Esc cancels.
  * Dragging an element type from the palette onto the plot: a faint marker with coordinates shows
    where it goes; the drop opens the Add dialog with that position.
"""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QColor

from ..theme import MARKERS
from .layer import set_box_text

MOUSE_MODES = ("select", "move", "pan")
ELEMENT_MIME = "application/x-potential-flow-element"     # drag from the element palette to the plot
DRAG_OPACITY = 0.3                                         # layers that fade while an element is dragged


def snap_step(view_width: float) -> float:
    """Grid step for Shift-snapping: 0.1 for a view a few units wide, 1 for ~50 units, ..."""
    return 10.0 ** np.floor(np.log10(max(view_width, 1e-9) / 50.0))


def snapped(value: float, step: float, snap: bool) -> float:
    """Shift held: the nearest multiple of `step`; otherwise rounded to step / 100 (clean numbers)."""
    q = step if snap else step / 100.0
    digits = max(0, int(-np.floor(np.log10(q))) if q < 1 else 0)
    return round(round(value / q) * q, digits) + 0.0


class PlotViewBox(pg.ViewBox):
    """View box that lets the canvas take a mouse drag (Move mode: drag an element); every other
    drag pans the view as usual."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.interaction = None                  # set by PlotInteraction

    def mouseDragEvent(self, ev, axis=None):
        if self.interaction is not None and self.interaction.drag_event(ev):
            ev.accept()
            return
        super().mouseDragEvent(ev, axis)


class PlotInteraction(QObject):
    """Mouse modes, Move-mode dragging and palette drops of one PlotCanvas."""

    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = cv = canvas
        self.mode = "select"
        self.drag = None                         # the element being dragged (see begin_drag)
        cv.vb.interaction = self
        cv.plot.scene().sigMouseMoved.connect(self._mouse_moved)
        cv.plot.scene().sigMouseClicked.connect(self._mouse_clicked)
        # element palette -> plot: drag an element type onto the plot to place it there
        cv.plot.setAcceptDrops(True)
        cv.plot.viewport().setAcceptDrops(True)
        self._viewport = cv.plot.viewport()
        self._viewport.installEventFilter(self)
        self.ghost = pg.ScatterPlotItem(size=15, symbol="o")      # where a dropped / moved element goes
        self.ghost_label = pg.TextItem(anchor=(0.0, 1.0))
        for item in (self.ghost, self.ghost_label):
            item.setZValue(7)
            item.setVisible(False)
            cv.plot.addItem(item)

    # ------------------------------------------------------------------ mouse modes
    def set_mode(self, mode: str) -> bool:
        """Change the mouse mode; True if it changed."""
        if mode not in MOUSE_MODES:
            return False
        if self.drag is not None:
            self.cancel_drag()
        changed, self.mode = mode != self.mode, mode
        self._viewport.setCursor(Qt.OpenHandCursor if mode == "pan" else Qt.ArrowCursor)
        return changed

    def _mouse_clicked(self, ev):
        cv = self.canvas
        if ev.button() != Qt.LeftButton or self.mode == "pan":      # Pan mode never selects
            return
        inside = cv.vb.sceneBoundingRect().contains(ev.scenePos())
        elements = cv.element_layer.pick(ev.scenePos()) if inside else []
        stags = cv.stagnation.pick(ev.scenePos()) if inside else []
        if ev.double():
            if elements:
                cv.element_double_clicked.emit(elements[0])
            return
        # everything under the mouse, nearest first: ("e", element index) or ("s", stagnation index)
        hits = [("s", k) for _, k in stags] + [("e", i) for i in elements]
        if not hits:
            cv.element_clicked.emit(-1)
            return
        current = ("e", cv.selected) if cv.selected >= 0 else ("s", cv.stagnation.selected)
        # clicking again on overlapping symbols (e.g. doublet + vortex) selects the next one
        kind, k = hits[(hits.index(current) + 1) % len(hits)] if current in hits else hits[0]
        (cv.element_clicked if kind == "e" else cv.stagnation_clicked).emit(k)

    def _mouse_moved(self, pos):
        cv = self.canvas
        if not cv.vb.sceneBoundingRect().contains(pos):
            cv.probe.emit(None)
            return
        pt = cv.vb.mapSceneToView(pos)
        cv.probe.emit((pt.x(), pt.y()))
        if self.mode == "move" and self.drag is None:               # grip over draggable elements
            grab = any(cv.elements[i].POSITION_KEYS for i in cv.element_layer.pick(pos))
            self._viewport.setCursor(Qt.OpenHandCursor if grab else Qt.ArrowCursor)

    # ------------------------------------------------------------------ Move mode: drag an element
    def drag_event(self, ev) -> bool:
        """Called by the view box for every drag event; True = handled here (no panning)."""
        if ev.button() != Qt.LeftButton:
            return False
        if ev.isStart() and (self.mode != "move" or not self.begin_drag(ev.buttonDownScenePos())):
            return False
        if self.drag is None:
            return False
        if self.drag.get("cancelled"):
            if ev.isFinish():
                self.drag = None
            return True                                   # swallow the rest of a cancelled drag
        self.drag_to(ev.scenePos(), bool(ev.modifiers() & Qt.ShiftModifier))
        if ev.isFinish():
            self.end_drag()
        return True

    def is_dragging(self) -> bool:
        return self.drag is not None and not self.drag.get("cancelled")

    def preview(self):
        """(row, moved copy) of the dragged element, or None."""
        d = self.drag
        return (d["row"], d["preview"]) if d is not None and d.get("preview") is not None else None

    def begin_drag(self, scene_pos) -> bool:
        """Start dragging the element under scene_pos (one with a position)."""
        cv = self.canvas
        rows = [i for i in cv.element_layer.pick(scene_pos) if cv.elements[i].POSITION_KEYS]
        if not rows:
            return False
        row = rows[0]
        el = cv.elements[row]
        kx, ky = el.POSITION_KEYS
        p = cv.vb.mapSceneToView(scene_pos)
        self.drag = {"row": row, "original": el, "preview": None,
                     "offset": (getattr(el, kx) - p.x(), getattr(el, ky) - p.y())}
        cv.element_clicked.emit(row)                    # the dragged element is the selected one
        cv.selected = row
        self._viewport.setCursor(Qt.ClosedHandCursor)
        cv.drag_started()
        return True

    def drag_to(self, scene_pos, snap: bool = False):
        """Move the dragged element (preview only; the model changes on release)."""
        d = self.drag
        if d is None or d.get("cancelled"):
            return
        cv = self.canvas
        el = d["original"]
        kx, ky = el.POSITION_KEYS
        p = cv.vb.mapSceneToView(scene_pos)
        step = snap_step(cv.view()[0][1] - cv.view()[0][0])
        x = snapped(p.x() + d["offset"][0], step, snap)
        y = snapped(p.y() + d["offset"][1], step, snap)
        d["preview"] = el.copy(**{kx: x, ky: y})
        cv.element_layer.draw()
        cv.drag_moved()
        self._show_ghost_label(x, y, snap)

    def end_drag(self):
        """Mouse released: the moved element goes to the model (one undo step), then everything is
        computed again."""
        d, self.drag = self.drag, None
        self._finish_drag()
        if d is not None and d["preview"] is not None and d["preview"] != d["original"]:
            self.canvas.element_moved.emit(d["row"], d["preview"])
        else:
            self.canvas.element_layer.draw()

    def cancel_drag(self) -> bool:
        """Esc while dragging: the element goes back, nothing changes."""
        if self.drag is None:
            return False
        self.drag = {"cancelled": True, "preview": None}
        self._finish_drag()
        self.canvas.element_layer.draw()
        return True

    def _finish_drag(self):
        self.ghost_label.setVisible(False)
        self._viewport.setCursor(Qt.OpenHandCursor if self.mode in ("move", "pan") else Qt.ArrowCursor)
        self.canvas.drag_finished()

    def _show_ghost_label(self, x, y, snap):
        cv = self.canvas
        set_box_text(self.ghost_label, cv.theme, f"{x:.3f}, {y:.3f}" + ("   (snap)" if snap else ""), "1px 4px")
        px, py = cv.vb.viewPixelSize()
        self.ghost_label.setPos(x + 12 * px, y + 12 * py)
        self.ghost_label.setVisible(True)

    # ------------------------------------------------------------------ palette -> plot (drop)
    def eventFilter(self, obj, event):
        if obj is self._viewport and event.type() in (QEvent.DragEnter, QEvent.DragMove, QEvent.Drop,
                                                      QEvent.DragLeave):
            return self._palette_drop_event(event.type(), event)
        return super().eventFilter(obj, event)

    def _drop_position(self, key, view_pos, snap):
        """Data position of a drop (None for elements without a position, e.g. uniform flow;
        'outside' outside the plot area)."""
        from physics import ELEMENT_TYPES
        if key not in ELEMENT_TYPES or not ELEMENT_TYPES[key].POSITION_KEYS:
            return None
        cv = self.canvas
        scene = cv.plot.mapToScene(view_pos)
        if not cv.vb.sceneBoundingRect().contains(scene):
            return "outside"
        p = cv.vb.mapSceneToView(scene)
        step = snap_step(cv.view()[0][1] - cv.view()[0][0])
        return snapped(p.x(), step, snap), snapped(p.y(), step, snap)

    def _palette_drop_event(self, et, event) -> bool:
        if et == QEvent.DragLeave:
            self.hide_ghost()
            return True
        md = event.mimeData()
        if not md.hasFormat(ELEMENT_MIME):
            return False
        key = bytes(md.data(ELEMENT_MIME)).decode()
        snap = bool(event.modifiers() & Qt.ShiftModifier)
        pos = self._drop_position(key, event.position().toPoint(), snap)
        if et == QEvent.Drop:
            self.hide_ghost()
            if pos == "outside":
                event.ignore()
                return True
            event.acceptProposedAction()
            QTimer.singleShot(0, self, lambda: self.canvas.element_dropped.emit(key, pos))   # dialog after the drop
            return True
        event.acceptProposedAction()
        self.show_drop_ghost(key, pos, snap)
        return True

    def show_drop_ghost(self, key, pos, snap=False):
        """Faint marker + coordinates where a dragged palette element would be placed."""
        if pos is None or pos == "outside":
            self.hide_ghost()
            return
        t = self.canvas.theme
        style = MARKERS.get(key, MARKERS["default"])
        color = QColor(t.get(f"el_{key}", t["plot_axis"]))
        color.setAlpha(150)
        symbol = "+" if key == "wall" else style["symbol"]
        if symbol == "stagnation":
            symbol = "o"
        self.ghost.setData([pos[0]], [pos[1]], symbol=symbol, size=style["size"] + 4,
                           brush=pg.mkBrush(color) if style["filled"] else pg.mkBrush(None),
                           pen=pg.mkPen(color, width=2))
        self.ghost.setVisible(True)
        self._show_ghost_label(pos[0], pos[1], snap)

    def hide_ghost(self):
        self.ghost.setVisible(False)
        self.ghost_label.setVisible(False)
