"""
panels.py — right-side panels: Elements list and Plot settings.
"""
from PySide6.QtCore import QModelIndex, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGridLayout, QGroupBox,
                               QHBoxLayout, QLabel, QPushButton, QScrollArea, QSlider, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from .canvas import LAYERS
from .chrome import button_font, themed_combo
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
        lay.setContentsMargins(8, 2, 8, 8)
        lay.setSpacing(10)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Element", "Parameters"])
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(False)
        self.tree.setColumnWidth(0, 150)
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
            b.setFont(button_font())
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

    def _later(self, signal, *args):
        """Emit after the current event (not inside the item view's own handler); dropped if the panel
        is gone by then."""
        QTimer.singleShot(0, self, lambda: signal.emit(*args))

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
# sliders whose position stands for a setting: value = offset + step × position
SLIDER_SCALES = {"density": (0.0, 0.2),          # 1…10 -> 0.2…2   (1 = default number of streamlines)
                 "line_width": (0.6, 0.4),       # 1…5  -> 1.0…2.6 px
                 "arrow_density": (0.5, 0.5)}    # 1…5  -> 1…3     (1 = default spacing between arrows)


def slider_value(key: str, position: int) -> float:
    offset, step = SLIDER_SCALES[key]
    return round(offset + step * position, 9)          # 1.4, not 1.4000000000000001 (saved in the scene)


def slider_position(key: str, value: float) -> int:
    offset, step = SLIDER_SCALES[key]
    return round((value - offset) / step)


class SettingsPanel(QScrollArea):
    """Plot limits, streamline density, layers, animation, computation quality."""
    message = Signal(str)
    view_edited = Signal(tuple, tuple)       # (xmin, xmax), (ymin, ymax) typed by the user
    fit_requested = Signal()
    density_changed = Signal(float)
    line_width_changed = Signal(float)
    arrows_changed = Signal(bool, float)     # show arrows?, arrow density (1 = default)
    layer_changed = Signal(str, bool)        # layer key (see LAYERS), visible?
    sections_changed = Signal()              # a section was hidden or shown again
    field_quality_changed = Signal(int)      # grid of the field layers: 1 low, 2 medium, 3 high
    cp_reference_changed = Signal(object)    # None = V∞ of the uniform flow, else the user's V_ref
    live_drag_changed = Signal(bool)         # streamlines follow a dragged element (program setting)
    particles_changed = Signal(int)          # animation: number of particles
    animation_speed_changed = Signal(int)    # animation: speed slider 1 … 10
    trail_changed = Signal(int)              # animation: trail length slider 0 … 10
    animation_style_changed = Signal(int)    # animation: 0 particles, 1 pulses along streamlines

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("DockBody")
        body.setAttribute(Qt.WA_StyledBackground, True)
        self.setWidget(body)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(10, 0, 10, 10)
        lay.setSpacing(2)
        self.sections = {}                     # key -> (title, group box), in panel order

        # --- View range ---------------------------------------------------
        g = QGroupBox("VIEW RANGE")
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
        fit.setFont(button_font())
        fit.clicked.connect(self.fit_requested)
        grid.addWidget(fit, 2, 0, 1, 4)
        for sp in (self.xmin, self.xmax, self.ymin, self.ymax):
            sp.editingFinished.connect(self._view_typed)
        self._add_section("view", "View range", g, lay)

        # --- Streamlines ----------------------------------------------------
        g = QGroupBox("STREAMLINES")
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
        self._add_section("streamlines", "Streamlines", g, lay)
        self.s_density.valueChanged.connect(lambda v: self.density_changed.emit(slider_value("density", v)))
        self.s_width.valueChanged.connect(lambda v: self.line_width_changed.emit(slider_value("line_width", v)))
        self.c_arrows.toggled.connect(self._arrows_edited)
        self.s_arrows.valueChanged.connect(self._arrows_edited)

        # --- Layers ---------------------------------------------------------
        g = QGroupBox("LAYERS")
        v = QVBoxLayout(g)
        self.layer_boxes = {}
        for key, text, on in LAYERS:
            c = QCheckBox(text)
            c.setChecked(on)
            c.toggled.connect(lambda checked, k=key: self.layer_changed.emit(k, checked))
            v.addWidget(c)
            self.layer_boxes[key] = c
        self._add_section("layers", "Layers", g, lay)

        # --- Animation ------------------------------------------------------
        g = QGroupBox("ANIMATION")
        f = QFormLayout(g)
        st = self.c_anim_style = themed_combo(QComboBox())
        st.addItems(["Particles", "Pulses along streamlines"])
        st.setToolTip("Particles: tracer particles carried by the flow, with fading trails.\n"
                      "Pulses: bright dashes running along the streamlines at the local speed\n"
                      "(released at the same moments: they stretch where the flow is fast).")
        f.addRow("Style", st)
        self.s_particles = self._slider(200, 5000, 1500, "Number of tracer particles")
        self.s_anim_speed = self._slider(1, 10, 5, "How fast the animation runs (5: a typical particle crosses the view in 6 s)")
        self.s_trail = self._slider(0, 10, 4, "Particles: how long the trails are (0: dots only).\n"
                                                "Pulses: how long each pulse is (0: short dashes).")
        f.addRow("Particles", self.s_particles)
        f.addRow("Speed", self.s_anim_speed)
        f.addRow("Trail length", self.s_trail)
        self.s_particles.valueChanged.connect(self.particles_changed)
        self.s_anim_speed.valueChanged.connect(self.animation_speed_changed)
        self.s_trail.valueChanged.connect(self.trail_changed)
        st.currentIndexChanged.connect(self._animation_style_edited)
        self._add_section("animation", "Animation", g, lay)

        # --- Computation ----------------------------------------------------
        g = QGroupBox("COMPUTATION")
        f = QFormLayout(g)
        q = self.c_quality = themed_combo(QComboBox())
        q.addItems(["Low (fast)", "Medium", "High (export quality)"])
        q.setCurrentIndex(1)
        q.setToolTip("Grid of the φ lines and the |V| / Cp color bands")
        q.currentIndexChanged.connect(lambda i: self.field_quality_changed.emit(i + 1))
        f.addRow("Grid quality", q)
        ref = self.c_cp_ref = themed_combo(QComboBox())
        ref.addItems(["From uniform flow (V∞)", "Custom"])
        ref.setToolTip("Cp = 1 − (V / V_ref)²  (probe, Cp color bands, exported data)")
        f.addRow("Cp reference", ref)
        self.s_vref = QDoubleSpinBox()
        self.s_vref.setRange(0.001, 1e6)
        self.s_vref.setDecimals(3)
        self.s_vref.setValue(1.0)
        self.s_vref.setSuffix("  m/s")
        self.s_vref.setEnabled(False)
        f.addRow("V_ref", self.s_vref)
        ref.currentIndexChanged.connect(self._cp_reference_edited)
        self.s_vref.editingFinished.connect(self._cp_reference_edited)
        self.c_live = QCheckBox("Live update while dragging")
        self.c_live.setToolTip("The streamlines follow an element while you drag it (Move mode).\n"
                               "Off: they fade and are computed when you release it.")
        self.c_live.toggled.connect(self.live_drag_changed)
        f.addRow(self.c_live)
        self._add_section("computation", "Computation", g, lay)

        lay.addStretch(1)

    def minimumSizeHint(self) -> QSize:
        """At least as wide as the content PLUS the vertical scrollbar: without it the scrollbar (shown
        when the panel is short) would cover the right edge, e.g. a slider's handle at its maximum."""
        hint = super().minimumSizeHint()
        body = self.widget().minimumSizeHint().width() if self.widget() else 0
        bar = self.verticalScrollBar().sizeHint().width()
        return QSize(max(hint.width(), body + bar + 2 * self.frameWidth()), hint.height())

    # ------------------------------------------------------------------ sections
    def _add_section(self, key, title, group, layout):
        """Each group (View range, Streamlines, ...) is a section the user can hide (right-click on the
        panel title, or View → Panels) and show again."""
        self.sections[key] = (title, group)
        layout.addWidget(group)

    def set_section_visible(self, key: str, on: bool):
        group = self.sections[key][1]
        if group.isHidden() == on:
            group.setVisible(on)
            self.sections_changed.emit()

    def section_visible(self, key: str) -> bool:
        return not self.sections[key][1].isHidden()

    def hidden_sections(self) -> list:
        return [k for k in self.sections if not self.section_visible(k)]

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

    def _animation_style_edited(self, index: int):
        self.s_particles.setEnabled(index != 1)                 # (the pulses follow the streamlines)
        self.animation_style_changed.emit(index)

    def show_settings(self, settings):
        """Show the plot settings of an opened scene without emitting signals (File → Open sets the
        canvas itself, with the exact values from the file)."""
        widgets = (self.s_density, self.s_width, self.s_arrows, self.c_arrows, self.c_quality, self.c_cp_ref,
                   self.s_vref, self.s_particles, self.s_anim_speed, self.s_trail, self.c_anim_style)
        for w in widgets:
            w.blockSignals(True)
        for w, key in ((self.s_density, "density"), (self.s_width, "line_width"), (self.s_arrows, "arrow_density")):
            w.setValue(min(max(slider_position(key, getattr(settings, key)), w.minimum()), w.maximum()))
        self.c_arrows.setChecked(settings.show_arrows)
        for w, val in ((self.s_particles, settings.particles), (self.s_anim_speed, settings.anim_speed),
                       (self.s_trail, settings.trail)):
            w.setValue(min(max(int(val), w.minimum()), w.maximum()))
        self.c_anim_style.setCurrentIndex(1 if settings.anim_style == 1 else 0)
        self.s_particles.setEnabled(settings.anim_style != 1)
        self.c_quality.setCurrentIndex(min(max(int(settings.field_quality), 1), 3) - 1)
        custom = settings.cp_reference
        self.c_cp_ref.setCurrentIndex(1 if custom else 0)
        if custom:
            self.s_vref.setValue(float(custom))
        self.s_vref.setEnabled(bool(custom))
        for w in widgets:
            w.blockSignals(False)

    def set_cp_available(self, available: bool):
        """The Cp layer needs a reference speed (V∞ of a uniform flow, or a custom V_ref)."""
        box = self.layer_boxes["cp"]
        base = dict((k, t) for k, t, _on in LAYERS)["cp"]
        box.setText(base if available else base + "  — needs V_ref")
        box.setToolTip("" if available else "This scene has no uniform flow (V∞): set a custom V_ref in "
                       "Computation → Cp reference")

    def show_cp_reference(self):
        """Bring the V_ref field into view: Computation section shown, 'Custom' chosen, field focused."""
        self.set_section_visible("computation", True)
        if self.c_cp_ref.currentIndex() != 1:
            self.c_cp_ref.setCurrentIndex(1)            # emits cp_reference_changed with the current V_ref
        self.ensureWidgetVisible(self.s_vref)
        self.s_vref.setFocus()
        self.s_vref.selectAll()

    def set_live_drag(self, on: bool):
        """Show the saved program setting (no signal)."""
        self.c_live.blockSignals(True)
        self.c_live.setChecked(on)
        self.c_live.blockSignals(False)

    def _cp_reference_edited(self, *_):
        custom = self.c_cp_ref.currentIndex() == 1
        self.s_vref.setEnabled(custom)
        self.cp_reference_changed.emit(self.s_vref.value() if custom else None)

    def _arrows_edited(self, *_):
        self.arrows_changed.emit(self.c_arrows.isChecked(), slider_value("arrow_density", self.s_arrows.value()))

    @staticmethod
    def _slider(lo, hi, val, tip=""):
        s = QSlider(Qt.Horizontal)
        s.setRange(lo, hi)
        s.setValue(val)
        s.setToolTip(tip)
        return s
