"""
paths.py — where the program's files are, the same way in the source folder and in the exe.

    ROOT          the program folder: the source checkout, or the exe's bundle folder (PyInstaller puts
                  the bundled files in sys._MEIPASS)
    ASSETS_DIR    fonts, icons
    PRESETS_DIR   the preset scenes (Presets menu)
    data_folder   the program's own data (logs, recovery copies, restart state, GPU guard, verification report)
    outside_path  a path as other programs (the browser, Explorer) see it — for "Open folder / report"

The compiled Numba kernels need no path here: run from the source folder they are cached in
__pycache__; in the exe Numba keeps them in the user's cache folder by itself (Windows:
%LOCALAPPDATA%\\numba), so only the first start after installing / updating compiles (checked with
packaging/build_exe.spec).
"""
import glob
import ntpath
import os
import sys

ROOT = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS_DIR = os.path.join(ROOT, "assets")
PRESETS_DIR = os.path.join(ROOT, "presets")


def data_folder(*parts: str) -> str:
    """A folder of the program's data: Windows %LOCALAPPDATA%\\<ORGANIZATION>\\<APP_NAME>\\<parts>
    (Qt's AppLocalDataLocation; the home folder if there is none)."""
    from PySide6.QtCore import QStandardPaths
    base = QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation) or os.path.expanduser("~")
    return os.path.join(base, *parts)


def outside_path(path: str) -> str:
    """The same file or folder as the browser and Explorer see it. Python from the Microsoft Store runs as a
    packaged app: what it writes under %LOCALAPPDATA% really lands in
    %LOCALAPPDATA%\\Packages\\<its package>\\LocalCache\\Local\\…, and only this program finds it at the usual
    place ("Open log folder" opened an empty or missing folder). Anywhere else — python.org Python, the exe,
    other systems — the path itself."""
    local = os.environ.get("LOCALAPPDATA")
    if sys.platform != "win32" or not local:
        return path
    try:
        rel = os.path.relpath(os.path.abspath(path), local)
    except ValueError:                                  # (another drive)
        return path
    if rel == ".." or rel.startswith(".." + os.sep):
        return path
    for package in _store_packages(local):
        candidate = os.path.join(local, "Packages", package, "LocalCache", "Local", rel)
        if os.path.exists(candidate):
            return candidate
    return path


def _store_packages(local: str) -> list:
    """Package folders of a Microsoft Store Python, the one this program runs on first ([] for other Pythons).
    sys.base_prefix is e.g. …\\WindowsApps\\PythonSoftwareFoundation.Python.3.13_3.13.2032.0_x64__qbz5n2kfra8p0,
    its data folder Packages\\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0."""
    base = ntpath.basename(ntpath.normpath(sys.base_prefix))
    if not base.startswith("PythonSoftwareFoundation.Python"):
        return []
    out = [base.split("_")[0] + "_" + base.split("__")[-1]] if "__" in base else []
    out += sorted(os.path.basename(p) for p in glob.glob(os.path.join(local, "Packages",
                                                                       "PythonSoftwareFoundation.Python.*")))
    return list(dict.fromkeys(out))
