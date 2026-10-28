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
    assert p.pick("verify_ok", n=102).count("102") >= 1
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
    assert b.state == "held" and win.elements_panel.current_row() == 1
    QTest.mouseRelease(b.sprite, Qt.LeftButton, Qt.NoModifier, b.sprite.rect().center())
    qapp.processEvents()
    assert b.state != "held"


def test_static_glass_joke_then_home(win, qapp):
    b = win.beaver
    assert win.canvas.view_mode == "static"
    p = b.to_window(complex(1.5, 1.0))
    b.drop(p)
    assert b.state == "glass"
    run(qapp, win, 1.0)
    assert b.bubble.active and "fall" in b.bubble.text
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
    assert b.state == "hop" and "stagnat" in b.bubble.text.lower()


def test_no_dropping_into_a_solid_body(win, qapp):
    win.canvas.set_layer("bodies", True)
    win.canvas.recompute()
    win.canvas.compute_now()
    win.canvas.set_view_mode("particles")
    b = win.beaver
    b.drop(b.to_window(complex(0.2, 0.3)))                          # inside the lifting cylinder
    assert b.state == "hop" and "solid" in b.bubble.text.lower()


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
    win.current_path = None
    win.model.add(Source(m=1.0, x0=2.0))
    assert win._write(str(tmp_path / "s.pflow"))
    assert "Saved" in b.bubble.text
    b.on_verified(102, 102)
    assert "102" in b.bubble.text


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
    assert b.state == "held"
    target = b.to_window(complex(1.0, 1.0))
    g = QPointF(win.mapToGlobal(target.toPoint()))
    for k in range(1, 11):
        send(QEvent.MouseMove, QPointF(start) + (g - QPointF(start)) * (k / 10), Qt.LeftButton)
        b.advance(DT)
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
