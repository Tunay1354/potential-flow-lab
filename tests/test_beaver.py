"""The beaver mascot (app/beaver): pixel art, speech bubble and what he does on the plot in each view mode,
also when the view is zoomed / panned, the mode switched or the scene changed."""
import numpy as np
import pytest

from physics.elements import Doublet, Source, Uniform, Vortex

DT = 1 / 30


# ---------------------------------------------------------------------- the art (no window)
def test_frames_are_crisp_whole_pixel_images(qapp):
    from app.beaver import art
    for kind in art.POSES:
        img = art.frame(kind, 3)
        assert img.width() == img.height() == art.CANVAS * 3
    a = art.rasterize(art.front(), art.PIVOT["front"])
    assert set(np.unique(a[..., 3])) <= {0, 255}                    # no half-transparent pixels
    assert a[..., 3].sum() > 0
    assert art.art_scale(1.0) == 2 and art.art_scale(1.25) == 3 and art.art_scale(2.0) == 4


def test_rotated_and_flipped_frames_keep_their_size(qapp):
    from app.beaver import art
    a = art.frame("swim", 2, rot=37, shrink=0.5, flip=True, mood="dizzy")
    assert a.width() == art.CANVAS * 2
    assert art.frame("swim", 2, rot=35) is art.frame("swim", 2, rot=36)    # 5° steps share one frame


def test_lines_are_english_and_not_repeated(qapp):
    from app.beaver.lines import LINES, Picker
    p = Picker(seed=1)
    a, b = p.pick("pulse_hit"), p.pick("pulse_hit")
    assert a != b
    assert all("{" not in p.pick("verify_ok", n=102) for _ in range(8))
    assert all(len(v) >= 2 for k, v in LINES.items() if k not in ("no_pulses",))      # variety
    text = " ".join(" ".join(v) for v in LINES.values())
    assert not any(ch in text for ch in "çğışöüÇĞİŞÖÜ")


# ---------------------------------------------------------------------- in the window
@pytest.fixture
def win(qapp):
    from app.main_window import MainWindow
    w = MainWindow()
    w._ask_save_changes = lambda: "discard"
    w.resize(1500, 830)
    w.show()
    qapp.processEvents()
    w.canvas.set_view((-4.0, 4.0), (-3.0, 3.0))
    w.canvas.recompute()
    qapp.processEvents()
    w.beaver.timer.stop()                      # stepped by the tests
    yield w
    w.close()


def run(qapp, w, seconds, until=None):
    b = w.beaver
    for _ in range(int(seconds / DT)):
        b.advance(DT)
        if until is not None and until(b):
            break
    qapp.processEvents()
    return b.state


def test_he_sits_on_the_ruler_right_of_help(win, qapp):
    b = win.beaver
    run(qapp, win, 0.5)
    assert b.state == "perch" and b.sprite.isVisible()
    ruler = win.header.ruler
    perch = ruler.beaver_perch.geometry()
    g = b.sprite.geometry()
    top = ruler.mapTo(win, ruler.rect().topLeft()).y()
    assert g.bottom() > top and g.top() < top                      # head above the ruler's edge, paws on it
    x = ruler.mapTo(win, perch.topLeft()).x()
    assert x - 10 < g.center().x() < x + perch.width()


def test_the_mask_lets_clicks_through_his_transparent_corners(win, qapp):
    b = win.beaver
    run(qapp, win, 0.2)
    m = b.sprite.mask()
    r = b.sprite.rect()
    assert not m.isEmpty() and not m.contains(r.topLeft()) and m.contains(r.center())


def test_clicking_him_does_not_clear_the_element_selection(win, qapp):
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt
    win.select_element(1)
    run(qapp, win, 0.2)
    b = win.beaver
    QTest.mousePress(b.sprite, Qt.LeftButton, Qt.NoModifier, b.sprite.rect().center())
    qapp.processEvents()
    assert win.elements_panel.current_row() == 1
    QTest.mouseRelease(b.sprite, Qt.LeftButton, Qt.NoModifier, b.sprite.rect().center())
    qapp.processEvents()
    assert b.state == "perch" and b.dialog == "menu"                # a click (no drag) opens his menu


def test_static_glass_joke_then_home(win, qapp):
    b = win.beaver
    assert win.canvas.view_mode == "static"
    p = b.to_window(complex(1.5, 1.0))
    b.drop(p)
    assert b.state == "glass"
    run(qapp, win, 1.0)
    from app.beaver.lines import LINES
    assert b.bubble.active and b.bubble.text in LINES["glass_drop"]
    win.canvas.set_view((-8.0, 8.0), (-6.0, 6.0))                   # zoom out: the glass does not move
    run(qapp, win, 0.1)
    assert abs(b.center.x() - p.x()) < 25 and b.state == "glass"
    run(qapp, win, 12, until=lambda b: b.state == "perch")
    assert b.state == "perch"


def test_particles_mode_he_rides_the_flow_and_walks_home(win, qapp):
    win.canvas.set_view_mode("particles")
    b = win.beaver
    z0 = complex(-3.5, 0.6)
    b.drop(b.to_window(z0))
    assert b.state == "flow"
    run(qapp, win, 1.0)
    assert b.z.real > z0.real + 0.3                                 # carried downstream (V∞ to the right)
    u = b.velocity(b.z)
    assert u.real > 0 and not b.flip and abs(b.rot) <= 30
    run(qapp, win, 30, until=lambda b: b.state == "gone")
    assert b.state == "gone" and b.z.real > 3.9
    run(qapp, win, 20, until=lambda b: b.state == "perch")
    assert b.state == "perch"


def test_he_moves_with_the_plot_when_zoomed_and_leaves_when_zoomed_out_of_view(win, qapp):
    win.canvas.set_view_mode("particles")
    win.canvas.set_paused(True)
    b = win.beaver
    b.drop(b.to_window(complex(-2.0, 2.0)))
    run(qapp, win, 0.2)
    z = b.z
    win.canvas.set_view((-3.0, -1.0), (1.0, 3.0))                   # zoom in around him
    run(qapp, win, 0.1)
    assert b.z == z and b.plot_rect().contains(b.center)            # same data point, new screen place
    win.canvas.set_view((2.0, 6.0), (-1.0, 1.0))                    # pan him out of the picture
    run(qapp, win, 0.2)
    assert b.state == "gone"


def test_a_free_vortex_makes_him_dizzy_and_a_drain_swallows_him(win, qapp):
    win.load_scene([Vortex(Gamma=6.0)], ((-3.0, 3.0), (-2.0, 2.0)), "vortex")
    win.canvas.recompute()
    win.canvas.set_view_mode("particles")
    b = win.beaver
    b.drop(b.to_window(complex(0.8, 0.0)))
    run(qapp, win, 60, until=lambda b: b.state != "flow")
    assert b.state == "hop" and b.data.get("dizzy")                  # closed streamlines: jumps out
    win.load_scene([Vortex(Gamma=6.0), Source(m=-3.0)], ((-3.0, 3.0), (-2.0, 2.0)), "drain")
    win.canvas.recompute()
    b._go("perch")
    b.drop(b.to_window(complex(1.6, 0.6)))
    run(qapp, win, 60, until=lambda b: b.state != "flow")
    assert b.state == "vanish"
    run(qapp, win, 3)
    assert b.state in ("gone", "walk")


def test_stagnation_point_stops_him(win, qapp):
    win.load_scene([Uniform(), Doublet(mu=1.0)], ((-4.0, 4.0), (-3.0, 3.0)), "cylinder")
    win.canvas.recompute()
    win.canvas.set_view_mode("particles")
    b = win.beaver
    b.drop(b.to_window(complex(-1.6, 0.0)))                         # on the dividing streamline
    run(qapp, win, 60, until=lambda b: b.state != "flow")
    from app.beaver.lines import LINES
    assert b.state == "hop" and (b.bubble.text in LINES["stagnation"] or b.waiting[1] == "stagnation")


def test_no_dropping_into_a_solid_body(win, qapp):
    win.canvas.set_layer("bodies", True)
    win.canvas.recompute()
    win.canvas.compute_now()
    win.canvas.set_view_mode("particles")
    b = win.beaver
    b.drop(b.to_window(complex(0.2, 0.3)))                          # inside the lifting cylinder
    from app.beaver.lines import LINES
    assert b.state == "hop" and (b.bubble.text in LINES["solid"] or (b.waiting and b.waiting[1] == "solid"))


def test_pulses_knock_him_along_his_line_to_the_edge(win, qapp):
    win.canvas.set_view_mode("pulses")
    b = win.beaver
    b.drop(b.to_window(complex(-1.5, -1.6)))
    assert b.state == "pulse"
    x0 = b.z.real
    for _ in range(int(25 / DT)):
        win.canvas.pulses.advance(DT)
        b.advance(DT)
        if b.state != "pulse":
            break
    assert b.data.get("hits", 0) >= 1 or b.state != "pulse"
    assert b.z.real > x0 + 1.0                                      # pushed downstream along the line


def test_mode_switch_while_on_the_plot(win, qapp):
    b = win.beaver
    win.canvas.set_view_mode("particles")
    b.drop(b.to_window(complex(-3.0, 1.0)))
    run(qapp, win, 0.3)
    win.canvas.set_view_mode("static")                              # onto the glass where he is
    assert b.state == "glass"
    win.canvas.set_view_mode("pulses")                              # off the glass onto a line
    assert b.state in ("pulse", "bored")


def test_new_empty_scene_sends_him_home(win, qapp):
    b = win.beaver
    win.canvas.set_view_mode("particles")
    b.drop(b.to_window(complex(-3.0, 1.0)))
    win.model.mark_clean()
    win.new_scene()
    run(qapp, win, 0.2)
    assert b.state in ("hop", "walk", "perch")


def test_switching_him_off_and_on(win, qapp):
    b = win.beaver
    win.act_beaver.setChecked(False)
    assert not b.sprite.isVisible() and not b.enabled and not b.timer.isActive()
    win.act_beaver.setChecked(True)
    assert b.sprite.isVisible() and b.enabled


def test_he_is_not_in_an_exported_figure(win, qapp, tmp_path):
    from PySide6.QtGui import QImage

    from app.export.figure import render_figure
    b = win.beaver
    b.drop(b.to_window(complex(0.0, 2.0)))
    run(qapp, win, 0.5)
    path = str(tmp_path / "f.png")
    render_figure(win.canvas, path, "png", 1.0, "white", mirror=False)
    img = QImage(path)
    reds = 0
    for y in range(0, img.height(), 2):
        for x in range(0, img.width(), 2):
            c = img.pixelColor(x, y)
            reds += c.red() > 180 and c.green() < 80 and c.blue() < 70     # the bandana's red
    assert reds == 0


def test_speech_bubble_types_and_goes_away(win, qapp):
    b = win.beaver
    b.say("glass_back")
    bub = b.bubble
    assert bub.active and bub.typing and bub.shown == 0
    run(qapp, win, 0.3)
    assert 0 < bub.shown < len(bub.text) or not bub.typing
    run(qapp, win, 6)
    assert not bub.active and not bub.isVisible()


def test_he_reacts_to_saving_and_verification(win, qapp, tmp_path):
    b = win.beaver
    run(qapp, win, 0.2)
    b.bubble.clear()
    b.waiting = None
    win.current_path = None
    win.model.add(Source(m=1.0, x0=2.0))
    assert win._write(str(tmp_path / "s.pflow"))
    from app.beaver.lines import LINES
    assert b.bubble.text in LINES["saved"]
    run(qapp, win, 6)
    b.on_verified(102, 102)
    from app.beaver.lines import LINES
    assert b.bubble.text in [l.format(n=102) for l in LINES["verify_ok"]]


def test_drag_him_from_the_ruler_onto_the_plot(win, qapp):
    """Mouse press on him, move over the plot (he hangs from the cursor), release: the glass joke."""
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    b = win.beaver
    run(qapp, win, 0.2)
    start = b.sprite.mapToGlobal(b.sprite.rect().center())

    def send(kind, gpos, buttons):
        local = QPointF(b.sprite.mapFromGlobal(gpos.toPoint()))
        ev = QMouseEvent(kind, local, gpos, Qt.LeftButton, buttons, Qt.NoModifier)
        qapp.sendEvent(b.sprite, ev)

    send(QEvent.MouseButtonPress, QPointF(start), Qt.LeftButton)
    assert b.state == "perch"                                       # not yet: a press is a click until it moves
    target = b.to_window(complex(1.0, 1.0))
    g = QPointF(win.mapToGlobal(target.toPoint()))
    for k in range(1, 11):
        send(QEvent.MouseMove, QPointF(start) + (g - QPointF(start)) * (k / 10), Qt.LeftButton)
        b.advance(DT)
        assert b.state == "held"
    assert (b.center - target).manhattanLength() < 120              # hanging just under the cursor
    send(QEvent.MouseButtonRelease, g, Qt.NoButton)
    qapp.processEvents()
    assert b.state == "glass"


def test_the_wheel_over_him_still_zooms_the_plot(win, qapp):
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent
    b = win.beaver
    b.drop(b.to_window(complex(0.5, 1.5)))
    run(qapp, win, 0.3)
    before = win.canvas.view()
    c = QPointF(b.sprite.rect().center())
    ev = QWheelEvent(c, QPointF(b.sprite.mapToGlobal(c.toPoint())), QPoint(), QPoint(0, 240), Qt.NoButton,
                     Qt.NoModifier, Qt.NoScrollPhase, False)
    qapp.sendEvent(b.sprite, ev)
    qapp.processEvents()
    assert win.canvas.view() != before


# ---------------------------------------------------------------------- very slow / very fast animations
def test_a_very_slow_ride_bores_him(win, qapp):
    win.canvas.set_view_mode("particles")
    win.canvas.particles.speed_slider = 1                          # 4× slower than normal
    b = win.beaver
    b.drop(b.to_window(complex(-3.5, 1.5)))
    assert b.crossing_time(b.z) > 18
    run(qapp, win, 12, until=lambda b: b.state != "flow")
    assert b.state == "hop" and b.t < 1                            # left after ~7 s, not after the whole ride
    assert "flow_bored" in b.said


def test_very_fast_flow_never_cuts_a_line_short(win, qapp):
    from app.beaver.bubble import READ_PER_CHAR_S, READ_S
    win.canvas.set_view_mode("particles")
    win.canvas.particles.speed_slider = 10                         # 5.7× faster
    b = win.beaver
    b.drop(b.to_window(complex(-3.5, 0.6)))
    shown = []
    for _ in range(int(15 / DT)):
        b.advance(DT)
        if b.bubble.active and (not shown or shown[-1][1] != b.bubble.text):
            shown.append((b.clock, b.bubble.text))
    assert len(shown) >= 2                                          # "too fast" … and the goodbye
    for (t0, text), (t1, _next) in zip(shown, shown[1:]):
        typing = len(text) / 38.0
        assert t1 - t0 >= typing + READ_S + READ_PER_CHAR_S * len(text) - 2 * DT


def test_slow_pulses_he_runs_off_along_his_line(win, qapp):
    win.canvas.set_view_mode("pulses")
    win.canvas.pulses.speed_slider = 1
    b = win.beaver
    b.drop(b.to_window(complex(-1.5, -1.6)))
    states = set()
    for _ in range(int(20 / DT)):
        win.canvas.pulses.advance(DT)
        b.advance(DT)
        states.add(b.state)
        if b.state in ("gone", "walk"):
            break
    assert "run" in states and "pulse_slow" in b.said


def test_paused_too_long_he_walks_home(win, qapp):
    win.canvas.set_view_mode("particles")
    b = win.beaver
    b.drop(b.to_window(complex(-3.0, 1.0)))
    win.canvas.set_paused(True)
    run(qapp, win, 10, until=lambda b: b.state != "flow")
    assert b.state == "hop" and "paused" in b.said and "paused_leave" in b.said


# ---------------------------------------------------------------------- click menu, questions & answers, tour
def _key(qapp, win, key):
    from PySide6.QtTest import QTest
    QTest.keyClick(win, key)
    qapp.processEvents()


def test_click_opens_the_menu_and_a_drag_carries_him(win, qapp):
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    b = win.beaver
    run(qapp, win, 0.2)
    c = QPointF(b.sprite.mapToGlobal(b.sprite.rect().center()))

    def send(kind, g, buttons):
        ev = QMouseEvent(kind, QPointF(b.sprite.mapFromGlobal(g.toPoint())), g, Qt.LeftButton, buttons, Qt.NoModifier)
        qapp.sendEvent(b.sprite, ev)

    send(QEvent.MouseButtonPress, c, Qt.LeftButton)
    send(QEvent.MouseMove, c + QPointF(2, 1), Qt.LeftButton)       # a tiny wobble is still a click
    assert b.state == "perch"
    send(QEvent.MouseButtonRelease, c, Qt.NoButton)
    assert b.dialog == "menu" and b.bubble.choices
    b.close_dialog()
    send(QEvent.MouseButtonPress, c, Qt.LeftButton)
    send(QEvent.MouseMove, c + QPointF(30, 40), Qt.LeftButton)     # moved: a drag
    assert b.state == "held"
    send(QEvent.MouseButtonRelease, c + QPointF(30, 40), Qt.NoButton)


def test_questions_and_answers_with_p_and_number_keys(win, qapp):
    from PySide6.QtCore import Qt

    from app.beaver.faq import FAQ
    b = win.beaver
    win.activateWindow()
    win.act_faq.trigger()                                          # P
    assert b.dialog == "faq" and len(b.bubble.choices) == len(FAQ)
    _key(qapp, win, Qt.Key_3)
    assert b.dialog == "answer" and b.bubble.text == FAQ[2][1]
    b._bubble_clicked(-1)                                          # click: back to the questions
    assert b.dialog == "faq"
    _key(qapp, win, Qt.Key_Down)
    _key(qapp, win, Qt.Key_Return)
    assert b.dialog == "answer" and b.bubble.text == FAQ[1][1]
    _key(qapp, win, Qt.Key_Escape)
    assert b.dialog is None and not b.bubble.active


def test_the_menu_starts_the_tour_and_says_fun_facts(win, qapp):
    b = win.beaver
    b.open_menu()
    b._choose(2)                                                   # a fun fact
    from app.beaver.lines import LINES
    assert b.dialog is None and b.bubble.text in LINES["facts"]
    b.bubble.clear()
    b.open_menu()
    b._choose(1)                                                   # the tour
    assert b.tour.active and b.state == "tour"
    b.tour.end(completed=False)
    assert not b.tour.active


def test_the_whole_tour_needs_the_actions_and_ends_on_an_empty_plot(win, qapp):
    from PySide6.QtCore import Qt

    from app.beaver.tour import STEPS
    from physics.elements import Doublet, Uniform
    b = win.beaver
    win.activateWindow()
    win.model.mark_clean()
    b.start_tour()
    assert b.tour.active and b.tour.i == 0 and win.elements == []   # starts from an empty sheet
    assert b.spotlight.isVisible()
    for _ in range(200):
        s = b.tour.step
        if s is None:
            break
        if s.wait is None:
            _key(qapp, win, Qt.Key_Space)                           # finish the typing …
            if b.tour.step is s:
                _key(qapp, win, Qt.Key_Space)                       # … then next
            continue
        i = b.tour.i
        _key(qapp, win, Qt.Key_Space)                              # Space does not skip an action step …
        assert b.tour.i == i or b.bubble.typing is False
        ev, val = s.wait
        if ev == "added":
            win.model.add(Uniform() if val == "uniform" else Doublet(mu=1.0))
        elif ev == "edited":
            b.notify("edited", "doublet")
        elif ev == "mouse_mode":
            win.canvas.set_mode(val)
        elif ev == "moved":
            b.notify("moved", "doublet")
        elif ev == "setting":
            sl = win.settings_panel.sliders[val]
            sl.setValue(sl.value() + 1)
        elif ev == "view_mode":
            win.canvas.set_view_mode(val)
        run(qapp, win, 1.5)                                         # "Nice!", then the next step
        assert b.tour.i == i + 1 or not b.tour.active
    assert not b.tour.active and win.elements == [] and win.canvas.view_mode == "static"
    assert win.canvas.mode == "select" and not b.spotlight.isVisible()
    run(qapp, win, 3)
    assert b.state == "perch"
    assert len(STEPS) >= 12


def _tour_at(b, win, qapp, index):
    """Start the tour and go to step `index` (typing finished)."""
    win.activateWindow()
    win.model.mark_clean()
    b.start_tour()
    while b.tour.i < index:
        b.bubble.finish_typing()
        b.tour.next()
    b.bubble.finish_typing()
    run(qapp, win, 0.3)
    b.bubble.finish_typing()


def _bubble_box(b):
    from PySide6.QtCore import QPointF
    return b.bubble._box.translated(QPointF(b.bubble.geometry().topLeft()) + b.bubble._offset)


def test_the_tour_locks_the_window_except_what_the_step_asks_for(win, qapp, monkeypatch):
    """Tour: a click only reaches what the step asks for (here: nothing, then the plot's zoom / pan, then the
    UNIFORM button); the beaver, his bubble and hovering keep working."""
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtTest import QTest
    b = win.beaver
    calls = []
    monkeypatch.setattr(win, "add_element_dialog", lambda key, at=None: calls.append(key))
    pal = {x.property("element_key"): x for x in win.element_toolbar.findChildren(type(win.canvas.bar.btn_move))
           if x.property("element_key")}
    bar, vp = win.canvas.bar, win.canvas.plot.viewport()
    _tour_at(b, win, qapp, 0)                                        # welcome: nothing
    for wdg in (pal["uniform"], bar.btn_particles, bar.btn_move, win.elements_panel.btn_edit):
        QTest.mouseClick(wdg, Qt.LeftButton)
    qapp.processEvents()
    assert calls == [] and win.canvas.view_mode == "static" and win.canvas.mode == "select"
    _tour_at(b, win, qapp, 1)                                        # the plot: zoom / pan only
    v0 = win.canvas.view()
    qapp.sendEvent(vp, QWheelEvent(QPointF(300, 200), QPointF(vp.mapToGlobal(QPoint(300, 200))), QPoint(0, 0),
                                   QPoint(0, 240), Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False))
    run(qapp, win, 0.2)
    assert win.canvas.view() != v0
    QTest.mouseClick(bar.btn_particles, Qt.LeftButton)
    assert win.canvas.view_mode == "static"
    _tour_at(b, win, qapp, 3)                                        # drag a UNIFORM flow: only that button
    QTest.mouseClick(pal["source"], Qt.LeftButton)
    QTest.mouseClick(pal["uniform"], Qt.LeftButton)
    qapp.processEvents()
    assert calls == ["uniform"]
    b.tour.end(completed=False)
    QTest.mouseClick(pal["source"], Qt.LeftButton)                   # after the tour: everything again
    qapp.processEvents()
    assert calls == ["uniform", "source"]


def test_tour_keys_work_from_a_text_field_and_other_keys_are_swallowed(win, qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QLineEdit
    b = win.beaver
    _tour_at(b, win, qapp, 1)
    field = next(f for f in win.settings_panel.findChildren(QLineEdit) if f.isVisible())
    field.setFocus()
    qapp.processEvents()
    QTest.keyClick(field, Qt.Key_Return)                              # Enter in a text field: next
    qapp.processEvents()
    assert b.tour.i == 2
    QTest.keyClick(win, Qt.Key_M)                                     # a shortcut: swallowed (not the Move step)
    QTest.keyClick(win, Qt.Key_Right)                                 # (not "next" any more)
    qapp.processEvents()
    assert win.canvas.mode == "select" and b.tour.i == 2
    _tour_at(b, win, qapp, 8)                                         # the Move step: M works there
    assert b.tour.step.wait == ("mouse_mode", "move")
    QTest.keyClick(win, Qt.Key_M)
    run(qapp, win, 1.5)
    assert win.canvas.mode == "move" and b.tour.step.wait == ("moved", None)    # on to "drag the doublet"
    b.tour.end(completed=False)
    assert win.canvas.mode == "select"


def test_tour_bubble_has_buttons_and_a_click_only_goes_on_in_a_reading_step(win, qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from app.beaver.tour import END_BUTTON, NEXT_BUTTON, SKIP_BUTTON
    b = win.beaver
    _tour_at(b, win, qapp, 2)
    assert b.bubble.buttons == [END_BUTTON, NEXT_BUTTON]
    QTest.mouseClick(b.bubble, Qt.LeftButton, pos=b.bubble.button_rect(1).center().toPoint())   # Next
    qapp.processEvents()
    assert b.tour.i == 3 and b.bubble.buttons == [END_BUTTON, SKIP_BUTTON]
    b.bubble.finish_typing()
    b.bubble.clicked.emit(-1)                                          # a click on an action step's text …
    b._pressed(b.center)                                               # … or on the beaver: no skip
    assert b.tour.i == 3
    b.bubble.button_clicked.emit(1)                                    # Skip
    assert b.tour.i == 4
    b.bubble.button_clicked.emit(0)                                    # End tour
    assert not b.tour.active


def test_tour_bubble_never_covers_what_it_shows(win, qapp):
    """Elements list, plot settings, the slider, buttons, menus: the bubble is beside them, not on them."""
    from app.beaver.tour import STEPS
    b = win.beaver
    for k, s in enumerate(STEPS):
        if s.where in ("inside", "perch") or s.target is None:
            continue
        _tour_at(b, win, qapp, k)
        run(qapp, win, 1.0)
        avoid = b.tour.avoid_rect()
        assert avoid is not None and not _bubble_box(b).intersects(avoid), s.target
        b.tour.end(completed=False)


def test_tour_sub_steps_drag_and_dialog(win, qapp):
    """Dragging from the palette highlights the plot; an open dialog gets the beaver beside it (Apply goes on,
    Cancel back to the step); an edit that changes nothing says so and waits."""
    from app.dialogs import ElementDialog
    from app.element_specs import spec_for
    b = win.beaver
    _tour_at(b, win, qapp, 3)
    b.notify("palette_drag", "uniform")
    assert b.tour.sub == "drag" and b.spotlight.target.contains(b.plot_rect().center())
    b.notify("palette_drag_end", "uniform")
    run(qapp, win, 0.5)
    assert b.tour.sub is None and b.tour.i == 3                        # let go elsewhere: back
    spec = spec_for("uniform")
    dlg = ElementDialog(spec, win.theme, False, win, values={p.key: p.default for p in spec.params})
    dlg.setModal(False)
    dlg.show()
    qapp.processEvents()
    b.notify("dialog_open", ("add", "uniform", dlg))
    run(qapp, win, 1.0)
    b.bubble.finish_typing()
    run(qapp, win, 0.1)
    r = b.tour.target_rect()
    assert b.tour.sub == "dialog" and r is not None and not _bubble_box(b).intersects(r)
    b.notify("dialog_closed", (False, False))                          # Cancel
    assert b.tour.sub is None and b.tour.i == 3
    dlg.close()
    dlg.deleteLater()
    _tour_at(b, win, qapp, 7)                                          # edit the doublet
    b.notify("dialog_open", ("edit", "doublet", None))
    b.notify("dialog_closed", (True, False))                           # Apply without a change
    assert b.tour.i == 7 and b.tour.note is not None and "Nothing changed" in b.bubble.text
    b.notify("edited", "doublet")
    run(qapp, win, 1.5)
    assert b.tour.i == 8
    b.tour.end(completed=False)


def test_a_second_tour_from_the_menu_shows_a_scrolled_away_slider(win, qapp):
    """Bug from his second tour: the Plot settings were scrolled down, the tour started from the menu while
    a remark was still typing; the Density step showed nothing (and the lock stopped him from scrolling)."""
    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtWidgets import QScrollArea
    b = win.beaver
    sl = win.settings_panel.sliders["density"]
    area = sl.parentWidget()
    while not isinstance(area, QScrollArea):
        area = area.parentWidget()
    area.verticalScrollBar().setValue(area.verticalScrollBar().maximum())
    qapp.processEvents()
    seen = lambda: QRect(sl.mapTo(area.viewport(), QPoint(0, 0)), sl.size()).intersects(area.viewport().rect())   # noqa: E731
    assert not seen()
    b.say("poked")                                                    # a remark, still typing …
    b.open_menu()
    b._choose(1)                                                      # … Show me around
    assert b.tour.active and b.tour.i == 0                             # (it used to stay at −1)
    _tour_at(b, win, qapp, 11)
    assert b.tour.step.target == "slider:density" and seen()
    dock = b.tour._map(win.dock_settings)
    assert dock.contains(b.spotlight.target.center())
    b.tour.end(completed=False)
    b.say("poked")
    b.start_tour()                                                    # Help → Beaver → Show me around
    assert b.tour.i == 0
    b.tour.end(completed=False)
    sl.setVisible(False)                                              # a hidden section: the step is skipped
    _tour_at(b, win, qapp, 11)
    assert b.tour.step.target != "slider:density"
    b.tour.end(completed=False)
    sl.setVisible(True)


def test_bubbles_have_the_name_a_tag_and_buttons(win, qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from app.beaver.lines import NAME
    b = win.beaver
    _tour_at(b, win, qapp, 0)
    bub = b.bubble
    assert bub.title == NAME.upper() and bub.tag.lower() == "tour 1/18" and bub.primary == 1 and not bub.hint
    _tour_at(b, win, qapp, 3)
    assert bub.tag.lower().startswith("your turn") and bub.primary is None
    b.tour.end(completed=False)
    b.ask_tour()                                                      # first start: buttons, Enter = yes
    assert b.dialog == "ask_tour" and bub.buttons and bub.primary == 1
    bub.finish_typing()
    QTest.keyClick(win, Qt.Key_Escape)                                # Esc = no
    qapp.processEvents()
    assert b.dialog is None and not b.tour.active
    b.ask_tour()
    bub.button_clicked.emit(1)                                        # "Yes, show me around"
    assert b.tour.active
    b.tour.end(completed=False)
    b.open_menu()
    assert bub.tag.lower() == "menu" and bub.buttons == ["Close"]
    bub.button_clicked.emit(0)
    assert b.dialog is None
    b.say("poked", cooldown=0.0)
    run(qapp, win, 0.1)
    assert not bub.title and not bub.buttons                          # a remark: no header, no buttons


def test_esc_ends_the_tour(win, qapp):
    from PySide6.QtCore import Qt
    b = win.beaver
    win.activateWindow()
    win.model.mark_clean()
    b.start_tour()
    _key(qapp, win, Qt.Key_Escape)
    assert not b.tour.active and not b.spotlight.isVisible()


def test_first_start_offers_the_tour_and_later_starts_do_not(qapp):
    from PySide6.QtCore import QSettings

    from app.main_window import MainWindow
    s = QSettings()
    s.setValue("beaver/tour_offered", False)
    try:
        w1 = MainWindow()
        w1.beaver.timer.stop()
        w1.beaver.start_session(True)                              # (what the 1.2 s timer does)
        assert w1.beaver.dialog == "ask_tour"
        assert s.value("beaver/tour_offered", False, bool)
        w1.beaver._choose(1)                                       # "No, thanks"
        assert not w1.beaver.tour.active
        w1.close()
        w2 = MainWindow()                                          # second start
        assert not (qapp.property("first_run") is True)
        w2.forget_first_start()                                    # Help → Beaver → Next start as a first-time user
        assert not s.value("beaver/tour_offered", True, bool)
        w2.close()
    finally:
        s.setValue("beaver/tour_offered", True)
