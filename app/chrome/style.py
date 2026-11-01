"""
style.py — bundled fonts, colors and small Qt styling helpers shared by the whole window
(1-pixel lines at any display scaling, themed combo boxes, the Windows title bar color).
"""
import glob
import os
import sys

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import QComboBox, QStyledItemDelegate

from ..paths import ASSETS_DIR
from ..theme import FONT, first_family

_fonts_loaded = False


def load_fonts():
    """Register the bundled fonts (IBM Plex Mono, Barlow, Barlow Condensed) once per process."""
    global _fonts_loaded
    if _fonts_loaded:
        return
    for path in sorted(glob.glob(os.path.join(ASSETS_DIR, "fonts", "*", "*.ttf"))):
        QFontDatabase.addApplicationFont(path)
    _fonts_loaded = True


def color(value: str) -> QColor:
    """QColor from '#RRGGBB' or '#RRGGBBAA' (CSS order; Qt itself reads 8 digits as #AARRGGBB)."""
    if len(value) == 9:
        c = QColor(value[:7])
        c.setAlpha(int(value[7:9], 16))
        return c
    return QColor(value)


def font(kind: str, size_pt: float, weight=QFont.Normal, caps=False, spacing_pct=100.0) -> QFont:
    """Font of a family list in FONT ("families", "mono", "heading"); caps = shown in capitals,
    spacing_pct = letter spacing in percent of the normal spacing."""
    f = QFont(first_family(kind))
    f.setPointSizeF(size_pt)
    f.setWeight(weight)
    if caps:
        f.setCapitalization(QFont.AllUppercase)
    if spacing_pct != 100.0:
        f.setLetterSpacing(QFont.PercentageSpacing, spacing_pct)
    return f


def heading_font(size_pt=None) -> QFont:
    return font("heading", size_pt or FONT["heading_size_pt"], QFont.Bold, caps=True, spacing_pct=118)


def button_font() -> QFont:
    return font("heading", FONT["button_size_pt"], QFont.DemiBold, caps=True, spacing_pct=108)


def themed_combo(combo):
    """Drop-down list whose items follow the style sheet (padding, hover color); Fusion's default
    menu-like delegate would ignore it."""
    combo.setItemDelegate(QStyledItemDelegate(combo))
    # the field may be narrower than its longest item (the open list still shows the whole text)
    combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(8)
    return combo


def device_line_rect(widget) -> QRectF:
    """Rectangle whose border, drawn with a cosmetic 1 px pen, lies on the outermost DEVICE pixels of
    `widget` (also at 125 % / 150 % display scaling, where logical pixels are not whole pixels)."""
    h = 0.5 / widget.devicePixelRatioF()
    return QRectF(h, h, widget.width() - 2 * h, widget.height() - 2 * h)


def tint_title_bar(window, theme: dict):
    """Windows 11: color the window's title bar in the header wood (otherwise Windows uses its own
    accent color, e.g. purple). Does nothing on other systems or older Windows versions."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        def colorref(hex_color):
            c = QColor(hex_color)
            return wintypes.DWORD(c.red() | (c.green() << 8) | (c.blue() << 16))

        hwnd = wintypes.HWND(int(window.winId()))
        set_attr = ctypes.windll.dwmapi.DwmSetWindowAttribute
        for attr, value in ((35, theme["plank"]), (36, theme["plank_text"]), (34, theme["plank_edge"])):
            ref = colorref(value)     # 35 caption, 36 caption text, 34 border (Windows 11 build 22000+)
            set_attr(hwnd, attr, ctypes.byref(ref), ctypes.sizeof(ref))
    except Exception:              # pragma: no cover - only on unusual Windows setups
        pass
