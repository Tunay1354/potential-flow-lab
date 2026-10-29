"""
panels.py — right-side panels: Elements list and Plot settings.
"""
from PySide6.QtCore import QEvent, QModelIndex, QObject, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QFontMetrics, QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGridLayout,
                               QGroupBox, QHBoxLayout, QHeaderView, QLabel, QPushButton, QScrollArea, QSlider,
                               QStyle, QStyledItemDelegate, QStyleOptionViewItem, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from .canvas import LAYERS
from .canvas.settings import SLIDERS, PlotSettings, slider
from .chrome import button_font, themed_combo
from .icons import make_element_icon


NEEDS_V_REF = ("cp", "surface")      # layers that show Cp: a note under them when there is no V∞


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


SUMMARY_ROLE = Qt.UserRole + 1          # the element's parameter text (e.summary()) on column 0
SUMMARY_SEP = ",  "                     # FlowElement.summary() joins its parts with this


def wrap_summary(text: str, fm: QFontMetrics, width: int) -> list[str]:
    """Break a parameter summary into lines no wider than `width` px, only between its parts
    ("V = 1", "vertex (0, 0)", ...), so a value is never split. A single part that is still too
    wide is elided (its full text is in the tooltip)."""
    parts = [p for p in text.split(SUMMARY_SEP) if p] or [""]
    lines: list[str] = []
    for part in parts:
        if lines and fm.horizontalAdvance(lines[-1] + SUMMARY_SEP + part) <= width:
            lines[-1] += SUMMARY_SEP + part
        else:
            lines.append(part)
    return [ln if fm.horizontalAdvance(ln) <= width else fm.elidedText(ln, Qt.ElideRight, max(width, 1))
            for ln in lines]


class ElementRowDelegate(QStyledItemDelegate):
    """Draws one element row: check box, icon and '1. Doublet' as before, the parameters in a column at
    PARAM_COLUMN px (where the old second column started). Parameters that do not fit on the rest of the
    line wrap onto more lines in that column, between parameters; a name too long to leave room for the
    column ('Sector (wedge) flow') puts the parameters on the lines below it instead. Nothing is cut off,
    whatever the panel width; short rows look exactly as with the old two fixed columns."""

    PARAM_COLUMN = 150                   # px from the row's left edge (the old column 0 width)
    GAP = 8                              # px at least between the name and the parameter column
    MIN_COLUMN = 90                      # px: a narrower parameter column is not used (lines below instead)

    def __init__(self, tree: QTreeWidget):
        super().__init__(tree)
        self.tree = tree

    def _layout(self, option, index, row_rect: QRect):
        """(text rect, title, parameter x, parameter lines, parameters below the title?)"""
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.rect = row_rect
        style = opt.widget.style() if opt.widget else self.tree.style()
        rect = style.subElementRect(QStyle.SE_ItemViewItemText, opt, opt.widget)
        fm = QFontMetrics(opt.font)
        title = opt.text
        summary = index.data(SUMMARY_ROLE) or ""
        col_x = row_rect.left() + self.PARAM_COLUMN + 2                 # + the item's 2 px side padding (theme)
        col_w = rect.right() + 1 - col_x
        beside = (rect.left() + fm.horizontalAdvance(title) + self.GAP <= col_x and col_w >= self.MIN_COLUMN)
        if not summary:
            return rect, title, col_x, [], False
        if beside:
            return rect, title, col_x, wrap_summary(summary, fm, col_w), False
        return rect, title, rect.left(), wrap_summary(summary, fm, rect.width()), True

    def sizeHint(self, option, index):
        base = super().sizeHint(option, index)                       # one text line + the item padding
        width = max(self.tree.viewport().width(), 1)
        _, _, _, lines, below = self._layout(option, index, QRect(0, 0, width, base.height()))
        n_lines = len(lines) + (1 if below else 0)
        extra = max(0, n_lines - 1) * QFontMetrics(option.font).lineSpacing()
        return QSize(base.width(), base.height() + extra)

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        style = opt.widget.style() if opt.widget else self.tree.style()
        rect, title, px, lines, below = self._layout(option, index, option.rect)
        opt.text = ""
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)   # background, check box, icon
        fm = QFontMetrics(opt.font)
        ls = fm.lineSpacing()
        n_lines = max(1, len(lines) + (1 if below else 0))
        y = rect.top() + max(0, (rect.height() - n_lines * ls) // 2)   # the text block centred like the icon
        painter.save()
        painter.setFont(opt.font)
        painter.setPen(opt.palette.color(opt.palette.ColorGroup.Normal, opt.palette.ColorRole.Text))
        flags = Qt.AlignLeft | Qt.AlignVCenter
        painter.drawText(QRect(rect.left(), y, rect.width(), ls), flags, fm.elidedText(title, Qt.ElideRight, rect.width()))
        if below:
            y += ls
        for ln in lines:
            painter.drawText(QRect(px, y, rect.right() + 1 - px, ls), flags, ln)
            y += ls
        painter.restore()


class _RelayoutOnWidth(QObject):
    """Re-measures the rows when the list's width changes (the parameters wrap to the new width)."""

    def __init__(self, tree: QTreeWidget):
        super().__init__(tree)
        self.tree = tree
        self.width = -1

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Resize and self.tree.viewport().width() != self.width:
            self.width = self.tree.viewport().width()
            QTimer.singleShot(0, self.tree, self.tree.doItemsLayout)
        return False


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
        # one visible column: name + parameters, wrapped (ElementRowDelegate); column 1 keeps the plain
        # parameter text (e.summary()) for code that reads it, but is not shown
        self.tree.setColumnHidden(1, True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tree.setUniformRowHeights(False)
        self.tree.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.row_delegate = ElementRowDelegate(self.tree)
        self.tree.setItemDelegate(self.row_delegate)
        self._relayout = _RelayoutOnWidth(self.tree)
        self.tree.viewport().installEventFilter(self._relayout)
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
            it.setData(0, SUMMARY_ROLE, e.summary())
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


class SettingsPanel(QScrollArea):
    """Plot limits, streamline density, layers, animation, computation quality."""
    message = Signal(str)
    view_edited = Signal(tuple, tuple)       # (xmin, xmax), (ymin, ymax) typed by the user
    fit_requested = Signal()
    setting_changed = Signal(str, object)    # a slider of settings.SLIDERS: key, value
    arrows_changed = Signal(bool)            # show direction arrows?
    layer_changed = Signal(str, bool)        # layer key (see LAYERS), visible?
    sections_changed = Signal()              # a section was hidden or shown again
    field_quality_changed = Signal(int)      # grid of the field layers: 1 low, 2 medium, 3 high
    cp_reference_changed = Signal(object)    # None = V∞ of the uniform flow, else the user's V_ref
    live_drag_changed = Signal(bool)         # streamlines follow a dragged element (program setting)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("DockBody")
        body.setAttribute(Qt.WA_StyledBackground, True)
        self.setWidget(body)
        body.installEventFilter(self)            # content got wider: the panel too (see eventFilter)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(10, 0, 10, 10)
        lay.setSpacing(2)
        self.sections = {}                     # key -> (title, group box), in panel order
        self.sliders = {}                      # setting key -> QSlider (settings.SLIDERS)

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
        self._add_slider(f, "density")
        self._add_slider(f, "line_width")
        self.c_arrows = QCheckBox("Direction arrows")
        self.c_arrows.setChecked(True)
        self.c_arrows.toggled.connect(self.arrows_changed)
        f.addRow(self.c_arrows)
        self._add_slider(f, "arrow_density")
        self._add_section("streamlines", "Streamlines", g, lay)

        # --- Layers ---------------------------------------------------------
        g = QGroupBox("LAYERS")
        v = QVBoxLayout(g)
        self.layer_boxes = {}
        self.v_ref_notes = {}                  # layer key -> "needs a reference speed V_ref" note
        for key, text, on in LAYERS:
            c = QCheckBox(text)
            c.setChecked(on)
            c.toggled.connect(lambda checked, k=key: self.layer_changed.emit(k, checked))
            v.addWidget(c)
            self.layer_boxes[key] = c
            if key in NEEDS_V_REF:
                # under the box, not in its text: a longer text would make the panel wider than it is
                # (everything on the right — slider ends, text — was cut off then)
                note = QLabel('needs a reference speed V_ref: <a href="vref">set V_ref…</a>')
                note.setObjectName("LayerNote")
                note.setWordWrap(True)
                note.setTextFormat(Qt.RichText)
                note.linkActivated.connect(lambda _link: self.show_cp_reference())
                note.setVisible(False)
                v.addWidget(note)
                self.v_ref_notes[key] = note
        self.cp_note = self.v_ref_notes["cp"]
        self.cp_needs_reference = False
        self._add_section("layers", "Layers", g, lay)

        # --- the animations: Particles, Pulses ---------------------------------
        for key, title, tip in (("particles", "Particles", "Settings of the Particles view (button above the plot)"),
                                ("pulses", "Pulses", "Settings of the Pulses view (button above the plot)")):
            g = QGroupBox(title.upper())
            g.setToolTip(tip)
            f = QFormLayout(g)
            for spec in SLIDERS:
                if spec.section == key:
                    self._add_slider(f, spec.key)
            self._add_section(key, title, g, lay)

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

    def eventFilter(self, obj, event):
        """The content asks for a new layout (e.g. a longer text): the panel's minimum width
        (minimumSizeHint) may have changed with it, so the dock is told to lay out again — otherwise the
        content would be wider than the panel and its right part cut off (no horizontal scrollbar)."""
        if obj is self.widget() and event.type() == QEvent.LayoutRequest:
            self.updateGeometry()
        return super().eventFilter(obj, event)

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

    def show_settings(self, settings):
        """Show the plot settings of an opened scene without emitting signals (File → Open sets the
        canvas itself, with the exact values from the file)."""
        widgets = list(self.sliders.values()) + [self.c_arrows, self.c_quality, self.c_cp_ref, self.s_vref]
        for w in widgets:
            w.blockSignals(True)
        for key, w in self.sliders.items():
            spec = slider(key)                           # (the Count maximum is higher with the graphics card)
            raw = int(round((getattr(settings, key) - spec.offset) / spec.step))
            w.setValue(min(max(raw, w.minimum()), w.maximum()))
        self.c_arrows.setChecked(settings.show_arrows)
        self.c_quality.setCurrentIndex(min(max(int(settings.field_quality), 1), 3) - 1)
        custom = settings.cp_reference
        self.c_cp_ref.setCurrentIndex(1 if custom else 0)
        if custom:
            self.s_vref.setValue(float(custom))
        self.s_vref.setEnabled(bool(custom))
        for w in widgets:
            w.blockSignals(False)

    def set_cp_available(self, available: bool):
        """The Cp layers (color bands, surface pressure) need a reference speed (V∞ of a uniform flow,
        or a custom V_ref)."""
        self.cp_needs_reference = not available
        for key, note in self.v_ref_notes.items():           # Cp bands and Cp on surfaces alike
            note.setVisible(not available)
            self.layer_boxes[key].setToolTip("" if available else "This scene has no uniform flow (V∞): set a "
                                             "custom V_ref in Computation → Cp reference")

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

    def set_slider_max(self, key: str, hi: int):
        """A slider's maximum (Particles → Count: higher while the graphics card draws). A value above it
        comes down to it (setting_changed is emitted then)."""
        self.sliders[key].setMaximum(int(hi))

    def _add_slider(self, form, key):
        """The slider of a setting (settings.SLIDERS), at the default value; moving it emits
        setting_changed(key, value)."""
        spec = slider(key)
        s = QSlider(Qt.Horizontal)
        s.setRange(spec.lo, spec.hi)
        s.setValue(spec.position(getattr(PlotSettings(), key)))
        s.setToolTip(spec.tip)
        s.valueChanged.connect(lambda pos, k=key: self.setting_changed.emit(k, slider(k).value(pos)))
        form.addRow(spec.label, s)
        self.sliders[key] = s
        return s
