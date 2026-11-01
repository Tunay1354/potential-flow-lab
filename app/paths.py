"""
paths.py — where the program's files are, the same way in the source folder and in the exe.

    ROOT          the program folder: the source checkout, or the exe's bundle folder (PyInstaller puts
                  the bundled files in sys._MEIPASS)
    ASSETS_DIR    fonts, icons
    PRESETS_DIR   the preset scenes (Presets menu)

The compiled Numba kernels need no path here: run from the source folder they are cached in
__pycache__; in the exe Numba keeps them in the user's cache folder by itself (Windows:
%LOCALAPPDATA%\\numba), so only the first start after installing / updating compiles (checked with
packaging/build_exe.spec).
"""
import os
import sys

ROOT = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS_DIR = os.path.join(ROOT, "assets")
PRESETS_DIR = os.path.join(ROOT, "presets")
