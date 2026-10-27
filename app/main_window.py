"""
main_window.py — assembles menus, element toolbar, plot, side panels and status bar, and connects
them to the scene model.

Data flow (one direction only):
    user action (toolbar, dialog, list, menu, shortcut)
        -> SceneModel command (add / edit / delete / hide / load ...)   [undoable]
        -> model notifies the window
        -> window refreshes list, Elements menu, plot, scene check, Undo/Redo texts
No widget changes the elements directly, so undo / redo always restores exactly.
"""
import os
import re

import numpy as np
from PySide6.QtCore import QByteArray, QEvent, QRect, QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QActionGroup, QColor, QDesktopServices, QFont, QKeySequence, QPalette, QShortcut
from PySide6.QtWidgets import (QAbstractButton, QApplication, QDockWidget, QFileDialog, QLabel, QMainWindow,
                               QHBoxLayout, QMenuBar, QMessageBox, QWidget)

from app_info import APP_NAME, APP_VERSION, ORGANIZATION
from model import EXTENSION, SceneDocument, SceneFileError, SceneModel, preview_change
from model import load_scene as read_scene_file
from model import save_scene as write_scene_file
from physics import ELEMENT_TYPES, check_scene, reference_speed, velocity
from physics.field import fluid_mask, singular_points

from .canvas import PlotCanvas
from .chrome import (DropIndicator, ElementPalette, HeaderBar, PanelBody, PanelTitle, load_fonts, paint_paper_grid,
                     tint_title_bar)
from .dialogs import ElementDialog
from .element_specs import spec_for, toolbar_types
from .icons import make_app_icon, make_element_icon, make_palette_icon
from .panels import LAYERS, ElementsPanel, SettingsPanel, element_icon, element_title
from .recent_files import RecentFiles
from .scene import PRESETS_DIR, list_presets, starter_scene
from .shortcuts import Shortcuts, ShortcutsDialog
from .theme import DARK, DEFAULT_THEME, FONT, LAYOUT, LIGHT, build_stylesheet

DUPLICATE_OFFSET = (0.5, 0.5)
# short names under the toolbar icons (the full name is in the tooltip)
TOOLBAR_NAMES = {"uniform": "Uniform", "source": "Source", "vortex": "Vortex", "doublet": "Doublet",
                 "sector": "Sector", "wall": "Wall"}
LAYOUT_STATE_VERSION = 1          # bump when the dock layout changes incompatibly (old saved layouts ignored)
SIDE_AREAS = (Qt.LeftDockWidgetArea, Qt.RightDockWidgetArea)
FILE_FILTER = f"{APP_NAME} scenes (*{EXTENSION});;JSON files (*.json);;All files (*)"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        load_fonts()
        self.theme = DEFAULT_THEME
        self.scene_title = "Lifting (rotating) cylinder"
        self.current_path: str | None = None           # file of the scene (None = never saved)
        self.recent = RecentFiles()
        self.setAcceptDrops(True)                      # drop a .pflow file on the window to open it
        self.resize(*LAYOUT["window_size"])

        # the scene: every change goes through the model (undo / redo)
        self.model = SceneModel(starter_scene())
        self.model.mark_clean()
        self.elements = self.model.elements            # same list object for the whole session

        # header: wooden plank (logo, name, file) + ruler with the menus (and, later, the beaver)
        self.header = HeaderBar(self)
        self.setMenuWidget(self.header)
        self._menu_bar = self.header.menu_bar
        self.header.plank.version.setText(f"REV {APP_VERSION}")

        # central plot card on the paper
        self.canvas = PlotCanvas(self.theme, self.elements, self)
        desk = self.desk = QWidget(self)
        desk_lay = self._desk_layout = QHBoxLayout(desk)       # [element palette] [plot card] (or mirrored)
        g = LAYOUT["gap"]
        desk_lay.setContentsMargins(g, 0, g - 4, g)            # 4 = dock separator
        desk_lay.setSpacing(g)
        desk_lay.addWidget(self.canvas, 1)
        self.setCentralWidget(desk)
        self.canvas.bar.message.connect(self.flash)
        self.canvas.bar.btn_export.clicked.connect(self.export_figure)
        self.canvas.probe.connect(self._update_probe)
        self.canvas.element_clicked.connect(self.select_element)
        self.canvas.stagnation_clicked.connect(self.select_stagnation)
        self.canvas.element_moved.connect(self.move_element)
        self.canvas.element_dropped.connect(lambda key, pos: self.add_element_dialog(key, at=pos))
        self.canvas.element_double_clicked.connect(
            lambda row: (self.select_element(row), QTimer.singleShot(0, lambda: self.edit_element(row))))

        # side panels (dock widgets): only left or right of the plot, stacked; no floating, no tabs
        self.setDockOptions(QMainWindow.AnimatedDocks)
        ep = self.elements_panel = ElementsPanel(self.theme)
        ep.edit_requested.connect(self.edit_element)
        ep.enabled_changed.connect(lambda row, on: self.model.set_enabled(row, on))
        ep.duplicate_requested.connect(self.duplicate_element)
        ep.delete_requested.connect(self.delete_element)
        ep.selection_changed.connect(self._selection_changed)
        ep.message.connect(self.flash)
        self.dock_elements = self._dock("Elements", ep)
        self.dock_elements.widget().setMinimumHeight(LAYOUT["elements_panel_min_height"])

        self.settings_panel = SettingsPanel()
        self.settings_panel.message.connect(self.flash)
        sp, cv = self.settings_panel, self.canvas
        sp.density_changed.connect(cv.set_density)
        sp.line_width_changed.connect(cv.set_line_width)
        sp.arrows_changed.connect(cv.set_arrows)
        sp.layer_changed.connect(self._layer_changed)
        sp.view_edited.connect(cv.set_view)
        sp.fit_requested.connect(cv.fit_view)
        cv.view_changed.connect(sp.set_view)
        self.dock_settings = self._dock("Plot settings", self.settings_panel)
        sp.sections_changed.connect(self._sections_changed)
        title = self.dock_settings.titleBarWidget()
        title.setContextMenuPolicy(Qt.CustomContextMenu)
        title.customContextMenuRequested.connect(
            lambda pos: self.sections_menu.exec(title.mapToGlobal(pos)))
        title.setToolTip("Drag to move the panel  ·  right-click to choose the sections shown")
        self._default_dock_layout()

        self._build_toolbar()
        self._build_menus()
        self._register_shortcuts()
        self._build_statusbar()
        self._build_plot_shortcuts()
        self.canvas.computed.connect(self._update_status)
        self.canvas.view_changed.connect(self._update_title_block_view)
        self.apply_theme(self.theme)

        # a click anywhere else in the window clears the selection (see eventFilter)
        QApplication.instance().installEventFilter(self)
        esc = QShortcut(QKeySequence(Qt.Key_Escape), self)
        esc.activated.connect(lambda: self.canvas.cancel_drag() or self.select_element(-1))

        self.model.subscribe(self._on_model_changed)
        self._on_model_changed(None)
        self.restore_layout()                          # the panels as the user left them last time

    # ------------------------------------------------------------------ building blocks
    def menuBar(self) -> QMenuBar:
        """The menus live on the ruler of the header (not in Qt's own menu bar)."""
        return self._menu_bar

    def _dock(self, title, widget):
        """Side panel: a card with a double frame; its title bar (heading over a rule) moves it."""
        d = QDockWidget(title, self)
        d.setObjectName(title)
        d.setWidget(PanelBody(widget))
        d.setTitleBarWidget(PanelTitle(title))
        d.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable)   # no floating
        d.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)              # never above / below
        d.dockLocationChanged.connect(lambda _area, d=d: self._place_dock_card(d))
        d.topLevelChanged.connect(lambda _floating, d=d: self._place_dock_card(d))
        self.addDockWidget(Qt.RightDockWidgetArea, d)
        self._place_dock_card(d)
        return d

    def _place_dock_card(self, d):
        """Paper margin between the card and the window edge, depending on where the dock is."""
        g = LAYOUT["gap"]
        if d.isFloating():
            title, body = (0, 0, 0, 0), (0, 0, 0, 0)
        elif self.dockWidgetArea(d) == Qt.LeftDockWidgetArea:
            title, body = (g, 0, 0, 0), (g, 0, 0, g)
        else:
            title, body = (0, 0, g, 0), (0, 0, g, g)
        d.titleBarWidget().set_outer(title)
        d.widget().set_outer(body)

    def _default_dock_layout(self):
        """Both panels on the right, Elements above Plot settings (also View → Panels → Reset layout)."""
        de, ds = self.dock_elements, self.dock_settings
        for d in (de, ds):
            self.removeDockWidget(d)
        self.addDockWidget(Qt.RightDockWidgetArea, de)
        self.addDockWidget(Qt.RightDockWidgetArea, ds)
        self.splitDockWidget(de, ds, Qt.Vertical)
        for d in (de, ds):
            d.show()
            self._place_dock_card(d)
        self.resizeDocks([de, ds], [LAYOUT["right_panel_width"]] * 2, Qt.Horizontal)
        self.resizeDocks([de, ds], [260, 560], Qt.Vertical)

    # ------------------------------------------------------------------ layout: remember / reset
    def reset_layout(self):
        """View → Panels → Reset layout: the layout of the first start."""
        self._default_dock_layout()
        self.set_palette_side("left")
        for key in self.settings_panel.sections:
            self.settings_panel.set_section_visible(key, True)
        self.flash("Layout reset.")

    def save_layout(self):
        s = QSettings()
        s.setValue("layout/version", LAYOUT_STATE_VERSION)
        s.setValue("layout/state", self.saveState(LAYOUT_STATE_VERSION))
        s.setValue("layout/palette_side", self.palette_side)
        s.setValue("layout/hidden_sections", ",".join(self.settings_panel.hidden_sections()))

    def restore_layout(self):
        """Panels, palette side and hidden Plot settings sections as saved when the window was closed.
        A missing, old or invalid saved layout leaves the default layout."""
        s = QSettings()
        if int(s.value("layout/version", 0) or 0) != LAYOUT_STATE_VERSION:
            return
        state = s.value("layout/state")
        if isinstance(state, QByteArray) and self.restoreState(state, LAYOUT_STATE_VERSION):
            docks = (self.dock_elements, self.dock_settings)
            if any(d.isFloating() or self.dockWidgetArea(d) not in SIDE_AREAS for d in docks):
                self._default_dock_layout()                 # never restore a forbidden place
            for d in docks:
                self._place_dock_card(d)
        self.set_palette_side(str(s.value("layout/palette_side", "left")))
        hidden = str(s.value("layout/hidden_sections", "") or "")
        for key in self.settings_panel.sections:
            self.settings_panel.set_section_visible(key, key not in hidden.split(","))

    # ------------------------------------------------------------------ element palette left / right
    def set_palette_side(self, side: str):
        """Put the element palette left or right of the plot card (it keeps its shape)."""
        side = "right" if side == "right" else "left"
        lay, pal = self._desk_layout, self.element_toolbar
        lay.removeWidget(pal)
        lay.insertWidget(0 if side == "left" else 1, pal)
        self.palette_side = side

    def _palette_target(self, global_pos) -> str:
        x = self.desk.mapFromGlobal(global_pos).x()
        return "left" if x < self.desk.width() / 2 else "right"

    def _palette_slot(self, side: str) -> QRect:
        """Where the palette sits on the given side (for the drop indicator)."""
        lay = self._desk_layout
        m = lay.contentsMargins()
        w = self.element_toolbar.width()
        h = self.desk.height() - m.top() - m.bottom()
        x = m.left() if side == "left" else self.desk.width() - m.right() - w
        return QRect(x, m.top(), w, h)

    def _palette_drag_moved(self, global_pos):
        ind = self._drop_indicator
        ind.setGeometry(self._palette_slot(self._palette_target(global_pos)))
        ind.raise_()
        ind.show()

    def _palette_drag_finished(self, global_pos):
        self._drop_indicator.hide()
        side = self._palette_target(global_pos)
        if side != self.palette_side:
            self.set_palette_side(side)

    # ------------------------------------------------------------------ Plot settings sections
    def _sections_changed(self):
        sp = self.settings_panel
        hidden = sp.hidden_sections()
        self.dock_settings.titleBarWidget().note.setText(f"{len(hidden)} HIDDEN" if hidden else "")
        for key, act in self.section_actions.items():
            act.blockSignals(True)
            act.setChecked(sp.section_visible(key))
            act.blockSignals(False)

    def _dock_parts(self):
        for d in (self.dock_elements, self.dock_settings):
            yield d.titleBarWidget()
            yield d.widget()

    def _build_toolbar(self):
        """Element palette left of the plot (a card on the paper, like the side panels)."""
        pal = ElementPalette(self)
        self.element_actions = {}
        separated = False
        for key in toolbar_types():
            spec = spec_for(key)
            if ELEMENT_TYPES[key].IS_BOUNDARY and not separated:
                pal.add_separator()     # walls are boundaries, not flows -> visually separated
                separated = True
            act = QAction(TOOLBAR_NAMES.get(key, spec.name), self)
            act.setToolTip(f"<b>{spec.name}</b><br>{spec.description}")
            act.triggered.connect(lambda _=False, k=key: self.add_element_dialog(k))
            pal.add_action(act, key)
            self.addAction(act)                      # its keyboard shortcut (if the user sets one) works
            self.element_actions[key] = act
        self.element_toolbar = pal
        self.palette_side = "left"
        self._desk_layout.insertWidget(0, pal)
        pal.drag_moved.connect(self._palette_drag_moved)
        pal.drag_finished.connect(self._palette_drag_finished)
        self._drop_indicator = DropIndicator(self.desk)

    def _build_menus(self):
        mb = self.menuBar()

        # File
        m = mb.addMenu("&File")
        self.act_new = m.addAction("New")
        self.act_new.setShortcut(QKeySequence.New)
        self.act_new.triggered.connect(self.new_scene)
        self.act_open = m.addAction("Open…")
        self.act_open.setShortcut(QKeySequence.Open)
        self.act_open.triggered.connect(lambda: self.open_scene())
        self.recent_menu = m.addMenu("Open recent")
        self.recent_menu.aboutToShow.connect(self._rebuild_recent_menu)
        self._rebuild_recent_menu()
        m.addSeparator()
        self.act_save = m.addAction("Save")
        self.act_save.setShortcut(QKeySequence.Save)
        self.act_save.triggered.connect(self.save_scene)
        self.act_save_as = m.addAction("Save as…")
        self.act_save_as.setShortcuts([QKeySequence.SaveAs, QKeySequence("Ctrl+Shift+S")])
        self.act_save_as.triggered.connect(self.save_scene_as)
        m.addSeparator()
        self.act_export_fig = m.addAction("Export figure (PNG / SVG / PDF)…")
        self.act_export_fig.setShortcut("Ctrl+E")
        self.act_export_fig.triggered.connect(self.export_figure)
        self.act_export_data = m.addAction("Export data (CSV)…")
        self.act_export_data.triggered.connect(self.export_data)
        m.addSeparator()
        m.addAction("Clear all").triggered.connect(self.clear_all)
        m.addSeparator()
        quit_ = self.act_exit = m.addAction("Exit")
        quit_.setShortcut(QKeySequence("Ctrl+Q"))      # (QKeySequence.Quit is empty on Windows)
        quit_.triggered.connect(self.close)

        # Edit
        m = mb.addMenu("&Edit")
        self.act_undo = m.addAction("Undo")
        self.act_undo.setShortcut(QKeySequence.Undo)
        self.act_undo.triggered.connect(self.model_undo)
        self.act_redo = m.addAction("Redo")
        self.act_redo.setShortcuts([QKeySequence.Redo, QKeySequence("Ctrl+Shift+Z")])
        self.act_redo.triggered.connect(self.model_redo)
        m.addSeparator()
        # "\t..." shows the key in the menu; the keys themselves only work in the list / plot
        # (so Delete inside a number field never deletes an element)
        self.act_edit = m.addAction("Edit selected element…\tEnter")
        self.act_edit.triggered.connect(lambda: self.edit_element(self.elements_panel.current_row()))
        self.act_dup = m.addAction("Duplicate selected element")
        self.act_dup.setShortcut("Ctrl+D")
        self.act_dup.triggered.connect(lambda: self.duplicate_element(self.elements_panel.current_row()))
        self.act_del = m.addAction("Delete selected element\tDel")
        self.act_del.triggered.connect(lambda: self.delete_element(self.elements_panel.current_row()))
        m.addSeparator()
        m.addAction("Keyboard shortcuts…").triggered.connect(self.edit_shortcuts)

        # Elements (the menu required by the assignment) — rebuilt whenever the scene changes
        self.elements_menu = mb.addMenu("E&lements")

        # View
        m = mb.addMenu("&View")
        lay = m.addMenu("Layers")
        self.layer_actions = {}
        for key, text, on, ready in LAYERS:              # same switches as in Plot settings → Layers
            a = lay.addAction(text)
            a.setCheckable(True)
            a.setChecked(on)
            a.setEnabled(ready)
            a.toggled.connect(lambda checked, k=key: self.settings_panel.layer_boxes[k].setChecked(checked))
            self.layer_actions[key] = a
        mode = QActionGroup(self)
        for text, on in [("Static streamlines", True), ("Animated particles", False)]:
            a = m.addAction(text)
            a.setCheckable(True)
            a.setChecked(on)
            a.setEnabled(on)
            mode.addAction(a)
        m.addSeparator()
        fit = self.act_fit = m.addAction("Fit view")
        fit.setShortcut("F")
        fit.triggered.connect(self.canvas.fit_view)
        # mouse mode of the plot (same as the Select / Move / Pan buttons above it)
        mm = m.addMenu("Mouse mode")
        group = QActionGroup(self)
        self.mode_actions = {}
        for mode, text, key in (("select", "Select", "V"), ("move", "Move elements", "M"), ("pan", "Pan", "H")):
            a = mm.addAction(text)
            a.setCheckable(True)
            a.setChecked(mode == self.canvas.mode)
            a.setShortcut(key)
            a.triggered.connect(lambda _=False, md=mode: self.canvas.set_mode(md))
            group.addAction(a)
            self.mode_actions[mode] = a
        self.canvas.mode_changed.connect(lambda md: self.mode_actions[md].setChecked(True))
        m.addSeparator()
        panels = m.addMenu("Panels")
        panels.addAction(self.dock_elements.toggleViewAction())
        panels.addAction(self.dock_settings.toggleViewAction())
        panels.addSeparator()
        # sections of Plot settings (the same menu opens with a right-click on the panel's title)
        self.sections_menu = panels.addMenu("Plot settings sections")
        self.section_actions = {}
        for key, (title, _group) in self.settings_panel.sections.items():
            a = self.sections_menu.addAction(title)
            a.setCheckable(True)
            a.setChecked(True)
            a.toggled.connect(lambda on, k=key: self.settings_panel.set_section_visible(k, on))
            self.section_actions[key] = a
        panels.addSeparator()
        panels.addAction("Reset layout").triggered.connect(self.reset_layout)
        m.addSeparator()
        theme_menu = m.addMenu("Theme")
        tg = QActionGroup(self)
        for name, pal in [("Light", LIGHT), ("Dark", DARK)]:
            a = theme_menu.addAction(name)
            a.setCheckable(True)
            a.setChecked(pal is self.theme)
            a.triggered.connect(lambda _=False, p=pal: self.apply_theme(p))
            tg.addAction(a)

        # Presets: scene files in the presets folder, one section per group folder
        m = mb.addMenu("&Presets")
        for i, (group, items) in enumerate(list_presets()):
            if i:
                m.addSeparator()
            hdr = m.addAction(group)
            hdr.setEnabled(False)
            for preset in items:
                a = m.addAction("    " + preset.title)
                a.triggered.connect(lambda _=False, p=preset: self.load_preset(p))
        m.addSeparator()
        m.addAction("Show presets folder").triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(PRESETS_DIR)))

        # Help
        m = mb.addMenu("&Help")
        self._placeholder(m, "User guide", "F1", "the user guide")
        m.addAction("Sign conventions").triggered.connect(self._show_conventions)
        m.addAction("Keyboard shortcuts…").triggered.connect(self.edit_shortcuts)
        m.addSeparator()
        m.addAction("About").triggered.connect(self._show_about)

    def _register_shortcuts(self):
        """Commands whose key the user can change (Edit → Keyboard shortcuts…)."""
        sc = self.shortcuts = Shortcuts()
        for ident, act, label, group in (
                ("file.new", self.act_new, "New scene", "File"),
                ("file.open", self.act_open, "Open…", "File"),
                ("file.save", self.act_save, "Save", "File"),
                ("file.save_as", self.act_save_as, "Save as…", "File"),
                ("file.export_figure", self.act_export_fig, "Export figure…", "File"),
                ("file.export_data", self.act_export_data, "Export data (CSV)…", "File"),
                ("file.exit", self.act_exit, "Exit", "File"),
                ("edit.undo", self.act_undo, "Undo", "Edit"),
                ("edit.redo", self.act_redo, "Redo", "Edit"),
                ("edit.duplicate", self.act_dup, "Duplicate selected element", "Edit"),
                ("view.fit", self.act_fit, "Fit view", "View"),
                ("mode.select", self.mode_actions["select"], "Mouse mode: Select", "Plot"),
                ("mode.move", self.mode_actions["move"], "Mouse mode: Move elements", "Plot"),
                ("mode.pan", self.mode_actions["pan"], "Mouse mode: Pan", "Plot")):
            sc.register(ident, act, label, group)
        for key, act in self.element_actions.items():
            sc.register(f"add.{key}", act, f"Add {spec_for(key).name.lower()}…", "Add element", default="")
        sc.listeners.append(self._shortcuts_changed)
        sc.load()

    def _shortcuts_changed(self):
        self.canvas.bar.set_shortcut_hints({m: self.shortcuts.first_key(f"mode.{m}") for m in self.mode_actions})

    def edit_shortcuts(self):
        ShortcutsDialog(self.shortcuts, self).exec()

    def _placeholder(self, menu, text, shortcut, phase):
        a = menu.addAction(text)
        if shortcut is not None:
            a.setShortcut(shortcut)
        a.triggered.connect(lambda _=False, t=text: self.flash(f"“{t}” comes with {phase}."))
        return a

    def _build_plot_shortcuts(self):
        """Delete / Ctrl+D also work while the plot has focus (not inside number fields)."""
        for key, fn in ((QKeySequence.Delete, lambda: self.delete_element(self.elements_panel.current_row())),
                        (QKeySequence(Qt.Key_Backspace), lambda: self.delete_element(self.elements_panel.current_row()))):
            sc = QShortcut(key, self.canvas.plot)
            sc.setContext(Qt.WidgetWithChildrenShortcut)
            sc.activated.connect(fn)

    def _rebuild_elements_menu(self):
        m = self.elements_menu
        m.clear()
        add = m.addMenu("Add")
        for key in toolbar_types():
            a = add.addAction(make_element_icon(key, self.theme, 48), spec_for(key).name + "…")
            a.triggered.connect(lambda _=False, k=key: self.add_element_dialog(k))
        m.addSeparator()
        hdr = m.addAction("Current elements:" if self.elements else "No elements — use Add or a preset")
        hdr.setEnabled(False)
        for row, el in enumerate(self.elements):
            label = f"{row + 1}. {element_title(el)}   ({el.summary()})" + ("" if el.enabled else "   [hidden]")
            sub = m.addMenu(element_icon(el, self.theme), label)
            sub.addAction("Edit…").triggered.connect(lambda _=False, r=row: self.edit_element(r))
            sub.addAction("Duplicate").triggered.connect(lambda _=False, r=row: self.duplicate_element(r))
            sub.addAction("Show" if not el.enabled else "Hide").triggered.connect(
                lambda _=False, r=row, on=not el.enabled: self.model.set_enabled(r, on))
            sub.addSeparator()
            sub.addAction("Delete").triggered.connect(lambda _=False, r=row: self.delete_element(r))
        m.addSeparator()
        clear = m.addAction("Delete all elements")
        clear.setEnabled(bool(self.elements))
        clear.triggered.connect(self.clear_all)

    def _build_statusbar(self):
        sb = self.statusBar()
        self.probe_label = QLabel("Move the mouse over the plot")
        self.probe_label.setObjectName("ProbeLabel")
        self.issue_label = QLabel("")
        self.count_label = QLabel("")
        sb.addPermanentWidget(self.probe_label)
        sb.addPermanentWidget(self.issue_label)
        sb.addPermanentWidget(self.count_label)

    # ------------------------------------------------------------------ model -> view
    def _on_model_changed(self, focus):
        self.elements_panel.set_elements(self.elements, select=focus)
        self.dock_elements.titleBarWidget().note.setText(
            f"{len(self.elements)} ITEM{'' if len(self.elements) == 1 else 'S'}")
        self._rebuild_elements_menu()
        self.canvas.set_elements(self.elements)
        self.canvas.set_selected(self.elements_panel.current_row())
        self._update_issues()
        self._update_edit_actions()
        self._update_title()

    def _update_edit_actions(self):
        m = self.model
        self.act_undo.setEnabled(m.can_undo)
        self.act_undo.setText(f"Undo {m.undo_text.lower()}" if m.can_undo else "Undo")
        self.act_redo.setEnabled(m.can_redo)
        self.act_redo.setText(f"Redo {m.redo_text.lower()}" if m.can_redo else "Redo")
        selected = self.elements_panel.current_row() >= 0
        for a in (self.act_edit, self.act_dup, self.act_del):
            a.setEnabled(selected)

    # ------------------------------------------------------------------ selection
    def select_element(self, row: int):
        """Select element `row` (from the plot or code); −1 clears the selection (also of a
        stagnation point)."""
        self.canvas.select_stagnation(None)
        self.elements_panel.select_row(row)

    def select_stagnation(self, index: int):
        """A stagnation point was clicked: no element selected, the point shows its details."""
        self.select_element(-1)
        self.canvas.select_stagnation(index)

    def _selection_changed(self, row: int):
        if row >= 0:
            self.canvas.select_stagnation(None)        # an element is selected now
        self.canvas.set_selected(row)
        self._update_edit_actions()

    def eventFilter(self, obj, event):
        """A mouse click anywhere in this window that is not on an element clears the selection.
        Exceptions: the plot (it decides itself: symbol = select, empty = clear), the element list
        (an item = select, empty space = clear), the Edit / Duplicate / Delete buttons and the menus
        (they act on the selection), and dialogs (other windows)."""
        if (event.type() == QEvent.Show and isinstance(obj, QWidget) and obj.isWindow()
                and obj.windowType() in (Qt.Window, Qt.Dialog)):
            tint_title_bar(obj, self.theme)             # Windows 11: title bars in the header wood
        if event.type() == QEvent.MouseButtonPress and isinstance(obj, QWidget) and obj.window() is self:
            # Qt passes a press that a child did not accept on to its parents; decide by the widget that is
            # really under the mouse, otherwise a click on the plot would look like a click on its parent
            under = obj.childAt(event.position().toPoint())
            obj = under if under is not None else obj
            tree = self.elements_panel.tree
            if obj is tree.viewport():
                if tree.itemAt(event.position().toPoint()) is None:
                    QTimer.singleShot(0, lambda: self.select_element(-1))
            elif self.canvas.plot.isAncestorOf(obj) or obj is self.canvas.plot:
                pass                                            # handled by PlotCanvas._mouse_clicked
            elif isinstance(obj, QMenuBar) or self.menuBar().isAncestorOf(obj):
                pass
            elif isinstance(obj, QAbstractButton) and obj in (self.elements_panel.btn_edit,
                                                              self.elements_panel.btn_dup,
                                                              self.elements_panel.btn_del):
                pass
            elif not tree.isAncestorOf(obj) and obj is not tree:
                self.select_element(-1)
        return False

    def closeEvent(self, event):
        if not self.maybe_save():
            event.ignore()
            return
        QApplication.instance().removeEventFilter(self)
        self.save_layout()
        self.canvas.shutdown()
        super().closeEvent(event)

    def _update_title(self):
        star = " *" if self.model.is_modified else ""
        name = os.path.basename(self.current_path) if self.current_path else self.scene_title
        self.setWindowTitle(f"{LAYOUT['window_title']} — {name}{star}")
        self.setWindowFilePath(self.current_path or "")
        file = os.path.basename(self.current_path) if self.current_path else "not saved"
        self.header.plank.file.setText(f"SHEET  {file}{star}")
        tb = self.canvas.title_block
        tb.set("scene", self.scene_title)
        tb.set("file", file + star)
        self._update_title_block_counts()

    def _update_title_block_counts(self):
        n = len(self.elements)
        k = len(self.canvas.stagnation_points)
        self.canvas.title_block.set("elements", f"{n}  ·  ⊗ {k}")

    def _update_title_block_view(self, xr, yr):
        self.canvas.title_block.set("view", f"x[{xr[0]:.2f}, {xr[1]:.2f}]  y[{yr[0]:.2f}, {yr[1]:.2f}]"
                                    .replace("-", "−"))

    # ------------------------------------------------------------------ files (File menu)
    def new_scene(self):
        """File → New: empty scene, default view, empty undo history."""
        if not self.maybe_save():
            return False
        rng = LAYOUT["plot_initial_range"]
        self.canvas.set_view(rng["x"], rng["y"])
        self.current_path = None
        self.scene_title = "untitled"
        self.model.reset([])
        self.flash("New scene — add elements from the toolbar or choose a preset.")
        return True

    def open_scene(self, path: str | None = None):
        """File → Open (asks for a file when `path` is None), Open recent, drag & drop, command line."""
        if not self.maybe_save():
            return False
        if path is None:
            path = self._ask_open_path()
            if not path:
                return False
        try:
            doc = read_scene_file(path)
        except SceneFileError as exc:
            self._notify_user("warning", "Cannot open the file", str(exc))
            if not os.path.exists(path):
                self.recent.remove(path)
            return False
        self._apply_document(doc)
        self.current_path = os.path.abspath(path)
        self.scene_title = doc.title or os.path.splitext(os.path.basename(path))[0]
        self.recent.add(path)
        self._update_title()
        self.flash(f"Opened {os.path.basename(path)}  —  {len(doc.elements)} elements")
        if doc.warnings:
            self._notify_user("information", "File opened with small problems",
                              "The file was opened, but:\n\n• " + "\n• ".join(doc.warnings))
        return True

    def save_scene(self) -> bool:
        """File → Save (asks for a name the first time). Returns False if cancelled or failed."""
        if self.current_path is None:
            return self.save_scene_as()
        return self._write(self.current_path)

    def save_scene_as(self) -> bool:
        base = self.scene_title if self.scene_title != "untitled" else "scene"
        base = re.sub(r'[\\/:*?"<>|]+', " ", base).strip() or "scene"
        start = os.path.dirname(self.current_path) if self.current_path else self.recent.last_folder
        path = self._ask_save_path(os.path.join(start, base + EXTENSION))
        if not path:
            return False
        if not os.path.splitext(path)[1]:
            path += EXTENSION
        if self.scene_title == "untitled":
            self.scene_title = os.path.splitext(os.path.basename(path))[0]
        return self._write(path)

    def _write(self, path: str) -> bool:
        try:
            write_scene_file(path, self._document())
        except SceneFileError as exc:
            self._notify_user("warning", "Cannot save the file", str(exc))
            return False
        self.current_path = os.path.abspath(path)
        self.model.mark_clean()
        self.recent.add(path)
        self._update_title()
        self.flash(f"Saved {os.path.basename(path)}")
        return True

    def _document(self) -> SceneDocument:
        """The current scene as it is saved: elements, title, view and streamline settings."""
        cv = self.canvas
        (x0, x1), (y0, y1) = cv.vb.viewRange()
        settings = {"density": cv.density, "line_width": cv.line_width,
                    "show_arrows": cv.show_arrows, "arrow_density": cv.arrow_density}
        return SceneDocument(list(self.elements), self.scene_title, ((x0, x1), (y0, y1)), settings)

    def _apply_document(self, doc: SceneDocument):
        cv = self.canvas
        if doc.view is not None:
            cv.set_view(*doc.view)
        s = doc.settings
        if s:
            cv.density = s.get("density", cv.density)
            cv.show_arrows = s.get("show_arrows", cv.show_arrows)
            cv.arrow_density = s.get("arrow_density", cv.arrow_density)
            cv.set_line_width(s.get("line_width", cv.line_width))
            self.settings_panel.set_streamline_settings(cv.density, cv.line_width, cv.show_arrows,
                                                        cv.arrow_density)
        self.model.reset(doc.elements)         # one streamline computation with the new view + settings

    def maybe_save(self) -> bool:
        """Before the scene is replaced or the window closes: offer to save unsaved changes.
        True = go on, False = the user cancelled (or saving failed)."""
        if not self.model.is_modified:
            return True
        answer = self._ask_save_changes()
        if answer == "save":
            return self.save_scene()
        return answer == "discard"

    # ------------------------------------------------------------------ export (File menu)
    def _export_settings(self, kind: str) -> dict:
        s = QSettings()
        raw = s.value(f"export/{kind}")
        try:
            import json
            return json.loads(raw) if raw else {}
        except (TypeError, ValueError):
            return {}

    def _save_export_settings(self, kind: str, options: dict, path: str):
        import json
        s = QSettings()
        s.setValue(f"export/{kind}", json.dumps(options))
        s.setValue("export/folder", os.path.dirname(os.path.abspath(path)))

    def _export_base_name(self) -> str:
        base = os.path.splitext(os.path.basename(self.current_path))[0] if self.current_path else self.scene_title
        return re.sub(r'[\\/:*?"<>|]+', " ", base).strip() or "figure"

    def export_figure(self):
        """File → Export figure…: options dialog, then where to save."""
        from .export import ExportFigureDialog, render_figure
        dlg = ExportFigureDialog(self.canvas, self._export_settings("figure"), self)
        if not self._run_dialog(dlg):
            return False
        opt = dlg.options()
        fmt = opt["format"]
        folder = QSettings().value("export/folder", "") or self.recent.last_folder
        path = self._ask_export_path(os.path.join(folder, self._export_base_name() + "." + fmt),
                                     f"{fmt.upper()} files (*.{fmt})")
        if not path:
            return False
        if not os.path.splitext(path)[1]:
            path += "." + fmt
        try:
            render_figure(self.canvas, path, fmt, opt["scale"], opt["background"], opt["light"])
        except (OSError, ValueError) as exc:
            self._notify_user("warning", "Cannot export the figure", str(exc))
            return False
        self._save_export_settings("figure", opt, path)
        self.flash(f"Figure saved: {os.path.basename(path)}")
        return True

    def export_data(self):
        """File → Export data (CSV)…: which tables, then where to save."""
        from .export import ExportDataDialog
        from .export import export_data as write_tables
        dlg = ExportDataDialog(self._export_settings("data"), self)
        if not self._run_dialog(dlg):
            return False
        opt = dlg.options()
        folder = QSettings().value("export/folder", "") or self.recent.last_folder
        path = self._ask_export_path(os.path.join(folder, self._export_base_name() + ".csv"), "CSV files (*.csv)")
        if not path:
            return False
        try:
            written = write_tables(path, opt["datasets"], self.elements, self.canvas, opt["grid"], opt["separator"])
        except OSError as exc:
            self._notify_user("warning", "Cannot export the data", str(exc))
            return False
        self._save_export_settings("data", opt, path)
        self.flash("Saved " + ", ".join(os.path.basename(p) for p in written))
        return True

    # dialogs (separate methods so the tests can answer them)
    def _run_dialog(self, dlg) -> bool:
        return bool(dlg.exec())

    def _ask_export_path(self, suggested: str, file_filter: str) -> str:
        path, _ = QFileDialog.getSaveFileName(self, "Export", suggested, file_filter)
        return path

    def _ask_save_changes(self) -> str:
        name = os.path.basename(self.current_path) if self.current_path else self.scene_title
        box = QMessageBox(QMessageBox.Warning, "Unsaved changes",
                          f"Do you want to save the changes to “{name}”?",
                          QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, self)
        box.setInformativeText("Your changes will be lost if you don't save them.")
        box.setDefaultButton(QMessageBox.Save)
        return {QMessageBox.Save: "save", QMessageBox.Discard: "discard"}.get(box.exec(), "cancel")

    def _ask_open_path(self) -> str:
        start = os.path.dirname(self.current_path) if self.current_path else self.recent.last_folder
        path, _ = QFileDialog.getOpenFileName(self, "Open scene", start, FILE_FILTER)
        return path

    def _ask_save_path(self, suggested: str) -> str:
        path, _ = QFileDialog.getSaveFileName(self, "Save scene as", suggested, FILE_FILTER)
        return path

    def _notify_user(self, kind: str, title: str, text: str):
        if kind == "warning":
            QMessageBox.warning(self, title, text)
        else:
            QMessageBox.information(self, title, text)

    def _rebuild_recent_menu(self):
        m = self.recent_menu
        m.clear()
        paths = self.recent.paths()
        if not paths:
            m.addAction("(no recent files)").setEnabled(False)
            return
        for i, path in enumerate(paths, 1):
            folder = os.path.basename(os.path.dirname(path)) or os.path.dirname(path)
            text = f"&{i}  {os.path.basename(path)}" if i < 10 else os.path.basename(path)
            a = m.addAction(f"{text}      — {folder}")
            a.setToolTip(path)
            a.setStatusTip(path)
            a.triggered.connect(lambda _=False, p=path: self.open_scene(p))
        m.addSeparator()
        m.addAction("Clear this list").triggered.connect(self.recent.clear)

    def dragEnterEvent(self, event):
        if self._dropped_file(event):
            event.acceptProposedAction()

    def dropEvent(self, event):
        path = self._dropped_file(event)
        if path:
            event.acceptProposedAction()
            QTimer.singleShot(0, lambda: self.open_scene(path))   # not inside the drop handler

    @staticmethod
    def _dropped_file(event) -> str | None:
        md = event.mimeData()
        if md.hasUrls():
            for url in md.urls():
                path = url.toLocalFile()
                if path.lower().endswith((EXTENSION, ".json")):
                    return path
        return None

    # ------------------------------------------------------------------ actions
    def add_element_dialog(self, key, at=None):
        """Palette / Elements → Add: dialog with default values. The position is `at` (an element
        dragged from the palette and dropped on the plot) or the view center."""
        spec, cls = spec_for(key), ELEMENT_TYPES[key]
        values = {p.key: p.default for p in spec.params}
        if at is not None and cls.POSITION_KEYS:
            kx, ky = cls.POSITION_KEYS
            values[kx], values[ky] = at
        elif cls.POSITION_KEYS == ("x0", "y0"):
            (x0, x1), (y0, y1) = self.canvas.vb.viewRange()
            values["x0"], values["y0"] = round(0.5 * (x0 + x1), 1) + 0.0, round(0.5 * (y0 + y1), 1) + 0.0
        dlg = ElementDialog(spec, self.theme, False, self, values=values,
                            validator=lambda vals: self._preview(cls(**vals), None))
        if dlg.exec():
            el = cls(**dlg.values())
            self.model.add(el)
            self._flash_done()

    def edit_element(self, row):
        if not 0 <= row < len(self.elements):
            return
        el = self.elements[row]
        spec = spec_for(el.TYPE)
        values = {p.key: getattr(el, p.key) for p in spec.params}
        dlg = ElementDialog(spec, self.theme, True, self, values=values,
                            validator=lambda vals: self._preview(el.copy(**vals), row))
        if dlg.exec():
            if self.model.replace(row, el.copy(**dlg.values()), f"Edit {element_title(el).lower()}") is None:
                self.flash("No change.")
            else:
                self._flash_done()

    def move_element(self, row, moved):
        """Move mode: an element was dragged to a new place (one undoable step)."""
        if 0 <= row < len(self.elements):
            self.model.replace(row, moved, f"Move {element_title(self.elements[row]).lower()}")
            self._flash_done()

    def duplicate_element(self, row):
        if 0 <= row < len(self.elements):
            self.model.duplicate(row, DUPLICATE_OFFSET)
            self._flash_done()

    def delete_element(self, row):
        if 0 <= row < len(self.elements):
            self.model.remove(row)
            self._flash_done()

    def clear_all(self):
        if self.model.clear() is None:
            self.flash("Nothing to clear.")
        else:
            self._flash_done()

    def model_undo(self):
        text = self.model.undo_text
        self.model.undo()
        if text:
            self.flash(f"Undone: {text}")

    def model_redo(self):
        text = self.model.redo_text
        self.model.redo()
        if text:
            self.flash(f"Redone: {text}")

    def load_preset(self, preset):
        """Presets menu: the preset becomes a new, unsaved scene (one undoable step)."""
        try:
            doc = read_scene_file(preset.path)
        except SceneFileError as exc:
            self._notify_user("warning", "Cannot load the preset", str(exc))
            return False
        self.load_scene(doc.elements, doc.view, title=doc.title or preset.title)
        return True

    def load_scene(self, elements, view=None, title=""):
        """Presets: replace the whole scene in ONE undoable step (File → Open starts a new history)."""
        if view:
            self.canvas.set_view(*view)
        self.scene_title = title or "untitled"
        self.current_path = None        # a preset is a new, unsaved scene (Save would not overwrite a file)
        self.model.load(elements, f"Load “{title}”" if title else "Load scene")
        self._flash_done()

    def _flash_done(self):
        if self.model.can_undo:
            self.flash(f"{self.model.undo_text}   —   Ctrl+Z to undo")

    def _preview(self, new, index):
        """Problems a change would cause, as (severity, text) for the dialog."""
        try:
            cand, issues = preview_change(self.elements, new, index)
        except Exception as exc:                     # never let validation crash the dialog
            return [("error", f"Invalid values: {exc}")]
        own = len(cand) - 1 if index is None else index
        out = []
        for s in issues:
            # problems of OTHER elements get their list number, e.g. "[2] Source / sink is behind the wall"
            who = f"[{s.index + 1}] " if s.index is not None and s.index != own else ""
            out.append((s.issue.severity, who + s.message))
        return out

    def flash(self, text):
        self.statusBar().showMessage(text, 5000)

    # ------------------------------------------------------------------ status bar
    def _layer_changed(self, key, on):
        self.canvas.set_layer(key, on)
        act = self.layer_actions.get(key)
        if act is not None and act.isChecked() != on:
            act.blockSignals(True)
            act.setChecked(on)
            act.blockSignals(False)

    def _update_probe(self, pos):
        if pos is None:
            self.probe_label.setText("Move the mouse over the plot")
            return
        x, y = pos
        z = complex(x, y)
        where = f"x = {x:7.3f}   y = {y:7.3f}   │   "
        stag = self.canvas.stagnation_near(x, y)
        if stag is not None:
            self.probe_label.setText(where + stag.describe())
            return
        near = [p for p in singular_points(self.elements) if abs(z - p) < 0.5 * self._probe_radius()]
        if near:
            self.probe_label.setText(where + "singular point (velocity → ∞)")
            return
        if not fluid_mask(self.elements, z):
            self.probe_label.setText(where + "outside the fluid region")
            return
        u, v = velocity(self.elements, x, y)
        u, v = float(u), float(v)
        V = float(np.hypot(u, v))
        text = where + f"u = {u:7.3f}   v = {v:7.3f}   |V| = {V:7.3f}"
        v_ref = reference_speed(self.elements)
        text += f"   Cp = {1.0 - (V / v_ref) ** 2:7.3f}" if v_ref else "   Cp: no V∞"
        self.probe_label.setText(text)

    def _probe_radius(self):
        (x0, x1), _ = self.canvas.vb.viewRange()
        return (x1 - x0) / 200.0

    def _update_issues(self):
        """Scene check (walls, invalid positions...) in the status bar (details in the tooltip) and,
        for errors, a red strip above the plot."""
        issues = check_scene(self.elements)
        errors = [s for s in issues if s.severity == "error"]
        warnings = [s for s in issues if s.severity == "warning"]
        notes = [s for s in issues if s.severity == "info"]
        if errors:
            text = f"✖ {len(errors)} error{'s' if len(errors) > 1 else ''}"
            color = self.theme["danger"]
        elif warnings:
            text = f"⚠ {len(warnings)} warning{'s' if len(warnings) > 1 else ''}"
            color = self.theme["el_doublet"]
        else:
            text, color = "✓ scene OK", self.theme["el_sector"]
        if notes and not errors:
            text += f"  ·  {len(notes)} note{'s' if len(notes) > 1 else ''}"
        self.issue_label.setText(text)
        self.issue_label.setStyleSheet(f"color: {color}; font-weight: 600;")
        symbol = {"error": "✖", "warning": "⚠", "info": "•"}     # (ℹ is drawn as a blue emoji on Windows)
        tips = []
        for s in issues:
            who = f"[{s.index + 1}] " if s.index is not None else ""      # number in the element list
            tips.append(f"{symbol.get(s.severity, '•')} {who}{s.message}")
        self.issue_label.setToolTip("\n".join(tips) if tips else "No problems found.")
        if errors:
            first = errors[0]
            who = f"[{first.index + 1}] " if first.index is not None else ""
            more = f"   (+{len(errors) - 1} more: hover the status bar)" if len(errors) > 1 else ""
            self.canvas.set_banner(f"✖ Not physically consistent — {who}{first.message}{more}")
        else:
            self.canvas.set_banner(None)

    def _update_status(self, n_lines, ms):
        self._update_title_block_counts()
        n = len(self.elements)
        on = sum(e.enabled for e in self.elements)
        self.count_label.setText(f"{n} elements ({on} shown)  |  {n_lines} streamlines in {ms:.0f} ms")

    # ------------------------------------------------------------------ appearance / help
    def apply_theme(self, theme):
        self.theme = theme
        app = QApplication.instance()
        app.setStyleSheet(build_stylesheet(theme))
        # Qt draws the "panel will go here" band of a dragged dock in the palette's Highlight color
        pal = app.palette()
        pal.setColor(QPalette.Highlight, QColor(theme["accent_strong"]))
        pal.setColor(QPalette.HighlightedText, QColor(theme["accent_text"]))
        app.setPalette(pal)
        self.setWindowIcon(make_app_icon(theme))
        self.header.apply_theme(theme)
        for w in QApplication.topLevelWidgets():
            if w.isVisible() and w.windowType() in (Qt.Window, Qt.Dialog):
                tint_title_bar(w, theme)
        if hasattr(self, "dock_settings"):
            for part in self._dock_parts():
                part.theme = theme
                part.update()
        self.update()                                  # paper
        for key, act in self.element_actions.items():
            act.setIcon(make_palette_icon(key, theme["text"]))
        self.element_toolbar.apply_theme(theme)
        self._drop_indicator.theme = theme
        self.canvas.apply_theme(theme)
        self.elements_panel.apply_theme(theme)
        if hasattr(self, "issue_label"):
            self._update_issues()
            self._rebuild_elements_menu()

    def paintEvent(self, _event):
        paint_paper_grid(self, self.theme)

    def _show_conventions(self):
        QMessageBox.information(self, "Sign conventions",
                                "<b>Complex potential</b>: F(z) = φ + iψ,  w = dF/dz = u − iv<br><br>"
                                "<b>Source/sink</b>: m &gt; 0 source, m &lt; 0 sink<br>"
                                "<b>Vortex</b>: Γ &gt; 0 counter-clockwise, Γ &lt; 0 clockwise<br>"
                                "<b>Doublet</b>: F = μ e<sup>iδ</sup>/(z − z₀),  cylinder radius a = √(μ/V∞)<br>"
                                "<b>Sector</b>: β = θ₂ − θ₁ (counter-clockwise),  n = π/β;  "
                                "V &gt; 0: in along θ₂, out along θ₁<br>"
                                "<b>Wall</b>: V·n = 0 by the method of images<br>"
                                "<b>Pressure</b>: Cp = 1 − (V/V∞)²")

    def _show_about(self):
        QMessageBox.about(self, "About Potential Flow Lab",
                          "<b>Potential Flow Lab</b><br>"
                          "Interactive 2D incompressible, irrotational flow builder.<br><br>"
                          "Aerodynamics semester project, IZTECH Mechanical Engineering.")


def setup_application(app):
    """Settings that must be identical on every computer (Windows TR/EN, macOS)."""
    from PySide6.QtCore import QLocale
    # numbers always with a decimal POINT (1.000), whatever the system region is (TR uses 1,000)
    QLocale.setDefault(QLocale(QLocale.English, QLocale.UnitedStates))
    # the streamline thread and the window share Python's interpreter lock (GIL); hand it over every
    # 0.5 ms instead of every 5 ms, so drawing never waits long for the background computation
    import sys
    sys.setswitchinterval(0.0005)
    app.setOrganizationName(ORGANIZATION)        # where QSettings keeps recent files etc.
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyle("Fusion")          # same look on Windows and macOS
    load_fonts()                    # bundled fonts (assets/fonts), the same on every computer
    app.setFont(default_font())


def default_font():
    from PySide6.QtGui import QFontDatabase
    families = set(QFontDatabase.families())
    f = QFont()
    for fam in FONT["families"]:
        if fam in families:
            f.setFamily(fam)
            break
    f.setPointSizeF(FONT["size_pt"])
    return f
