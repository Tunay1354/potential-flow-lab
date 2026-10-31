# PyInstaller spec of Flowy (Potential Flow Lab) (Faz 5).   Build (from the project folder):
#     pip install pyinstaller
#     pyinstaller packaging/potential_flow_lab.spec
# Result: dist/Flowy/ (the exe + an _internal folder with the bundled files and presets);
# zip that folder to share it.
#
# Numba: the exe compiles its kernels at the first start (~10 s, the window says so) and keeps them in
# the user's cache folder (Windows: %LOCALAPPDATA%\numba); later starts load them (< 1 s). A new exe
# (other size / date) compiles once again. Checked on Linux (27 Oct): 1st start ~18 s CPU, 2nd ~2 s.
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
NAME = "Flowy"

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "assets"), "assets"), (os.path.join(ROOT, "presets"), "presets")],
    excludes=["tkinter", "matplotlib", "scipy", "pytest", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=NAME, console=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name=NAME, upx=False)
