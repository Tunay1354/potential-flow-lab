"""
startup.py — application settings made before anything else (light: only PySide6 and the theme, so the
loading screen can appear before the heavy modules — pyqtgraph, Numba, the physics — are imported).
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
    app.setOrganizationName(ORGANIZATION)        # settings and data folder: …/ORGANIZATION/APP_NAME
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyle("Fusion")          # same look on Windows and macOS
    load_fonts()                    # bundled fonts (assets/fonts), the same on every computer
    app.setFont(default_font())


PREPARED_KEY = "startup/prepared"          # signature of the last start that prepared everything (main.py)


def prepared_signature() -> str:
    """What the prepared fast engine (Numba's cache) and the found hardware depend on: the program's version,
    Python, and the physics sources (a pulled update recompiles). Only file sizes and times: instant."""
    import os
    import platform
    import sys
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "physics")
    stamp = 0
    for folder, _dirs, files in os.walk(root):
        for name in files:
            if name.endswith(".py"):
                try:
                    st = os.stat(os.path.join(folder, name))
                    stamp = (stamp * 31 + st.st_size * 1000003 + int(st.st_mtime)) % (1 << 61)
                except OSError:
                    pass
    return f"{APP_VERSION}|{sys.version.split()[0]}|{platform.machine()}|{stamp}"


def is_first_start() -> bool:
    """First start on this computer (or after an update): the loading screen says it takes a while."""
    from PySide6.QtCore import QSettings
    s = QSettings()
    return s.value(PREPARED_KEY, "") != prepared_signature() or not s.contains("hardware/profile")


def mark_prepared():
    from PySide6.QtCore import QSettings
    QSettings().setValue(PREPARED_KEY, prepared_signature())


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
