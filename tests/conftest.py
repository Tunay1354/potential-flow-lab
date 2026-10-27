"""Shared test setup. GUI tests run without opening windows (Qt 'offscreen' platform)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def qapp(tmp_path_factory):
    """One QApplication for all GUI tests (skipped if PySide6 is not installed).
    Settings (recent files ...) go to a temporary folder, never to the user's real settings."""
    widgets = pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtCore import QSettings
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path_factory.mktemp("settings")))
    from app.main_window import setup_application
    app = widgets.QApplication.instance() or widgets.QApplication([])
    setup_application(app)
    return app


@pytest.fixture(autouse=True)
def fresh_layout():
    """Every test starts with the default window layout and keyboard shortcuts."""
    try:
        from PySide6.QtCore import QSettings
    except ImportError:                       # pragma: no cover
        yield
        return
    for group in ("layout", "shortcuts", "export"):
        QSettings().remove(group)
    yield
    for group in ("layout", "shortcuts", "export"):
        QSettings().remove(group)


@pytest.fixture(autouse=True)
def collect_garbage_between_tests():
    """Qt objects left over by a test (also those kept alive by a failed test's traceback) are
    destroyed right after it, while no background computation of a later window is running.
    A later garbage collection could otherwise delete them in the middle of another test."""
    yield
    import gc
    gc.collect()
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:                       # pragma: no cover
        return
    app = QApplication.instance()
    if app is not None:
        app.processEvents()
