"""Autosave + recovery (app/recovery.py): an unsaved scene is kept while the program runs and offered again
when the program did not close normally."""
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def window(qapp, tmp_path):
    from app.main_window import MainWindow
    from app.recovery import SessionRecovery
    w = MainWindow()
    w.recovery.close()
    w.recovery = SessionRecovery(w._document, lambda: w.model.is_modified, lambda: (w.current_path, w.scene_title),
                                 folder=str(tmp_path / "recovery"), parent=w)
    yield w
    w.model.mark_clean()
    w.close()


def test_unsaved_changes_are_copied_and_the_copy_goes_when_saved(window, tmp_path):
    from physics.elements import Source
    rec = window.recovery
    assert not os.path.exists(rec.scene_path)
    window.model.add(Source(m=1.0, x0=2.0))
    assert rec.timer.isActive()                          # a copy a few seconds later
    rec.save_now()
    assert os.path.exists(rec.scene_path) and os.path.exists(rec.stem + ".json")
    window.current_path = None
    assert window._write(str(tmp_path / "scene.pflow"))  # saved → nothing to recover
    assert not os.path.exists(rec.scene_path)


def test_undo_back_to_the_saved_scene_removes_the_copy(window):
    from physics.elements import Vortex
    window.model.add(Vortex(Gamma=1.0, x0=2.0))
    window.recovery.save_now()
    assert os.path.exists(window.recovery.scene_path)
    window.model.undo()
    assert not window.model.is_modified and not os.path.exists(window.recovery.scene_path)


def test_a_normal_close_leaves_nothing(qapp, window):
    from app.recovery import find_recoverable
    from physics.elements import Source
    window.model.add(Source(m=1.0, x0=2.0))
    window.recovery.save_now()
    folder = window.recovery.folder
    window.recovery.close()
    assert find_recoverable(folder) == [] and os.listdir(folder) == []


def test_a_running_session_is_not_offered(window):
    from app.recovery import find_recoverable
    from physics.elements import Source
    window.model.add(Source(m=1.0, x0=2.0))
    window.recovery.save_now()
    assert find_recoverable(window.recovery.folder) == []          # its lock is held (this program runs)


def _crashed_session(folder, settings='{"density": 1.5}'):
    """A program that had an unsaved scene and then died (no normal close)."""
    code = f"""
import os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, {ROOT!r})
from PySide6.QtCore import QCoreApplication
app = QCoreApplication([])
from app.recovery import SessionRecovery
from model.scene_file import SceneDocument
from physics.elements import Uniform, Doublet, Vortex
doc = SceneDocument([Uniform(V=2.0), Doublet(mu=2.0), Vortex(Gamma=-3.0)], "My cylinder", ((-5.0, 5.0), (-3.0, 3.0)),
                    {settings})
rec = SessionRecovery(lambda: doc, lambda: True, lambda: ({str(folder / 'work.pflow')!r}, "My cylinder"),
                      folder={str(folder / 'recovery')!r})
rec.save_now()
os._exit(3)
"""
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert res.returncode == 3, res.stderr


def test_a_crashed_session_is_offered_and_restored(window, tmp_path):
    _crashed_session(tmp_path)
    asked = []
    assert window.offer_recovery(str(tmp_path / "recovery"), ask=lambda r: asked.append(r) or "restore")
    assert asked[0].title == "My cylinder" and asked[0].original.endswith("work.pflow")
    assert [e.TYPE for e in window.elements] == ["uniform", "doublet", "vortex"]
    assert window.elements[0].V == 2.0 and window.elements[2].Gamma == -3.0
    assert window.model.is_modified and window.scene_title == "My cylinder"
    assert window.current_path.endswith("work.pflow")                 # Save writes back to its file
    assert window.canvas.settings.density == 1.5
    assert not os.path.exists(asked[0].scene_path)                     # the old copy is gone …
    assert os.path.exists(window.recovery.scene_path)                  # … this session keeps its own
    window.model.undo()                                                # Undo: the scene before (V∞ = 1)
    assert window.elements[0].V == 1.0


def test_a_restored_scene_keeps_to_the_slider_limits(window, tmp_path):
    """Saved with the graphics card's 50 000 particles, restored where the processor draws: as many as its
    slider allows (as when a file is opened; the restore used to skip that)."""
    from app.canvas.settings import slider
    _crashed_session(tmp_path, '{"particles": 50000.0}')
    assert window.offer_recovery(str(tmp_path / "recovery"), ask=lambda r: "restore")
    assert window.canvas.settings.particles == slider("particles").hi


def test_not_now_keeps_it_and_discard_removes_it(window, tmp_path):
    from app.recovery import find_recoverable
    _crashed_session(tmp_path)
    folder = str(tmp_path / "recovery")
    assert not window.offer_recovery(folder, ask=lambda r: "later")
    assert len(find_recoverable(folder)) == 1                          # still there
    for r in find_recoverable(folder):
        r.release()
    assert not window.offer_recovery(folder, ask=lambda r: "discard")
    assert find_recoverable(folder) == []


def test_nothing_to_recover_asks_nothing(window, tmp_path):
    assert not window.offer_recovery(str(tmp_path / "empty"), ask=lambda r: pytest.fail("asked"))
