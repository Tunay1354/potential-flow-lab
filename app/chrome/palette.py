"""
palette.py — the element palette beside the plot: one button per element type (click = Add dialog,
drag onto the plot = add it there); dragged by its heading to the other side of the plot.
"""
from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QLabel, QToolButton, QVBoxLayout, QWidget

from ..theme import LAYOUT
from .cards import frame_lines
from .style import font, heading_font


class ElementPalette(QWidget):
    """Column of 'add element' buttons beside the plot: a card with the double frame, a centered
    ADD heading, icon + name buttons and a short rule before the boundaries (walls).

    The card is moved as a whole by dragging its heading: the window places it left or right of the
    plot (drag_moved / drag_finished carry the global mouse position); its size never changes."""
    drag_moved = Signal(QPoint)
    drag_finished = Signal(QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ElementPalette")
        self.theme = None
        self.setFixedWidth(LAYOUT["palette_width"])
        self.setMouseTracking(True)                # cursor shows the grip over the heading
        self._press = None                         # global position of the press on the heading
        self.dragging = False
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 12, 0, 12)
        self._lay.setSpacing(4)
        heading = self._heading = QLabel("Add")
        heading.setObjectName("ToolbarHeading")
        heading.setFont(heading_font())
        heading.setAlignment(Qt.AlignCenter)
        heading.setAttribute(Qt.WA_TransparentForMouseEvents, True)    # the card itself handles the drag
        heading.setToolTip("Drag to move the palette to the other side of the plot")
        self._lay.addWidget(heading)
        self._lay.addSpacing(12)                 # room for the rule under the heading (as in the panels)
        self._lay.addStretch(1)

    def add_action(self, action, key: str = "") -> QToolButton:
        """Button of one element type; click = add dialog, drag onto the plot = add it there."""
        b = QToolButton(self)
        b.setDefaultAction(action)
        b.setProperty("element_key", key)
        b.installEventFilter(self)
        b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        b.setIconSize(QSize(LAYOUT["toolbar_icon_px"], LAYOUT["toolbar_icon_px"]))
        b.setFixedSize(*LAYOUT["palette_button"])
        b.setFont(font("mono", 7.5, caps=True, spacing_pct=104))
        b.setCursor(Qt.PointingHandCursor)
        self._lay.insertWidget(self._lay.count() - 1, b, 0, Qt.AlignHCenter)
        return b

    def add_separator(self):
        rule = QWidget(self)
        rule.setObjectName("PaletteRule")
        rule.setAttribute(Qt.WA_StyledBackground, True)
        rule.setFixedSize(LAYOUT["palette_button"][0] - 20, 1)
        self._lay.insertSpacing(self._lay.count() - 1, 4)
        self._lay.insertWidget(self._lay.count() - 1, rule, 0, Qt.AlignHCenter)
        self._lay.insertSpacing(self._lay.count() - 1, 4)

    def apply_theme(self, theme):
        self.theme = theme
        self.update()

    # dragging an element type out of the palette (onto the plot) ----------------------------
    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if isinstance(obj, QToolButton) and obj.property("element_key"):
            et = event.type()
            if et == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                obj._press_pos = event.position().toPoint()
            elif et == QEvent.MouseMove and event.buttons() & Qt.LeftButton:
                start = getattr(obj, "_press_pos", None)
                from PySide6.QtWidgets import QApplication
                if start is not None and (event.position().toPoint() - start).manhattanLength() \
                        >= QApplication.startDragDistance():
                    obj._press_pos = None
                    self._start_element_drag(obj)
                    return True
            elif et == QEvent.MouseButtonRelease:
                obj._press_pos = None
        return super().eventFilter(obj, event)

    def _start_element_drag(self, button):
        from PySide6.QtCore import QMimeData
        from PySide6.QtGui import QDrag
        from ..canvas import ELEMENT_MIME
        key = button.property("element_key")
        mime = QMimeData()
        mime.setData(ELEMENT_MIME, key.encode())
        drag = QDrag(button)
        drag.setMimeData(mime)
        size = LAYOUT["toolbar_icon_px"] + 6
        drag.setPixmap(button.icon().pixmap(size, size))
        drag.setHotSpot(QPoint(size // 2, size // 2))
        button.setDown(False)
        drag.exec(Qt.CopyAction)
        button.setDown(False)                     # no click after a drag

    # dragging the card by its heading -------------------------------------------------------
    def _on_handle(self, pos) -> bool:
        return pos.y() <= self._heading.geometry().bottom() + 12

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._on_handle(event.position().toPoint()):
            self._press = event.globalPosition().toPoint()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        g = event.globalPosition().toPoint()
        if self._press is None:
            self.setCursor(Qt.OpenHandCursor if self._on_handle(event.position().toPoint()) else Qt.ArrowCursor)
            return
        if not self.dragging and (g - self._press).manhattanLength() >= 6:
            self.dragging = True
            self.setCursor(Qt.ClosedHandCursor)
        if self.dragging:
            self.drag_moved.emit(g)

    def mouseReleaseEvent(self, event):
        if self._press is not None and self.dragging:
            self.drag_finished.emit(event.globalPosition().toPoint())
        self._press, self.dragging = None, False
        self.setCursor(Qt.OpenHandCursor if self._on_handle(event.position().toPoint()) else Qt.ArrowCursor)

    def leaveEvent(self, _event):
        if self._press is None:
            self.unsetCursor()

    def paintEvent(self, _event):
        if self.theme is None:
            return
        p = QPainter(self)
        r = QRectF(self.rect())
        p.fillRect(r, QColor(self.theme["panel_bg"]))
        frame_lines(p, r, self.theme, top=True, bottom=True)
        p.setPen(QPen(QColor(self.theme["ink"]), 1.5))          # heading rule, like PanelTitle
        y = self._heading.geometry().bottom() + 6.5
        p.drawLine(QPointF(r.left() + 12, y), QPointF(r.right() - 12, y))
        p.end()
