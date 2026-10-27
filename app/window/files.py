"""
files.py — part of MainWindow: the scene as a file. File → New / Open / Open recent / Save / Save as,
presets, a .pflow file dropped on the window, and the "unsaved changes" question.

The dialogs (_ask_* and _notify_user) are separate methods so the tests can answer them.
"""
import os
import re

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog, QMessageBox

from app_info import APP_NAME
from model import EXTENSION, SceneDocument, SceneFileError
from model import load_scene as read_scene_file
from model import save_scene as write_scene_file

from ..theme import LAYOUT

FILE_FILTER = f"{APP_NAME} scenes (*{EXTENSION});;JSON files (*.json);;All files (*)"


def safe_file_name(text: str, fallback: str) -> str:
    """`text` without the characters Windows does not allow in file names."""
    return re.sub(r'[\\/:*?"<>|]+', " ", text).strip() or fallback


class FilesMixin:

    def new_scene(self):
        """File → New: empty scene, default view, empty undo history."""
        if not self.maybe_save():
            return False
        rng = LAYOUT["plot_initial_range"]
        self.canvas.set_view(rng["x"], rng["y"])
        self.current_path = None
        self.scene_title = "untitled"
        self.model.reset([])
        self.flash("New scene — add elements from the toolbar or choose a preset.")
        return True

    def open_scene(self, path: str | None = None):
        """File → Open (asks for a file when `path` is None), Open recent, drag & drop, command line."""
        if not self.maybe_save():
            return False
        if path is None:
            path = self._ask_open_path()
            if not path:
                return False
        try:
            doc = read_scene_file(path)
        except SceneFileError as exc:
            self._notify_user("warning", "Cannot open the file", str(exc))
            if not os.path.exists(path):
                self.recent.remove(path)
            return False
        self._apply_document(doc)
        self.current_path = os.path.abspath(path)
        self.scene_title = doc.title or os.path.splitext(os.path.basename(path))[0]
        self.recent.add(path)
        self._update_title()
        self.flash(f"Opened {os.path.basename(path)}  —  {len(doc.elements)} elements")
        if doc.warnings:
            self._notify_user("information", "File opened with small problems",
                              "The file was opened, but:\n\n• " + "\n• ".join(doc.warnings))
        return True

    def save_scene(self) -> bool:
        """File → Save (asks for a name the first time). Returns False if cancelled or failed."""
        if self.current_path is None:
            return self.save_scene_as()
        return self._write(self.current_path)

    def save_scene_as(self) -> bool:
        base = safe_file_name(self.scene_title if self.scene_title != "untitled" else "scene", "scene")
        start = os.path.dirname(self.current_path) if self.current_path else self.recent.last_folder
        path = self._ask_save_path(os.path.join(start, base + EXTENSION))
        if not path:
            return False
        if not os.path.splitext(path)[1]:
            path += EXTENSION
        if self.scene_title == "untitled":
            self.scene_title = os.path.splitext(os.path.basename(path))[0]
        return self._write(path)

    def _write(self, path: str) -> bool:
        try:
            write_scene_file(path, self._document())
        except SceneFileError as exc:
            self._notify_user("warning", "Cannot save the file", str(exc))
            return False
        self.current_path = os.path.abspath(path)
        self.model.mark_clean()
        self.recent.add(path)
        self._update_title()
        self.flash(f"Saved {os.path.basename(path)}")
        return True

    def _document(self) -> SceneDocument:
        """The current scene as it is saved: elements, title, view and plot settings."""
        cv = self.canvas
        return SceneDocument(list(self.elements), self.scene_title, cv.view(), cv.settings.to_document())

    def _apply_document(self, doc: SceneDocument):
        if doc.view is not None:
            self.canvas.set_view(*doc.view)
        settings = self.canvas.settings.updated(doc.settings)
        self.canvas.apply_settings(settings)
        self.settings_panel.show_settings(settings)
        self.model.reset(doc.elements)         # one computation with the new view + settings

    def maybe_save(self) -> bool:
        """Before the scene is replaced or the window closes: offer to save unsaved changes.
        True = go on, False = the user cancelled (or saving failed)."""
        if not self.model.is_modified:
            return True
        answer = self._ask_save_changes()
        if answer == "save":
            return self.save_scene()
        return answer == "discard"

    def load_preset(self, preset):
        """Presets menu: the preset becomes a new, unsaved scene (one undoable step)."""
        try:
            doc = read_scene_file(preset.path)
        except SceneFileError as exc:
            self._notify_user("warning", "Cannot load the preset", str(exc))
            return False
        self.load_scene(doc.elements, doc.view, title=doc.title or preset.title)
        return True

    def load_scene(self, elements, view=None, title=""):
        """Presets: replace the whole scene in ONE undoable step (File → Open starts a new history)."""
        if view:
            self.canvas.set_view(*view)
        self.scene_title = title or "untitled"
        self.current_path = None        # a preset is a new, unsaved scene (Save would not overwrite a file)
        self.model.load(elements, f"Load “{title}”" if title else "Load scene")
        self._flash_done()

    # ------------------------------------------------------------------ a scene file dropped on the window
    def dragEnterEvent(self, event):
        if self._dropped_file(event):
            event.acceptProposedAction()

    def dropEvent(self, event):
        path = self._dropped_file(event)
        if path:
            event.acceptProposedAction()
            QTimer.singleShot(0, self, lambda: self.open_scene(path))   # not inside the drop handler

    @staticmethod
    def _dropped_file(event) -> str | None:
        md = event.mimeData()
        for url in md.urls() if md.hasUrls() else []:
            path = url.toLocalFile()
            if path.lower().endswith((EXTENSION, ".json")):
                return path
        return None

    # ------------------------------------------------------------------ dialogs
    def _ask_save_changes(self) -> str:
        name = os.path.basename(self.current_path) if self.current_path else self.scene_title
        box = QMessageBox(QMessageBox.Warning, "Unsaved changes",
                          f"Do you want to save the changes to “{name}”?",
                          QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, self)
        box.setInformativeText("Your changes will be lost if you don't save them.")
        box.setDefaultButton(QMessageBox.Save)
        return {QMessageBox.Save: "save", QMessageBox.Discard: "discard"}.get(box.exec(), "cancel")

    def _ask_open_path(self) -> str:
        start = os.path.dirname(self.current_path) if self.current_path else self.recent.last_folder
        path, _ = QFileDialog.getOpenFileName(self, "Open scene", start, FILE_FILTER)
        return path

    def _ask_save_path(self, suggested: str) -> str:
        path, _ = QFileDialog.getSaveFileName(self, "Save scene as", suggested, FILE_FILTER)
        return path

    def _notify_user(self, kind: str, title: str, text: str):
        (QMessageBox.warning if kind == "warning" else QMessageBox.information)(self, title, text)
