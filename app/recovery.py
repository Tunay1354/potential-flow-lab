"""
recovery.py — the scene is never lost when the program does not close normally (a crash, the computer
switched off, the process killed).

While the scene has unsaved changes, a copy is written a few seconds after the last change (and after a
change of the view) into the program's data folder: recovery/session-<id>.pflow (the normal scene format,
with the plot settings) + .json (which file it was, its title, the time). A session holds a lock file
(QLockFile) while it runs. When the scene is saved, or the changes are undone back to the saved state, or the
program closes normally, the copy is removed.

At the next start, a copy whose session is no longer running (its lock is stale) means that session did not
end normally: MainWindow.offer_recovery asks "Restore it?" — the scene comes back as an unsaved change of
the current one (Undo goes back), with its file name if it had one. Several programs open at once each keep
their own copy and never touch the others'.
"""
from __future__ import annotations

import datetime
import glob
import json
import os
from dataclasses import dataclass

from PySide6.QtCore import QLockFile, QObject, QStandardPaths, QTimer

from model.scene_file import SceneFileError, dumps, loads

AUTOSAVE_DELAY_MS = 3000


def recovery_folder() -> str:
    base = QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation) or os.path.expanduser("~")
    return os.path.join(base, "recovery")


@dataclass
class RecoveredScene:
    """A copy left by a session that did not end normally."""
    scene_path: str
    meta: dict
    lock: QLockFile                       # held while the user decides (another program cannot take it)

    @property
    def title(self) -> str:
        return self.meta.get("title") or "untitled"

    @property
    def original(self) -> str | None:
        return self.meta.get("path")

    @property
    def when(self) -> str:
        try:
            t = datetime.datetime.fromisoformat(self.meta["saved_at"])
            return f"{t:%d %b %Y, %H:%M}"
        except (KeyError, ValueError):
            return "unknown time"

    def document(self):
        with open(self.scene_path, encoding="utf-8") as f:
            return loads(f.read(), "the recovered scene")

    def discard(self):
        """Delete the copy and its session files."""
        stem = os.path.splitext(self.scene_path)[0]
        for ext in (".pflow", ".json"):
            _remove(stem + ext)
        self.lock.unlock()
        _remove(stem + ".lock")

    def release(self):
        """Keep the copy for the next start (Not now)."""
        self.lock.unlock()


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def find_recoverable(folder: str | None = None, exclude: str | None = None) -> list[RecoveredScene]:
    """Copies of sessions that are not running any more (newest first). Each found copy stays locked until
    discard() / release()."""
    folder = folder or recovery_folder()
    out = []
    for path in glob.glob(os.path.join(folder, "session-*.pflow")):
        stem = os.path.splitext(path)[0]
        if exclude and os.path.abspath(stem) == os.path.abspath(exclude):
            continue
        lock = QLockFile(stem + ".lock")
        lock.setStaleLockTime(0)                         # stale only when its program is gone
        if not lock.tryLock(0):
            continue                                     # that program is still running
        try:
            with open(stem + ".json", encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, ValueError):
            meta = {}
        out.append(RecoveredScene(path, meta, lock))
    out.sort(key=lambda r: r.meta.get("saved_at", ""), reverse=True)
    return out


class SessionRecovery(QObject):
    """The copy of this session's scene (see the module docstring). `document()` gives the scene as it
    would be saved, `modified()` whether it has unsaved changes, `info()` the file path and title."""

    def __init__(self, document, modified, info, folder: str | None = None, parent=None):
        super().__init__(parent)
        self._document, self._modified, self._info = document, modified, info
        self.folder = folder or recovery_folder()
        os.makedirs(self.folder, exist_ok=True)
        sid = f"{datetime.datetime.now():%Y%m%d-%H%M%S}-{os.getpid()}"
        self.stem = os.path.join(self.folder, f"session-{sid}")
        self.lock = QLockFile(self.stem + ".lock")      # taken with the first copy (no files before that)
        self.lock.setStaleLockTime(0)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(AUTOSAVE_DELAY_MS)
        self.timer.timeout.connect(self.save_now)
        self.saved = False                               # a copy exists now
        self.closed = False

    @property
    def scene_path(self) -> str:
        return self.stem + ".pflow"

    def changed(self, *_):
        """The scene / view changed: a copy a few seconds later — or none, if nothing is unsaved."""
        if self.closed:
            return
        if self._modified():
            self.timer.start()
        else:
            self.timer.stop()
            self.remove()

    def save_now(self):
        if self.closed or not self._modified():
            return
        try:
            if not self.lock.isLocked():
                self.lock.tryLock(0)
            text = dumps(self._document())
            path, title = self._info()
            meta = {"path": path, "title": title, "saved_at": datetime.datetime.now().isoformat(timespec="seconds")}
            for target, content in ((self.scene_path, text), (self.stem + ".json", json.dumps(meta, indent=1))):
                tmp = target + ".tmp"
                with open(tmp, "w", encoding="utf-8", newline="\n") as f:
                    f.write(content)
                os.replace(tmp, target)
            self.saved = True
        except (OSError, SceneFileError, ValueError):
            import logging
            logging.getLogger("pflab").exception("autosave failed")

    def remove(self):
        if self.saved or os.path.exists(self.scene_path):
            _remove(self.scene_path)
            _remove(self.stem + ".json")
            self.saved = False

    def close(self):
        """The program closes normally: nothing to recover."""
        self.timer.stop()
        self.remove()
        self.closed = True
        if self.lock.isLocked():
            self.lock.unlock()
