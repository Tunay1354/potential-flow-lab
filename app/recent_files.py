"""
recent_files.py — the "Open recent" list and the last used folder, remembered between sessions.

Stored with QSettings (Windows: the registry under HKEY_CURRENT_USER\\Software\\IZTECH\\<APP_NAME>), so it
survives restarts and needs no file of our own.
"""
import os

from PySide6.QtCore import QSettings


class RecentFiles:
    KEY = "recent_files"
    DIR_KEY = "last_folder"

    def __init__(self, settings: QSettings | None = None, limit: int = 8):
        self.settings = settings or QSettings()
        self.limit = limit

    def paths(self) -> list[str]:
        val = self.settings.value(self.KEY, [])
        if isinstance(val, str):                 # QSettings returns a single entry as a plain string
            val = [val]
        return [str(p) for p in (val or []) if p]

    def add(self, path: str):
        path = os.path.abspath(path)
        key = os.path.normcase(path)             # Windows: C:\\A.pflow and c:\\a.pflow are the same file
        items = [path] + [p for p in self.paths() if os.path.normcase(p) != key]
        self.settings.setValue(self.KEY, items[:self.limit])
        self.last_folder = os.path.dirname(path)

    def remove(self, path: str):
        key = os.path.normcase(os.path.abspath(path))
        self.settings.setValue(self.KEY, [p for p in self.paths() if os.path.normcase(p) != key])

    def clear(self):
        self.settings.setValue(self.KEY, [])

    @property
    def last_folder(self) -> str:
        folder = self.settings.value(self.DIR_KEY, "")
        if folder and os.path.isdir(folder):
            return str(folder)
        docs = os.path.join(os.path.expanduser("~"), "Documents")
        return docs if os.path.isdir(docs) else os.path.expanduser("~")

    @last_folder.setter
    def last_folder(self, folder: str):
        self.settings.setValue(self.DIR_KEY, folder)
