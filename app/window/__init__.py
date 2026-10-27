"""
window — the parts of MainWindow (app/main_window.py), one mixin class per concern:

    layout.py     side panels, palette left / right, remembering / resetting the layout
    menus.py      element palette, menus, keyboard shortcuts
    files.py      New / Open / Save / Save as, presets, dropped scene files
    exporting.py  Export figure / Export data
    status.py     status bar (probe, scene check), error strip, window title, title block
"""
from .exporting import ExportMixin
from .files import FilesMixin
from .layout import LayoutMixin
from .menus import MenusMixin
from .status import StatusMixin

__all__ = ["ExportMixin", "FilesMixin", "LayoutMixin", "MenusMixin", "StatusMixin"]
