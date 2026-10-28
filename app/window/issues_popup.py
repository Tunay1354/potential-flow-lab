"""
issues_popup.py — the scene check in the status bar ("⚠ 2 warnings · 1 note") is a button: a click
opens a small panel above it that lists every error, warning and note with the element it is about.
Clicking a line selects that element (in the list and on the plot).
"""
from __future__ import annotations

import html

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QToolButton, QVBoxLayout, QWidget

SEVERITY = {  # symbol, heading, theme color key
    "error": ("✖", "Error", "danger"),
    "warning": ("⚠", "Warning", "el_doublet"),
    "info": ("•", "Note", "text_muted"),
}
EXPLAIN = ("Error: the scene is not physically consistent (nothing is computed until it is fixed). "
           "Warning: allowed, but probably not what you meant. Note: just for information.")
WIDTH = 440


class IssueButton(QToolButton):
    """The status bar text of the scene check; a click shows the details (IssuesPopup)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoRaise(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.color = "#000000"
        self.hover = "#00000010"

    def set_look(self, color: str, hover: str):
        self.color, self.hover = color, hover
        self.setStyleSheet(f"QToolButton {{ color: {color}; font-weight: 600; border: none; padding: 1px 6px; }}"
                           f"QToolButton:hover {{ background: {hover}; border-radius: 3px; }}")


class _Row(QFrame):
    clicked = Signal()

    def __init__(self, clickable: bool, parent=None):
        super().__init__(parent)
        self.setObjectName("IssueRow")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_Hover, True)
        self.clickable = clickable
        if clickable:
            self.setCursor(Qt.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        if self.clickable and event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class IssuesPopup(QFrame):
    """Every issue of the scene, one line each; click → select the element."""
    select = Signal(int)

    def __init__(self, issues, elements, theme: dict, parent=None):
        super().__init__(parent, Qt.Popup)
        self.setObjectName("IssuesPopup")
        self.setAttribute(Qt.WA_DeleteOnClose)
        t = theme
        self.setStyleSheet(
            f"QFrame#IssuesPopup {{ background: {t['panel_bg']}; border: 1px solid {t['border']}; }}"
            f"QFrame#IssueRow {{ border: none; border-top: 1px solid {t['border_soft']}; }}"
            f"QFrame#IssueRow:hover {{ background: {t['accent_soft']}; }}"
            f"QLabel {{ color: {t['text']}; background: transparent; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(0)
        head = QLabel("<b>Scene check</b>")
        head.setContentsMargins(0, 0, 0, 6)
        lay.addWidget(head)
        if not issues:
            ok = QLabel("No problems found.")
            ok.setContentsMargins(0, 6, 0, 4)
            lay.addWidget(ok)
        order = {"error": 0, "warning": 1, "info": 2}
        for s in sorted(issues, key=lambda s: order.get(s.severity, 3)):
            symbol, word, key = SEVERITY.get(s.severity, SEVERITY["info"])
            on_element = s.index is not None and 0 <= s.index < len(elements)
            row = _Row(on_element)
            rl = QVBoxLayout(row)
            rl.setContentsMargins(4, 6, 4, 6)
            rl.setSpacing(2)
            el = elements[s.index] if on_element else None
            who = (f"[{s.index + 1}] {html.escape(el.NAME)}: {html.escape(el.summary())}" if on_element
                   else "The whole scene")
            title = QLabel(f"<span style='color:{t[key]}'><b>{symbol} {word}</b></span>"
                           f"&nbsp;&nbsp;<span style='color:{t['text_muted']}'>{who}</span>")
            msg = QLabel(s.message)
            msg.setTextFormat(Qt.PlainText)
            msg.setWordWrap(True)
            msg.setFixedWidth(WIDTH)
            rl.addWidget(title)
            rl.addWidget(msg)
            if on_element:
                row.setToolTip("Click: select this element")
                row.clicked.connect(lambda i=s.index: (self.select.emit(i), self.close()))
            lay.addWidget(row)
        note = QLabel(EXPLAIN)
        note.setWordWrap(True)
        note.setFixedWidth(WIDTH)
        note.setStyleSheet(f"color: {t['text_muted']}; font-size: 8.5pt;")
        note.setContentsMargins(0, 6, 0, 0)
        line = QFrame()
        line.setObjectName("IssueRow")
        line.setFixedHeight(1)
        line.setAttribute(Qt.WA_StyledBackground, True)
        lay.addWidget(line)
        lay.addWidget(note)

    def show_above(self, anchor: QWidget):
        """Open just above `anchor` (the status bar button), right edges aligned, kept on the screen."""
        self.adjustSize()
        top_right = anchor.mapToGlobal(QPoint(anchor.width(), 0))
        x, y = top_right.x() - self.width(), top_right.y() - self.height() - 4
        screen = anchor.screen() or self.screen()
        if screen is not None:
            g = screen.availableGeometry()
            x = max(g.left() + 4, min(x, g.right() - self.width() - 4))
            if y < g.top():
                y = anchor.mapToGlobal(QPoint(0, anchor.height())).y() + 4
        self.move(x, y)
        self.show()
