"""Unexpected errors (app/errors.py): logged with their traceback, reported once in a window, the program
goes on; hard crashes are found at the next start."""
import logging
import os
import subprocess
import sys
import threading
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def logdir(qapp, tmp_path):
    from app import errors
    path = errors.setup_logging(str(tmp_path / "logs"))
    yield tmp_path / "logs"
    errors._close_crash_file(remove=True)
    assert os.path.exists(path)


@pytest.fixture
def reporter(qapp, logdir):
    from app.errors import ErrorReporter
    rep = ErrorReporter().install()
    yield rep
    rep.uninstall()
    if rep.dialog is not None:
        rep.dialog.close()


def _log_text(logdir):
    for h in logging.getLogger("pflab").handlers:
        h.flush()
    return (logdir / "potential-flow-lab.log").read_text(encoding="utf-8")


def _spin(qapp, seconds=0.3):
    t = time.time()
    while time.time() - t < seconds:
        qapp.processEvents()
        time.sleep(0.01)


def test_log_file_starts_with_the_versions(logdir):
    text = _log_text(logdir)
    assert "start: Flowy" in text and "Python" in text


def test_an_error_in_a_slot_is_logged_and_shown_once(qapp, reporter, logdir):
    from PySide6.QtCore import QTimer

    def bad():
        raise ValueError("broken on purpose")

    for _ in range(3):                                   # the same error three times
        QTimer.singleShot(0, bad)
    _spin(qapp)
    text = _log_text(logdir)
    assert "unexpected error" in text and "ValueError: broken on purpose" in text and "Traceback" in text
    assert text.count("Traceback") == 1                   # repeats only counted
    assert reporter.dialog is not None and reporter.dialog.isVisible()
    assert "broken on purpose" in reporter.dialog.details_text
    reporter.dialog.accept()
    _spin(qapp, 0.1)
    assert reporter.dialog is None                        # the same error is not shown again


def test_a_second_error_waits_for_the_first_window(qapp, reporter):
    from PySide6.QtCore import QTimer

    def one():
        raise KeyError("first")

    def two():
        raise ZeroDivisionError("second")

    QTimer.singleShot(0, one)
    QTimer.singleShot(0, two)
    _spin(qapp)
    assert "first" in reporter.dialog.details_text
    reporter.dialog.accept()
    _spin(qapp, 0.2)
    assert reporter.dialog is not None and "second" in reporter.dialog.details_text


def test_an_error_in_a_background_thread_reaches_the_window(qapp, reporter, logdir):
    def work():
        raise RuntimeError("in a thread")

    t = threading.Thread(target=work, name="worker")
    t.start()
    t.join()
    _spin(qapp)
    assert "in a thread" in _log_text(logdir) and "(worker)" in _log_text(logdir)
    assert reporter.dialog is not None


def test_an_error_while_drawing_does_not_flood(qapp, reporter, logdir):
    from PySide6.QtWidgets import QWidget

    class Bad(QWidget):
        def paintEvent(self, _e):
            raise IndexError("paint")

    w = Bad()
    w.setAttribute(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.WA_DontShowOnScreen)
    w.show()
    for _ in range(5):
        w.update()                                         # drawn by the event loop: errors go to the hook
        _spin(qapp, 0.05)
    w.close()
    assert _log_text(logdir).count("IndexError: paint") == 1
    assert reporter.dialog is not None


def test_without_a_console_print_goes_to_the_log(qapp, logdir, monkeypatch):
    from app import errors
    monkeypatch.setattr(sys, "stderr", None)
    errors.setup_logging(str(logdir))
    print("message for the console", file=sys.stderr)
    assert "message for the console" in _log_text(logdir)


def test_a_hard_crash_is_found_at_the_next_start(tmp_path):
    folder = tmp_path / "logs"
    code = ("import os, sys; os.environ['QT_QPA_PLATFORM'] = 'offscreen'; sys.path.insert(0, %r)\n"
            "from app import errors\nerrors.setup_logging(%r)\nimport faulthandler\nfaulthandler._sigsegv()\n"
            % (ROOT, str(folder)))
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=120)
    assert res.returncode != 0
    assert (folder / "crash.txt").stat().st_size > 0
    code2 = ("import os, sys; sys.path.insert(0, %r)\nfrom app import errors\nerrors.setup_logging(%r)\n"
             "print('CRASH' if 'Fatal Python error' in errors.previous_crash() else 'none')\n"
             "errors.shutdown_logging()\n" % (ROOT, str(folder)))
    res = subprocess.run([sys.executable, "-c", code2], capture_output=True, text=True, timeout=120)
    assert res.stdout.strip() == "CRASH"
    assert "previous session ended in a crash" in (folder / "potential-flow-lab.log").read_text(encoding="utf-8")
    assert not (folder / "crash.txt").exists()            # a normal end removes it


def test_help_menu_opens_the_log_folder(qapp):
    from app.main_window import MainWindow
    w = MainWindow()
    try:
        names = [a.text() for m in w.menuBar().actions() if m.menu() for a in m.menu().actions()]
        assert "Open log folder" in names
    finally:
        w.close()
