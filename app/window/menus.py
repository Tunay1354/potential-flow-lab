"""
menus.py — part of MainWindow: the element palette, the menus on the ruler (File, Edit, Elements,
View, Presets, Help) and the keyboard shortcuts the user can change (Edit → Keyboard shortcuts…).
"""
import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QKeySequence, QShortcut

from physics import ELEMENT_TYPES

from ..chrome import DropIndicator, ElementPalette
from ..dialogs import dispose
from ..element_specs import spec_for, toolbar_types
from ..icons import make_element_icon
from ..canvas import LAYERS
from ..panels import element_icon, element_title
from ..scene import PRESETS_DIR, list_presets
from ..shortcuts import Shortcuts, ShortcutsDialog
from ..theme import DARK, LIGHT

# short names under the palette icons (the full name is in the tooltip)
PALETTE_NAMES = {"uniform": "Uniform", "source": "Source", "vortex": "Vortex", "doublet": "Doublet",
                 "sector": "Sector", "wall": "Wall"}


class MenusMixin:

    # ------------------------------------------------------------------ element palette
    def _build_palette(self):
        """Element palette left of the plot (a card on the paper, like the side panels)."""
        pal = ElementPalette(self)
        self.element_actions = {}
        separated = False
        for key in toolbar_types():
            spec = spec_for(key)
            if ELEMENT_TYPES[key].IS_BOUNDARY and not separated:
                pal.add_separator()     # walls are boundaries, not flows -> visually separated
                separated = True
            act = QAction(PALETTE_NAMES.get(key, spec.name), self)
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

    # ------------------------------------------------------------------ menus
    def _build_menus(self):
        mb = self.menuBar()
        self._build_file_menu(mb.addMenu("&File"))
        self._build_edit_menu(mb.addMenu("&Edit"))
        self.elements_menu = mb.addMenu("E&lements")      # rebuilt whenever the scene changes
        self._build_view_menu(mb.addMenu("&View"))
        self._build_presets_menu(mb.addMenu("&Presets"))
        self._build_help_menu(mb.addMenu("&Help"))

    def _build_file_menu(self, m):
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
        self.act_exit = m.addAction("Exit")
        self.act_exit.setShortcut(QKeySequence("Ctrl+Q"))      # (QKeySequence.Quit is empty on Windows)
        self.act_exit.triggered.connect(self.close)

    def _build_edit_menu(self, m):
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

    def _build_view_menu(self, m):
        lay = m.addMenu("Layers")
        self.layer_actions = {}
        for key, text, on in LAYERS:                     # same switches as in Plot settings → Layers
            a = lay.addAction(text)
            a.setCheckable(True)
            a.setChecked(on)
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
        self.act_fit = m.addAction("Fit view")
        self.act_fit.setShortcut("F")
        self.act_fit.triggered.connect(self.canvas.fit_view)
        # mouse mode of the plot (same as the Select / Move / Pan buttons above it)
        mm = m.addMenu("Mouse mode")
        group = QActionGroup(self)
        self.mode_actions = {}
        for md, text, key in (("select", "Select", "V"), ("move", "Move elements", "M"), ("pan", "Pan", "H")):
            a = mm.addAction(text)
            a.setCheckable(True)
            a.setChecked(md == self.canvas.mode)
            a.setShortcut(key)
            a.triggered.connect(lambda _=False, md=md: self.canvas.set_mode(md))
            group.addAction(a)
            self.mode_actions[md] = a
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

    def _build_presets_menu(self, m):
        """Scene files in the presets folder, one section per group folder."""
        for i, (group, items) in enumerate(list_presets()):
            if i:
                m.addSeparator()
            m.addAction(group).setEnabled(False)
            for preset in items:
                a = m.addAction("    " + preset.title)
                a.triggered.connect(lambda _=False, p=preset: self.load_preset(p))
        m.addSeparator()
        m.addAction("Show presets folder").triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(PRESETS_DIR)))

    def _build_help_menu(self, m):
        guide = m.addAction("User guide")
        guide.setShortcut("F1")
        guide.triggered.connect(lambda: self.flash("The user guide is not written yet (it comes with the report)."))
        m.addAction("Sign conventions").triggered.connect(self._show_conventions)
        m.addAction("Keyboard shortcuts…").triggered.connect(self.edit_shortcuts)
        m.addSeparator()
        m.addAction("About").triggered.connect(self._show_about)

    def _rebuild_elements_menu(self):
        """Elements menu (required by the assignment): Add, then every element with its actions."""
        m = self.elements_menu
        m.clear()
        add = m.addMenu("Add")
        for key in toolbar_types():
            a = add.addAction(make_element_icon(key, self.theme, 48), spec_for(key).name + "…")
            a.triggered.connect(lambda _=False, k=key: self.add_element_dialog(k))
        m.addSeparator()
        m.addAction("Current elements:" if self.elements else "No elements — use Add or a preset").setEnabled(False)
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

    # ------------------------------------------------------------------ keyboard shortcuts
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
        dlg = ShortcutsDialog(self.shortcuts, self)
        dlg.exec()
        dispose(dlg)

    def _build_plot_shortcuts(self):
        """Delete / Backspace also work while the plot has focus (not inside number fields)."""
        for key in (QKeySequence.Delete, QKeySequence(Qt.Key_Backspace)):
            sc = QShortcut(key, self.canvas.plot)
            sc.setContext(Qt.WidgetWithChildrenShortcut)
            sc.activated.connect(lambda: self.delete_element(self.elements_panel.current_row()))
