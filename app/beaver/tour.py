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
swallowed, except the ones a step asks for (M in the Move step). Right arrow = next too, Left arrow = the step
before (an action already done there is shown as done, with Next). The bubble has the same as buttons (End tour,
Back, Next / Skip); a click on the bubble or the beaver = next in a reading step. A slider step goes on when the
slider is let go, not while it is dragged.

Sub-steps (`Tour.sub`): while an element is dragged from the palette the plot is highlighted ("drag"); while
an element dialog is open the beaver stands beside it and explains it ("dialog"; Apply goes on, Cancel back);
a doublet dialog that shows the "doublet axis not along the flow" warning gets a short hint (the angle that fixes it).
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt

from .spotlight import PAD


def _scroll_area_of(w):
    from PySide6.QtWidgets import QScrollArea
    while w is not None and not isinstance(w, QScrollArea):
        w = w.parentWidget()
    return w


@dataclass
class Step:
    text: str
    target: str | None = None        # what to highlight (Tour._rect)
    wait: tuple | None = None        # (event, value) the user has to do; None: just read
    where: str = "auto"              # where the beaver stands: right / left / below / inside / perch
    enter: str | None = None         # something the tour does first ("clear")
    allow: str | None = None         # what the mouse may use (Tour.allows); None: nothing
    keys: tuple = ()                 # keys that keep their normal meaning in this step (e.g. M = Move mode)


END_BUTTON = "End tour"            # Esc does the same
NEXT_BUTTON = "Next \u203a"        # Enter / Space / a click on the bubble do the same (the main button)
SKIP_BUTTON = "Skip"               # an action step: Enter / Space do the same
BACK_BUTTON = "\u2039 Back"         # Left arrow does the same
TAIL_ROOM = 16                       # px: the bubble's tail and margin (bubble.TAIL + 6)

STEPS = [
    Step("Welcome to Flowy! I'll show you around in two minutes. "
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
    Step("The GPU box: your graphics card draws the plot, smoother and faster, and the sliders reach "
         "further. The program restarts in seconds, your work stays. The arrow beside it: frame rate.", "gpu",
         where="below"),
    Step("And me! Drag me onto the plot for fun, and click me (or press P) whenever you need help. You'll find "
         "me on my shelf. Have fun!", "perch", where="perch"),
]
GPU_OFF_TEXT = " (Not on this computer: point at it to see why.)"

# what the beaver says beside an open element dialog
DIALOG_TEXT = {
    "add": "This is where the numbers go. Change them if you like (Tab moves to the next box), then press "
           "APPLY. Cancel takes you back.",
    "edit": "Make the doublet stronger: type a bigger mu, for example 2, then press APPLY.",
}
DRAG_TEXT = "Now let go over the plot, where you want it."
DONE_TEXT = "Done already: Next goes on, or do it again."
# a doublet dialog showing the alignment warning (validation.doublet_misalignment): the first time …
ALIGN_TEXT = ("See the warning? The doublet must point the same way as the flow. Your uniform flow goes at "
              "{alpha}° (its angle α), so set Orientation δ to {want}° too, and the warning goes away.")
ALIGN_TEXT_REVERSED = ("See the warning? Your uniform flow goes at {alpha}° (its angle α). With a negative strength "
                       "the doublet points the other way round: set Orientation δ to {want}°, and the warning goes away.")
ALIGN_TEXT_OTHER = ("See the warning? The other elements turn the flow at the doublet to {alpha}°. Set Orientation δ "
                    "to {want}°, and the warning goes away.")
# … and again later (short: any angle is fine)
ALIGN_AGAIN_TEXT = "That warning again: pick any angle you like and go on. With δ = {want}° it goes away."
GONE_TEXT = "That's it: the warning is gone."
HINT_EVERY_S = 0.25                  # how often an open doublet dialog is checked for the warning


def _deg(x: float) -> str:
    """An angle as a person writes it: 0, 30, 12.5 (round-off like 1.03e-07 is 0)."""
    v = round(float(x), 1)
    if abs(v) < 0.05:
        v = 0.0
    return f"{v:g}".replace("-", "−")


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
        self.done = set()                # steps whose action the user did
        self.marks = {}                  # step -> (model's last undo id, slider value) when it began (back())
        self.released = None             # a slider step: the value changed, waiting for the slider to be let go
        self.hint = ""                   # the alignment hint shown beside a doublet dialog
        self.hint_t = 0.0
        self.warned = False              # the alignment warning was explained once …
        self.long_hint = True            # … so this dialog explains it (True) or only reminds (False)

    @property
    def step(self) -> Step | None:
        return STEPS[self.i] if 0 <= self.i < len(STEPS) else None

    # ------------------------------------------------------------------ control
    def start(self):
        self.active = True
        self.i = -1
        self._restore = {}
        self.done = set()
        self.marks = {}
        self.warned = False
        self.done_wait = None
        self.beaver.bubble.clear()                       # a remark still typing must not hold up step 1
        fw = self.win.focusWidget()
        if fw is not None:
            fw.clearFocus()                              # (a text field must not keep Enter / Space)
        self.win.setFocus()
        self.next()

    def next(self):
        """Enter / Space / Right / the Next button: finish the typing, or go on (an action step: skip it)."""
        b = self.beaver.bubble
        if b.typing and self.done_wait is None:
            b.finish_typing()
            return
        self.i += 1
        self._reset_step()
        if self.i >= len(STEPS):
            self.end(completed=True)
            return
        s = self.step
        if s.enter == "clear":
            self.win.canvas.set_view_mode("static")
            self.win.canvas.set_mode("select")
            self.win.model.mark_clean()                  # (the beaver asked before the tour: beaver.start_tour)
            self.win.new_scene()
        if s.wait == ("mouse_mode", "move") and self.win.canvas.mode == "move" and self.i not in self.done:
            self.next()                                  # already in Move mode: straight to the drag
            return
        if not self._prepare(s):                         # (e.g. its panel section is hidden): skip it
            b.finish_typing()
            self.next()
            return
        slider_value = None
        if s.target and s.target.startswith("slider:"):
            key = s.target.split(":")[1]
            sl = self.win.settings_panel.sliders.get(key)
            if sl is not None:
                slider_value = sl.value()
                self._restore.setdefault(key, sl.value())
        self.marks[self.i] = (self._model_mark(), slider_value)     # how things were when this step began
        self.show()

    def _model_mark(self):
        undo = self.win.model._undo
        return undo[-1].id if undo else None

    def back(self):
        """Left arrow / the Back button: the step before (never its "enter" again: no second clearing). What
        was done in that step and after it is taken back (the element added, the edit, the move, Move mode,
        the slider, Particles), so the step asks for it again (his report of 30 Oct: the uniform stayed and
        he had to add a second one)."""
        if self.i <= 0 or self.sub is not None or self.done_wait is not None:
            return
        j = self.i - 1
        while j > 0 and not self._prepare(STEPS[j]):     # (a hidden section: that step is skipped back too)
            j -= 1
        self.i = j
        self._reset_step()
        self._take_back(j)
        self._prepare(self.step)
        self.show()

    def _take_back(self, j: int):
        """Undo what happened since step j began (it is shown fresh again)."""
        win, s = self.win, STEPS[j]
        mark, slider_value = self.marks.get(j, (self._model_mark(), None))
        model = win.model
        for _ in range(100):                             # (the tour's own few steps; never the user's earlier work)
            if self._model_mark() == mark or not model.can_undo:
                break
            model.undo()
        if s.wait is not None:
            ev, val = s.wait
            if ev == "mouse_mode" and win.canvas.mode == val:
                win.canvas.set_mode("select")
            elif ev == "view_mode" and win.canvas.view_mode == val:
                win.canvas.set_view_mode("static")
            elif ev == "setting" and slider_value is not None:
                sl = win.settings_panel.sliders.get(val)
                if sl is not None:
                    sl.setValue(slider_value)
        self.done = {k for k in self.done if k < j}

    def _reset_step(self):
        self.done_wait = None
        self.sub, self.dialog, self.note = None, None, None
        self.released = None
        self.hint = ""

    def is_done(self, i: int | None = None) -> bool:
        """Was the action of step i (default: this one) done already? (Coming back to it.)"""
        i = self.i if i is None else i
        if not 0 <= i < len(STEPS) or STEPS[i].wait is None:
            return False
        ev, val = STEPS[i].wait
        if ev == "mouse_mode" and self.win.canvas.mode == val:
            return True
        if ev == "view_mode" and self.win.canvas.view_mode == val:
            return True
        return i in self.done

    def _prepare(self, s) -> bool:
        """Make the step's part visible: its panel open, a slider scrolled into view in the Plot settings
        (the panel may have been scrolled or closed since, and the lock stops the user from scrolling it).
        False: it cannot be shown (a hidden section), the step is skipped."""
        win, t = self.win, s.target or ""
        if t == "elements" and not win.dock_elements.isVisible():
            win.dock_elements.show()
        if t == "settings" or t.startswith("slider:"):
            if not win.dock_settings.isVisible():
                win.dock_settings.show()
            area = _scroll_area_of(win.settings_panel.sliders.get("density") or win.settings_panel)
            if t == "settings" and area is not None:
                area.verticalScrollBar().setValue(0)
            if t.startswith("slider:"):
                sl = win.settings_panel.sliders.get(t.split(":")[1])
                if sl is None or not sl.isVisibleTo(win.dock_settings):
                    return False
                if area is not None:
                    area.ensureWidgetVisible(sl, 40, 60)       # (scrolls at once; the highlight follows)
        return True

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
        """The bubble's buttons (by their text): End tour, Back, Next / Skip."""
        btns = self.beaver.bubble.buttons
        label = btns[k] if 0 <= k < len(btns) else ""
        if label == END_BUTTON:
            self.end(completed=False)
        elif label == BACK_BUTTON:
            self.back()
        elif label in (NEXT_BUTTON, SKIP_BUTTON) and self.sub is None and self.done_wait is None:
            self.next()

    def show(self):
        s = self.step
        rect = self.target_rect()
        self.spot.show_on(rect)
        self.spot.raise_()
        self.beaver.tour_goto(self._feet_now(rect))
        bub, name = self.beaver.bubble, self.beaver.name.upper()
        back = [BACK_BUTTON] if self.i > 0 else []
        if self.sub == "dialog":
            bub.say(self._dialog_text(), sticky=True, title=name, tag=self.tag())
        elif self.sub == "drag":
            bub.say(DRAG_TEXT, sticky=True, title=name, tag=self.tag())
        elif s.wait and self.is_done():
            bub.say(self.note or f"{s.text} {DONE_TEXT}", sticky=True, title=name, tag=self.tag(),
                    buttons=[END_BUTTON, *back, NEXT_BUTTON], primary=1 + len(back))
        elif s.wait:
            bub.say(self.note or s.text, sticky=True, title=name, tag=self.tag(),
                    buttons=[END_BUTTON, *back, SKIP_BUTTON])
        else:
            text = s.text
            if s.target == "gpu" and not self.win.header.plank.gpu.isEnabled():
                text += GPU_OFF_TEXT
            bub.say(self.note or text, sticky=True, title=name, tag=self.tag(),
                    buttons=[END_BUTTON, *back, NEXT_BUTTON], primary=1 + len(back))
        self.beaver._place_bubble()

    def _dialog_text(self) -> str:
        base = DIALOG_TEXT.get(self.dialog_kind, DIALOG_TEXT["add"])
        return f"{base}\n{self.hint}" if self.hint else base

    def _alignment_hint(self) -> str:
        """The open dialog is a doublet's and shows the "axis not along the flow" warning: what fixes it
        (the first time with the uniform flow's angle; later short). "" when there is no such warning."""
        dlg = self.dialog
        if dlg is None or getattr(getattr(dlg, "spec", None), "key", "") != "doublet":
            return ""
        try:
            from model.preview import candidate_scene
            from physics.elements import Doublet
            from physics.validation import doublet_misalignment
            vals, row, els = dlg.values(), getattr(dlg, "row", None), self.win.elements
            new = Doublet(**vals) if row is None else els[row].copy(**vals)
            cand, idx = candidate_scene(els, new, row)
            found = doublet_misalignment(cand).get(idx)
        except Exception:                                # noqa: BLE001 - invalid numbers typed: no hint
            return ""
        if found is None:
            return ""
        angle, want, only_uniform = found
        if not self.long_hint:                           # explained in an earlier dialog already: short
            return ALIGN_AGAIN_TEXT.format(want=_deg(want))
        text = ALIGN_TEXT_OTHER if not only_uniform else \
            ALIGN_TEXT if abs((want - angle + 180.0) % 360.0 - 180.0) < 1e-9 else ALIGN_TEXT_REVERSED
        return text.format(alpha=_deg(angle), want=_deg(want))

    def _update_hint(self):
        """The doublet dialog's warning came or went (numbers typed). What he said stays (his wish, 30 Oct: the
        explanation must not vanish when the angle is fixed); the warning gone: a short "that's it" is added;
        back again: the line without it. Only new text is typed on."""
        hint = self._alignment_hint()
        if not hint and self.hint:                       # fixed: keep the explanation, add the good news
            base_hint = self.hint[:-len(GONE_TEXT) - 1] if self.hint.endswith(GONE_TEXT) else self.hint
            hint = f"{base_hint} {GONE_TEXT}"
        if hint == self.hint:
            return
        bub = self.beaver.bubble
        old_text, old_shown = self._dialog_text(), bub.shown
        self.hint = hint
        if hint and self.long_hint and not hint.endswith(GONE_TEXT):
            self.warned = True
        new_text = self._dialog_text()
        same = 0                                         # (typed on from where the texts differ)
        while same < min(len(old_text), len(new_text)) and old_text[same] == new_text[same]:
            same += 1
        bub.say(new_text, sticky=True, title=self.beaver.name.upper(), tag=self.tag())
        bub.shown = min(old_shown, float(same))
        self.beaver._place_bubble()

    def tag(self) -> str:
        """Header tag of the bubble: "TOUR 3/19", or "YOUR TURN · 4/19" in an action step (not done yet)."""
        s = self.step
        n = f"{self.i + 1}/{len(STEPS)}"
        turn = s is not None and s.wait and self.sub is None and not self.is_done()
        return f"your turn \u00b7 {n}" if turn else f"tour {n}"

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
            self.hint_t = 0.0
            self.long_hint = not self.warned             # the first dialog with the warning explains it
            self.hint = self._alignment_hint()
            if self.hint and self.long_hint:
                self.warned = True
            self.show()
            return
        if event == "dialog_closed":
            accepted, changed = value
            if self.sub == "dialog":
                self.sub, self.dialog, self.hint = None, None, ""
                if accepted and not changed and s.wait and s.wait[0] == "edited":
                    self._completed()                    # Apply without a change: he got the idea, go on
                    return
                self.show()
            return
        if s.wait is None:
            return
        if s.wait[0] == event and (s.wait[1] is None or s.wait[1] == value):
            if event == "setting":
                sl = self.win.settings_panel.sliders.get(value)
                if sl is not None and sl.isSliderDown():
                    self.released = value                # dragged: goes on when the slider is let go
                    return
            self._completed()

    def _completed(self):
        """The step's action is done: "Nice!", then the next step (advance)."""
        self.done.add(self.i)
        self.done_wait = 1.0
        self.released = None
        self.sub, self.dialog, self.hint = None, None, ""
        self.beaver.bubble.say(self.beaver.lines.pick("tour_nice"), sticky=True,
                               title=self.beaver.name.upper(), tag=f"tour {self.i + 1}/{len(STEPS)}")
        self.beaver._place_bubble()

    def may_add(self, key: str) -> bool:
        """May an Add dialog of `key` open now (palette click / drop)? Only in its own palette step."""
        s = self.step
        return s is not None and s.allow == f"palette:{key}" and self.done_wait is None and \
            self.sub in (None, "drag", "drag_end")

    def may_edit(self, kind: str) -> bool:
        s = self.step
        return s is not None and s.allow == f"elements:{kind}" and self.done_wait is None and self.sub is None

    def advance(self, dt):
        self.spot.advance(dt)
        if self.done_wait is not None:
            self.done_wait -= dt
            if self.done_wait <= 0:
                self.done_wait = None
                self.beaver.bubble.clear()
                self.next()
            return
        if self.released is not None:
            sl = self.win.settings_panel.sliders.get(self.released)
            if sl is None or not sl.isSliderDown():
                self._completed()
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
                self.hint_t += dt
                if self.hint_t >= HINT_EVERY_S:         # the doublet warning came / went (numbers typed)
                    self.hint_t = 0.0
                    self._update_hint()
                self.beaver.tour_goto(self._feet_now(rect))
                self.beaver._place_bubble()

    def end(self, completed: bool):
        self.active = False
        self.spot.hide()
        self.i = -1
        self._reset_step()
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
        if target == "gpu":
            return self._map(win.header.plank.gpu)
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
