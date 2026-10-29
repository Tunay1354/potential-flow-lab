"""
startup.py — application settings made before anything else (light: only PySide6 and the theme, so the
loading screen can appear before the heavy modules — pyqtgraph, Numba, the physics — are imported).
main_window.setup_application is this function (kept there for scripts and tests).
"""
from PySide6.QtGui import QFont

from app_info import APP_NAME, APP_VERSION, ORGANIZATION

from .chrome.style import load_fonts
from .theme import FONT


def setup_application(app):
    """Settings that must be identical on every computer (Windows TR/EN, macOS)."""
    import sys

    from PySide6.QtCore import QLocale
    # numbers always with a decimal POINT (1.000), whatever the system region is (TR uses 1,000)
    QLocale.setDefault(QLocale(QLocale.English, QLocale.UnitedStates))
    # the streamline thread and the window share Python's interpreter lock (GIL); hand it over every
    # 0.5 ms instead of every 5 ms, so drawing never waits long for the background computation
    sys.setswitchinterval(0.0005)
    app.setOrganizationName(ORGANIZATION)        # where QSettings keeps recent files etc.
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyle("Fusion")          # same look on Windows and macOS
    load_fonts()                    # bundled fonts (assets/fonts), the same on every computer
    app.setFont(default_font())


def default_font():
    from PySide6.QtGui import QFontDatabase
    families = set(QFontDatabase.families())
    f = QFont()
    for fam in FONT["families"]:
        if fam in families:
            f.setFamily(fam)
            break
    f.setPointSizeF(FONT["size_pt"])
    return f
