"""
main_window.py — assembles menus, element toolbar, plot, side panels and status bar.
"""
import numpy as np
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QActionGroup, QFont, QKeySequence
from PySide6.QtWidgets import (QApplication, QDockWidget, QLabel, QMainWindow, QMessageBox, QToolBar,
                               QToolButton)

from . import demo_flow
from .canvas import PlotCanvas
from .dialogs import ElementDialog
from .element_specs import ELEMENT_SPECS, SPEC_BY_KEY
from .icons import make_app_icon, make_element_icon
from .panels import ElementsPanel, SettingsPanel
from .theme import DARK, DEFAULT_THEME, FONT, LAYOUT, LIGHT, build_stylesheet

PRESETS = ["Non-lifting cylinder", "Lifting (rotating) cylinder", "Rankine half-body",
           "Rankine oval", "Corner flow (90° sector)", "Source near a wall", "Vortex near a wall"]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.theme = DEFAULT_THEME
        self.setWindowTitle(LAYOUT["window_title"] + " — untitled")
        self.resize(*LAYOUT["window_size"])

        # central plot
        self.canvas = PlotCanvas(self.theme, self)
        self.setCentralWidget(self.canvas)
        self.canvas.bar.message.connect(self.flash)
        self.canvas.probe.connect(self._update_probe)

        # right panels (dock widgets -> user can move / float / close them)
        self.elements_panel = ElementsPanel(self.theme)
        self.elements_panel.edit_requested.connect(lambda k: self.open_element_dialog(k, editing=True))
        self.elements_panel.message.connect(self.flash)
        self.dock_elements = self._dock("Elements", self.elements_panel)
        self.dock_elements.widget().setMinimumHeight(LAYOUT["elements_panel_min_height"])

        self.settings_panel = SettingsPanel()
        self.settings_panel.message.connect(self.flash)
        self.dock_settings = self._dock("Plot settings", self.settings_panel)
        self.splitDockWidget(self.dock_elements, self.dock_settings, Qt.Vertical)
        self.resizeDocks([self.dock_elements, self.dock_settings], [LAYOUT["right_panel_width"]] * 2,
                         Qt.Horizontal)
        self.resizeDocks([self.dock_elements, self.dock_settings], [260, 560], Qt.Vertical)

        self._build_toolbar()
        self._build_menus()
        self._build_statusbar()
        self.apply_theme(self.theme)

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

        # Elements (the menu required by the assignment)
        m = mb.addMenu("E&lements")
        add = m.addMenu("Add")
        for spec in ELEMENT_SPECS:
            a = add.addAction(make_element_icon(spec.key, self.theme, 48), spec.name)
            a.triggered.connect(lambda _=False, k=spec.key: self.open_element_dialog(k))
        m.addSeparator()
        hdr = m.addAction("Current elements:")
        hdr.setEnabled(False)
        from .panels import DEMO_ELEMENTS
        for key, name, params, _ in DEMO_ELEMENTS:
            sub = m.addMenu(make_element_icon(key, self.theme, 48), f"{name}   ({params})")
            e = sub.addAction("Edit…")
            e.triggered.connect(lambda _=False, k=key: self.open_element_dialog(k, editing=True))
            sub.addAction("Duplicate").triggered.connect(lambda: self.flash("Prototype: not connected yet."))
            sub.addAction("Delete").triggered.connect(lambda: self.flash("Prototype: not connected yet."))
        m.addSeparator()
        self._act(m, "Delete all elements")

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
        for p in PRESETS:
            a = m.addAction(p)
            a.triggered.connect(lambda _=False, p=p: self.flash(f"Prototype: preset “{p}” is not connected yet."))

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

    def _build_statusbar(self):
        sb = self.statusBar()
        self.probe_label = QLabel("Move the mouse over the plot")
        self.probe_label.setObjectName("ProbeLabel")
        self.count_label = QLabel("3 elements  |  no walls  |  Prototype (demo flow)")
        sb.addPermanentWidget(self.probe_label)
        sb.addPermanentWidget(self.count_label)

    # ------------------------------------------------------------------ actions
    def open_element_dialog(self, key, editing=False):
        dlg = ElementDialog(SPEC_BY_KEY[key], self.theme, editing, self)
        if dlg.exec():
            self.flash(f"Prototype: {SPEC_BY_KEY[key].name} would be "
                       f"{'updated' if editing else 'added'} now.")

    def flash(self, text):
        self.statusBar().showMessage(text, 4000)

    def _update_probe(self, pos):
        if pos is None:
            self.probe_label.setText("Move the mouse over the plot")
            return
        x, y = pos
        if demo_flow.inside_body(x, y):
            self.probe_label.setText(f"x = {x:6.2f}   y = {y:6.2f}   │   inside body")
            return
        u, v = demo_flow.velocity(x, y)
        V = float(np.hypot(u, v))
        cp = 1.0 - (V / demo_flow.V_INF) ** 2
        self.probe_label.setText(f"x = {x:6.2f}   y = {y:6.2f}   │   u = {float(u):6.3f}   "
                                 f"v = {float(v):6.3f}   |V| = {V:6.3f}   Cp = {cp:6.3f}")

    def apply_theme(self, theme):
        self.theme = theme
        app = QApplication.instance()
        app.setStyleSheet(build_stylesheet(theme))
        self.setWindowIcon(make_app_icon(theme))
        for key, act in self.element_actions.items():
            act.setIcon(make_element_icon(key, theme))
        self.canvas.apply_theme(theme)
        self.elements_panel.apply_theme(theme)

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
