"""
shortcuts.py — keyboard shortcuts the user can see and change (Edit → Keyboard shortcuts…).

Every command with a shortcut is registered once with its default key(s). A changed key is stored in
the program settings (QSettings, "shortcuts/<id>", portable text such as "Ctrl+Shift+S"), so it is
the same after a restart; "Reset all" goes back to the defaults.
"""
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (QDialog, QGridLayout, QHBoxLayout, QKeySequenceEdit, QLabel, QMessageBox,
                               QPushButton, QScrollArea, QToolButton, QVBoxLayout, QWidget)

from .chrome import heading_font

PORTABLE = QKeySequence.PortableText


def _text(seq: QKeySequence) -> str:
    return seq.toString(PORTABLE)


class Shortcuts:
    """id -> (action, label, group, default key texts). Changing keys updates the actions at once."""

    def __init__(self):
        self.entries = {}                       # in registration order (groups appear in that order)
        self.listeners = []                     # called after any change (e.g. tooltips with keys)

    def register(self, ident: str, action, label: str, group: str, default=None):
        if default is None:
            default = [_text(s) for s in action.shortcuts()]
        elif isinstance(default, str):
            default = [default] if default else []
        default = list(dict.fromkeys(k for k in default if k))     # no empty or repeated keys
        self.entries[ident] = {"action": action, "label": label, "group": group, "default": list(default)}
        action.setShortcuts([QKeySequence(k) for k in default])

    def keys(self, ident: str) -> list:
        return [_text(s) for s in self.entries[ident]["action"].shortcuts()]

    def first_key(self, ident: str) -> str:
        """The key as shown to the user (native text, e.g. 'Ctrl+S'), or ''."""
        seqs = self.entries[ident]["action"].shortcuts()
        return seqs[0].toString(QKeySequence.NativeText) if seqs else ""

    def set_keys(self, ident: str, keys: list, save: bool = True):
        self.entries[ident]["action"].setShortcuts([QKeySequence(k) for k in keys if k])
        if save:
            s = QSettings()
            if keys == self.entries[ident]["default"]:
                s.remove(f"shortcuts/{ident}")
            else:
                s.setValue(f"shortcuts/{ident}", ";".join(keys))

    def load(self):
        """Keys the user changed earlier (unknown ids in the settings are ignored)."""
        s = QSettings()
        for ident in self.entries:
            value = s.value(f"shortcuts/{ident}")
            if value is not None:
                self.set_keys(ident, [k for k in str(value).split(";") if k], save=False)
        self._notify()

    def reset_all(self):
        for ident, e in self.entries.items():
            self.set_keys(ident, e["default"])
        self._notify()

    def apply(self, changes: dict):
        for ident, keys in changes.items():
            self.set_keys(ident, keys)
        self._notify()

    def _notify(self):
        for fn in self.listeners:
            fn()

    @staticmethod
    def conflicts(assignment: dict) -> list:
        """[(key text, [ids])] of keys given to more than one command."""
        used = {}
        for ident, keys in assignment.items():
            for k in set(keys):
                used.setdefault(k, []).append(ident)
        return [(k, ids) for k, ids in used.items() if len(ids) > 1]


class ShortcutsDialog(QDialog):
    """Table of all commands with their key: click a field and press the new key combination;
    × clears it; 'Reset all' restores the defaults. Two commands may not share a key."""

    def __init__(self, shortcuts: Shortcuts, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard shortcuts")
        self.shortcuts = shortcuts
        self.edits = {}
        self.resize(560, 640)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)
        title = QLabel("Keyboard shortcuts")
        title.setObjectName("DialogTitle")
        lay.addWidget(title)
        hint = QLabel("Click a field and press the new key combination. × removes the shortcut.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        body = QWidget()
        body.setObjectName("DockBody")
        body.setAttribute(Qt.WA_StyledBackground, True)
        grid = QGridLayout(body)
        grid.setContentsMargins(10, 4, 10, 10)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        row, group = 0, None
        for ident, e in shortcuts.entries.items():
            if e["group"] != group:
                group = e["group"]
                h = QLabel(group)
                h.setFont(heading_font())
                h.setContentsMargins(0, 10 if row else 2, 0, 2)
                grid.addWidget(h, row, 0, 1, 3)
                row += 1
            grid.addWidget(QLabel(e["label"]), row, 0)
            edit = QKeySequenceEdit()
            keys = shortcuts.keys(ident)
            if keys:
                edit.setKeySequence(QKeySequence(keys[0]))
            if hasattr(edit, "setMaximumSequenceLength"):
                edit.setMaximumSequenceLength(1)        # one key combination (no "Ctrl+K, Ctrl+S")
            edit.setToolTip(f"Default: {', '.join(e['default']) or 'none'}")
            grid.addWidget(edit, row, 1)
            clear = QToolButton()
            clear.setText("×")
            clear.setToolTip("Remove this shortcut")
            clear.clicked.connect(edit.clear)
            grid.addWidget(clear, row, 2)
            self.edits[ident] = edit
            row += 1
        grid.setColumnStretch(0, 1)
        grid.setRowStretch(row, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        lay.addWidget(scroll, 1)

        buttons = QHBoxLayout()
        reset = QPushButton("Reset all to defaults")
        reset.clicked.connect(self._reset)
        buttons.addWidget(reset)
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.setObjectName("Primary")
        save.setDefault(True)
        save.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        lay.addLayout(buttons)

    def assignment(self) -> dict:
        """Keys as currently typed in the dialog: id -> [key text] (empty list = no shortcut).
        A command with several default keys keeps its extra ones while the first is unchanged."""
        out = {}
        for ident, edit in self.edits.items():
            typed = _text(edit.keySequence())
            current = self.shortcuts.keys(ident)
            default = self.shortcuts.entries[ident]["default"]
            if current and typed == current[0]:
                out[ident] = current
            elif default and typed == default[0]:
                out[ident] = list(default)
            else:
                out[ident] = [typed] if typed else []
        return out

    def _reset(self):
        for ident, edit in self.edits.items():
            d = self.shortcuts.entries[ident]["default"]
            edit.setKeySequence(QKeySequence(d[0]) if d else QKeySequence())

    def _save(self):
        assignment = self.assignment()
        clashes = Shortcuts.conflicts(assignment)
        if clashes:
            names = self.shortcuts.entries
            text = "\n".join(f"{QKeySequence(k).toString(QKeySequence.NativeText)}:  "
                             + ",  ".join(names[i]["label"] for i in ids) for k, ids in clashes)
            self._warn("The same key is used more than once", "Give each command its own key:\n\n" + text)
            return
        self.shortcuts.apply(assignment)
        self.accept()

    def _warn(self, title, text):        # separate method so the tests can record it
        QMessageBox.warning(self, title, text)
