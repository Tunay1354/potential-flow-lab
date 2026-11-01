"""
bar.py — the bar above the plot: view mode (Static · Particles · Pulses), mouse mode (Select · Move · Pan),
Fit view, Export.
"""
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QMenu, QToolButton, QWidget

from ..chrome import button_font
from ..icons import make_tool_icon


class CanvasBar(QWidget):
    """Bar above the plot: view mode (Static · Particles · Pulses), mouse mode (Select · Move · Pan), Fit view,
    Export."""
    mode_selected = Signal(str)               # "select", "move" or "pan" (clicked by the user)
    view_mode_selected = Signal(str)          # "static", "particles" or "pulses" (clicked by the user)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CanvasBar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(46)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(8)

        self.btn_static = self._tool("Static", "Streamlines with direction arrows", checkable=True)
        self.btn_particles = self._tool("Particles", "Animated: tracer particles moving with the flow, colored by "
                                        "speed   [Space: pause]", checkable=True)
        self.btn_pulses = self._tool("Pulses", "Animated: bright pulses running along the streamlines at the local "
                                     "speed, colored by speed   [Space: pause]", checkable=True)
        self.view_buttons = {"static": self.btn_static, "particles": self.btn_particles, "pulses": self.btn_pulses}
        self.btn_static.setChecked(True)
        views = QButtonGroup(self)
        views.setExclusive(True)
        for key, b in self.view_buttons.items():          # spaced like Select · Move · Pan
            views.addButton(b)
            lay.addWidget(b)
            b.clicked.connect(lambda _=False, k=key: self.view_mode_selected.emit(k))

        lay.addWidget(self._separator())
        self.btn_select = self._tool("Select", "", checkable=True, icon="select")
        self.btn_move = self._tool("Move", "", checkable=True, icon="move")
        self.btn_pan = self._tool("Pan", "", checkable=True, icon="pan")
        self.mode_buttons = {"select": self.btn_select, "move": self.btn_move, "pan": self.btn_pan}
        self.mode_tips = {
            "select": "Select: click an element or a stagnation point (elements cannot be dragged here)",
            "move": "Move: drag an element to a new place (hold Shift to snap to the grid, Esc cancels)",
            "pan": "Pan: drag anywhere to move the view (nothing is selected)"}
        self.btn_select.setChecked(True)
        tools = QButtonGroup(self)
        tools.setExclusive(True)
        for mode, b in self.mode_buttons.items():
            tools.addButton(b)
            lay.addWidget(b)
            b.clicked.connect(lambda _=False, m=mode: self.mode_selected.emit(m))
        self.set_shortcut_hints({})
        self.btn_fit = self._tool("Fit", "Fit plot limits to the elements   [F]", icon="fit")
        lay.addWidget(self.btn_fit)

        lay.addStretch(1)
        self.btn_export = self._tool("Export", "Save the plot as a figure (PNG / SVG / PDF), the animation as a "
                                     "GIF / MP4, or the data as CSV", icon="export")
        self.btn_export.setObjectName("Export")
        self.btn_export.setPopupMode(QToolButton.InstantPopup)
        self.export_menu = QMenu(self.btn_export)
        self.btn_export.setMenu(self.export_menu)
        lay.addWidget(self.btn_export)

    def set_export_actions(self, actions):
        """The menu of the Export button: [(text, callback), …]."""
        self.export_menu.clear()
        for text, callback in actions:
            self.export_menu.addAction(text).triggered.connect(lambda _=False, f=callback: f())

    def set_view_mode(self, mode: str):
        self.view_buttons[mode].setChecked(True)

    def set_mode(self, mode: str):
        self.mode_buttons[mode].setChecked(True)

    def set_shortcut_hints(self, keys: dict):
        """Tooltips of the mode buttons with their current keyboard shortcut, e.g. {'move': 'M'}."""
        for mode, b in self.mode_buttons.items():
            key = keys.get(mode)
            b.setToolTip(self.mode_tips[mode] + (f"   [{key}]" if key else "") +
                         "\nScroll: zoom · drag an empty place: pan")

    def _tool(self, text, tip, checkable=False, icon=None):
        b = QToolButton(self)
        b.setText(text)
        b.setToolTip(tip)
        b.setCheckable(checkable)
        b.setCursor(Qt.PointingHandCursor)
        b.setFont(button_font())
        b.setFixedHeight(30)
        if icon:
            b.setProperty("tool_icon", icon)
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            b.setIconSize(QSize(15, 15))
        return b

    def apply_theme(self, theme: dict):
        """Icons in the text color of each button (rust for Export, paper on a checked button)."""
        for b in self.findChildren(QToolButton):
            name = b.property("tool_icon")
            if name:
                col = theme["accent"] if b is self.btn_export else theme["text"]
                icon = make_tool_icon(name, col)
                icon.addPixmap(make_tool_icon(name, theme["toggle_on_text"]).pixmap(32, 32),
                               QIcon.Normal, QIcon.On)
                b.setIcon(icon)

    @staticmethod
    def _separator():
        s = QFrame()
        s.setFrameShape(QFrame.VLine)
        s.setFixedWidth(14)
        s.setStyleSheet("color: transparent;")
        return s
