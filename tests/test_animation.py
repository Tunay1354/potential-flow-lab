"""Phase 4b: the animated view — tracer particles carried by the flow and travel times along
streamlines (physics/particles.py), and the two animation styles of the plot (particles with trails,
pulses along streamlines; colors by speed, legend, Static / Animated, pause, settings)."""
import numpy as np
import pytest

from physics import Doublet, SectorFlow, Source, SymmetryWall, Uniform, Vortex, kernel
from physics.field import fluid_mask
from physics.particles import CROSSING_S, Particles, travel_times


# ---------------------------------------------------------------- physics
@pytest.mark.parametrize("compiled", [True, False])
def test_particles_in_uniform_flow_move_exactly_with_it(monkeypatch, compiled):
    if compiled and not kernel.HAVE_NUMBA:
        pytest.skip("Numba not installed")
    monkeypatch.setattr(kernel, "HAVE_NUMBA", compiled)
    p = Particles(500)
    p.set_scene([Uniform(V=2.0, alpha=30.0)])
    p.set_view((-4, 4, -3, 3))
    z0 = p.pos.copy()
    p.step(0.05)
    dt = 0.05 * p.time_scale()
    moved = ~p.fresh
    assert moved.sum() > 450
    np.testing.assert_allclose(p.pos[moved] - z0[moved], 2.0 * dt * np.exp(1j * np.radians(30.0)), atol=1e-12)
    np.testing.assert_allclose(p.speed[moved], 2.0)


def test_time_scale_makes_a_typical_particle_cross_the_view_in_a_few_seconds():
    p = Particles(100)
    p.set_scene([Uniform(V=3.0)])
    for box in ((-4, 4, -3, 3), (-0.5, 0.5, -0.3, 0.3)):            # any zoom
        p.set_view(box)
        assert 3.0 * p.time_scale() * CROSSING_S == pytest.approx(box[1] - box[0])
        assert p.time_scale(2.0) == pytest.approx(2.0 * p.time_scale())


@pytest.mark.parametrize("compiled", [True, False])
@pytest.mark.parametrize("scene, box", [
    ([Uniform(), SymmetryWall(), Source(m=2.0, y0=1.0)], (-4, 4, -1, 5)),
    ([SectorFlow(theta2=360.0)], (-3, 3, -2.4, 2.4)),                      # plate: never crossed
    ([Uniform(), Doublet(mu=1.0), Vortex(Gamma=-2.0)], (-4, 4, -3, 3)),
])
def test_particles_stay_in_the_fluid_and_in_the_view(monkeypatch, compiled, scene, box):
    if compiled and not kernel.HAVE_NUMBA:
        pytest.skip("Numba not installed")
    monkeypatch.setattr(kernel, "HAVE_NUMBA", compiled)
    p = Particles(800)
    p.set_scene(scene)
    p.set_view(box)
    for _ in range(90):
        p.step(1 / 30)
        assert fluid_mask(p.els, p.pos).all()
        x0, x1, y0, y1 = box
        assert ((p.pos.real >= x0) & (p.pos.real <= x1) & (p.pos.imag >= y0) & (p.pos.imag <= y1)).all()
    if scene[0].TYPE == "sector":                                    # plate along +x: nobody jumped across
        a, b = p.prev[~p.fresh], p.pos[~p.fresh]
        sides = a.imag * b.imag < 0
        x_cross = a.real[sides] - a.imag[sides] * (b.real[sides] - a.real[sides]) / (b.imag[sides] - a.imag[sides])
        assert not (x_cross > 0.2).any()             # (going round the tip within one frame is fine)


def test_particles_restart_staggered_not_all_at_once():
    p = Particles(1000)
    p.set_scene([Uniform()])
    p.set_view((-4, 4, -3, 3))
    restarts = []
    for _ in range(120):
        p.step(1 / 60)
        restarts.append(p.fresh.mean())
    assert max(restarts) < 0.1 and np.mean(restarts) > 0                # a few every frame


def test_travel_times_along_streamlines():
    """Uniform flow: τ = distance / V from the start of each line, pieces about `step` long."""
    lines = [np.column_stack([np.linspace(0, 4, 9), np.zeros(9)]),
             np.column_stack([np.linspace(-1, 1, 5), np.ones(5)])]
    a, b, tau, v = travel_times(lines, [Uniform(V=2.0)], 0.1, 1e-3)
    assert a.size == 40 + 20
    np.testing.assert_allclose(np.abs(b - a), 0.1)
    mid = 0.5 * (a + b)
    np.testing.assert_allclose(tau[:40], mid.real[:40] / 2.0)
    np.testing.assert_allclose(tau[40:], (mid.real[40:] + 1.0) / 2.0)          # a new line starts at 0
    np.testing.assert_allclose(v, 2.0)


def test_travel_time_grows_towards_a_stagnation_point_but_stays_finite():
    """Towards the stagnation point of a source in a uniform flow the flow slows down: τ grows faster
    and faster, limited by the speed floor."""
    scene = [Uniform(V=1.0), Source(m=2 * np.pi)]                  # stagnation point at x = −1
    x = np.linspace(-4.0, -1.0, 301)
    a, b, tau, v = travel_times([np.column_stack([x, np.zeros_like(x)])], scene, 0.01, 1e-2)
    assert np.isfinite(tau).all() and (np.diff(tau) > 0).all()
    assert v[-1] < 0.02 and v[0] > 0.6
    assert tau[-1] - tau[-30] > 10 * (tau[29] - tau[0])               # the last 0.3 take much longer


@pytest.mark.skipif(not kernel.HAVE_NUMBA, reason="Numba not installed")
def test_draw_segments_keep_max_does_not_darken_where_pieces_overlap():
    img = np.zeros((20, 40, 4), np.uint8)
    pal = np.array([[200.0, 100.0, 50.0, 0.8]])
    x = np.linspace(5, 35, 16)                                          # 2 px pieces with round ends
    ax, bx = x[:-1].copy(), x[1:].copy()
    ay = by = np.full(ax.size, 10.0)
    kernel.draw_segments(img, ax, ay, bx, by, np.zeros(ax.size, np.int64), pal, 1.5, np.ones(ax.size), True)
    assert img[10, 20, 3] == round(255 * 0.8)                           # the line's own opacity
    img2 = np.zeros_like(img)
    kernel.draw_segments(img2, ax, ay, bx, by, np.zeros(ax.size, np.int64), pal, 1.5, np.ones(ax.size), False)
    assert img2[10, 20, 3] > img[10, 20, 3]                             # blending: darker where they overlap
    half = np.zeros_like(img)
    kernel.draw_segments(half, ax, ay, bx, by, np.zeros(ax.size, np.int64), pal, 1.5, np.full(ax.size, 0.5), True)
    assert half[10, 20, 3] == round(255 * 0.4)


# ---------------------------------------------------------------- the plot
@pytest.fixture
def win(qapp):
    from app.main_window import MainWindow
    w = MainWindow()
    w._ask_save_changes = lambda: "discard"
    w.resize(1300, 820)
    w.show()
    qapp.processEvents()
    w.canvas.set_view((-4.0, 4.0), (-3.0, 3.0))
    w.canvas.recompute()
    qapp.processEvents()
    yield w
    w.close()


def _frames(qapp, n=12):
    from PySide6.QtTest import QTest
    QTest.qWait(17 * n)
    qapp.processEvents()


def _trail_alpha(cv):
    img = cv.particles.trail.image
    if img is None:
        return 0
    a = np.frombuffer(img.bits(), np.uint8).reshape(img.height(), img.bytesPerLine() // 4, 4)[..., 3]
    return int(a.max())


def test_animated_button_starts_particles_over_faint_streamlines(win, qapp):
    cv = win.canvas
    alpha_static = cv.streamlines.line_items[0].opts["pen"].color().alphaF()
    cv.bar.btn_particles.click()
    assert cv.animated and cv.particles._timer.isActive() and win.view_mode_actions["particles"].isChecked()
    _frames(qapp)
    assert _trail_alpha(cv) > 100                                    # trails are drawn
    assert cv.streamlines.line_items[0].opts["pen"].color().alphaF() < 0.5 * alpha_static
    assert not cv.streamlines.arrow_item.isVisible()
    assert cv.particles.legend.isVisible() and cv.particles.legend.title.startswith("|V|")
    assert cv.stagnation.symbol_item.isVisible() and len(cv.stagnation_points) == 2
    cv.bar.btn_static.click()
    assert not cv.animated and not cv.particles._timer.isActive()
    assert not cv.particles.trail.isVisible() and cv.streamlines.arrow_item.isVisible()
    assert cv.streamlines.line_items[0].opts["pen"].color().alphaF() == pytest.approx(alpha_static)


def test_space_pauses_and_continues(win, qapp):
    cv = win.canvas
    assert not win.act_pause.isEnabled()                              # nothing to pause in Static mode
    cv.set_animated(True)
    _frames(qapp, 4)
    win.act_pause.trigger()
    assert cv.particles.paused and win.act_pause.isChecked()
    before = cv.particles.particles.pos.copy()
    _frames(qapp, 6)
    np.testing.assert_array_equal(cv.particles.particles.pos, before)
    win.act_pause.trigger()
    _frames(qapp, 6)
    assert not cv.particles.paused and not np.array_equal(cv.particles.particles.pos, before)
    assert win.shortcuts.keys("view.pause") == ["Space"]


def test_color_map_layer_takes_the_legend_place(win, qapp):
    cv = win.canvas
    cv.set_animated(True)
    win.settings_panel.layer_boxes["speed"].setChecked(True)
    _frames(qapp, 3)
    assert cv.fields.legend.isVisible() and not cv.particles.legend.isVisible()


def test_animation_settings_are_saved_with_the_scene(win, qapp, tmp_path):
    sp, cv = win.settings_panel, win.canvas
    sp.s_particles.setValue(800)
    sp.s_anim_speed.setValue(8)
    sp.s_trail.setValue(0)
    assert (cv.settings.particles, cv.settings.anim_speed, cv.settings.trail) == (800, 8, 0)
    path = str(tmp_path / "anim.pflow")
    win._ask_save_path = lambda suggested: path
    assert win.save_scene_as()
    sp.s_particles.setValue(1500)
    sp.s_trail.setValue(4)
    assert win.open_scene(path)
    assert (cv.settings.particles, cv.settings.anim_speed, cv.settings.trail) == (800, 8, 0)
    assert sp.s_particles.value() == 800 and sp.s_trail.value() == 0
    cv.set_animated(True)
    assert cv.particles.particles.pos.size == 800


def test_export_while_animating_draws_the_items_and_keeps_animating(win, qapp, tmp_path):
    from PySide6.QtWidgets import QGraphicsItem
    from app.export import render_figure
    cv = win.canvas
    cv.set_animated(True)
    _frames(qapp, 4)
    render_figure(cv, str(tmp_path / "a.png"), "png", 2)
    assert (tmp_path / "a.png").exists()
    assert cv.static_cache and cv.streamlines.line_items[0].cacheMode() == QGraphicsItem.DeviceCoordinateCache
    assert cv.particles._timer.isActive()


def test_particles_follow_a_dragged_element(win, qapp):
    cv = win.canvas
    cv.set_animated(True)
    _frames(qapp, 2)
    flows_before = list(cv.particles.particles.flows)
    from PySide6.QtCore import QPointF
    cv.set_mode("move")
    pos = cv.vb.mapViewToScene(QPointF(0.0, 0.0))
    assert cv.interaction.begin_drag(pos)
    cv.interaction.drag_to(cv.vb.mapViewToScene(QPointF(1.0, 0.5)))
    assert cv.particles.particles.flows != flows_before                  # moved element used at once
    cv.interaction.cancel_drag()
    assert cv.particles.particles.flows == flows_before


# ---------------------------------------------------------------- view "Pulses along streamlines"
def test_three_view_buttons_do_not_overlap_the_mouse_mode_buttons(win, qapp):
    bar = win.canvas.bar
    b = [bar.btn_static, bar.btn_particles, bar.btn_pulses, bar.btn_select, bar.btn_move, bar.btn_pan, bar.btn_fit,
         bar.btn_export]
    for w in (1300, win.minimumSizeHint().width()):
        win.resize(w, 820)
        qapp.processEvents()
        for left, right in zip(b, b[1:]):
            assert left.geometry().right() < right.geometry().left()
        assert bar.btn_export.geometry().right() <= bar.width()
        assert all(x.width() >= x.sizeHint().width() for x in b)                 # no cut text


def test_pulse_view_button(win, qapp):
    cv = win.canvas
    alpha_static = cv.streamlines.line_items[0].opts["pen"].color().alphaF()
    cv.bar.btn_pulses.click()
    assert cv.view_mode == "pulses" and cv.animation is cv.pulses and win.view_mode_actions["pulses"].isChecked()
    assert cv.pulses._timer.isActive() and not cv.particles._timer.isActive() and win.act_pause.isEnabled()
    _frames(qapp)
    img = cv.pulses.trail.image
    assert img is not None and cv.pulses.trail.isVisible() and not cv.particles.trail.isVisible()
    a = np.frombuffer(img.bits(), np.uint8).reshape(img.height(), img.bytesPerLine() // 4, 4)[..., 3]
    assert a.max() > 150 and 0.002 < (a > 0).mean() < 0.2                 # bright dashes, not everywhere
    assert cv.streamlines.line_items[0].opts["pen"].color().alphaF() < 0.6 * alpha_static
    assert not cv.streamlines.arrow_item.isVisible()
    assert cv.pulses.legend.isVisible() and not cv.particles.legend.isVisible()
    t = cv.pulses.t
    _frames(qapp, 6)
    assert cv.pulses.t > t                                                 # running
    cv.bar.btn_particles.click()                                           # straight to the other animation
    assert cv.view_mode == "particles" and cv.static_cache
    assert cv.particles._timer.isActive() and not cv.pulses._timer.isActive()
    assert not cv.pulses.trail.isVisible() and cv.particles.legend.isVisible()
    _frames(qapp)
    assert _trail_alpha(cv) > 100
    cv.bar.btn_static.click()
    assert not cv.animated and not cv.static_cache and not win.act_pause.isEnabled()
    assert cv.streamlines.arrow_item.isVisible()


def test_pulse_settings_are_their_own(win, qapp):
    sp, cv = win.settings_panel, win.canvas
    assert set(sp.sections) >= {"particles", "pulses"}
    sp.s_pulse_speed.setValue(8)
    sp.s_pulse_length.setValue(0)
    sp.s_pulse_spacing.setValue(7)
    assert (cv.pulses.speed_slider, cv.pulses.trail_slider, cv.pulses.spacing_slider) == (8, 0, 7)
    assert (cv.particles.speed_slider, cv.particles.trail_slider) == (5, 4)          # particles unchanged
    sp.s_anim_speed.setValue(2)
    assert cv.pulses.speed_slider == 8
    cv.set_view_mode("pulses")
    _frames(qapp, 4)
    from app.canvas.animation_layer import pulse_spacing
    sep = cv.pulses.result.separation
    assert cv.pulses.period == pytest.approx(pulse_spacing(7) * sep / cv.pulses.v_typ)


def test_pulses_pause_and_follow_new_streamlines(win, qapp):
    cv = win.canvas
    cv.set_view_mode("pulses")
    _frames(qapp, 4)
    win.act_pause.trigger()
    assert cv.paused and cv.pulses.paused
    t = cv.pulses.t
    cv.set_view((-3.0, 3.0), (-2.0, 2.0))                                  # zoom while paused: drawn again
    _frames(qapp, 6)
    assert cv.pulses.t == t and cv.pulses.trail.image is not None
    win.act_pause.trigger()
    assert not cv.paused
    old = cv.pulses.result
    win.load_scene([Uniform(alpha=20.0)], ((-4, 4), (-3, 3)))
    from PySide6.QtTest import QTest
    for _ in range(200):
        if cv.pulses.result is not old and not cv.streamlines.busy:
            break
        cv.wait_idle()
        QTest.qWait(20)
    assert cv.pulses.result is not old
    _frames(qapp, 4)
    ax, ay, bx, by, phase, band = cv.pulses._px
    ang = np.degrees(np.arctan2(by - ay, bx - ax))
    np.testing.assert_allclose(np.median(ang), 20.0, atol=1.0)               # pieces along the new flow


def test_pulses_without_numba(win, qapp, monkeypatch):
    cv = win.canvas
    monkeypatch.setattr(kernel, "HAVE_NUMBA", False)
    cv.set_view_mode("pulses")
    _frames(qapp, 6)
    img = cv.pulses.trail.image
    a = np.frombuffer(img.bits(), np.uint8).reshape(img.height(), img.bytesPerLine() // 4, 4)[..., 3]
    assert a.max() > 100


def test_pulse_settings_are_saved_with_the_scene_but_not_the_view_mode(win, qapp, tmp_path):
    sp, cv = win.settings_panel, win.canvas
    sp.s_pulse_length.setValue(9)
    sp.s_pulse_spacing.setValue(2)
    path = str(tmp_path / "pulses.pflow")
    win._ask_save_path = lambda suggested: path
    assert win.save_scene_as()
    sp.s_pulse_length.setValue(4)
    sp.s_pulse_spacing.setValue(4)
    cv.set_view_mode("pulses")
    assert win.open_scene(path)
    assert (cv.settings.pulse_length, cv.settings.pulse_spacing) == (9, 2)
    assert (sp.s_pulse_length.value(), sp.s_pulse_spacing.value()) == (9, 2)
    assert (cv.pulses.trail_slider, cv.pulses.spacing_slider) == (9, 2)
    assert cv.view_mode == "pulses" and cv.pulses.animated                 # the view stays as it was


def test_older_files_with_an_animation_style_open_without_a_warning():
    from model.scene_file import FORMAT, from_data
    doc = from_data({"format": FORMAT, "version": 1, "elements": [], "settings": {"anim_style": 1.0, "trail": 2.0}})
    assert doc.warnings == [] and doc.settings == {"trail": 2.0}
