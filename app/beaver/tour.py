"""
tour.py — the beaver's guided tour (first start, or Help → Beaver → Show me around): a game-like tutorial
that shows each part of the window and lets the user DO the main things — add a uniform flow and a
doublet, edit an element, move one, change a setting, start the animation — then leaves an empty plot.

Every step has a text, the part of the window it is about (highlighted, the beaver goes next to it, his
bubble never covers it) and either nothing to wait for (a reading step) or an action the user has to do (the
window tells the tour: added / edited / mouse_mode / moved / setting / view_mode; then it goes on by itself).

While the tour runs the window is locked: a click, double-click, wheel or right-click only reaches what the
step allows (`Step.allow`, checked by `Tour.allows`); the mouse still hovers everywhere (highlights,
tooltips). Keys: Enter / Space = next (an action step: skip it), Esc = end the tour; every other key is
swallowed, except the ones a step asks for (M in the Move step). The bubble has the same as buttons (End tour,
Next / Skip); a click on the bubble or the beaver = next in a reading step.

Sub-steps (`Tour.sub`): while an element is dragged from the palette the plot is highlighted ("drag"); while
an element dialog is open the beaver stands beside it and explains it ("dialog"; Apply goes on, Cancel back).
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt

from .spotlight import PAD


@dataclass
class Step:
    text: str
    target: str | None = None        # what to highlight (Tour._rect)
    wait: tuple | None = None        # (event, value) the user has to do; None: just read
    where: str = "auto"              # where the beaver stands: right / left / below / inside / perch
    enter: str | None = None         # something the tour does first ("clear")
    allow: str | None = None         # what the mouse may use (Tour.allows); None: nothing
    keys: tuple = ()                 # keys that keep their normal meaning in this step (e.g. M = Move mode)


END_BUTTON = "End tour (Esc)"
NEXT_BUTTON = "Next (Enter)"
SKIP_BUTTON = "Skip (Enter)"
READ_HINT = "Enter / Space / click: next"
DO_HINT = "Your turn!   Enter / Space: skip"
DIALOG_HINT = "Apply: go on   Cancel: back"
DRAG_HINT = "Let go over the plot"
TAIL_ROOM = 16                       # px: the bubble's tail and margin (bubble.TAIL + 6)

STEPS = [
    Step("Welcome to Potential Flow Lab! I'll show you around in two minutes. "
         "Let's start with an empty sheet.", None, enter="clear", where="inside"),
    Step("This is the plot. Everything you build shows up here: streamlines, stagnation points, colours "
         "and animations. Try it: scroll to zoom, drag to pan.", "plot", where="inside", allow="plot"),
    Step("This is the ADD palette: the building blocks of potential flow. Uniform flow, source, vortex, "
         "doublet, sector flow and walls. Point at one to see what it is.", "palette", where="right"),
    Step("Let's build something! Drag a UNIFORM flow from here onto the plot (a click works too).",
         "palette:uniform", ("added", "uniform"), where="right", allow="palette:uniform"),
    Step("Streamlines! Each line follows the flow. A uniform flow is just parallel lines, so let's make it "
         "more interesting.", "plot", where="inside", allow="plot"),
    Step("Now drag a DOUBLET to the middle of the plot (a click works too). Uniform flow + doublet = the "
         "flow round a cylinder.", "palette:doublet", ("added", "doublet"), where="right",
         allow="palette:doublet"),
    Step("That's a cylinder! The crossed circles are stagnation points: the flow stops there, V = 0 and "
         "Cp = 1.", "plot", where="inside", allow="plot"),
    Step("Your elements are listed here. Double-click the DOUBLET row to edit it.",
         "elements", ("edited", "doublet"), where="left", allow="elements:doublet"),
    Step("Elements can also be moved with the mouse. Press MOVE (or the M key).", "move",
         ("mouse_mode", "move"), where="below", allow="move", keys=(Qt.Key_M,)),
    Step("Now grab the doublet's orange symbol on the plot and drag it to a new place.", "plot",
         ("moved", None), where="inside", allow="plot_move"),
    Step("Plot settings: line density, arrows, colour maps of Cp and speed, phi lines, solid bodies, surface "
         "pressure with lift and drag.", "settings", where="left"),
    Step("Try one: drag the DENSITY slider and watch the streamlines.", "slider:density",
         ("setting", "density"), where="left", allow="slider:density"),
    Step("Time for some motion: click PARTICLES.", "particles", ("view_mode", "particles"), where="below",
         allow="particles"),
    Step("Particles ride the flow, colour = speed. PULSES shows pulses running along the streamlines, STATIC "
         "brings back the arrows. Space pauses.", "plot", where="inside", allow="plot"),
    Step("EXPORT saves a figure (PNG, SVG, PDF), an animation (GIF, MP4) or the numbers (CSV) for your "
         "report.", "export", where="below"),
    Step("File: save and open your scenes. Presets: ready-made scenes, with the assignment's verification "
         "cases.", "menu:File", where="below"),
    Step("Help: Run verification checks the program against the theory, and this tour lives there too.",
         "menu:Help", where="below"),
    Step("And me! Drag me onto the plot for fun, click me for help, and press P any time for questions and "
         "answers. You'll find me on my shelf. Have fun!", "perch", where="perch"),
]

# what the beaver says beside an open element dialog
DIALOG_TEXT = {
    "add": "This is where the numbers go. Change them if you like (Tab moves to the next box), then press "
           "APPLY. Cancel takes you back.",
    "edit": "Make the doublet stronger: type a bigger mu, for example 2, then press APPLY.",
}
DRAG_TEXT = "Now let go over the plot, where you want it."
NO_CHANGE_TEXT = "Nothing changed! Double-click the DOUBLET row again and type a bigger mu."


class Tour:
    def __init__(self, beaver, window, spotlight):
        self.beaver, self.win, self.spot = beaver, window, spotlight
        self.i = -1
        self.done_wait = None            # seconds until "next" after the user did the action
        self.active = False
        self.sub = None                  # None, "drag" (palette → plot), "drag_end", "dialog"
        self.sub_t = 0.0
        self.dialog = None               # the open element dialog (sub == "dialog")
        self.dialog_kind = "add"
        self.note = None                 # a text shown instead of the step's text (e.g. nothing changed)
        self._restore = {}               # settings changed by the tour: put back at the end

    @property
    def step(self) -> Step | None:
        return STEPS[self.i] if 0 <= self.i < len(STEPS) else None

    # ------------------------------------------------------------------ control
    def start(self):
        self.active = True
        self.i = -1
        self._restore = {}
        fw = self.win.focusWidget()
        if fw is not None:
            fw.clearFocus()                              # (a text field must not keep Enter / Space)
        self.win.setFocus()
        self.next()

    def next(self):
        """Enter / Space / the Next button: finish the typing, or go on (an action step: skip it)."""
        b = self.beaver.bubble
        if b.typing and self.done_wait is None:
            b.finish_typing()
            return
        self.i += 1
        self.done_wait = None
        self.sub, self.dialog, self.note = None, None, None
        if self.i >= len(STEPS):
            self.end(completed=True)
            return
        s = self.step
        if s.enter == "clear":
            self.win.canvas.set_view_mode("static")
            self.win.canvas.set_mode("select")
            self.win.new_scene()
        if s.wait == ("mouse_mode", "move") and self.win.canvas.mode == "move":
            self.i += 1                                  # already in Move mode: straight to the drag
        if s.target and s.target.startswith("slider:"):
            key = s.target.split(":")[1]
            sl = self.win.settings_panel.sliders.get(key)
            if sl is not None and key not in self._restore:
                self._restore[key] = sl.value()
        self.show()

    def click(self):
        """A click on the bubble or on the beaver: next in a reading step (an action step needs the
        action, or Enter / Space / Skip)."""
        s = self.step
        if s is None or self.sub is not None or self.done_wait is not None:
            return
        if self.beaver.bubble.typing:
            self.beaver.bubble.finish_typing()
        elif s.wait is None:
            self.next()

    def button(self, k: int):
        """The bubble's buttons: 0 = End tour, 1 = Next / Skip."""
        if k == 0:
            self.end(completed=False)
        elif k == 1 and self.sub is None and self.done_wait is None:
            self.next()

    def show(self):
        s = self.step
        rect = self.target_rect()
        self.spot.show_on(rect)
        self.spot.raise_()
        self.beaver.tour_goto(self._feet_now(rect))
        n = f"{self.i + 1}/{len(STEPS)}"
        if self.sub == "dialog":
            self.beaver.bubble.say(DIALOG_TEXT.get(self.dialog_kind, DIALOG_TEXT["add"]),
                                   hint=f"{n}   {DIALOG_HINT}", sticky=True)
        elif self.sub == "drag":
            self.beaver.bubble.say(DRAG_TEXT, hint=f"{n}   {DRAG_HINT}", sticky=True)
        else:
            hint = DO_HINT if s.wait else READ_HINT
            self.beaver.bubble.say(self.note or s.text, hint=f"{n}   {hint}", sticky=True,
                                   buttons=[END_BUTTON, SKIP_BUTTON if s.wait else NEXT_BUTTON])
        self.beaver._place_bubble()

    def notify(self, event: str, value=None):
        """The user did something (the window tells): a sub-step, or the action of this step?"""
        s = self.step
        if not self.active or s is None or self.done_wait is not None:
            return
        if event == "palette_drag":
            if s.allow == f"palette:{value}":
                self.sub, self.sub_t = "drag", 0.0
                self.show()
                self.spot.repaint()                     # (the drag runs its own event loop)
            return
        if event == "palette_drag_end":
            if self.sub == "drag":
                self.sub, self.sub_t = "drag_end", 0.0  # a drop opens the dialog right after this
            return
        if event == "dialog_open":
            kind, _key, dlg = value
            self.sub, self.dialog, self.dialog_kind = "dialog", dlg, kind
            self.show()
            return
        if event == "dialog_closed":
            accepted, changed = value
            if self.sub == "dialog":
                self.sub, self.dialog = None, None
                if accepted and not changed and s.wait and s.wait[0] == "edited":
                    self.note = NO_CHANGE_TEXT
                self.show()
            return
        if s.wait is None:
            return
        if s.wait[0] == event and (s.wait[1] is None or s.wait[1] == value):
            self.done_wait = 1.0
            self.sub, self.dialog = None, None
            self.beaver.bubble.say(self.beaver.lines.pick("tour_nice"), sticky=True)
            self.beaver._place_bubble()

    def advance(self, dt):
        self.spot.advance(dt)
        if self.done_wait is not None:
            self.done_wait -= dt
            if self.done_wait <= 0:
                self.done_wait = None
                self.beaver.bubble.clear()
                self.next()
            return
        if self.sub == "drag_end":
            self.sub_t += dt
            if self.sub_t > 0.3:                        # let go somewhere else: back to the step
                self.sub = None
                self.show()
            return
        if self.step is not None:                       # keep the highlight on its widget (resizes, docks)
            rect = self.target_rect()
            self.spot.show_on(rect)
            if self.sub == "dialog":
                self.beaver.tour_goto(self._feet_now(rect))
                self.beaver._place_bubble()

    def end(self, completed: bool):
        self.active = False
        self.spot.hide()
        self.i = -1
        self.sub, self.dialog, self.note, self.done_wait = None, None, None, None
        for key, pos in self._restore.items():           # settings the tour changed (the Density slider)
            sl = self.win.settings_panel.sliders.get(key)
            if sl is not None:
                sl.setValue(pos)
        self._restore = {}
        self.beaver.tour_ended(completed)
        self.win.canvas.set_mode("select")
        if completed:                                    # an empty plot, as at the start
            self.win.canvas.set_view_mode("static")
            self.win.model.mark_clean()
            self.win.new_scene()

    # ------------------------------------------------------------------ the lock
    def allows(self, obj, event) -> bool:
        """May this mouse press / double-click / wheel / context menu reach `obj` (a widget of the
        window)? Only what the current step asks for; nothing while a sub-step or "Nice!" runs."""
        s = self.step
        if s is None or self.done_wait is not None or self.sub is not None or s.allow is None:
            return False
        t = event.type()
        if t == QEvent.ContextMenu:
            return False
        left = t == QEvent.Wheel or event.button() == Qt.LeftButton
        win, a = self.win, s.allow
        if a in ("plot", "plot_move"):                   # zoom, pan (and in Move mode: drag an element)
            plot = win.canvas.plot
            inside = obj is plot or plot.isAncestorOf(obj)
            return inside and t != QEvent.MouseButtonDblClick and (left or event.button() == Qt.MiddleButton)
        if not left:
            return False
        if a.startswith("palette:"):
            return obj is self._palette_button(a.split(":")[1]) and t != QEvent.Wheel
        if a == "elements:doublet":
            return self._on_element_row(obj, event, "doublet")
        if a == "move":
            return obj is win.canvas.bar.btn_move and t != QEvent.Wheel
        if a == "particles":
            return obj is win.canvas.bar.btn_particles and t != QEvent.Wheel
        if a.startswith("slider:"):
            return obj is win.settings_panel.sliders.get(a.split(":")[1])
        return False

    def allows_key(self, key) -> bool:
        s = self.step
        return s is not None and self.sub is None and self.done_wait is None and key in s.keys

    def _on_element_row(self, obj, event, kind) -> bool:
        """A press / double-click on the row of an element of type `kind`, not on its check box."""
        tree = self.win.elements_panel.tree
        if obj is not tree.viewport() or event.type() == QEvent.Wheel:
            return False
        pos = event.position().toPoint()
        item = tree.itemAt(pos)
        if item is None:
            return False
        row = tree.indexOfTopLevelItem(item)
        els = self.win.elements
        if not (0 <= row < len(els)) or els[row].TYPE != kind:
            return False
        return not self._check_box_rect(tree, item).contains(pos)

    @staticmethod
    def _check_box_rect(tree, item):
        from PySide6.QtWidgets import QStyle, QStyleOptionViewItem
        index = tree.indexFromItem(item, 0)
        opt = QStyleOptionViewItem()
        opt.initFrom(tree)
        tree.itemDelegate().initStyleOption(opt, index)
        opt.rect = tree.visualItemRect(item)
        r = tree.style().subElementRect(QStyle.SE_ItemViewItemCheckIndicator, opt, tree)
        return r.adjusted(-4, -6, 4, 6)                  # a little margin round the box

    # ------------------------------------------------------------------ geometry
    def target_rect(self):
        """What is highlighted now: the step's target, the plot while dragging, the open dialog."""
        if self.sub in ("drag", "drag_end"):
            return self._rect("plot")
        if self.sub == "dialog" and self.dialog is not None:
            try:
                g = self.dialog.frameGeometry()
                p = self.win.mapFromGlobal(g.topLeft())
                return QRectF(p.x(), p.y(), g.width(), g.height())
            except RuntimeError:                         # (the dialog is gone)
                return None
        s = self.step
        return self._rect(s.target) if s is not None else None

    def avoid_rect(self):
        """What the bubble must not cover (the highlighted part with its frame); None when the beaver
        stands inside it (the plot steps) or on his shelf."""
        s = self.step
        if s is None or (self.sub is None and s.where in ("inside", "perch")) or self.sub in ("drag", "drag_end"):
            return None
        r = self.target_rect()
        return None if r is None else QRectF(r).adjusted(-PAD - 4, -PAD - 4, PAD + 4, PAD + 4)

    def _feet_now(self, rect):
        if self.sub == "dialog":
            return self._feet_beside_dialog(rect)
        if self.sub in ("drag", "drag_end"):
            return self.beaver.data.get("feet")          # he stays where he is
        s = self.step
        if rect is not None and s.target and s.target.startswith("slider:"):
            dock = self._map(self.win.dock_settings)    # outside the panel, level with the slider
            rect = QRectF(dock.left(), rect.top(), rect.right() - dock.left(), rect.height())
        return self._feet(rect, s.where)

    def _feet_beside_dialog(self, r):
        """Next to the open dialog, on a side with room for him AND his bubble (left, right, below, above),
        so the bubble never covers the dialog (a separate window: it would hide the bubble)."""
        if r is None:
            return None
        b, win = self.beaver, self.win
        W, H = win.width(), win.height()
        top = b.ruler_bottom() + 10
        bw = b.bubble._box.width() + 2 * TAIL_ROOM + 90          # bubble + his body beside it
        bh = b.bubble._box.height() + 90
        if r.left() > bw:
            return QPointF(r.left() - 50, min(r.center().y() + 30, H - 40))
        if W - r.right() > bw:
            return QPointF(r.right() + 50, min(r.center().y() + 30, H - 40))
        if H - r.bottom() > bh:
            return QPointF(max(60.0, r.left() + 40), min(r.bottom() + 90, H - 30))
        if r.top() - top > bh:
            return QPointF(max(60.0, r.left() + 40), r.top() - 20)
        return QPointF(60.0, H - 40)                                # (a tiny window: bottom left)

    def _map(self, w) -> QRectF:
        p = w.mapTo(self.win, QPoint(0, 0))
        return QRectF(p.x(), p.y(), w.width(), w.height())

    def _palette_button(self, key):
        win = self.win
        for b in win.element_toolbar.findChildren(type(win.canvas.bar.btn_move)):
            if b.property("element_key") == key:
                return b
        return None

    def _rect(self, target):
        win = self.win
        if target is None:
            return None
        if target == "plot":
            return self.beaver.plot_rect()
        if target == "palette":
            return self._map(win.element_toolbar)
        if target.startswith("palette:"):
            b = self._palette_button(target.split(":")[1])
            return self._map(b if b is not None else win.element_toolbar)
        if target == "elements":
            return self._map(win.dock_elements)
        if target == "settings":
            return self._map(win.dock_settings) if hasattr(win, "dock_settings") else self._map(win.settings_panel)
        if target.startswith("slider:"):
            sl = win.settings_panel.sliders.get(target.split(":")[1])
            return self._map(sl) if sl is not None else self._map(win.dock_settings)
        if target == "move":
            return self._map(win.canvas.bar.btn_move)
        if target == "particles":
            return self._map(win.canvas.bar.btn_particles)
        if target == "export":
            return self._map(win.canvas.bar.btn_export)
        if target.startswith("menu:"):
            name = target.split(":")[1]
            mb = win.menuBar()
            for a in mb.actions():
                if a.text().replace("&", "") == name:
                    g = mb.actionGeometry(a)
                    p = mb.mapTo(win, g.topLeft())
                    return QRectF(p.x(), p.y(), g.width(), g.height())
        if target == "perch":
            p = self.beaver.perch_feet()
            return QRectF(p.x() - 40, p.y() - 60, 80, 64)
        return None

    def _feet(self, rect, where) -> QPointF:
        """Where the beaver stands (his feet) for this step."""
        b, win = self.beaver, self.win
        S = b.S()
        plot = b.plot_rect()
        if where == "perch":
            return None
        if where == "inside" or rect is None:
            return QPointF(plot.left() + 70, plot.top() + 110)
        W, H = win.width(), win.height()
        if where == "right" and rect.right() + 90 < W:
            return QPointF(rect.right() + 50, min(rect.center().y() + 30, H - 40))
        if where == "left" and rect.left() - 90 > 0:
            y = rect.top() + 140 if rect.height() > 200 else rect.center().y() + 30    # a panel / a slider
            return QPointF(rect.left() - 50, min(y, H - 40))
        return QPointF(min(max(rect.center().x(), 60), W - 60), min(rect.bottom() + 20 + 30 * S, H - 40))
