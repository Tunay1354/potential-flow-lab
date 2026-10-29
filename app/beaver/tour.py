"""
tour.py — the beaver's guided tour (first start, or Help → Beaver → Show me around): a game-like tutorial
that shows each part of the window and lets the user DO the main things — add a uniform flow and a
doublet, edit an element, move one, start the animation — then leaves an empty plot.

Every step has a text, the part of the window it is about (highlighted, the beaver goes next to it) and
either nothing to wait for (Enter / Space / a click on the bubble or the beaver: next) or an action the user
has to do (the window tells the tour: added / edit / moved / view_mode). Enter skips an action step, Esc ends
the tour.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPoint, QPointF, QRectF


@dataclass
class Step:
    text: str
    target: str | None = None        # what to highlight (Tour._rect)
    wait: tuple | None = None        # (event, value) the user has to do; None: just read
    where: str = "auto"              # where the beaver stands: right / left / below / inside / perch
    enter: str | None = None         # something the tour does first ("clear")


NEXT_HINT = "Enter, Space or click: next   Esc: end the tour"
DO_HINT = "Your turn!   Enter: skip this step   Esc: end the tour"

STEPS = [
    Step("Welcome to Potential Flow Lab! I'll show you around in two minutes. "
         "Let's start with an empty sheet.", None, enter="clear", where="inside"),
    Step("This is the plot. Everything you build shows up here: streamlines, stagnation points, colours "
         "and animations.", "plot", where="inside"),
    Step("This is the ADD palette: the building blocks of potential flow. Uniform flow, source, vortex, "
         "doublet, sector flow and walls.", "palette", where="right"),
    Step("Let's build something! Drag a UNIFORM flow from here onto the plot (a click works too), "
         "then press OK.", "palette:uniform", ("added", "uniform"), where="right"),
    Step("Streamlines! Each line follows the flow. A uniform flow is just parallel lines, so let's make it "
         "more interesting.", "plot", where="inside"),
    Step("Now drag a DOUBLET to the middle of the plot and press OK. Uniform flow + doublet = the flow round "
         "a cylinder.", "palette:doublet", ("added", "doublet"), where="right"),
    Step("That's a cylinder! The crossed circles are stagnation points: the flow stops there, V = 0 and "
         "Cp = 1.", "plot", where="inside"),
    Step("Your elements are listed here. Double-click the doublet to edit it. Try a bigger mu!",
         "elements", ("edit", None), where="left"),
    Step("Now press MOVE (or M) and drag the doublet's symbol on the plot.", "move", ("moved", None),
         where="below"),
    Step("Plot settings: line density, arrows, colour maps of Cp and speed, phi lines, solid bodies, surface "
         "pressure with lift and drag. Have a look later!", "settings", where="left"),
    Step("Time for some motion: click PARTICLES.", "particles", ("view_mode", "particles"), where="below"),
    Step("Particles ride the flow, colour = speed. PULSES shows pulses running along the streamlines, STATIC "
         "brings back the arrows. Space pauses.", "plot", where="inside"),
    Step("EXPORT saves a figure (PNG, SVG, PDF), an animation (GIF, MP4) or the numbers (CSV) for your "
         "report.", "export", where="below"),
    Step("File: save and open your scenes. Presets: ready-made scenes, with the assignment's verification "
         "cases.", "menu:File", where="below"),
    Step("Help: Run verification checks the program against the theory, and this tour lives there too.",
         "menu:Help", where="below"),
    Step("And me! Drag me onto the plot for fun, click me for help, and press P any time for questions and "
         "answers. You'll find me on my shelf. Have fun!", "perch", where="perch"),
]


class Tour:
    def __init__(self, beaver, window, spotlight):
        self.beaver, self.win, self.spot = beaver, window, spotlight
        self.i = -1
        self.done_wait = None            # seconds until "next" after the user did the action
        self.active = False

    @property
    def step(self) -> Step | None:
        return STEPS[self.i] if 0 <= self.i < len(STEPS) else None

    # ------------------------------------------------------------------ control
    def start(self):
        self.active = True
        self.i = -1
        self.next()

    def next(self):
        """Enter / click: finish the typing, or go on (an action step: skip it)."""
        b = self.beaver.bubble
        if b.typing:
            b.finish_typing()
            return
        self.i += 1
        self.done_wait = None
        if self.i >= len(STEPS):
            self.end(completed=True)
            return
        s = self.step
        if s.enter == "clear":
            self.win.canvas.set_view_mode("static")
            self.win.new_scene()
        self.show()

    def show(self):
        s = self.step
        rect = self._rect(s.target)
        self.spot.show_on(rect)
        self.spot.raise_()
        self.beaver.tour_goto(self._feet(rect, s.where))
        hint = DO_HINT if s.wait else NEXT_HINT
        self.beaver.bubble.say(s.text, hint=f"{self.i + 1}/{len(STEPS)}   {hint}", sticky=True)
        self.beaver._place_bubble()

    def notify(self, event: str, value=None):
        """The user did something (the window tells): the action of this step?"""
        s = self.step
        if not self.active or s is None or s.wait is None or self.done_wait is not None:
            return
        if s.wait[0] == event and (s.wait[1] is None or s.wait[1] == value):
            self.done_wait = 1.0
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
        elif self.step is not None:                       # keep the highlight on its widget (resizes, docks)
            self.spot.show_on(self._rect(self.step.target))

    def end(self, completed: bool):
        self.active = False
        self.spot.hide()
        self.i = -1
        self.beaver.tour_ended(completed)
        if completed:                                    # an empty plot, as at the start
            self.win.canvas.set_view_mode("static")
            self.win.model.mark_clean()
            self.win.new_scene()

    # ------------------------------------------------------------------ geometry
    def _map(self, w) -> QRectF:
        p = w.mapTo(self.win, QPoint(0, 0))
        return QRectF(p.x(), p.y(), w.width(), w.height())

    def _rect(self, target):
        win = self.win
        if target is None:
            return None
        if target == "plot":
            return self.beaver.plot_rect()
        if target == "palette":
            return self._map(win.element_toolbar)
        if target.startswith("palette:"):
            key = target.split(":")[1]
            for b in win.element_toolbar.findChildren(type(win.canvas.bar.btn_move)):
                if b.property("element_key") == key:
                    return self._map(b)
            return self._map(win.element_toolbar)
        if target == "elements":
            return self._map(win.dock_elements)
        if target == "settings":
            return self._map(win.dock_settings) if hasattr(win, "dock_settings") else self._map(win.settings_panel)
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
            return QPointF(rect.left() - 50, min(rect.top() + 140, H - 40))
        return QPointF(min(max(rect.center().x(), 60), W - 60), min(rect.bottom() + 20 + 30 * S, H - 40))
