"""Shared test setup. GUI tests run without opening windows (Qt 'offscreen' platform)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    """One QApplication for all GUI tests (skipped if PySide6 is not installed)."""
    widgets = pytest.importorskip("PySide6.QtWidgets")
    from app.main_window import setup_application
    app = widgets.QApplication.instance() or widgets.QApplication([])
    setup_application(app)
    return app
