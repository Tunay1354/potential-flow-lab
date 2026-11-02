# PyInstaller spec of the program (ROADMAP 24). Build from the project folder:
#     pip install -r requirements-dev.txt
#     pyinstaller --noconfirm packaging/build_exe.spec
# Result: dist/<APP_NAME>/ — the exe + an _internal folder (bundled fonts, icons, presets, ffmpeg); zip that
# folder. GitHub builds it on Windows by itself (.github/workflows/windows-build.yml) and puts the zip on the
# Releases page. Numba compiles its kernels at the first start (the loading screen says so) and keeps them in
# the user's cache folder (Windows: %LOCALAPPDATA%\numba); later starts load them.
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
sys.path.insert(0, ROOT)
from app_info import APP_NAME  # noqa: E402  (the exe is named after the program)

ICON = os.path.join(workpath, APP_NAME + ".ico")                         # the logo (packaging/make_icon.py)
subprocess.run([sys.executable, os.path.join(SPECPATH, "make_icon.py"), ICON], check=True)

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "assets"), "assets"), (os.path.join(ROOT, "presets"), "presets")],
    # (not used by the program: Qt's QML / Quick / PDF / web parts, test tools, other plotting libraries)
    excludes=["tkinter", "matplotlib", "scipy", "pytest", "IPython", "yaml",
              "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtPdf",
              "PySide6.QtVirtualKeyboard", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=APP_NAME, console=False, upx=False, icon=ICON)
coll = COLLECT(exe, a.binaries, a.datas, name=APP_NAME, upx=False)
