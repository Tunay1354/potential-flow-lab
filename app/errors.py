"""
errors.py — what happens when something goes wrong.

  setup_logging()     a log file in the program's data folder (logs/<name>.log, at most 3 × 1 MB):
                      start-up information, every unexpected error with its traceback, Qt's warnings.
                      The exe has no console: print / sys.stderr go to the log there. Hard crashes (the whole
                      process dies, e.g. in compiled code) are written by faulthandler to logs/crash.txt; the
                      next start copies them into the log (previous_crash() says if there was one).
  ErrorReporter       an error that nobody caught — in a button handler, in drawing, in a background
                      computation re-raised in the window — no longer just disappears: it is logged and a
                      window says what happened (details, copy, open the log folder). The program stays open.
                      The same error is reported once (repeats are only counted in the log), and never
                      several windows at once.
"""
from __future__ import annotations

import faulthandler
import logging
import logging.handlers
import os
import platform
import sys
import threading
import traceback

from PySide6.QtCore import QObject, QStandardPaths, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QStyle, QVBoxLayout)

from app_info import APP_NAME

LOG_NAME = f"{APP_NAME.lower()}.log"
CRASH_NAME = "crash.txt"
log = logging.getLogger("pflab")

_state = {"folder": None, "crash_file": None, "previous_crash": "", "handler": None}


# ---------------------------------------------------------------------- the log file
def log_folder() -> str:
    if _state["folder"]:
        return _state["folder"]
    base = QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation) or os.path.expanduser("~")
    return os.path.join(base, "logs")


def log_path() -> str:
    return os.path.join(log_folder(), LOG_NAME)


class _LogStream:
    """sys.stdout / sys.stderr of the exe (which has none): lines go to the log."""

    def __init__(self, level):
        self.level, self._buf = level, ""

    def write(self, text):
        self._buf += str(text)
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                log.log(self.level, line)
        return len(text)

    def flush(self):
        pass

    def isatty(self):
        return False


def setup_logging(folder: str | None = None) -> str:
    """Start the log (again: a new folder replaces the old one — tests). Returns the log file path."""
    if folder:
        _state["folder"] = folder
    folder = log_folder()
    os.makedirs(folder, exist_ok=True)
    path = log_path()
    old = _state["handler"]
    if old is None or old.baseFilename != os.path.abspath(path):
        if old is not None:
            log.removeHandler(old)
            old.close()
            _close_crash_file(remove=False)
        handler = logging.handlers.RotatingFileHandler(path, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        log.propagate = False
        _state["handler"] = handler
    if sys.stderr is None:                     # the exe (no console)
        sys.stderr = _LogStream(logging.WARNING)
    if sys.stdout is None:
        sys.stdout = _LogStream(logging.INFO)
    _start_faulthandler(folder)
    log.info("=" * 60)
    log.info("start: %s", _versions())
    return path


def _versions() -> str:
    from app_info import APP_VERSION
    parts = [f"{APP_NAME} {APP_VERSION}", f"Python {platform.python_version()}", platform.platform()]
    try:
        import PySide6
        parts.append(f"PySide6 {PySide6.__version__}")
    except Exception:                                 # noqa: BLE001
        pass
    try:
        import numpy
        parts.append(f"NumPy {numpy.__version__}")
        import numba
        parts.append(f"Numba {numba.__version__}")
    except Exception:                                 # noqa: BLE001 - Numba is optional
        parts.append("no Numba")
    if getattr(sys, "frozen", False):
        parts.append("exe")
    return " · ".join(parts)


def _start_faulthandler(folder):
    """A hard crash (the process itself dies) writes its stack to crash.txt; copied into the log at the
    next start."""
    path = os.path.join(folder, CRASH_NAME)
    _state["previous_crash"] = ""
    try:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
            _state["previous_crash"] = text
            log.error("the previous session ended in a crash:\n%s", text.rstrip())
        if _state["crash_file"] is None:
            _state["crash_file"] = open(path, "w", encoding="utf-8")   # (kept open: faulthandler writes to it)
            faulthandler.enable(_state["crash_file"], all_threads=True)
    except OSError:                                   # pragma: no cover - read-only folder: no crash file
        pass


def previous_crash() -> str:
    """The stack written by the previous session's hard crash ('' if it ended normally)."""
    return _state["previous_crash"]


def _close_crash_file(remove: bool):
    f = _state["crash_file"]
    if f is None:
        return
    try:
        faulthandler.disable()
        f.close()
        if remove:
            os.remove(f.name)
    except OSError:                                   # pragma: no cover
        pass
    _state["crash_file"] = None


def shutdown_logging():
    """Normal end of the program: no crash to report next time."""
    _close_crash_file(remove=True)
    log.info("end")


# ---------------------------------------------------------------------- unexpected errors
def _signature(exc_type, exc, tb) -> str:
    """The same error from the same place = the same signature (reported once)."""
    frames = traceback.extract_tb(tb)
    where = f"{frames[-1].filename}:{frames[-1].lineno}" if frames else ""
    return f"{exc_type.__name__}@{where}"


class ErrorReporter(QObject):
    """sys.excepthook / threading.excepthook / Qt messages → the log, and a window for the user."""
    _report = Signal(str, str, str)              # signature, one-line message, details (thread-safe: queued)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.window_parent = None                # the main window (dialogs are centered on it)
        self.shown: dict[str, int] = {}          # signature → how often it happened
        self.dialog: ErrorDialog | None = None
        self.waiting: list = []                  # errors that came while a window was open
        self.enabled_dialogs = True              # False: only logged (tests)
        self._report.connect(self._on_report, Qt.QueuedConnection)
        self._old = None

    def install(self):
        self._old = (sys.excepthook, threading.excepthook)
        sys.excepthook = self.handle
        threading.excepthook = lambda args: self.handle(args.exc_type, args.exc_value, args.exc_traceback)
        return self

    def uninstall(self):
        if self._old:
            sys.excepthook, threading.excepthook = self._old
            self._old = None

    def handle(self, exc_type, exc, tb):
        """An error nobody caught (any thread)."""
        if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            sys.__excepthook__(exc_type, exc, tb)
            return
        sig = _signature(exc_type, exc, tb)
        n = self.shown.get(sig, 0) + 1
        self.shown[sig] = n
        details = "".join(traceback.format_exception(exc_type, exc, tb))
        if n == 1:
            log.error("unexpected error (%s):\n%s", threading.current_thread().name, details.rstrip())
        elif n in (2, 10, 100, 1000):
            log.error("the same error again (%d times): %s", n, sig)
        if n == 1:
            message = f"{exc_type.__name__}: {exc}" if str(exc) else exc_type.__name__
            self._report.emit(sig, message, details)

    def _on_report(self, sig, message, details):
        if not self.enabled_dialogs:
            return
        if self.dialog is not None:
            self.waiting.append((sig, message, details))
            return
        self.dialog = ErrorDialog(message, details, self.window_parent)
        self.dialog.finished.connect(self._closed)
        self.dialog.show()
        self.dialog.raise_()

    def _closed(self, *_):
        self.dialog.deleteLater()
        self.dialog = None
        if self.waiting:
            more = self.waiting
            self.waiting = []
            sig, message, details = more[0]
            if len(more) > 1:
                message += f"\n\n(+ {len(more) - 1} more error{'s' if len(more) > 2 else ''} — all in the log)"
            QTimer.singleShot(0, lambda: self._on_report(sig, message, details))


class ErrorDialog(QDialog):
    """'Something went wrong' — what, where the details are, and that the work is not lost."""

    def __init__(self, message: str, details: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Unexpected error")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.details_text = details
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)
        top = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(self.style().standardIcon(QStyle.SP_MessageBoxWarning).pixmap(36, 36))
        icon.setAlignment(Qt.AlignTop)
        top.addWidget(icon)
        text = QLabel("<b>Something went wrong inside the program.</b><br>The program is still running and "
                      "your scene is not lost — you can go on working (saving it now is a good idea). The "
                      "error has been written to the log file; if it happens again, please send that file.")
        text.setWordWrap(True)
        top.addWidget(text, 1)
        lay.addLayout(top)
        what = QLabel(message)
        what.setObjectName("Muted")
        what.setWordWrap(True)
        what.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(what)
        self.details = QPlainTextEdit(details)
        self.details.setReadOnly(True)
        self.details.setVisible(False)
        self.details.setMinimumHeight(220)
        self.details.setLineWrapMode(QPlainTextEdit.NoWrap)
        try:
            from app.theme import first_family
            self.details.setStyleSheet(f"font-family: '{first_family('mono')}'; font-size: 8.5pt;")
        except Exception:                             # noqa: BLE001 - only the look
            pass
        lay.addWidget(self.details, 1)
        where = QLabel(f"Log file: {log_path()}")
        where.setObjectName("Muted")
        where.setWordWrap(True)
        where.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(where)
        row = QHBoxLayout()
        self.btn_details = QPushButton("Show details")
        self.btn_details.clicked.connect(self._toggle)
        copy = QPushButton("Copy details")
        copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(f"{_versions()}\n\n{self.details_text}"))
        folder = QPushButton("Open log folder")
        folder.clicked.connect(open_log_folder)
        ok = QPushButton("Continue")
        ok.setObjectName("Primary")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        for b in (self.btn_details, copy, folder):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(ok)
        lay.addLayout(row)
        self.resize(560, 220)

    def _toggle(self):
        show = not self.details.isVisible()
        self.details.setVisible(show)
        self.btn_details.setText("Hide details" if show else "Show details")
        self.resize(self.width(), 480 if show else 220)


def open_log_folder():
    folder = log_folder()
    os.makedirs(folder, exist_ok=True)
    QDesktopServices.openUrl(QUrl.fromLocalFile(folder))


def qt_message_handler(mode, context, message):
    """Qt's own warnings: into the log (and the console, if there is one)."""
    from PySide6.QtCore import QtMsgType
    if "propagateSizeHints" in message:            # offscreen platform noise
        return
    if mode in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
        log.warning("Qt: %s", message)
    if sys.__stderr__ is not None:
        print(message, file=sys.__stderr__)
