"""
layout.py — part of MainWindow: the side panels (dock widgets), the element palette left / right of
the plot, and remembering / resetting the layout.

Side panels sit only left or right of the plot, stacked (no floating, no tabs). The layout the user
leaves is restored at the next start (QSettings "layout/*"); View → Panels → Reset layout goes back to
the layout of the first start (the plot is not touched):
    left: the element palette · middle: the plot · right: Elements (DEFAULT_ELEMENTS_HEIGHT) over Plot settings
Surface pressure opens on the left (it comes with its layer), as wide as the user left it last time
(QSettings "layout/surface_width"; a missing or odd width: LAYOUT["surface_panel_width"]).
"""
from PySide6.QtCore import QByteArray, QRect, QSettings, Qt, QTimer
from PySide6.QtWidgets import QDockWidget

from ..chrome import PanelBody, PanelTitle
from ..theme import LAYOUT

LAYOUT_STATE_VERSION = 2          # bump when the dock layout changes incompatibly (old saved layouts ignored)
SIDE_AREAS = (Qt.LeftDockWidgetArea, Qt.RightDockWidgetArea)
DEFAULT_ELEMENTS_HEIGHT = 260     # px: the Elements panel of the default layout (Plot settings gets the rest)
SURFACE_WIDTH_KEY = "layout/surface_width"
SURFACE_WIDTH_RANGE = (240, 0.45)  # a remembered width outside [240 px, 45 % of the window] is not used


class LayoutMixin:

    # ------------------------------------------------------------------ side panels
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

    def _docks(self):
        return self.dock_elements, self.dock_settings, self.dock_surface, self.dock_gpu

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
        """Elements above Plot settings on the right, Graphics card under them (only while the graphics card
        draws); Surface pressure on the left (the graph needs the height), hidden: View → Panels, or it
        opens with the Surface pressure layer. The heights are set again once the window has its final size
        (_default_heights; Qt shares out the extra room of a maximized window)."""
        de, ds, du, dg = self._docks()
        for d in (de, ds, du, dg):
            self.removeDockWidget(d)
        self.addDockWidget(Qt.RightDockWidgetArea, de)
        self.addDockWidget(Qt.RightDockWidgetArea, ds)
        self.addDockWidget(Qt.LeftDockWidgetArea, du)
        self.splitDockWidget(de, ds, Qt.Vertical)
        self.splitDockWidget(ds, dg, Qt.Vertical)
        for d in (de, ds, du, dg):
            d.show()
            self._place_dock_card(d)
        self.resizeDocks([de, ds, du], [LAYOUT["right_panel_width"], LAYOUT["right_panel_width"],
                                        LAYOUT["surface_panel_width"]], Qt.Horizontal)
        du.hide()
        if not getattr(getattr(self, "canvas", None), "gpu", False):
            dg.hide()
        self._default_heights()
        self._layout_is_default = True

    def _default_heights(self):
        """Elements DEFAULT_ELEMENTS_HEIGHT tall, Plot settings the rest of the right column."""
        de, ds = self.dock_elements, self.dock_settings
        if self.dockWidgetArea(de) != self.dockWidgetArea(ds):
            return
        self._resize_dock(de, DEFAULT_ELEMENTS_HEIGHT, Qt.Vertical)

    def _resize_dock(self, d, size: int, orientation):
        """resizeDocks, made exact: Qt shares the room out in its own way (title bars, separators, the
        other docks), so ask, look, correct (a few times, a few px)."""
        ask = size
        for _ in range(4):
            self.resizeDocks([d], [ask], orientation)
            if not d.isVisible():
                return
            self.layout().activate()
            now = d.height() if orientation == Qt.Vertical else d.width()
            if abs(size - now) <= 1:
                return
            ask += size - now

    def _layout_shown(self):
        """The window has its size (shown, maximized): a default layout gets its heights now."""
        if getattr(self, "_layout_is_default", False):
            self._default_heights()
            QTimer.singleShot(50, self, self._default_heights)          # (after a maximize settles)

    def _sections_changed(self):
        """Plot settings sections hidden / shown: the note on the panel title and the menu ticks."""
        sp = self.settings_panel
        hidden = sp.hidden_sections()
        self.dock_settings.titleBarWidget().note.setText(f"{len(hidden)} HIDDEN" if hidden else "")
        for key, act in self.section_actions.items():
            act.blockSignals(True)
            act.setChecked(sp.section_visible(key))
            act.blockSignals(False)

    # ------------------------------------------------------------------ remember / reset
    def reset_layout(self):
        """View → Panels → Reset layout: the layout of the first start (the scene and the plot stay as they
        are). An open Surface pressure panel stays open, in its default place and width."""
        surface_open = self.dock_surface.isVisible()
        self._default_dock_layout()
        QSettings().remove(SURFACE_WIDTH_KEY)             # (after: hiding it just remembered its width)
        self.set_palette_side("left")
        for key in self.settings_panel.sections:
            self.settings_panel.set_section_visible(key, True)
        if surface_open:
            self.dock_surface.show()
        QTimer.singleShot(0, self, self._default_heights)
        self.flash("Layout reset.")

    # ------------------------------------------------------------------ the Surface pressure panel's width
    def _surface_dock_visible(self, visible: bool):
        """Opened: as wide as last time (or the default); closed: its width is remembered."""
        if visible:
            QTimer.singleShot(0, self, self._fit_surface_dock)
        elif getattr(self, "_surface_fitted", False):      # (not the hiding while a layout is restored)
            self._remember_surface_width()
            self._surface_fitted = False

    def _remember_surface_width(self):
        du = self.dock_surface
        if not du.isFloating() and self._surface_alone() and du.width() > 0:
            lo, hi = self._surface_width_range()
            if lo <= du.width() <= hi:
                QSettings().setValue(SURFACE_WIDTH_KEY, int(du.width()))

    def _surface_width_range(self):
        lo, frac = SURFACE_WIDTH_RANGE
        return lo, max(lo + 60, frac * max(self.width(), 1))

    def _surface_alone(self) -> bool:
        """Nothing else open on its side (its own column: its width is its own)."""
        du = self.dock_surface
        area = self.dockWidgetArea(du)
        return not any(d is not du and d.isVisible() and self.dockWidgetArea(d) == area for d in self._docks())

    def surface_width(self) -> int:
        """The width it opens with: the remembered one, or the default when none / an odd one is saved."""
        lo, hi = self._surface_width_range()
        try:
            w = int(QSettings().value(SURFACE_WIDTH_KEY, 0) or 0)
        except (TypeError, ValueError):
            w = 0
        return w if lo <= w <= hi else int(LAYOUT["surface_panel_width"])

    def _fit_surface_dock(self):
        du = self.dock_surface
        if not du.isVisible():
            return
        if du.isFloating() or self.dockWidgetArea(du) not in SIDE_AREAS:       # never a forbidden place
            du.setFloating(False)
            self.addDockWidget(Qt.LeftDockWidgetArea, du)
            self._place_dock_card(du)
        if self._surface_alone():
            self._resize_dock(du, self.surface_width(), Qt.Horizontal)
        self._surface_fitted = True

    def save_layout(self):
        s = QSettings()
        s.setValue("layout/version", LAYOUT_STATE_VERSION)
        s.setValue("layout/state", self.saveState(LAYOUT_STATE_VERSION))
        s.setValue("layout/palette_side", self.palette_side)
        s.setValue("layout/hidden_sections", ",".join(self.settings_panel.hidden_sections()))
        if self.dock_surface.isVisible():
            self._remember_surface_width()

    def restore_layout(self):
        """Panels, palette side and hidden Plot settings sections as saved when the window was closed.
        A missing, old or invalid saved layout leaves the default layout."""
        s = QSettings()
        if int(s.value("layout/version", 0) or 0) != LAYOUT_STATE_VERSION:
            return
        state = s.value("layout/state")
        if isinstance(state, QByteArray) and self.restoreState(state, LAYOUT_STATE_VERSION):
            self._layout_is_default = False
            if any(d.isFloating() or self.dockWidgetArea(d) not in SIDE_AREAS for d in self._docks()):
                self._default_dock_layout()                 # never restore a forbidden place
            for d in self._docks():
                self._place_dock_card(d)
        self.dock_surface.hide()             # its place is kept; it opens with its layer (or View → Panels)
        self.dock_gpu.setVisible(self.canvas.gpu)  # only while the graphics card draws
        self.set_palette_side(str(s.value("layout/palette_side", "left")))
        hidden = str(s.value("layout/hidden_sections", "") or "").split(",")
        for key in self.settings_panel.sections:
            self.settings_panel.set_section_visible(key, key not in hidden)

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
