"""
main_window.py — assembles menus, element toolbar, plot, side panels and status bar.
"""
import numpy as np
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QActionGroup, QFont, QKeySequence
from PySide6.QtWidgets import (QApplication, QDockWidget, QLabel, QMainWindow, QMessageBox, QToolBar,
                               QToolButton)

from physics import check_scene, reference_speed, velocity
from physics.field import fluid_mask, singular_points

from .canvas import PlotCanvas
from .dialogs import ElementDialog
from .element_specs import ELEMENT_SPECS, SPEC_BY_KEY
from .icons import make_app_icon, make_element_icon
from .panels import ElementsPanel, SettingsPanel, element_icon, element_title
from .scene import PRESETS, starter_scene
from .theme import DARK, DEFAULT_THEME, FONT, LAYOUT, LIGHT, build_stylesheet


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.theme = DEFAULT_THEME
        self.setWindowTitle(LAYOUT["window_title"] + " — untitled")
        self.resize(*LAYOUT["window_size"])

        # the flow elements (Phase 2 will replace this list by a FlowModel with undo/redo)
        self.elements = starter_scene()

        # central plot
        self.canvas = PlotCanvas(self.theme, self.elements, self)
        self.setCentralWidget(self.canvas)
        self.canvas.bar.message.connect(self.flash)
        self.canvas.probe.connect(self._update_probe)

        # right panels (dock widgets -> user can move / float / close them)
        self.elements_panel = ElementsPanel(self.theme)
        self.elements_panel.edit_requested.connect(lambda row: self.edit_element(row))
        self.elements_panel.message.connect(self.flash)
        self.elements_panel.enabled_changed.connect(self._set_enabled)
        self.dock_elements = self._dock("Elements", self.elements_panel)
        self.dock_elements.widget().setMinimumHeight(LAYOUT["elements_panel_min_height"])

        self.settings_panel = SettingsPanel()
        self.settings_panel.message.connect(self.flash)
        sp, cv = self.settings_panel, self.canvas
        sp.density_changed.connect(cv.set_density)
        sp.line_width_changed.connect(cv.set_line_width)
        sp.arrows_changed.connect(cv.set_arrows)
        sp.view_edited.connect(cv.set_view)
        sp.fit_requested.connect(cv.fit_view)
        cv.view_changed.connect(sp.set_view)
        self.dock_settings = self._dock("Plot settings", self.settings_panel)
        self.splitDockWidget(self.dock_elements, self.dock_settings, Qt.Vertical)
        self.resizeDocks([self.dock_elements, self.dock_settings], [LAYOUT["right_panel_width"]] * 2,
                         Qt.Horizontal)
        self.resizeDocks([self.dock_elements, self.dock_settings], [260, 560], Qt.Vertical)

        self._build_toolbar()
        self._build_menus()
        self._build_statusbar()
        self.canvas.computed.connect(self._update_status)
        self.apply_theme(self.theme)
        self.elements_panel.set_elements(self.elements)
        self._update_issues()

    # ------------------------------------------------------------------ building blocks
    def _dock(self, title, widget):
        d = QDockWidget(title, self)
        d.setObjectName(title)
        d.setWidget(widget)
        d.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable |
                      QDockWidget.DockWidgetClosable)
        self.addDockWidget(Qt.RightDockWidgetArea, d)
        return d

    def _build_toolbar(self):
        tb = QToolBar("Add element", self)
        tb.setObjectName("ElementToolbar")
        tb.setMovable(False)
        tb.setOrientation(Qt.Vertical)
        px = LAYOUT["toolbar_icon_px"]
        tb.setIconSize(QSize(px, px))
        tb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon if LAYOUT["toolbar_show_text"]
                              else Qt.ToolButtonIconOnly)
        self.addToolBar(Qt.LeftToolBarArea, tb)
        self.element_actions = {}
        for spec in ELEMENT_SPECS:
            act = QAction(spec.name, self)
            act.setToolTip(f"<b>{spec.name}</b><br>{spec.description}")
            act.triggered.connect(lambda _=False, k=spec.key: self.open_element_dialog(k))
            tb.addAction(act)
            self.element_actions[spec.key] = act
            if spec.key == "sector":
                tb.addSeparator()       # walls are boundaries, not flows -> visually separated
        for btn in tb.findChildren(QToolButton):
            btn.setCursor(Qt.PointingHandCursor)
        self.element_toolbar = tb

    def _build_menus(self):
        mb = self.menuBar()

        # File
        m = mb.addMenu("&File")
        self._act(m, "New", QKeySequence.New)
        self._act(m, "Open…", QKeySequence.Open)
        recent = m.addMenu("Open recent")
        recent.addAction("(empty)").setEnabled(False)
        m.addSeparator()
        self._act(m, "Save", QKeySequence.Save)
        self._act(m, "Save as…", QKeySequence.SaveAs)
        m.addSeparator()
        self._act(m, "Export figure (PNG / PDF / SVG)…", "Ctrl+E")
        self._act(m, "Export data (CSV)…")
        m.addSeparator()
        self._act(m, "Clear all")
        m.addSeparator()
        quit_ = self._act(m, "Exit", QKeySequence.Quit)
        quit_.triggered.disconnect()
        quit_.triggered.connect(self.close)

        # Edit
        m = mb.addMenu("&Edit")
        self._act(m, "Undo", QKeySequence.Undo)
        self._act(m, "Redo", QKeySequence.Redo)
        m.addSeparator()
        self._act(m, "Edit selected element…", "Return")
        self._act(m, "Duplicate selected element", "Ctrl+D")
        self._act(m, "Delete selected element", QKeySequence.Delete)

        # Elements (the menu required by the assignment) — rebuilt whenever the scene changes
        self.elements_menu = mb.addMenu("E&lements")
        self._rebuild_elements_menu()

        # View
        m = mb.addMenu("&View")
        lay = m.addMenu("Layers")
        for text, on in [("Streamlines", True), ("Dividing streamline / body", True),
                         ("Equipotential lines", False), ("|V| contours", False), ("Cp contours", False),
                         ("Element markers", True), ("Walls", True)]:
            a = lay.addAction(text)
            a.setCheckable(True)
            a.setChecked(on)
        mode = QActionGroup(self)
        for text, on in [("Static streamlines", True), ("Animated particles", False)]:
            a = m.addAction(text)
            a.setCheckable(True)
            a.setChecked(on)
            mode.addAction(a)
        m.addSeparator()
        fit = m.addAction("Fit view")
        fit.setShortcut("F")
        fit.triggered.connect(self.canvas.fit_view)
        m.addSeparator()
        m.addAction(self.dock_elements.toggleViewAction())
        m.addAction(self.dock_settings.toggleViewAction())
        m.addSeparator()
        theme_menu = m.addMenu("Theme")
        tg = QActionGroup(self)
        for name, pal in [("Light", LIGHT), ("Dark", DARK)]:
            a = theme_menu.addAction(name)
            a.setCheckable(True)
            a.setChecked(pal is self.theme)
            a.triggered.connect(lambda _=False, p=pal: self.apply_theme(p))
            tg.addAction(a)

        # Presets
        m = mb.addMenu("&Presets")
        for name, make in PRESETS.items():
            if name.strip() == "—":
                m.addSeparator()
                continue
            a = m.addAction(name if make else f"{name}   (Phase 1d)")
            a.setEnabled(make is not None)
            if make:
                a.triggered.connect(lambda _=False, n=name, mk=make: self.load_scene(*mk(), title=n))

        # Help
        m = mb.addMenu("&Help")
        self._act(m, "User guide", "F1")
        m.addAction("Sign conventions").triggered.connect(self._show_conventions)
        m.addSeparator()
        m.addAction("About").triggered.connect(self._show_about)

    def _act(self, menu, text, shortcut=None):
        a = menu.addAction(text)
        if shortcut is not None:
            a.setShortcut(shortcut)
        a.triggered.connect(lambda _=False, t=text: self.flash(f"Prototype: “{t}” is not connected yet."))
        return a

    def _rebuild_elements_menu(self):
        m = self.elements_menu
        m.clear()
        add = m.addMenu("Add")
        for spec in ELEMENT_SPECS:
            a = add.addAction(make_element_icon(spec.key, self.theme, 48), spec.name)
            a.triggered.connect(lambda _=False, k=spec.key: self.open_element_dialog(k))
        m.addSeparator()
        hdr = m.addAction("Current elements:")
        hdr.setEnabled(False)
        for el in self.elements:
            sub = m.addMenu(element_icon(el, self.theme), f"{element_title(el)}   ({el.summary()})")
            e = sub.addAction("Edit…")
            e.triggered.connect(lambda _=False, el=el: self.edit_element(self.elements.index(el)))
            sub.addAction("Duplicate").triggered.connect(lambda: self.flash("Prototype: not connected yet."))
            sub.addAction("Delete").triggered.connect(lambda: self.flash("Prototype: not connected yet."))
        m.addSeparator()
        self._act(m, "Delete all elements")

    def _build_statusbar(self):
        sb = self.statusBar()
        self.probe_label = QLabel("Move the mouse over the plot")
        self.probe_label.setObjectName("ProbeLabel")
        self.issue_label = QLabel("")
        self.count_label = QLabel("")
        sb.addPermanentWidget(self.probe_label)
        sb.addPermanentWidget(self.issue_label)
        sb.addPermanentWidget(self.count_label)

    # ------------------------------------------------------------------ actions
    def open_element_dialog(self, key, editing=False, element=None):
        spec = SPEC_BY_KEY[key]
        values = None
        if element is not None:
            values = {p.key: getattr(element, p.key) for p in spec.params if hasattr(element, p.key)}
        dlg = ElementDialog(spec, self.theme, editing, self, values=values)
        if dlg.exec():
            vals = ",  ".join(f"{k} = {v:g}" for k, v in dlg.values().items())
            self.flash(f"Not connected yet (Phase 2). Dialog returned: {vals}")

    def edit_element(self, row):
        if 0 <= row < len(self.elements):
            el = self.elements[row]
            self.open_element_dialog(el.TYPE, editing=True, element=el)

    def flash(self, text):
        self.statusBar().showMessage(text, 4000)

    def load_scene(self, elements, view=None, title=""):
        """Replace all elements (used by Presets; Phase 2 adds New / Open)."""
        self.elements[:] = elements                  # same list object: canvas and panels keep it
        self.elements_panel.set_elements(self.elements)
        self._rebuild_elements_menu()
        if title:
            self.setWindowTitle(f"{LAYOUT['window_title']} — {title}")
        if view:
            self.canvas.set_view(*view)
        self.canvas.recompute()
        self._update_issues()

    def _update_probe(self, pos):
        if pos is None:
            self.probe_label.setText("Move the mouse over the plot")
            return
        x, y = pos
        z = complex(x, y)
        where = f"x = {x:7.3f}   y = {y:7.3f}   │   "
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

    def _set_enabled(self, row, enabled):
        self.elements[row].enabled = enabled
        self.canvas.recompute()
        self._update_issues()

    def _update_issues(self):
        """Scene check (walls, invalid positions...) shown in the status bar; details in the tooltip."""
        issues = check_scene(self.elements)
        errors = [s for s in issues if s.is_error]
        warnings = [s for s in issues if not s.is_error]
        if errors:
            text = f"✖ {len(errors)} error{'s' if len(errors) > 1 else ''}"
            color = self.theme["danger"]
        elif warnings:
            text = f"⚠ {len(warnings)} warning{'s' if len(warnings) > 1 else ''}"
            color = self.theme["el_doublet"]
        else:
            text, color = "✓ scene OK", self.theme["el_sector"]
        self.issue_label.setText(text)
        self.issue_label.setStyleSheet(f"color: {color}; font-weight: 600;")
        tips = []
        for s in issues:
            who = f"{element_title(self.elements[s.index])}: " if s.index is not None else ""
            tips.append(f"{'✖' if s.is_error else '⚠'} {who}{s.message}")
        self.issue_label.setToolTip("\n".join(tips) if tips else "No problems found.")

    def _update_status(self, n_lines, ms):
        n = len(self.elements)
        on = sum(e.enabled for e in self.elements)
        self.count_label.setText(f"{n} elements ({on} active)  |  {n_lines} streamlines in {ms:.0f} ms"
                                 f"  |  editing not connected yet")

    def apply_theme(self, theme):
        self.theme = theme
        app = QApplication.instance()
        app.setStyleSheet(build_stylesheet(theme))
        self.setWindowIcon(make_app_icon(theme))
        for key, act in self.element_actions.items():
            act.setIcon(make_element_icon(key, theme))
        self.canvas.apply_theme(theme)
        self.elements_panel.apply_theme(theme)
        if hasattr(self, "issue_label"):
            self._update_issues()

    def _show_conventions(self):
        QMessageBox.information(self, "Sign conventions",
                                "<b>Complex potential</b>: F(z) = φ + iψ,  w = dF/dz = u − iv<br><br>"
                                "<b>Source/sink</b>: m &gt; 0 source, m &lt; 0 sink<br>"
                                "<b>Vortex</b>: Γ &gt; 0 counter-clockwise, Γ &lt; 0 clockwise<br>"
                                "<b>Doublet</b>: F = μ e<sup>iδ</sup>/(z − z₀),  cylinder radius a = √(μ/V∞)<br>"
                                "<b>Sector</b>: β = θ₂ − θ₁,  n = π/β<br>"
                                "<b>Pressure</b>: Cp = 1 − (V/V∞)²")

    def _show_about(self):
        QMessageBox.about(self, "About Potential Flow Lab",
                          "<b>Potential Flow Lab</b> — UI prototype<br>"
                          "Interactive 2D incompressible, irrotational flow builder.<br><br>"
                          "Aerodynamics semester project, IZTECH Mechanical Engineering.")


def setup_application(app):
    """Settings that must be identical on every computer (Windows TR/EN, macOS)."""
    from PySide6.QtCore import QLocale
    # numbers always with a decimal POINT (1.000), whatever the system region is (TR uses 1,000)
    QLocale.setDefault(QLocale(QLocale.English, QLocale.UnitedStates))
    app.setApplicationName("Potential Flow Lab")
    app.setStyle("Fusion")          # same look on Windows and macOS
    app.setFont(default_font())


def default_font():
    from PySide6.QtGui import QFontDatabase
    families = set(QFontDatabase.families())
    f = QFont()
    for fam in FONT["families"]:
        if fam in families:
            f.setFamily(fam)
            break
    f.setPointSize(FONT["size_pt"])
    return f
