"""
main_window.py — the main window: assembles header, element palette, plot, side panels and status bar,
and connects them to the scene model.

Data flow (one direction only):
    user action (palette, dialog, list, menu, shortcut, drag on the plot)
        -> SceneModel command (add / edit / delete / hide / load ...)   [undoable]
        -> model notifies the window
        -> window refreshes list, Elements menu, plot, scene check, Undo/Redo texts
No widget changes the elements directly, so undo / redo always restores exactly.

The window's parts are in app/window/: layout.py (side panels, palette side), menus.py (palette, menus,
shortcuts), files.py (New / Open / Save, presets), exporting.py (figure and CSV export), status.py
(status bar, probe, scene check, titles). This file keeps the assembly, the wiring and the element
commands (add / edit / move / duplicate / delete, undo / redo).
"""
from PySide6.QtCore import QEvent, QSettings, Qt, QTimer
from PySide6.QtGui import QColor, QKeySequence, QPalette, QShortcut
from PySide6.QtWidgets import QAbstractButton, QApplication, QHBoxLayout, QMainWindow, QMenuBar, QMessageBox, QWidget

from app_info import APP_VERSION
from model import SceneModel, preview_change
from physics import ELEMENT_TYPES
from physics.warmup import warm_up_in_background

from .beaver import Beaver, BeaverSprite
from .canvas import LIVE_DRAG_DEFAULT, PlotCanvas
from .recovery import SessionRecovery
from .chrome import HeaderBar, load_fonts, paint_paper_grid, tint_title_bar
from .dialogs import ElementDialog, dispose
from .element_specs import spec_for
from .gpu_panel import GpuPanel
from .hardware import load_profile
from .icons import make_app_icon, make_palette_icon
from .panels import ElementsPanel, LimitSlider, SettingsPanel, element_title
from .recent_files import RecentFiles
from .surface_panel import SurfacePanel
from .theme import DEFAULT_THEME, LAYOUT, build_stylesheet
from .window import ExportMixin, FilesMixin, GraphicsMixin, LayoutMixin, MenusMixin, StatusMixin

DUPLICATE_OFFSET = (0.5, 0.5)
GRID_KEY = "plot/grid"            # the plot's background grid shown (Layers → Background grid; a program setting)


class MainWindow(LayoutMixin, MenusMixin, FilesMixin, ExportMixin, StatusMixin, GraphicsMixin, QMainWindow):
    # the scene a new window starts with: None = an empty sheet (the program); (title, function returning the
    # elements) otherwise — the tests start with the lifting cylinder they were written for (tests/conftest.py)
    START_SCENE = None

    def __init__(self):
        super().__init__()
        load_fonts()
        self.theme = DEFAULT_THEME
        self._verification = None                # Help → Run verification (created on first use)
        self.hardware = load_profile()           # this computer (app/hardware.py; main.py sets the fresh one)
        # a copy of an unsaved scene, restored if the program does not close normally (app/recovery.py)
        self.recovery = SessionRecovery(self._document, lambda: self.model.is_modified,
                                        lambda: (self.current_path, self.scene_title), parent=self)
        start = self.START_SCENE
        self.scene_title = start[0] if start else "untitled"
        self.current_path: str | None = None           # file of the scene (None = never saved)
        self.recent = RecentFiles()
        self._last_probe = None
        self.setAcceptDrops(True)                      # drop a .pflow file on the window to open it
        # freed when closed (signal connections to lambdas would otherwise keep it alive in Python)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.resize(*LAYOUT["window_size"])

        # the scene: every change goes through the model (undo / redo)
        self.model = SceneModel(start[1]() if start else [])     # (empty: Presets has ready-made scenes)
        self.model.mark_clean()
        self.elements = self.model.elements            # same list object for the whole session

        # header: wooden plank (logo, name, file) + ruler with the menus (and, later, the beaver)
        self.header = HeaderBar(self)
        self.setMenuWidget(self.header)
        self._menu_bar = self.header.menu_bar
        self.header.plank.version.setText(f"REV {APP_VERSION}")

        # central plot card on the paper, the element palette beside it
        self.canvas = PlotCanvas(self.theme, self.elements, self)
        self.desk = QWidget(self)
        self._desk_layout = QHBoxLayout(self.desk)             # [element palette] [plot card] (or mirrored)
        g = LAYOUT["gap"]
        self._desk_layout.setContentsMargins(g, 0, g - 4, g)   # 4 = dock separator
        self._desk_layout.setSpacing(g)
        self._desk_layout.addWidget(self.canvas, 1)
        self.setCentralWidget(self.desk)

        # side panels: only left or right of the plot, stacked; no floating, no tabs
        # left or right of the plot; nested: a panel can also stand beside another (a second column)
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowNestedDocks)
        self.elements_panel = ElementsPanel(self.theme)
        self.dock_elements = self._dock("Elements", self.elements_panel)
        self.dock_elements.widget().setMinimumHeight(LAYOUT["elements_panel_min_height"])
        self.settings_panel = SettingsPanel()
        self.dock_settings = self._dock("Plot settings", self.settings_panel)
        self.surface_panel = SurfacePanel(self.theme)
        self.dock_surface = self._dock("Surface pressure", self.surface_panel)
        self._default_dock_layout()
        # the Graphics card panel: over the right part of the window, opened with the arrow beside the GPU
        # box (app/gpu_panel.py, app/window/graphics.py); not a side panel
        self.gpu_panel = GpuPanel(self)

        self._build_palette()
        self._build_menus()
        self._register_shortcuts()
        self._build_statusbar()
        self._build_plot_shortcuts()
        self._connect()
        self.apply_theme(self.theme)

        self.model.subscribe(self._on_model_changed)
        self._on_model_changed(None)
        self.restore_layout()                          # the panels as the user left them last time
        self._build_graphics()                         # the graphics card: as remembered (off on a first start)
        # the beaver mascot (app/beaver): on the ruler next to Help; View → Beaver switches him off
        self.beaver = Beaver(self)
        on = QSettings().value("beaver/enabled", True, bool)
        self.act_beaver.setChecked(on)
        self.beaver.set_enabled(on)
        # first start (or `main.py --first-run`): the beaver offers the tour; later starts: no question
        settings = QSettings()
        starts = int(settings.value("beaver/starts", 0)) + 1
        settings.setValue("beaver/starts", starts)
        first = (QApplication.instance().property("first_run") is True
                 or not settings.value("beaver/tour_offered", False, bool))
        if first and on:
            settings.setValue("beaver/tour_offered", True)
        QTimer.singleShot(1200, self, lambda: self.beaver.start_session(first))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if getattr(self, "gpu_panel", None) is not None:
            self._place_gpu_panel()                      # (it lies over the window's right part)

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, "_shown_once", False):
            self._shown_once = True
            self._layout_shown()                         # the default panel heights, at the final size

    def menuBar(self) -> QMenuBar:
        """The menus live on the ruler of the header (not in Qt's own menu bar)."""
        return self._menu_bar

    def _connect(self):
        cv, ep, sp = self.canvas, self.elements_panel, self.settings_panel
        # plot -> window
        cv.message.connect(self.flash)
        cv.bar.set_export_actions([("Figure (PNG / SVG / PDF)…", self.export_figure),
                                   ("Animation (GIF / MP4)…", self.export_animation),
                                   ("Data (CSV)…", self.export_data)])
        cv.probe.connect(self._update_probe)
        cv.element_clicked.connect(self.select_element)
        cv.stagnation_clicked.connect(self.select_stagnation)
        cv.element_moved.connect(self.move_element)
        cv.element_dropped.connect(lambda key, pos: self.add_element_dialog(key, at=pos))
        cv.element_double_clicked.connect(
            lambda row: (self.select_element(row), QTimer.singleShot(0, self, lambda: self.edit_element(row))))
        cv.cp_reference_requested.connect(self._show_cp_reference)
        cv.computed.connect(self._update_status)
        cv.computed.connect(lambda *_: warm_up_in_background())     # the other kernels, once, unseen
        cv.view_changed.connect(self._update_title_block_view)
        cv.view_changed.connect(sp.set_view)
        cv.view_changed.connect(self.recovery.changed)
        # element list -> model
        ep.edit_requested.connect(self.edit_element)
        ep.enabled_changed.connect(lambda row, on: self.model.set_enabled(row, on))
        ep.duplicate_requested.connect(self.duplicate_element)
        ep.delete_requested.connect(self.delete_element)
        ep.selection_changed.connect(self._selection_changed)
        ep.message.connect(self.flash)
        # plot settings -> plot
        sp.message.connect(self.flash)
        sp.setting_changed.connect(cv.set_setting)
        sp.setting_changed.connect(lambda key, _v: self._tell_beaver("setting", key))      # (the tour)
        sp.arrows_changed.connect(cv.set_arrows)
        sp.layer_changed.connect(self._layer_changed)
        sp.field_quality_changed.connect(cv.set_field_quality)
        sp.cp_reference_changed.connect(self._cp_reference_changed)
        sp.layer_boxes["grid"].setChecked(QSettings().value(GRID_KEY, True, type=bool))   # as left last time
        live = QSettings().value("plot/live_drag", LIVE_DRAG_DEFAULT, type=bool)      # a program setting
        cv.set_live_drag(live)
        sp.set_live_drag(live)
        sp.live_drag_changed.connect(lambda on: (cv.set_live_drag(on), QSettings().setValue("plot/live_drag", on)))
        sp.view_edited.connect(cv.set_view)
        sp.fit_requested.connect(cv.fit_view)
        sp.sections_changed.connect(self._sections_changed)
        # surface pressure panel <-> plot
        su = self.surface_panel
        su.set_layer(cv.surfaces)
        su.export_requested.connect(self.export_surface)
        su.cp_reference_requested.connect(self._show_cp_reference)
        self.dock_surface.visibilityChanged.connect(self._surface_panel_shown)
        self.dock_surface.visibilityChanged.connect(self._surface_dock_visible)     # its width (window/layout.py)
        title = self.dock_settings.titleBarWidget()
        title.setContextMenuPolicy(Qt.CustomContextMenu)
        title.customContextMenuRequested.connect(lambda pos: self.sections_menu.exec(title.mapToGlobal(pos)))
        title.setToolTip("Drag to move the panel  ·  right-click to choose the sections shown")
        sp.set_view(*cv.view())
        self._update_title_block_view(*cv.view())
        # a click anywhere else in the window clears the selection (see eventFilter); Esc too
        QApplication.instance().installEventFilter(self)
        esc = QShortcut(QKeySequence(Qt.Key_Escape), self)
        esc.activated.connect(lambda: self.canvas.cancel_drag() or self.select_element(-1))

    # ------------------------------------------------------------------ model -> view
    def _tell_beaver(self, event: str, value=None):
        """Tell the beaver what the user did (his tour waits for some of it)."""
        if getattr(self, "beaver", None) is not None:
            self.beaver.notify(event, value)

    def _beaver_scene(self):
        """Tell the beaver (tour) which element types were added."""
        types = [e.TYPE for e in self.elements]
        before = getattr(self, "_types_before", [])
        self._types_before = types
        for t in set(types):
            if types.count(t) > before.count(t):
                self._tell_beaver("added", t)

    def _on_model_changed(self, focus):
        self._beaver_scene()
        self.elements_panel.set_elements(self.elements, select=focus)
        self.surface_panel.set_elements(self.elements)
        self._update_cp_available()
        n = len(self.elements)
        self.dock_elements.titleBarWidget().note.setText(f"{n} ITEM{'' if n == 1 else 'S'}")
        self._rebuild_elements_menu()
        self.canvas.set_elements(self.elements)
        self.canvas.set_selected(self.elements_panel.current_row())
        self._update_issues()
        self._update_edit_actions()
        self._update_title()
        if getattr(self, "_gpu_guard", None) is not None:
            self.gpu_redraw()

    def _update_edit_actions(self):
        m = self.model
        self.act_undo.setEnabled(m.can_undo)
        self.act_undo.setText(f"Undo {m.undo_text.lower()}" if m.can_undo else "Undo")
        self.act_redo.setEnabled(m.can_redo)
        self.act_redo.setText(f"Redo {m.redo_text.lower()}" if m.can_redo else "Redo")
        selected = self.elements_panel.current_row() >= 0
        for a in (self.act_edit, self.act_dup, self.act_del):
            a.setEnabled(selected)

    def _layer_changed(self, key, on):
        other = {"speed": "cp", "cp": "speed"}.get(key)
        if on and other and self.settings_panel.layer_boxes[other].isChecked():
            self.settings_panel.layer_boxes[other].setChecked(False)     # one color map at a time
        self.canvas.set_layer(key, on)
        if key == "surface" and on and not self.dock_surface.isVisible():
            self.dock_surface.show()                    # the graph and the forces go with the colors
        elif key == "surface" and not on and self.dock_surface.isVisible():
            self.dock_surface.hide()                    # … and go with them too
        if key == "grid":
            QSettings().setValue(GRID_KEY, bool(on))    # (a program setting, like the theme)
        act = self.layer_actions.get(key)
        if act is not None and act.isChecked() != on:
            act.blockSignals(True)
            act.setChecked(on)
            act.blockSignals(False)

    def _surface_panel_shown(self, visible):
        layer = self.canvas.surfaces
        layer.panel_open = bool(visible)
        if visible:
            layer.refresh()
            self.surface_panel.refresh()

    def _cp_reference_changed(self, v_ref):
        self.canvas.set_cp_reference(v_ref)
        self._update_probe(self._last_probe)
        self._update_cp_available()

    def _update_cp_available(self):
        """The "needs a reference speed V_ref" notes: only when there is something to compute (an empty
        page has no V∞ either, but nothing is missing there)."""
        empty = not any(e.enabled for e in self.elements)
        self.settings_panel.set_cp_available(empty or self.canvas.cp_reference() is not None)

    def _show_cp_reference(self):
        if not self.dock_settings.isVisible():
            self.dock_settings.show()
        self.settings_panel.show_cp_reference()
        self.flash("Enter a reference speed V_ref for Cp (Computation → Cp reference).")

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
            ep = self.elements_panel
            tree = ep.tree
            if obj is tree.viewport():
                if tree.itemAt(event.position().toPoint()) is None:
                    QTimer.singleShot(0, self, lambda: self.select_element(-1))
            elif isinstance(obj, BeaverSprite):
                pass                                                          # grabbing the beaver
            elif (self.canvas.plot.isAncestorOf(obj) or obj is self.canvas.plot       # the plot decides
                  or isinstance(obj, QMenuBar) or self.menuBar().isAncestorOf(obj)
                  or (isinstance(obj, QAbstractButton) and obj in (ep.btn_edit, ep.btn_dup, ep.btn_del))):
                pass
            elif not tree.isAncestorOf(obj) and obj is not tree:
                self.select_element(-1)
        return False

    # ------------------------------------------------------------------ element commands
    def add_element_dialog(self, key, at=None):
        """Palette / Elements → Add: dialog with default values. The position is `at` (an element
        dragged from the palette and dropped on the plot) or the view center."""
        if getattr(self, "beaver", None) is not None and not self.beaver.tour_allows_add(key):
            return                                       # the tour: only in its own palette step
        spec, cls = spec_for(key), ELEMENT_TYPES[key]
        values = {p.key: p.default for p in spec.params}
        if at is not None and cls.POSITION_KEYS:
            kx, ky = cls.POSITION_KEYS
            values[kx], values[ky] = at
        elif cls.POSITION_KEYS == ("x0", "y0"):
            (x0, x1), (y0, y1) = self.canvas.view()
            values["x0"], values["y0"] = round(0.5 * (x0 + x1), 1) + 0.0, round(0.5 * (y0 + y1), 1) + 0.0
        dlg = ElementDialog(spec, self.theme, False, self, values=values,
                            validator=lambda vals: self._preview(cls(**vals), None))
        dlg.row = None                                   # (a new element; the tour reads it)
        accepted = False
        self._tell_beaver("dialog_open", ("add", key, dlg))
        try:
            if dlg.exec():
                accepted = True
                self.model.add(cls(**dlg.values()))
                self._flash_done()
        finally:
            self._tell_beaver("dialog_closed", (accepted, accepted))
            dispose(dlg)

    def edit_element(self, row):
        if not 0 <= row < len(self.elements):
            return
        el = self.elements[row]
        if getattr(self, "beaver", None) is not None and not self.beaver.tour_allows_edit(el.TYPE):
            return                                       # the tour: only in its edit step
        spec = spec_for(el.TYPE)
        values = {p.key: getattr(el, p.key) for p in spec.params}
        dlg = ElementDialog(spec, self.theme, True, self, values=values,
                            validator=lambda vals: self._preview(el.copy(**vals), row))
        dlg.row = row                                    # (the element edited; the tour reads it)
        accepted = changed = False
        self._tell_beaver("dialog_open", ("edit", el.TYPE, dlg))
        try:
            if dlg.exec():
                accepted = True
                if self.model.replace(row, el.copy(**dlg.values()), f"Edit {element_title(el).lower()}") is None:
                    self.flash("No change.")
                else:
                    changed = True
                    self._flash_done()
                    self._tell_beaver("edited", el.TYPE)
        finally:
            self._tell_beaver("dialog_closed", (accepted, changed))
            dispose(dlg)

    def move_element(self, row, moved):
        """Move mode: an element was dragged to a new place (one undoable step)."""
        if 0 <= row < len(self.elements):
            self.model.replace(row, moved, f"Move {element_title(self.elements[row]).lower()}")
            self._tell_beaver("moved", moved.TYPE)
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
        # problems of OTHER elements get their list number, e.g. "[2] Source / sink is behind the wall"
        return [(s.issue.severity, (f"[{s.index + 1}] " if s.index is not None and s.index != own else "")
                 + s.message) for s in issues]

    # ------------------------------------------------------------------ window
    def closeEvent(self, event):
        if not getattr(self, "_restarting", False) and not self.maybe_save():     # (a restart keeps it all)
            event.ignore()
            return
        QApplication.instance().removeEventFilter(self)
        self.save_layout()
        self.canvas.shutdown()
        if self._verification is not None:
            self._verification.shutdown()
        self.recovery.close()                    # closed normally: no copy to restore next time
        self._gpu_closing()
        self.beaver.shutdown()
        super().closeEvent(event)

    def apply_theme(self, theme):
        self.theme = theme
        LimitSlider.mark_color = theme["logo_dot"]
        if getattr(self, "gpu_panel", None) is not None:
            self.gpu_panel.apply_theme(theme)
        if getattr(self, "_guide", None) is not None:
            self._guide.apply_theme(theme)
        app = QApplication.instance()
        app.setStyleSheet(build_stylesheet(theme))
        # Qt draws the "panel will go here" band of a dragged dock in the palette's Highlight color
        pal = app.palette()
        pal.setColor(QPalette.Highlight, QColor(theme["accent_strong"]))
        pal.setColor(QPalette.HighlightedText, QColor(theme["accent_text"]))
        pal.setColor(QPalette.Link, QColor(theme["accent"]))           # links in labels (e.g. "set V_ref…")
        app.setPalette(pal)
        self.setWindowIcon(make_app_icon(theme))
        self.header.apply_theme(theme)
        self.surface_panel.apply_theme(theme)
        if getattr(self, "_verification", None) is not None:
            self._verification.apply_theme(theme)
        if getattr(self, "beaver", None) is not None:
            self.beaver.set_theme(theme)
        for w in QApplication.topLevelWidgets():
            if w.isVisible() and w.windowType() in (Qt.Window, Qt.Dialog):
                tint_title_bar(w, theme)
        for d in self._docks():
            for part in (d.titleBarWidget(), d.widget()):
                part.theme = theme
                part.update()
        self.update()                                  # paper
        for key, act in self.element_actions.items():
            act.setIcon(make_palette_icon(key, theme["text"]))
        self.element_toolbar.apply_theme(theme)
        self._drop_indicator.theme = theme
        self.canvas.apply_theme(theme)
        self.elements_panel.apply_theme(theme)
        self._update_issues()
        self._rebuild_elements_menu()

    def paintEvent(self, _event):
        paint_paper_grid(self, self.theme)

    def forget_first_start(self):
        """Help → Beaver → Next start as a first-time user (to try the first start again)."""
        QSettings().setValue("beaver/tour_offered", False)
        QSettings().setValue("beaver/starts", 0)
        self.flash("The next start will be like a first start: the beaver will offer the tour again.")

    def set_beaver(self, on: bool):
        """View → Beaver: show / hide the mascot (remembered)."""
        QSettings().setValue("beaver/enabled", bool(on))
        if getattr(self, "beaver", None) is not None:
            self.beaver.set_enabled(on)

    def run_verification(self):
        """Help → Run verification…: the verification report, made in the background (one dialog, kept)."""
        from .verification_dialog import VerificationDialog
        if self._verification is None:
            self._verification = VerificationDialog(self.theme, self)
        dlg = self._verification
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        tint_title_bar(dlg, self.theme)
        if not dlg.running and dlg.report is None:             # a finished report stays (Run again)
            dlg.start()

    def _show_conventions(self):
        """Help → Sign conventions: one card per element (app/conventions_dialog.py)."""
        from .conventions_dialog import ConventionsDialog
        dlg = ConventionsDialog(self.theme, self)
        try:
            dlg.exec()
        finally:
            dispose(dlg)

    def show_hardware(self):
        """Help → Your computer…"""
        from .hardware_dialog import HardwareDialog
        dlg = HardwareDialog(self)
        try:
            dlg.exec()
        finally:
            dispose(dlg)

    def _show_about(self):
        QMessageBox.about(self, "About Potential Flow Lab",
                          "<b>Potential Flow Lab</b><br>"
                          "Interactive 2D incompressible, irrotational flow builder.<br><br>"
                          "Aerodynamics semester project, IZTECH Mechanical Engineering.")


# (moved to app/startup.py: light, so the loading screen can show before this module is imported)
from .startup import default_font, setup_application  # noqa: E402,F401
