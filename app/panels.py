"""
panels.py — right-side panels: Elements list and Plot settings.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGridLayout, QGroupBox,
                               QHBoxLayout, QLabel, QPushButton, QScrollArea, QSlider, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from .icons import make_element_icon

# Demo content of the list (in the real program this comes from the FlowModel)
DEMO_ELEMENTS = [
    ("uniform", "Uniform flow", "V∞ = 1,  α = 0°", 1),
    ("doublet", "Doublet", "μ = 1,  (0, 0),  δ = 0°", 1),
    ("vortex", "Vortex", "Γ = −2 (cw),  (0, 0)", 1),
]


class ElementsPanel(QWidget):
    """List of all elements with visibility checkbox and Edit / Duplicate / Delete."""
    edit_requested = Signal(str)
    message = Signal(str)

    def __init__(self, theme: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("DockBody")
        self.setAttribute(Qt.WA_StyledBackground, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Element", "Parameters"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setColumnWidth(0, 138)
        self.tree.setToolTip("Untick an element to hide it temporarily without deleting it.\n"
                             "Double-click to edit.")
        self.tree.itemDoubleClicked.connect(lambda it, _c: self.edit_requested.emit(it.data(0, Qt.UserRole)))
        lay.addWidget(self.tree, 1)

        row = QHBoxLayout()
        self.btn_edit = QPushButton("Edit…")
        self.btn_dup = QPushButton("Duplicate")
        self.btn_del = QPushButton("Delete")
        self.btn_del.setObjectName("Danger")
        for b in (self.btn_edit, self.btn_dup, self.btn_del):
            b.setCursor(Qt.PointingHandCursor)
            row.addWidget(b)
        lay.addLayout(row)

        self.btn_edit.clicked.connect(self._edit_selected)
        self.btn_dup.clicked.connect(lambda: self.message.emit("Prototype: Duplicate is not connected yet."))
        self.btn_del.clicked.connect(lambda: self.message.emit("Prototype: Delete is not connected yet."))

        self.apply_theme(theme)

    def apply_theme(self, theme: dict):
        self.tree.clear()
        for key, name, params, enabled in DEMO_ELEMENTS:
            it = QTreeWidgetItem([name, params])
            it.setIcon(0, make_element_icon(key, theme, 48))
            it.setCheckState(0, Qt.Checked if enabled else Qt.Unchecked)
            it.setData(0, Qt.UserRole, key)
            self.tree.addTopLevelItem(it)
        self.tree.setCurrentItem(self.tree.topLevelItem(0))

    def _edit_selected(self):
        it = self.tree.currentItem()
        if it:
            self.edit_requested.emit(it.data(0, Qt.UserRole))


class SettingsPanel(QScrollArea):
    """Plot limits, streamline density, layers, animation, computation quality."""
    message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        body = QWidget()
        body.setObjectName("DockBody")
        body.setAttribute(Qt.WA_StyledBackground, True)
        self.setWidget(body)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(10, 4, 10, 10)
        lay.setSpacing(4)

        # --- View range ---------------------------------------------------
        g = QGroupBox("View range")
        grid = QGridLayout(g)
        self.xmin, self.xmax = self._spin(-4.0), self._spin(4.0)
        self.ymin, self.ymax = self._spin(-2.6), self._spin(2.6)
        grid.addWidget(QLabel("x"), 0, 0)
        grid.addWidget(self.xmin, 0, 1)
        grid.addWidget(QLabel("to"), 0, 2)
        grid.addWidget(self.xmax, 0, 3)
        grid.addWidget(QLabel("y"), 1, 0)
        grid.addWidget(self.ymin, 1, 1)
        grid.addWidget(QLabel("to"), 1, 2)
        grid.addWidget(self.ymax, 1, 3)
        fit = QPushButton("Fit to elements")
        fit.clicked.connect(lambda: self.message.emit("Prototype: Fit to elements is not connected yet."))
        grid.addWidget(fit, 2, 0, 1, 4)
        lay.addWidget(g)

        # --- Streamlines ----------------------------------------------------
        g = QGroupBox("Streamlines")
        f = QFormLayout(g)
        f.addRow("Density", self._slider(1, 10, 5, "Number of streamlines"))
        f.addRow("Line width", self._slider(1, 5, 2))
        arrows = QCheckBox("Direction arrows")
        arrows.setChecked(True)
        f.addRow(arrows)
        f.addRow("Arrows per line", self._slider(1, 5, 1))
        lay.addWidget(g)

        # --- Layers ---------------------------------------------------------
        g = QGroupBox("Layers")
        v = QVBoxLayout(g)
        for text, on in [("Streamlines", True), ("Dividing streamline (ψ = 0) / body", True),
                         ("Equipotential lines (φ)", False), ("|V| contours", False),
                         ("Cp contours", False), ("Element markers", True), ("Walls", True)]:
            c = QCheckBox(text)
            c.setChecked(on)
            v.addWidget(c)
        lay.addWidget(g)

        # --- Animation ------------------------------------------------------
        g = QGroupBox("Animation")
        f = QFormLayout(g)
        f.addRow("Particles", self._slider(200, 5000, 1500))
        f.addRow("Speed", self._slider(1, 10, 5))
        f.addRow("Trail length", self._slider(0, 10, 4))
        lay.addWidget(g)

        # --- Computation ----------------------------------------------------
        g = QGroupBox("Computation")
        f = QFormLayout(g)
        q = QComboBox()
        q.addItems(["Low (fast)", "Medium", "High (export quality)"])
        q.setCurrentIndex(1)
        f.addRow("Grid quality", q)
        ref = QComboBox()
        ref.addItems(["From uniform flow (V∞)", "Custom…"])
        f.addRow("Cp reference", ref)
        lay.addWidget(g)

        lay.addStretch(1)

    @staticmethod
    def _spin(val):
        s = QDoubleSpinBox()
        s.setRange(-1e4, 1e4)
        s.setDecimals(2)
        s.setSingleStep(0.5)
        s.setValue(val)
        return s

    @staticmethod
    def _slider(lo, hi, val, tip=""):
        s = QSlider(Qt.Horizontal)
        s.setRange(lo, hi)
        s.setValue(val)
        s.setToolTip(tip)
        return s
