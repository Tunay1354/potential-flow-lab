"""
beaver.py — Psi, the pixel-art beaver (placeholder name). He lives on the ruler next to Help and can be
dragged onto the plot; what happens then depends on the view mode:

  Static     there is glass in front of the plot: he sticks to it, taps on it, jokes, and goes home.
             He is fixed to the SCREEN (the glass): zoom / pan move the plot behind him.
  Particles  he is a tracer: carried by the flow from where he was dropped (the same time scale as the
             particles, paused with them), until he leaves the view; then he walks back along the ruler
             from the right. Physics on the way: a free vortex alone has closed streamlines (he goes round,
             gets dizzy, jumps out), a sink swallows him (spinning and shrinking), a stagnation point stops
             him, he cannot be dropped into a solid body or behind a wall.
  Pulses     he stands on the nearest streamline; every pulse that arrives knocks him over and pushes him
             along the line; at its end (edge of the view, a stagnation point) he bonks, complains, goes home.

In Particles / Pulses he is fixed to the DATA (a point of the flow): zoom / pan move him with the plot; if
the view leaves him outside, he complains and walks home. Switching the mode while he is on the plot
changes what he does (onto the glass, into the flow …). He never appears in exported figures or
animations (he is a widget over the window, not part of the plot), takes no clicks outside his own pixels,
and passes the mouse wheel on to the plot. View → Beaver switches him off.

State machine (state, time in state t): perch → held → glass / flow / pulse → hop → walk → perch;
flow → vanish / gone → walk. `advance(dt)` is one step (the timer, or tests).
"""
from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QPainter, QRegion, QWheelEvent
from PySide6.QtWidgets import QApplication, QWidget

from physics.field import active, complex_velocity, fluid_mask
from physics.images import resolve
from physics.particles import time_scale, typical_speed

from . import art
from .bubble import SpeechBubble
from .faq import FAQ
from .lines import PRIORITY, Picker
from .spotlight import Spotlight
from .tour import Tour

ACTIVE_MS, IDLE_MS = 33, 120          # timer: while something happens / sitting on the ruler
WALK_PX_S = 270.0                     # walking speed on the ruler
HOP_S = 0.6
SLEEP_AFTER_S = 180.0
HEAD_TOP = 15.0                       # art px from the canvas centre up to the top of the head (front / perch)
STAG_FRACTION = 0.03                  # slower than this × the typical speed = at a stagnation point
LAPS_DIZZY = 2.0
FLOW_BORED_S = 25.0                   # the longest ride before he has had enough
SLOW_CROSS_S = 18.0                   # crossing the view would take longer than this: "slow"
FAST_CROSS_S = 2.5                    # … shorter than this: "too fast"
PULSE_SLOW_S = 2.0                    # pulses further apart (in time) than this are "slow": he runs off …
PULSE_DODGE_S = 0.6                   # … when the next one is still at least this far away
RUN_FRACTION_S = 0.22                 # running: this part of the view width per second
PAUSED_LEAVE_S = 8.0
DRAG_PX = 6                           # a press that moves further than this is a drag, otherwise a click
TOUR_MOUSE = (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick, QEvent.Wheel, QEvent.ContextMenu)   # (the lock)
MENU = ["Questions & answers  (P)", "Show me around (tour)", "Tell me a fun fact", "Nothing, thanks"]


class BeaverSprite(QWidget):
    """The beaver's picture: a small child widget of the main window, shaped like the sprite (clicks on its
    transparent pixels go to what is below)."""
    pressed = Signal(QPointF)           # global position
    released = Signal(QPointF)
    wheel = Signal(object)

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setCursor(Qt.OpenHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.image = None
        self._key = None

    def set_frame(self, image, key, center: QPointF):
        dpr = image.devicePixelRatio()
        w, h = image.width() / dpr, image.height() / dpr
        if key != self._key:
            self._key = key
            self.image = image
            self.setMask(_mask(image))
            self.update()
        self.setGeometry(int(round(center.x() - w / 2)), int(round(center.y() - h / 2)), int(round(w)), int(round(h)))

    def paintEvent(self, _e):
        if self.image is not None:
            p = QPainter(self)
            p.drawImage(0, 0, self.image)
            p.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.pressed.emit(e.globalPosition())
        e.accept()

    def mouseReleaseEvent(self, e):
        self.setCursor(Qt.OpenHandCursor)
        if e.button() == Qt.LeftButton:
            self.released.emit(e.globalPosition())
        e.accept()

    def mouseDoubleClickEvent(self, e):                # (a second click: the same as a click)
        if e.button() == Qt.LeftButton:
            self.pressed.emit(e.globalPosition())
        e.accept()

    def wheelEvent(self, e):
        self.wheel.emit(e)
        e.accept()


def _mask(image) -> QRegion:
    """The opaque pixels as a region in logical pixels (rows of runs)."""
    dpr = image.devicePixelRatio()
    w, h = image.width(), image.height()
    ptr = image.constBits()
    a = np.frombuffer(ptr, np.uint8, count=image.sizeInBytes()).reshape(h, image.bytesPerLine())[:, 3:w * 4:4] > 0
    region = QRegion()
    step = max(1, int(round(dpr * 2)))                        # one art pixel = whole device pixels
    for y in range(0, h, step):
        row = a[y]
        if not row.any():
            continue
        edges = np.flatnonzero(np.diff(np.concatenate([[0], row.astype(np.int8), [0]])))
        for x0, x1 in zip(edges[::2], edges[1::2]):
            region += QRect(int(x0 / dpr), int(y / dpr), max(1, int(math.ceil((x1 - x0) / dpr))),
                            max(1, int(math.ceil(step / dpr))))
    return region


class Beaver(QObject):
    def __init__(self, window, seed=None):
        super().__init__(window)
        self.win = window
        self.cv = window.canvas
        self.sprite = BeaverSprite(window)
        self.bubble = SpeechBubble(window)
        self.lines = Picker(seed)
        self.enabled = True
        self.state = "perch"
        self.t = 0.0                    # seconds in this state
        self.clock = 0.0
        self.center = QPointF()         # sprite centre, window coordinates (perch, held, hop, walk, glass)
        self.z = 0j                     # data point (flow, pulse)
        self.rel = QPointF()            # glass: centre relative to the plot's viewport
        self.kind, self.pose, self.rot, self.shrink, self.flip = "perch", {}, 0.0, 1.0, False
        self.last_input = 0.0
        self.asleep = False
        self.said = {}                  # key -> clock of the last time (cool-downs)
        self.data = {}                  # per-state values
        self.waiting = None             # (priority, key, fmt): a line that waits for the current one
        self._flows_key = None
        self._flows = None
        self._vtyp = (None, 0.0)
        self.timer = QTimer(self)
        self.timer.setInterval(IDLE_MS)
        self.timer.timeout.connect(self._tick)
        self._last_tick = None
        self.sprite.pressed.connect(self._pressed)
        self.sprite.released.connect(self._released)
        self.bubble.clicked.connect(self._bubble_clicked)
        self.bubble.button_clicked.connect(self._bubble_button)
        self.spotlight = Spotlight(window)
        self.tour = Tour(self, window, self.spotlight)
        self.dialog = None              # an open dialog bubble: "menu", "faq", "answer", "ask_tour"
        self._press = None              # global position of a press that is not (yet) a drag
        self.sprite.wheel.connect(self._forward_wheel)
        self.cv.view_mode_changed.connect(self.mode_changed)
        self.cv.mode_changed.connect(lambda m: self.notify("mouse_mode", m))
        QApplication.instance().installEventFilter(self)
        self.set_theme(window.theme)
        self.timer.start()

    # ------------------------------------------------------------------ public
    def set_enabled(self, on: bool):
        self.enabled = bool(on)
        if not self.enabled:
            if self.tour.active:
                self.tour.end(completed=False)
            self.dialog = None
            self.sprite.hide()
            self.bubble.clear()
            self.waiting = None
            self.timer.stop()
            self._go("perch")
        else:
            self._go("perch")
            self.timer.start()
            self.advance(0.0)
            self.sprite.show()
            self.sprite.raise_()

    def set_theme(self, theme):
        self.bubble.set_theme(theme)
        if hasattr(self, "spotlight"):
            self.spotlight.set_theme(theme)

    def say(self, key: str, cooldown: float = 0.0, **fmt) -> bool:
        """A line of `key` (lines.py) unless one was said less than `cooldown` seconds ago. A line is never
        cut off before it can be read: while he is still talking, an important line (PRIORITY 2) waits for
        its turn (only the newest one waits), anything else is skipped."""
        if not self.enabled:
            return False
        last = self.said.get(key)
        if cooldown and last is not None and self.clock - last < cooldown:
            return False
        prio = PRIORITY.get(key, 1)
        if self.tour.active or self.dialog:
            return False                                   # (a dialog / the tour has the bubble)
        if self.bubble.busy():
            if prio >= 2 and (self.waiting is None or self.waiting[0] <= prio):
                self.waiting = (prio, key, fmt)
                self.said[key] = self.clock
                return True
            return False
        self.said[key] = self.clock
        self._show(key, fmt)
        return True

    def _show(self, key, fmt):
        self.bubble.say(self.lines.pick(key, **fmt))
        self._place_bubble()

    def talking(self) -> bool:
        """Something is being said or waits to be said."""
        return self.bubble.busy() or self.waiting is not None

    # reactions to the program (called by the window)
    def on_error(self):
        if self.state in ("perch", "walk"):
            self.say("error", cooldown=30.0)

    def on_saved(self):
        if self.state == "perch":
            self.say("saved", cooldown=600.0)

    def on_verified(self, n_ok: int, n: int):
        self._wake()
        self.say("verify_ok" if n_ok == n else "verify_fail", n=n)

    def greet(self):
        self.say("hello")

    def start_session(self, first: bool):
        """The program has started: a first-time user is offered the tour; later, now and then, a hello."""
        if not self.enabled:
            return
        if first:
            self.ask_tour()
        elif self.lines.rng.random() < 0.35:
            self.say("welcome_back")

    def shutdown(self):
        self.timer.stop()
        QApplication.instance().removeEventFilter(self)

    # ------------------------------------------------------------------ time
    def _tick(self):
        if not self.enabled or not self.win.isVisible() or self.win.isMinimized():
            self._last_tick = None
            return
        now = self.clock_now()
        dt = 0.0 if self._last_tick is None else min(0.1, now - self._last_tick)
        self._last_tick = now
        self.advance(dt)

    @staticmethod
    def clock_now():
        import time
        return time.perf_counter()

    def advance(self, dt: float):
        """One step of dt seconds: state, picture, position, bubble."""
        if not self.enabled:
            return
        self.clock += dt
        self.t += dt
        getattr(self, "_s_" + self.state)(dt)
        if self.tour.active:
            self.tour.advance(dt)
        if self.dialog and not self.bubble.active:
            self.dialog = None
        busy = self.state != "perch" or self.bubble.active
        self.timer.setInterval(ACTIVE_MS if busy else IDLE_MS)
        self._draw()
        self.bubble.advance(dt)
        if self.waiting is not None and not self.bubble.busy():
            _p, key, fmt = self.waiting
            self.waiting = None
            self._show(key, fmt)
        self._place_bubble()

    def _go(self, state: str, **data):
        self.state, self.t, self.data = state, 0.0, data
        self.rot, self.shrink = 0.0, 1.0
        if state != "perch":
            self._wake()

    # ------------------------------------------------------------------ geometry
    def S(self) -> float:
        """One art pixel in logical pixels."""
        return art.art_scale(self.dpr()) / self.dpr()

    def dpr(self) -> float:
        return self.win.devicePixelRatioF() or 1.0

    def _origin(self) -> QPointF:
        return QPointF(self.cv.plot.viewport().mapTo(self.win, QPoint(0, 0)))

    def to_window(self, z: complex) -> QPointF:
        sp = self.cv.vb.mapViewToScene(QPointF(z.real, z.imag))
        return self.cv.plot.viewportTransform().map(sp) + self._origin()

    def to_data(self, p: QPointF) -> complex:
        inv, _ok = self.cv.plot.viewportTransform().inverted()
        v = self.cv.vb.mapSceneToView(inv.map(p - self._origin()))
        return complex(v.x(), v.y())

    def plot_rect(self) -> QRectF:
        r = self.cv.plot.viewportTransform().mapRect(self.cv.vb.sceneBoundingRect())
        return r.translated(self._origin())

    def ruler_top(self) -> float:
        return float(self.win.header.ruler.mapTo(self.win, QPoint(0, 0)).y())

    def ruler_bottom(self) -> float:
        r = self.win.header.ruler
        return float(r.mapTo(self.win, QPoint(0, r.height())).y())

    def perch_feet(self) -> QPointF:
        perch = self.win.header.ruler.beaver_perch
        p = perch.mapTo(self.win, QPoint(0, 0))
        return QPointF(p.x() + 30, self.ruler_top() + 13)

    def _feet_to_center(self, feet: QPointF, kind: str) -> QPointF:
        return feet - QPointF(0, art.FEET[kind] * self.S())

    def _in_view(self, z: complex, margin: float = 0.0) -> bool:
        (x0, x1), (y0, y1) = self.cv.view()
        m = margin * (x1 - x0)
        return x0 - m <= z.real <= x1 + m and y0 - m <= z.imag <= y1 + m

    # ------------------------------------------------------------------ the flow
    def _flow(self):
        els = active(self.cv.shown_elements())
        key = tuple(id(e) for e in els) + tuple(repr(e) for e in els)
        if key != self._flows_key:
            self._flows_key = key
            self._flows = resolve(els) if els else None
            self._vtyp = (None, 0.0)
        return els, self._flows

    def velocity(self, z: complex) -> complex:
        els, flows = self._flow()
        if flows is None or not len(flows):
            return 0j
        with np.errstate(all="ignore"):
            w = complex(complex_velocity(flows, np.array([z]))[0])
        return w.conjugate() if np.isfinite(w) else complex("nan")

    def typical_speed(self) -> float:
        els, flows = self._flow()
        (x0, x1), (y0, y1) = self.cv.view()
        key = (x0, x1, y0, y1, self._flows_key)
        if self._vtyp[0] != key:
            v = typical_speed(els, flows, (x0, x1, y0, y1)) if flows is not None and len(flows) else 0.0
            self._vtyp = (key, v)
        return self._vtyp[1]

    def anim_dt(self, dt: float) -> float:
        """Animation time for dt real seconds: the same time scale as the particles (their speed slider)."""
        if self.cv.paused:
            return 0.0
        from app.canvas.animation_layer import speed_factor
        (x0, x1), (y0, y1) = self.cv.view()
        return dt * time_scale((x0, x1, y0, y1), self.typical_speed(), speed_factor(self.cv.particles.speed_slider))

    def _blocked(self, z: complex) -> str | None:
        """'solid' / 'wall' if z is no place for him in the flow."""
        els, _ = self._flow()
        if els and not bool(fluid_mask(els, np.array([z]))[0]):
            return "wall"
        if bool(self.cv.bodies.contains(np.array([z]))[0]):
            return "solid"
        return None

    # ------------------------------------------------------------------ input
    def eventFilter(self, obj, event):
        t = event.type()
        if t == QEvent.Resize and obj is self.win and self.enabled:
            QTimer.singleShot(0, self, lambda: self.advance(0.0))        # stay on the ruler / plot
            return False
        if t == QEvent.ShortcutOverride and self._keys(obj, event, act=False):
            event.accept()                                  # Space / Esc are ours in the tour and dialogs
            return True
        if t == QEvent.KeyPress and self._keys(obj, event):
            return True
        if t in TOUR_MOUSE and self._tour_blocks(obj, event):
            return True                                     # the tour: only what the step asks for
        if t in (QEvent.MouseMove, QEvent.MouseButtonPress, QEvent.KeyPress, QEvent.Wheel):
            self.last_input = self.clock
            if t == QEvent.MouseMove:
                self._mouse = event.globalPosition()
                if self._press is not None and (event.globalPosition() - self._press).manhattanLength() > DRAG_PX:
                    self._press = None                      # moved: it is a drag
                    self._grab()
            if self.asleep:
                self._wake(say=True)
        elif t == QEvent.MouseButtonRelease and self.state == "held":
            self._mouse = event.globalPosition()
            QTimer.singleShot(0, self._release)
        return False

    def _tour_blocks(self, obj, event) -> bool:
        """The tour is on: a mouse press / double-click / wheel / right-click in the window reaches only
        what the step allows (Tour.allows); the beaver and his bubble always take it. Other windows (an
        element dialog) are not touched; hovering is never blocked."""
        if not (self.enabled and self.tour.active) or not isinstance(obj, QWidget) or obj.window() is not self.win:
            return False
        if QApplication.activeModalWidget() is not None:
            return False
        for own in (self.sprite, self.bubble):
            if obj is own or own.isAncestorOf(obj):
                return False
        return not self.tour.allows(obj, event)

    def _keys(self, obj, event, act: bool = True) -> bool:
        """Keys for the tour and the dialog bubbles (not while another window or a text field has them).
        act=False: only whether the key is ours.
        The tour takes Enter / Space (next, skip) and Esc (end) wherever the focus is in the window and
        swallows every other key, except the ones its step asks for (Tour.allows_key)."""
        if not self.enabled or not (self.tour.active or self.dialog):
            return False
        from PySide6.QtWidgets import QAbstractSpinBox, QLineEdit
        if QApplication.activeModalWidget() is not None:
            return False
        if not isinstance(obj, QWidget) or obj.window() is not self.win:
            return False
        k = event.key()
        if self.tour.active:
            if k in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
                if act and not event.isAutoRepeat():
                    self.tour.next()
                return True
            if k == Qt.Key_Escape:
                if act:
                    self.tour.end(completed=False)
                return True
            return not self.tour.allows_key(k)          # True: swallowed (no shortcut, no typing)
        if isinstance(QApplication.focusWidget(), (QLineEdit, QAbstractSpinBox)):
            return False
        b = self.bubble
        if not act:
            return k in (Qt.Key_Escape, Qt.Key_Return, Qt.Key_Enter, Qt.Key_Up, Qt.Key_Down) or \
                (bool(b.choices) and Qt.Key_0 <= k <= Qt.Key_9)
        if k == Qt.Key_Escape:
            self.close_dialog()
            return True
        if b.choices:
            if Qt.Key_0 <= k <= Qt.Key_9:
                i = (k - Qt.Key_0 - 1) % 10
                if i < len(b.choices):
                    b.finish_typing()
                    self._choose(i)
                return True
            if k in (Qt.Key_Up, Qt.Key_Down):
                b.finish_typing()
                b.move_selection(-1 if k == Qt.Key_Up else 1)
                return True
            if k in (Qt.Key_Return, Qt.Key_Enter):
                if b.typing:
                    b.finish_typing()
                else:
                    self._choose(b.sel)
                return True
        elif k in (Qt.Key_Return, Qt.Key_Enter):
            if b.typing:
                b.finish_typing()
            else:
                self.close_dialog()
            return True
        return False

    def _pressed(self, gpos: QPointF):
        if self.tour.active:
            self.tour.click()                               # clicking him: next (a reading step)
            return
        self._press = QPointF(gpos)
        self._mouse = QPointF(gpos)

    def _released(self, gpos: QPointF):
        if self._press is not None:                         # did not move: a click
            self._press = None
            self.on_click()

    def on_click(self):
        """A click on him: on his shelf the menu (questions, tour, a fun fact); elsewhere a remark."""
        if self.state in ("perch", "walk") or self.dialog:
            if self.dialog == "menu":
                self.close_dialog()
            else:
                self.open_menu()
        else:
            self.say("poked", cooldown=1.0)

    # ------------------------------------------------------------------ dialogs
    def _dialog(self, kind, text, choices=None, hint=""):
        if self.state not in ("perch", "walk", "tour"):
            self._go("perch")
        self.waiting = None
        self.dialog = kind
        self.bubble.say(text, choices=choices, hint=hint, sticky=True)
        self._place_bubble()

    def open_menu(self):
        self._dialog("menu", self.lines.pick("menu"), MENU, "1-4, arrows + Enter or click   Esc: close")

    def open_faq(self):
        if not self.enabled:
            return
        if self.dialog == "faq":
            self.close_dialog()
            return
        if self.tour.active:
            return
        self._dialog("faq", "Ask me something:", [q for q, _a in FAQ], "1-9, 0, arrows + Enter or click   Esc: close")

    def answer(self, i: int):
        q, a = FAQ[i]
        self._dialog("answer", a, hint="P or click: more questions   Esc: close")
        self.data["question"] = i

    def ask_tour(self):
        """First start: offer the tour."""
        self._dialog("ask_tour", self.lines.pick("ask_tour"), ["Yes, show me around", "No, thanks"],
                     "1-2, arrows + Enter or click")

    def close_dialog(self):
        if self.dialog:
            self.dialog = None
            self.bubble.clear()

    def _bubble_clicked(self, k: int):
        if self.tour.active:
            self.tour.click()
        elif self.dialog == "answer":
            self.open_faq()
        elif k >= 0:
            self._choose(k)

    def _bubble_button(self, k: int):
        if self.tour.active:
            self.tour.button(k)

    def _choose(self, k: int):
        kind = self.dialog
        if kind == "menu":
            self.close_dialog()
            [self.open_faq, self.start_tour, lambda: self.say("facts"), lambda: None][k]()
        elif kind == "faq":
            self.answer(k)
        elif kind == "ask_tour":
            self.close_dialog()
            if k == 0:
                self.start_tour()
            else:
                self.say("tour_declined")

    # ------------------------------------------------------------------ the tour
    def start_tour(self):
        if not self.enabled:
            return
        self.close_dialog()
        self.waiting = None
        self._press = None
        self._go("tour", feet=None)
        self.tour.start()

    def tour_goto(self, feet):
        """The tour moves him next to the part it explains (feet: window point; None: his shelf)."""
        self.data["feet"] = feet

    def tour_ended(self, completed: bool):
        self.bubble.clear()
        self._go("hop", start=QPointF(self.center)) if self.state == "tour" and self.data.get("feet") else \
            self._go("perch")
        if not completed:
            self.say("tour_skipped")

    def notify(self, event: str, value=None):
        """The window tells what the user did (the tour waits for some of it)."""
        if self.tour.active:
            self.tour.notify(event, value)

    def _s_tour(self, dt):
        feet = self.data.get("feet")
        if feet is None:                                   # on his shelf
            self.kind, self.flip, self.rot = "perch", False, 0.0
            target = self._feet_to_center(self.perch_feet(), "perch")
        else:
            self.kind, self.flip, self.rot = "front", False, 0.0
            target = self._feet_to_center(feet, "front")
        if self.center.isNull():
            self.center = target
        d = target - self.center
        k = min(1.0, dt * 7.0)
        self.center = self.center + d * k if d.manhattanLength() > 1 else target
        hop = d.manhattanLength() > 20
        blink = (self.clock % 4.3) < 0.14
        self.pose = {"mood": "closed" if blink else ("happy" if hop else "open"), "f": self._f()}
        if self.kind == "front":
            self.pose["arm"] = "up" if hop else "down"

    def _wake(self, say=False):
        if self.asleep:
            self.asleep = False
            if say and self.state == "perch":
                self.say("wake")

    def _grab(self):
        if self.state in ("vanish", "gone", "tour") or self.tour.active:
            return
        self.close_dialog()
        self._mouse = QPointF(QCursor.pos()) if getattr(self, "_mouse", None) is None else self._mouse
        self._go("held", angle=0.0, speed=0.0, prev=self._cursor())
        self.say("grabbed", cooldown=1.5)

    def _cursor(self) -> QPointF:
        """The mouse in window coordinates (the last move event; the system cursor before any)."""
        g = getattr(self, "_mouse", None)
        return QPointF(self.win.mapFromGlobal(g.toPoint() if g is not None else QCursor.pos()))

    def _release(self, pos: QPointF | None = None):
        """Let go at the cursor (or `pos`): onto the plot (what happens depends on the mode) or home."""
        if self.state != "held":
            return
        pos = self._cursor() if pos is None else pos
        center = self.center
        if self.plot_rect().contains(pos):
            self.drop(center)
        elif pos.y() < self.ruler_bottom() + 12:
            self._go("walk", x=center.x())
        else:
            self._go("hop", start=QPointF(center))

    def drop(self, center: QPointF):
        """He is let go over the plot at `center` (window coordinates)."""
        mode = self.cv.view_mode
        if mode == "static":
            self.rel = center - self._origin()
            self._go("glass", fresh=True)
        elif mode == "particles":
            self._start_flow(self.to_data(center))
        else:
            self._start_pulse(self.to_data(center + QPointF(0, art.FEET["side"] * self.S())))

    def _forward_wheel(self, e):
        """Zoom with the wheel works over him too (the plot gets the event)."""
        vp = self.cv.plot.viewport()
        pos = QPointF(vp.mapFromGlobal(e.globalPosition().toPoint()))
        if not vp.rect().contains(pos.toPoint()):
            return
        ev = QWheelEvent(pos, e.globalPosition(), e.pixelDelta(), e.angleDelta(), e.buttons(), e.modifiers(),
                         e.phase(), e.inverted())
        QApplication.sendEvent(vp, ev)

    def mode_changed(self, mode: str):
        """The view mode changed while he is on the plot: onto the glass, into the flow, onto a line."""
        self.notify("view_mode", mode)
        if self.state in ("flow", "pulse"):
            if mode == "static":
                self.rel = self.to_window(self.z) - self._origin()
                self._go("glass", fresh=False)
            elif mode == "particles" and self.state == "pulse":
                self._start_flow(self.z, quiet=True)
            elif mode == "pulses" and self.state == "flow":
                self._start_pulse(self.z)
        elif self.state == "glass" and mode in ("particles", "pulses"):
            z = self.to_data(self._origin() + self.rel)
            if mode == "particles":
                self._start_flow(z, quiet=True)
            else:
                self._start_pulse(z)
            self.say("splash")

    # ------------------------------------------------------------------ states
    def _s_perch(self, dt):
        self.kind, self.flip = "perch", False
        if not self.asleep and self.clock - self.last_input > SLEEP_AFTER_S:
            self.asleep = True
            self.data["zzz"] = -1e9
        if self.asleep and self.clock - self.data.get("zzz", -1e9) > 25.0 and not self.bubble.active:
            self.data["zzz"] = self.clock
            self.bubble.say(self.lines.pick("sleep"), typed=False)
        blink = (self.clock % 5.3) < 0.14
        self.pose = {"mood": "closed" if (self.asleep or blink) else "open", "f": self._f()}
        self.center = self._feet_to_center(self.perch_feet(), "perch")

    def _s_held(self, dt):
        cur = self._cursor()
        d = self.data
        vx = (cur.x() - d["prev"].x()) / dt if dt > 0 else 0.0
        d["prev"] = cur
        # a pendulum hanging from the cursor, pushed by the mouse's acceleration
        acc = -60.0 * d["angle"] - 7.0 * d["speed"] - 0.9 * (vx - d.get("vx", 0.0)) / max(dt, 1e-3)
        d["vx"] = vx
        d["speed"] += acc * dt
        d["angle"] = max(-40.0, min(40.0, d["angle"] + d["speed"] * dt))
        self.kind, self.flip, self.rot = "front", False, d["angle"]
        self.pose = {"mood": "worried", "arm": "up", "f": self._f()}
        self.center = cur + QPointF(0, 8 + HEAD_TOP * self.S())

    def _s_glass(self, dt):
        """Bonk on the glass, a joke, *tap tap* with the second line, a goodbye — each line readable before the
        next — then home."""
        t, d = self.t, self.data
        self.kind, self.flip, self.rot = "front", False, 0.0
        rect = self.plot_rect()
        drop = 10.0 * min(1.0, t / 0.25) if d.get("fresh") else 0.0
        c = self._origin() + self.rel + QPointF(0, drop)
        half = 12 * self.S()
        self.center = QPointF(min(max(c.x(), rect.left() + half), rect.right() - half),
                              min(max(c.y(), rect.top() + half), rect.bottom() - half))
        step = d.setdefault("step", 0)
        free = not self.talking()
        if step == 0 and t > 0.3:
            self.say("glass_drop" if d.get("fresh") else "glass_again")
            d["step"], d["at"] = 1, t
        elif step == 1 and free and t - d["at"] > 0.4:
            self.say("glass_tap")
            d["step"], d["at"] = 2, t
        elif step == 2 and free and t - d["at"] > 0.6:
            self.say("glass_back")
            d["step"], d["at"] = 3, t
        elif step == 3 and not self.bubble.typing and t - d["at"] > 1.2:
            self._go("hop", start=QPointF(self.center))
            return
        mood = "worried" if (d.get("fresh") and t < 0.3) else ("happy" if step == 3 else "open")
        if (self.clock % 4.1) < 0.14:
            mood = "closed"
        tap = step == 2 and int(t / 0.25) % 2 == 0
        self.pose = {"mood": mood, "tap": tap, "f": self._f()}

    def _start_flow(self, z: complex, quiet=False):
        self.z = z
        self._go("flow", laps=0.0, angle=None, slow=0.0, fast=False)
        els, _ = self._flow()
        if not els:
            self.say("no_flow")
            self._go("bored")
            return
        blocked = self._blocked(z)
        if blocked:
            self.say(blocked)
            self._go("hop", start=QPointF(self.to_window(z)))
            return
        cross = self.crossing_time(z)
        if self._near(z, "source", 0.06):
            self.say("source")
        elif cross > SLOW_CROSS_S and not self.cv.paused:
            self.say("flow_slow")
        elif cross < FAST_CROSS_S:
            self.say("flow_too_fast")
        elif not quiet:
            self.say("flow_start")

    def crossing_time(self, z: complex) -> float:
        """Real seconds he would need to cross the view at the speed he has at z (inf when nothing moves)."""
        (x0, x1), _ = self.cv.view()
        v = self.velocity(z)
        rate = self.anim_dt(1.0)
        if not np.isfinite(v) or not abs(v) * rate > 0:
            return float("inf")
        return (x1 - x0) / (abs(v) * rate)

    def _near(self, z, kind, frac):
        (x0, x1), _ = self.cv.view()
        L = x1 - x0
        els, _ = self._flow()
        for e in els:
            if kind == "source" and e.TYPE == "source" and e.m > 0 and abs(z - e.z0) < frac * L:
                return e
            if kind == "sink" and e.TYPE == "source" and e.m < 0 and abs(z - e.z0) < frac * L:
                return e
        return None

    def _s_flow(self, dt):
        d = self.data
        els, flows = self._flow()
        if not els:
            self.say("flow_gone")
            self._go("hop", start=QPointF(self.center))
            return
        (x0, x1), (y0, y1) = self.cv.view()
        L = x1 - x0
        T = self.anim_dt(dt)
        v_typ = self.typical_speed()
        z = self.z
        # too slow a ride, or paused too long: he walks home
        if self.cv.paused:
            d["paused"] = d.get("paused", 0.0) + dt
            if "said_paused" not in d and d["paused"] > 0.8:
                d["said_paused"] = True
                self.say("paused")
            if d["paused"] > PAUSED_LEAVE_S:
                self.say("paused_leave")
                self._go("hop", start=QPointF(self.center))
                return
        else:
            d["paused"] = 0.0
            slow = self.crossing_time(z) > SLOW_CROSS_S
            d["crawl"] = d.get("crawl", 0.0) + dt if slow else max(0.0, d.get("crawl", 0.0) - 0.5 * dt)
            if d["crawl"] > 7.0 or self.t > FLOW_BORED_S:
                self.say("flow_bored")
                self._go("hop", start=QPointF(self.center))
                return
        if T > 0:
            v0 = self.velocity(z)
            n = int(min(24, max(1, math.ceil(abs(v0) * T / (0.006 * L))))) if np.isfinite(v0) else 1
            h = T / n
            for _ in range(n):
                k1 = self.velocity(z)
                k2 = self.velocity(z + 0.5 * h * k1)
                k3 = self.velocity(z + 0.5 * h * k2)
                k4 = self.velocity(z + h * k3)
                step = h / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)
                if not np.isfinite(step):
                    break
                if abs(step) > 0.02 * L:                    # next to a singular point: no jumps
                    step *= 0.02 * L / abs(step)
                z = z + step
        moved = z - self.z
        self.z = z
        v = self.velocity(z)
        # what happens here
        sink = self._near(z, "sink", 0.035)
        if sink is not None:
            self.say("drain_gone")
            shrink, rot = self.shrink, self.rot
            self._go("vanish", at=QPointF(self.to_window(z)), shrink=shrink, rot=rot)
            return
        if not self._in_view(z, 0.02):
            if "exited" not in d:
                self.say("flow_exit", cooldown=8.0)
            self._go("gone")
            return
        vort = [e for e in els if e.TYPE == "vortex" and abs(z - e.z0) < 0.45 * L]
        if vort and T > 0:
            e = min(vort, key=lambda e: abs(z - e.z0))
            a = math.atan2((z - e.z0).imag, (z - e.z0).real)
            if d["angle"] is not None:
                da = (a - d["angle"] + math.pi) % (2 * math.pi) - math.pi
                d["laps"] += abs(da) / (2 * math.pi)
            d["angle"] = a
            if d["laps"] > LAPS_DIZZY and self._near(z, "sink", 0.6) is None:
                self.say("vortex_dizzy")
                self._go("hop", start=QPointF(self.to_window(z)), dizzy=True)
                return
        sink_near = self._near(z, "sink", 0.25)
        if sink_near is not None and "drain" not in d:
            d["drain"] = True
            self.say("drain")
        if T > 0 and v_typ > 0:
            speed = abs(v) if np.isfinite(v) else 0.0
            d["slow"] = d["slow"] + dt if speed < STAG_FRACTION * v_typ else 0.0
            if d["slow"] > 2.5:
                self.say("stagnation")
                self._go("hop", start=QPointF(self.to_window(z)))
                return
            if speed > 1.6 * v_typ and not d["fast"] and self.t > 1.0:
                d["fast"] = True
                self.say("flow_fast", cooldown=6.0)
        # picture: facing the way he goes, tilted at most 30°; shrinking into a drain
        u = moved if abs(moved) > 0 else (v if np.isfinite(v) else 1 + 0j)
        self._swim_pose(u, dizzy=d["laps"] > 1.2)
        if sink_near is not None:
            r = abs(z - sink_near.z0) / L
            self.shrink = max(0.3, min(1.0, r / 0.2))
            self.rot = (self.rot + self.clock * 900.0 * (1.0 - self.shrink)) % 360.0     # spinning down the drain
        self.center = self.to_window(z)

    def _swim_pose(self, u: complex, dizzy=False):
        ang = math.degrees(math.atan2(u.imag, u.real))
        flip = u.real < 0
        if flip:
            ang = 180 - ang if ang > 0 else -180 - ang
        self.kind, self.flip = "swim", flip
        tilt = max(-30.0, min(30.0, ang))
        self.rot = tilt if not flip else -tilt
        self.shrink = 1.0
        self.pose = {"mood": "dizzy" if dizzy else "happy", "phase": int(self.clock / 0.22) % 2, "f": self._f()}

    def _s_bored(self, dt):
        self.kind, self.flip, self.rot = "front", False, 0.0
        self.pose = {"mood": "open", "f": self._f()}
        if self.t > 2.2:
            self._go("hop", start=QPointF(self.center))

    # pulses
    def _start_pulse(self, z: complex):
        line = self._nearest_line(z)
        if line is None:
            self.z = z
            self.center = self.to_window(z)
            self.say("no_pulses")
            self._go("bored")
            return
        pts, i = line
        self.z = pts[i]
        self._go("pulse", pts=pts, s=self._arc(pts)[i], push=0.0, knocked=0.0, phase=None, hits=0)
        blocked = self._blocked(self.z)
        if blocked:
            self.say(blocked)
            self._go("hop", start=QPointF(self.to_window(self.z)))
            return
        self.say("pulse_wait", cooldown=20.0)

    def _nearest_line(self, z: complex):
        res = self.cv.last_result
        if res is None or not res.lines:
            return None
        best = None
        for ln in res.lines:
            if len(ln) < 2:
                continue
            pts = ln[:, 0] + 1j * ln[:, 1]
            k = int(np.argmin(np.abs(pts - z)))
            dist = abs(pts[k] - z)
            if best is None or dist < best[0]:
                best = (dist, pts, k)
        (x0, x1), _ = self.cv.view()
        if best is None or best[0] > 0.12 * (x1 - x0):
            return None
        return best[1], best[2]

    @staticmethod
    def _arc(pts):
        return np.concatenate([[0.0], np.cumsum(np.abs(np.diff(pts)))])

    def _pulse_phase(self, z: complex):
        """frac(t/T − τ/T) of the pulses at z (the pulse layer's own numbers), or None."""
        pl = self.cv.pulses
        pieces = getattr(pl, "_pieces", None)
        if pieces is None or not pl.period > 0:
            return None
        a, b, tau, _speed = pieces
        if not len(a):
            return None
        k = int(np.argmin(np.abs(0.5 * (a + b) - z)))
        (x0, x1), _ = self.cv.view()
        if abs(0.5 * (a[k] + b[k]) - z) > 0.05 * (x1 - x0):
            return None
        return (pl.t / pl.period - tau[k] / pl.period) % 1.0

    def _s_pulse(self, dt):
        d = self.data
        pts, arc = d["pts"], self._arc(d["pts"])
        (x0, x1), _ = self.cv.view()
        L = x1 - x0
        ph = self._pulse_phase(self.z) if self.cv.view_mode == "pulses" else None
        hit = ph is not None and d["phase"] is not None and ph < d["phase"] - 0.5 and not self.cv.paused
        if hit and d["knocked"] <= 0 and "bonk" not in d:
            d["push"] += 0.08 * L                      # a pulse arrived: knocked over, pushed along
            d["knocked"] = 1.1
            d["hits"] += 1
            self.say("pulse_hit", cooldown=2.5)
        d["phase"] = ph
        if d["push"] > 0:
            ds = min(d["push"], max(0.02 * L, 3.0 * d["push"]) * dt * 3.0)
            d["push"] -= ds
            d["s"] += ds
        d["knocked"] = max(0.0, d["knocked"] - dt)
        d["s"] = s = min(d["s"], arc[-1])
        self.z = complex(np.interp(s, arc, pts.real), np.interp(s, arc, pts.imag))
        end = d["s"] >= arc[-1] - 1e-9 or not self._in_view(self.z, -0.03)
        if end and "bonk" not in d:
            d["bonk"] = self.t
            d["push"] = 0.0
            self.say("pulse_bonk")
        if not self._in_view(self.z, 0.05) and "bonk" not in d:
            self.say("zoomed_out", cooldown=5.0)
            self._go("gone")
            return
        wait = self.next_pulse_in(ph)
        if self.cv.paused:
            d["paused"] = d.get("paused", 0.0) + dt
            if d["paused"] > PAUSED_LEAVE_S and "bonk" not in d:
                self.say("paused_leave")
                self._go("hop", start=QPointF(self.center))
                return
        elif (self.pulse_period() > PULSE_SLOW_S and wait > PULSE_DODGE_S and d["knocked"] == 0 and "bonk" not in d
              and self.t > 1.2 and d["push"] <= 0):
            self.say("pulse_slow")                         # the next pulse is far: off he runs, away from it
            self._go("run", pts=pts, s=s)
            return
        k = int(np.searchsorted(arc, s))
        k = min(max(k, 1), len(pts) - 1)
        tangent = pts[k] - pts[k - 1]
        self.kind, self.flip = "side", tangent.real < 0
        if d["knocked"] > 0:
            prog = min(1.0, (1.1 - d["knocked"]) / 0.25, d["knocked"] / 0.2)       # falls, lies, gets up
            self.rot = (-1 if not self.flip else 1) * 100 * prog
            self.pose = {"mood": "dizzy", "f": self._f()}
        else:
            self.rot = 0.0
            self.pose = {"mood": "closed" if (self.clock % 4.7) < 0.14 else "open", "f": self._f()}
        feet = self.to_window(self.z)
        self.center = self._feet_to_center(feet, "side") if not d["knocked"] else feet - QPointF(0, 6 * self.S())
        if "bonk" in d and self.t - d["bonk"] > 2.2 and not self.bubble.typing:
            self._go("hop", start=QPointF(self.center))
        elif self.t > 16.0 and "bonk" not in d and d["knocked"] == 0:
            self.say("pulse_leave")
            self._go("hop", start=QPointF(self.center))

    def pulse_period(self) -> float:
        """Real seconds between two pulses (inf: none)."""
        pl = self.cv.pulses
        if not pl.period > 0 or self.cv.paused:
            return float("inf")
        from app.canvas.animation_layer import speed_factor
        (x0, x1), (y0, y1) = self.cv.view()
        rate = time_scale((x0, x1, y0, y1), pl.v_typ, speed_factor(pl.speed_slider))
        return pl.period / rate if rate > 0 else float("inf")

    def next_pulse_in(self, ph) -> float:
        """Real seconds until the next pulse reaches him (inf: no pulses / paused)."""
        return float("inf") if ph is None else (1.0 - ph) * self.pulse_period()

    def _s_run(self, dt):
        """Running along his line, away from the slow pulses, until the end of the line / the view."""
        d = self.data
        pts, arc = d["pts"], self._arc(d["pts"])
        (x0, x1), _ = self.cv.view()
        d["s"] = s = min(arc[-1], d["s"] + RUN_FRACTION_S * (x1 - x0) * dt)
        self.z = complex(np.interp(s, arc, pts.real), np.interp(s, arc, pts.imag))
        if self.t > 0.7 and "said" not in d:
            d["said"] = True
            self.say("pulse_run")
        if s >= arc[-1] or not self._in_view(self.z, 0.0):
            self._go("gone")
            return
        k = min(max(int(np.searchsorted(arc, s)), 1), len(pts) - 1)
        self.kind, self.flip, self.rot = "side", (pts[k] - pts[k - 1]).real < 0, 0.0
        self.pose = {"mood": "happy", "step": (-1, 0, 1, 0)[int(self.clock / 0.07) % 4], "f": self._f()}
        self.center = self._feet_to_center(self.to_window(self.z), "side")

    # going home
    def _s_hop(self, dt):
        d = self.data
        start = d["start"]
        perch = self.perch_feet()
        x_end = min(max(start.x(), perch.x()), self.win.width() - 40)
        end = self._feet_to_center(QPointF(x_end, self.ruler_top() + 1), "side")
        s = min(1.0, self.t / HOP_S)
        x = start.x() + (end.x() - start.x()) * s
        y = start.y() + (end.y() - start.y()) * s - 90 * math.sin(math.pi * s)
        self.center = QPointF(x, y)
        self.kind, self.flip = "side", end.x() < start.x()
        self.rot = (-25 + 50 * s) * (1 if not self.flip else -1)
        self.pose = {"mood": "dizzy" if d.get("dizzy") else "happy", "f": self._f()}
        if s >= 1.0:
            self._go("walk", x=x_end)

    def _s_walk(self, dt):
        d = self.data
        target = self.perch_feet().x()
        x = d["x"]
        step = WALK_PX_S * dt
        x = target if abs(target - x) <= step else x + math.copysign(step, target - x)
        d["x"] = x
        self.kind, self.flip, self.rot = "side", target < x or (target == x and d.get("left", True)), 0.0
        if target != x:
            d["left"] = target < x
        self.pose = {"mood": "open", "step": (-1, 0, 1, 0)[int(self.clock / 0.11) % 4], "f": self._f()}
        self.center = self._feet_to_center(QPointF(x, self.ruler_top() + 1), "side")
        if x == target:
            self._go("perch")

    def _s_vanish(self, dt):
        s = min(1.0, self.t / 0.9)
        self.kind, self.flip = "swim", False
        self.rot = self.data.get("rot", 0.0) + 720 * s
        self.shrink = max(0.05, self.data.get("shrink", 1.0) * (1 - s))
        self.pose = {"mood": "dizzy", "phase": 0, "f": self._f()}
        self.center = self.data["at"]
        if s >= 1.0:
            self._go("gone")

    def _s_gone(self, dt):
        if self.t > 1.0:
            self._go("walk", x=float(self.win.width() + 30))

    # ------------------------------------------------------------------ drawing
    def _f(self) -> int:
        return int(self.clock / 0.22) % 3

    def _draw(self):
        if self.state == "gone":
            self.sprite.hide()
            return
        scale = art.art_scale(self.dpr())
        img = art.frame(self.kind, scale, self.rot, self.shrink, self.flip, **self.pose)
        img.setDevicePixelRatio(self.dpr())
        key = (self.kind, scale, round(self.rot / 5), round(self.shrink * 20), self.flip, tuple(sorted(self.pose.items())))
        self.sprite.set_frame(img, key, self.center)
        if not self.sprite.isVisible():
            self.sprite.show()
        self.sprite.raise_()

    def _place_bubble(self):
        if not self.bubble.active or self.state == "gone":
            return                                       # (gone: the last words stay where he left)
        S = self.S()
        bounds = QRectF(self.win.rect())
        if self.state == "perch" or (self.state == "tour" and self.data.get("feet") is None):
            anchor, tail = self.center + QPointF(13 * S, -3 * S), "left"
        elif self.state == "tour":
            # beside him, but never over what the tour shows (the highlighted part)
            sides = [(QPointF(12 * S, -6 * S), "left"), (QPointF(-12 * S, -6 * S), "right"),
                     (QPointF(2 * S, 16 * S), "up"), (QPointF(2 * S, -HEAD_TOP * S), "down")]
            if self.center.x() + 12 * S + 360 > self.win.width():
                sides[0], sides[1] = sides[1], sides[0]
            avoid = self.tour.avoid_rect()
            anchor, tail = self.center + sides[0][0], sides[0][1]
            if avoid is not None:
                for off, side in sides:
                    if not self.bubble.box_at(self.center + off, side, bounds).intersects(avoid):
                        anchor, tail = self.center + off, side
                        break
        else:
            anchor, tail = self.center + QPointF(2 * S, -HEAD_TOP * S), "down"
            if anchor.y() - 70 < self.ruler_bottom():
                anchor, tail = self.center + QPointF(2 * S, 16 * S), "up"
        self.bubble.place(anchor, tail, bounds)
