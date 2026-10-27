"""
layout.py — part of MainWindow: the side panels (dock widgets), the element palette left / right of
the plot, and remembering / resetting the layout.

Side panels sit only left or right of the plot, stacked (no floating, no tabs). The layout the user
leaves is restored at the next start (QSettings "layout/*"); View → Panels → Reset layout goes back to
the layout of the first start.
"""
from PySide6.QtCore import QByteArray, QRect, QSettings, Qt
from PySide6.QtWidgets import QDockWidget

from ..chrome import PanelBody, PanelTitle
from ..theme import LAYOUT

LAYOUT_STATE_VERSION = 1          # bump when the dock layout changes incompatibly (old saved layouts ignored)
SIDE_AREAS = (Qt.LeftDockWidgetArea, Qt.RightDockWidgetArea)


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
        return self.dock_elements, self.dock_settings

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
        """Both panels on the right, Elements above Plot settings."""
        de, ds = self._docks()
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
            if any(d.isFloating() or self.dockWidgetArea(d) not in SIDE_AREAS for d in self._docks()):
                self._default_dock_layout()                 # never restore a forbidden place
            for d in self._docks():
                self._place_dock_card(d)
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
