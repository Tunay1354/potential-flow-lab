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
