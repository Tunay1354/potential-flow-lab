"""
panels.py — right-side panels: Elements list and Plot settings.
"""
from PySide6.QtCore import QModelIndex, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGridLayout, QGroupBox,
                               QHBoxLayout, QLabel, QPushButton, QScrollArea, QSlider, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from .icons import make_element_icon


def element_icon(element, theme, size=48):
    """Toolbar-style icon of an element instance (sink: inward arrows, clockwise vortex: mirrored)."""
    negative = getattr(element, "is_sink", False) or (element.TYPE == "vortex" and element.Gamma < 0)
    return make_element_icon(element.TYPE, theme, size, sign=-1 if negative else 1)


def element_title(element) -> str:
    if element.TYPE == "source":
        return "Sink" if element.is_sink else "Source"
    if element.TYPE == "wall":
        return "Wall"
    return element.NAME


class ElementsPanel(QWidget):
    """List of all elements with visibility checkbox and Edit / Duplicate / Delete.
    The panel never changes elements itself: it only emits requests, the main window turns them
    into undoable commands of the scene model.

    Requests are emitted LATER (next event-loop turn): a request rebuilds this list, and deleting the
    list item whose own click / double-click / tick signal is still running would crash Qt."""
    edit_requested = Signal(int)             # row index of the element to edit
    enabled_changed = Signal(int, bool)      # row index, ticked?
    duplicate_requested = Signal(int)
    delete_requested = Signal(int)
    selection_changed = Signal(int)          # −1 = nothing selected
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
                             "Double-click or Enter: edit   ·   Delete: remove   ·   Ctrl+D: duplicate")
        self.tree.itemDoubleClicked.connect(lambda it, _c: self._later(self.edit_requested,
                                                                       self.tree.indexOfTopLevelItem(it)))
        self.tree.itemChanged.connect(self._item_changed)
        self.tree.currentItemChanged.connect(lambda *_: self._selection_changed())
        self.tree.itemSelectionChanged.connect(self._selection_changed)
        # keyboard shortcuts that only act while the list has focus
        for key, fn in ((QKeySequence.Delete, self._delete_selected), (QKeySequence(Qt.Key_Backspace), self._delete_selected),
                        (QKeySequence(Qt.Key_Return), self._edit_selected), (QKeySequence(Qt.Key_Enter), self._edit_selected)):
            sc = QShortcut(key, self.tree)
            sc.setContext(Qt.WidgetWithChildrenShortcut)
            sc.activated.connect(fn)
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
        self.btn_dup.clicked.connect(self._duplicate_selected)
        self.btn_del.clicked.connect(self._delete_selected)
        self.btn_edit.setToolTip("Edit the selected element (or double-click it)")
        self.btn_dup.setToolTip("Copy the selected element, shifted by (0.5, 0.5)   [Ctrl+D]")
        self.btn_del.setToolTip("Remove the selected element   [Delete]  —  Ctrl+Z brings it back")

        self.theme = theme
        self.elements = []

    def apply_theme(self, theme: dict):
        self.theme = theme
        self.set_elements(self.elements)

    def current_row(self) -> int:
        it = self.tree.currentItem()
        if it is None or not it.isSelected():
            return -1
        return self.tree.indexOfTopLevelItem(it)

    def select_row(self, row: int):
        """Select row `row`; row < 0 (or out of range) clears the selection."""
        if 0 <= row < self.tree.topLevelItemCount():
            self.tree.setCurrentItem(self.tree.topLevelItem(row))
            self.tree.topLevelItem(row).setSelected(True)
        else:
            self.tree.blockSignals(True)
            self.tree.clearSelection()
            self.tree.setCurrentIndex(QModelIndex())
            self.tree.blockSignals(False)
        self._selection_changed()

    def set_elements(self, elements: list, select: int | None = None):
        self.elements = elements
        current = self.current_row() if select is None else select
        self.tree.blockSignals(True)
        self.tree.clear()
        for k, e in enumerate(elements):
            it = QTreeWidgetItem([f"{k + 1}. {element_title(e)}", e.summary()])
            it.setIcon(0, element_icon(e, self.theme))
            it.setCheckState(0, Qt.Checked if e.enabled else Qt.Unchecked)
            it.setData(0, Qt.UserRole, e.TYPE)
            it.setToolTip(1, e.summary())
            self.tree.addTopLevelItem(it)
        if elements and current is not None and current >= 0:      # keep / set the selection (none stays none)
            item = self.tree.topLevelItem(min(current, len(elements) - 1))
            self.tree.setCurrentItem(item)
            item.setSelected(True)
        self.tree.blockSignals(False)
        self._selection_changed()

    def _selection_changed(self):
        row = self.current_row()
        for b in (self.btn_edit, self.btn_dup, self.btn_del):
            b.setEnabled(row >= 0)
        self.selection_changed.emit(row)

    @staticmethod
    def _later(signal, *args):
        QTimer.singleShot(0, lambda: signal.emit(*args))

    def _item_changed(self, item, column):
        if column == 0:
            self._later(self.enabled_changed, self.tree.indexOfTopLevelItem(item), item.checkState(0) == Qt.Checked)

    def _edit_selected(self):
        if self.current_row() >= 0:
            self._later(self.edit_requested, self.current_row())

    def _duplicate_selected(self):
        if self.current_row() >= 0:
            self._later(self.duplicate_requested, self.current_row())

    def _delete_selected(self):
        if self.current_row() >= 0:
            self._later(self.delete_requested, self.current_row())


# plot layers: key, label, visible at start, implemented yet
LAYERS = (
    ("streamlines", "Streamlines", True, True),
    ("dividing", "Dividing streamlines", True, True),
    ("stagnation", "Stagnation points", True, True),
    ("equipotential", "Equipotential lines (φ)", False, False),
    ("speed", "|V| contours", False, False),
    ("cp", "Cp contours", False, False),
    ("markers", "Element markers", True, True),
    ("walls", "Walls", True, True),
)


class SettingsPanel(QScrollArea):
    """Plot limits, streamline density, layers, animation, computation quality."""
    message = Signal(str)
    view_edited = Signal(tuple, tuple)       # (xmin, xmax), (ymin, ymax) typed by the user
    fit_requested = Signal()
    density_changed = Signal(float)
    line_width_changed = Signal(float)
    arrows_changed = Signal(bool, float)     # show arrows?, arrow density (1 = default)
    layer_changed = Signal(str, bool)        # layer key (see LAYERS), visible?

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
        fit.clicked.connect(self.fit_requested)
        grid.addWidget(fit, 2, 0, 1, 4)
        for sp in (self.xmin, self.xmax, self.ymin, self.ymax):
            sp.editingFinished.connect(self._view_typed)
        lay.addWidget(g)

        # --- Streamlines ----------------------------------------------------
        g = QGroupBox("Streamlines")
        f = QFormLayout(g)
        self.s_density = self._slider(1, 10, 5, "Number of streamlines")
        self.s_width = self._slider(1, 5, 2)
        self.c_arrows = QCheckBox("Direction arrows")
        self.c_arrows.setChecked(True)
        self.s_arrows = self._slider(1, 5, 1)
        f.addRow("Density", self.s_density)
        f.addRow("Line width", self.s_width)
        f.addRow(self.c_arrows)
        f.addRow("Arrow density", self.s_arrows)
        lay.addWidget(g)
        self.s_density.valueChanged.connect(lambda v: self.density_changed.emit(v / 5.0))
        self.s_width.valueChanged.connect(lambda v: self.line_width_changed.emit(0.6 + 0.4 * v))
        self.c_arrows.toggled.connect(lambda on: self.arrows_changed.emit(on, self.arrow_density()))
        self.s_arrows.valueChanged.connect(lambda v: self.arrows_changed.emit(self.c_arrows.isChecked(),
                                                                             self.arrow_density()))

        # --- Layers ---------------------------------------------------------
        g = QGroupBox("Layers")
        v = QVBoxLayout(g)
        self.layer_boxes = {}
        for key, text, on, ready in LAYERS:
            c = QCheckBox(text)
            c.setChecked(on)
            c.setEnabled(ready)
            if not ready:
                c.setToolTip("Comes with Phase 4")
            c.toggled.connect(lambda checked, k=key: self.layer_changed.emit(k, checked))
            v.addWidget(c)
            self.layer_boxes[key] = c
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

    def set_view(self, xr, yr):
        """Show the current plot limits without triggering view_edited."""
        for sp, val in ((self.xmin, xr[0]), (self.xmax, xr[1]), (self.ymin, yr[0]), (self.ymax, yr[1])):
            if not sp.hasFocus():
                sp.blockSignals(True)
                sp.setValue(val)
                sp.blockSignals(False)

    def _view_typed(self):
        xr, yr = (self.xmin.value(), self.xmax.value()), (self.ymin.value(), self.ymax.value())
        if xr[0] < xr[1] and yr[0] < yr[1]:
            self.view_edited.emit(xr, yr)
        else:
            self.message.emit("View range: minimum must be smaller than maximum.")

    @staticmethod
    def _spin(val):
        s = QDoubleSpinBox()
        s.setRange(-1e4, 1e4)
        s.setDecimals(2)
        s.setSingleStep(0.5)
        s.setValue(val)
        return s

    def set_streamline_settings(self, density: float, line_width: float, show_arrows: bool,
                                arrow_density: float):
        """Move the sliders to the given values without emitting signals (File → Open sets the
        canvas itself, with the exact values from the file)."""
        for w, val in ((self.s_density, round(density * 5.0)), (self.s_width, round((line_width - 0.6) / 0.4)),
                       (self.s_arrows, round((arrow_density - 0.5) / 0.5)), (self.c_arrows, show_arrows)):
            w.blockSignals(True)
            if isinstance(val, bool):
                w.setChecked(val)
            else:
                w.setValue(int(min(max(val, w.minimum()), w.maximum())))
            w.blockSignals(False)

    def arrow_density(self) -> float:
        """Slider 1…5 -> arrow density 1…3 (1 = default spacing between arrows)."""
        return 0.5 + 0.5 * self.s_arrows.value()

    @staticmethod
    def _slider(lo, hi, val, tip=""):
        s = QSlider(Qt.Horizontal)
        s.setRange(lo, hi)
        s.setValue(val)
        s.setToolTip(tip)
        return s
