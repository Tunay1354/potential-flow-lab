"""
window — the parts of MainWindow (app/main_window.py), one mixin class per concern:

    layout.py     side panels, palette left / right, remembering / resetting the layout
    menus.py      element palette, menus, keyboard shortcuts
    files.py      New / Open / Save / Save as, presets, dropped scene files, restore after a restart / crash
    exporting.py  Export figure / animation / data
    status.py     status bar (probe, scene check; issues_popup.py), error strip, window title, title block
    graphics.py   drawing with the graphics card (GPU box, Graphics card panel, the faster laptop card)
"""
from .exporting import ExportMixin
from .files import FilesMixin
from .graphics import GraphicsMixin
from .layout import LayoutMixin
from .menus import MenusMixin
from .status import StatusMixin

__all__ = ["ExportMixin", "FilesMixin", "GraphicsMixin", "LayoutMixin", "MenusMixin", "StatusMixin"]
