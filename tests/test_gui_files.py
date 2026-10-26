"""File menu in the GUI: New / Open / Save / Save as, unsaved changes, recent files, drag & drop,
presets as files. Verification case 5: save → reopen → same element list and same streamlines."""
import os

import numpy as np
import pytest

from physics import Doublet, Source, Uniform, Vortex, check_scene
from physics.streamlines import trace_streamlines
from tests.test_gui import preset


@pytest.fixture
def win(qapp, tmp_path):
    from app.main_window import MainWindow
    w = MainWindow()
    w.recent.clear()
    w.messages = []
    w._notify_user = lambda kind, title, text: w.messages.append((kind, title, text))
    w.answers = []                                    # answers for "save changes?" (default: discard)
    w._ask_save_changes = lambda: w.answers.pop(0) if w.answers else "discard"
    w.save_path = str(tmp_path / "scene.pflow")
    w.asked = []

    def ask_save(suggested):
        w.asked.append(suggested)
        return w.save_path
    w._ask_save_path = ask_save
    w.resize(1400, 860)
    w.show()
    qapp.processEvents()
    yield w
    w._ask_save_changes = lambda: "discard"
    w.close()
    w.deleteLater()


def settle(qapp, w):
    for _ in range(20):
        w.canvas.wait_idle(50)
        qapp.processEvents()


def test_verification_case_5_save_and_reopen_reproduces_list_and_plot(win, qapp, tmp_path):
    w = win
    w.load_preset(preset("Lifting (rotating) cylinder"))
    w.model.add(Source(m=0.75, x0=-2.25, y0=1.125))
    w.settings_panel.s_density.setValue(7)              # density 1.4
    w.settings_panel.s_arrows.setValue(3)               # arrow density 2
    settle(qapp, w)
    assert w.save_scene()
    saved_elements = list(w.elements)
    saved_view = w.canvas.vb.viewRange()

    # change everything, then reopen
    w.new_scene()
    w.settings_panel.s_density.setValue(3)
    w.canvas.set_view((-10, 10), (-8, 8))
    assert w.elements == []
    assert w.open_scene(w.save_path)
    settle(qapp, w)

    assert w.elements == saved_elements                                  # same element list, exactly
    assert [w.elements_panel.tree.topLevelItem(i).text(1) for i in range(len(w.elements))] == \
        [e.summary() for e in saved_elements]
    assert w.canvas.density == 1.4 and w.canvas.arrow_density == 2.0
    assert w.settings_panel.s_density.value() == 7 and w.settings_panel.s_arrows.value() == 3
    np.testing.assert_allclose(w.canvas.vb.viewRange(), saved_view, rtol=1e-6, atol=1e-9)
    # same streamlines: what the canvas computes now equals the computation for the saved scene
    (x0, x1), (y0, y1) = w.canvas.vb.viewRange()
    a = trace_streamlines(saved_elements, (x0, x1), (y0, y1), density=1.4, arrow_density=2.0)
    b = trace_streamlines(tuple(w.elements), (x0, x1), (y0, y1), density=w.canvas.density,
                          arrow_density=w.canvas.arrow_density)
    assert len(a.lines) == len(b.lines) and all(np.array_equal(p, q) for p, q in zip(a.lines, b.lines))
    assert not w.model.can_undo and not w.model.is_modified           # a fresh document


def test_title_shows_file_name_and_unsaved_star(win):
    w = win
    assert w.windowTitle().endswith("Lifting (rotating) cylinder")
    w.model.add(Uniform())
    assert w.windowTitle().endswith(" *")
    assert w.save_scene()
    assert w.windowTitle().endswith("— scene.pflow")
    w.model.add(Source())
    assert w.windowTitle().endswith("scene.pflow *")
    w.model_undo()                                         # back to the saved state -> no star
    assert w.windowTitle().endswith("scene.pflow")


def test_save_asks_for_a_name_only_the_first_time(win):
    w = win
    assert w.save_scene() and len(w.asked) == 1
    assert w.asked[0].endswith("Lifting (rotating) cylinder.pflow")   # suggested from the scene title
    w.model.add(Vortex())
    assert w.save_scene() and len(w.asked) == 1                         # saved to the same file
    assert w.save_scene_as() and len(w.asked) == 2


def test_save_as_adds_the_extension_and_cancel_does_nothing(win, tmp_path):
    w = win
    w.save_path = str(tmp_path / "no_extension")
    assert w.save_scene_as()
    assert w.current_path.endswith("no_extension.pflow") and os.path.exists(w.current_path)
    w.save_path = ""                                                    # user pressed Cancel
    w.model.add(Source())
    assert not w.save_scene_as() and w.model.is_modified


def test_unsaved_changes_save_discard_cancel(win, tmp_path):
    w = win
    w.model.add(Source(m=3.0))
    before = list(w.elements)

    w.answers = ["cancel"]
    assert not w.new_scene() and w.elements == before                  # nothing happened

    w.answers = ["save"]
    assert w.new_scene() and w.elements == []                          # saved first, then new
    assert os.path.exists(w.save_path)
    from model import load_scene
    assert load_scene(w.save_path).elements == before

    w.model.add(Doublet())
    w.answers = ["discard"]
    assert w.open_scene(w.save_path) and w.elements == before


def test_close_with_unsaved_changes_can_be_cancelled(win, qapp):
    w = win
    w.model.add(Source())
    w.answers = ["cancel"]
    w.close()
    qapp.processEvents()
    assert w.isVisible()                                                # still open
    w.answers = ["discard"]
    assert w.close()


def test_new_scene_is_empty_with_fresh_history(win):
    w = win
    w.model.add(Source())
    assert w.new_scene()
    assert w.elements == [] and not w.model.can_undo and not w.model.is_modified
    assert w.current_path is None and w.windowTitle().endswith("untitled")


def test_broken_file_gives_a_message_and_keeps_the_scene(win, tmp_path):
    w = win
    bad = tmp_path / "broken.pflow"
    bad.write_text("{ this is not json", encoding="utf-8")
    before = list(w.elements)
    assert not w.open_scene(str(bad))
    assert w.elements == before
    kind, title, text = w.messages[-1]
    assert kind == "warning" and "broken.pflow" in text


def test_small_problems_are_reported_after_opening(win, tmp_path):
    w = win
    p = tmp_path / "old.pflow"
    p.write_text('{"format": "potential-flow-lab-scene", "version": 1, "title": "x", '
                 '"elements": [{"type": "source", "m": 2.0, "x0": 1.0}], "settings": {"speed": 3}}',
                 encoding="utf-8")
    assert w.open_scene(str(p))
    assert w.elements == [Source(m=2.0, x0=1.0, y0=0.0)]
    kind, _, text = w.messages[-1]
    assert kind == "information" and "default 0" in text and "“speed”" in text


def test_recent_files_menu(win, tmp_path):
    w = win
    paths = []
    for i in range(10):
        w.save_path = str(tmp_path / f"s{i}.pflow")
        w.model.add(Source(x0=float(i)))
        assert w.save_scene_as()
        paths.append(os.path.abspath(w.save_path))
    recent = w.recent.paths()
    assert recent == list(reversed(paths))[:8]                           # newest first, at most 8
    w.open_scene(paths[5])
    assert w.recent.paths()[0] == paths[5] and len(set(w.recent.paths())) == 8   # moved up, no duplicate
    w._rebuild_recent_menu()
    texts = [a.text() for a in w.recent_menu.actions() if a.text()]
    assert texts[0].startswith("&1  s5.pflow") and texts[-1] == "Clear this list"
    # a file that was deleted meanwhile: message, and it leaves the list
    os.remove(paths[9])
    assert not w.open_scene(paths[9])
    assert paths[9] not in w.recent.paths()
    w.recent.clear()
    w._rebuild_recent_menu()
    assert [a.text() for a in w.recent_menu.actions()] == ["(no recent files)"]


def test_drop_a_scene_file_on_the_window(win, qapp, tmp_path):
    from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
    from PySide6.QtGui import QDropEvent
    from model import SceneDocument, save_scene
    path = tmp_path / "dropped.pflow"
    save_scene(str(path), SceneDocument([Uniform(alpha=10.0)], "dropped"))
    md = QMimeData()
    md.setUrls([QUrl.fromLocalFile(str(path))])
    ev = QDropEvent(QPointF(100, 100), Qt.CopyAction, md, Qt.LeftButton, Qt.NoModifier)
    win.dropEvent(ev)
    qapp.processEvents()
    assert win.elements == [Uniform(alpha=10.0)] and win.current_path == str(path)


def test_presets_are_files_and_all_of_them_load(win):
    from app.scene import list_presets
    groups = list_presets()
    labels = [g for g, _ in groups]
    assert labels[0] == "Verification cases (assignment)" and len(labels) == 4
    titles = [p.title for _, items in groups for p in items]
    assert len(titles) == len(set(titles)) >= 20
    menu = next(a.menu() for a in win.menuBar().actions() if a.text() == "&Presets")
    menu_texts = [a.text().strip() for a in menu.actions()]
    for _, items in groups:
        for p in items:
            assert p.title in menu_texts
            assert win.load_preset(p)
            assert win.current_path is None and win.model.is_modified
            assert [i.message for i in check_scene(win.elements) if i.severity == "error"] == [], p.title
    assert win.messages == []


def test_preset_after_a_saved_file_does_not_overwrite_that_file(win, tmp_path):
    """Open my file, choose a preset, press Ctrl+S: my file must stay untouched (Save asks for a name)."""
    w = win
    w.model.add(Source(m=5.0))
    assert w.save_scene()
    mine = w.current_path
    content = open(mine, encoding="utf-8").read()
    w.load_preset(preset("Rankine oval"))
    assert w.current_path is None and "Rankine oval" in w.windowTitle()
    w.save_path = str(tmp_path / "oval.pflow")
    assert w.save_scene()
    assert w.asked[-1].endswith("Rankine oval.pflow")
    assert open(mine, encoding="utf-8").read() == content
