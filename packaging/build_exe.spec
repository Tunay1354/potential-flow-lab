# PyInstaller spec of the program (ROADMAP 24). Build from the project folder:
#     pip install -r requirements-dev.txt
#     pyinstaller packaging/build_exe.spec
# Result: dist/<APP_NAME>/ — the exe + an _internal folder (bundled fonts, icons, presets); zip that folder.
# Numba compiles its kernels at the first start (~10 s, the loading screen says so) and keeps them in the
# user's cache folder (Windows: %LOCALAPPDATA%\numba); later starts load them (< 1 s).
import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
sys.path.insert(0, ROOT)
from app_info import APP_NAME  # noqa: E402  (the exe is named after the program)

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "assets"), "assets"), (os.path.join(ROOT, "presets"), "presets")],
    excludes=["tkinter", "matplotlib", "scipy", "pytest", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=APP_NAME, console=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name=APP_NAME, upx=False)
