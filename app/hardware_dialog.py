"""
hardware_dialog.py — Help → Your computer…: what the program found about this computer (app/hardware.py):
processor and threads, graphics cards, the OpenGL renderer the program gets, the screens. "Check again"
finds everything anew (e.g. after a driver update or with another screen).
"""
from __future__ import annotations

import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from . import hardware


class HardwareDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.win = window
        self.setWindowTitle("Your computer")
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(12)
        self.text = QLabel()
        self.text.setTextFormat(Qt.RichText)
        self.text.setWordWrap(True)
        self.text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.text)
        row = QHBoxLayout()
        row.addStretch(1)
        self.btn_check = QPushButton("Check again")
        self.btn_check.setToolTip("Find the processor, graphics cards and screens again (a few seconds)")
        self.btn_check.clicked.connect(self.check_again)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        close.setDefault(True)
        for b in (self.btn_check, close):
            b.setCursor(Qt.PointingHandCursor)
            row.addWidget(b)
        lay.addLayout(row)
        self.refresh()

    def refresh(self):
        p = self.win.hardware
        if p is None:
            self.text.setText("<p>Not checked yet. Press <b>Check again</b>.</p>")
            return
        rows = "".join(f"<li>{html.escape(line)}</li>" for line in hardware.summary_lines(p))
        weak = hardware.opengl_uses_weak_card(p)
        note = ""
        if weak is not None:
            note = (f"<p><b>Note:</b> this computer also has <b>{html.escape(weak['name'])}</b>, but OpenGL runs on "
                    f"the other card. The program will offer to switch when graphics card drawing is turned "
                    f"on.</p>")
        when = html.escape(str(p.get("date", "?")))
        self.text.setText(f"<p>What the program found (checked {when}; again automatically when the computer "
                          f"changes):</p><ul>{rows}</ul>{note}")

    def check_again(self):
        self.btn_check.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.win.hardware, _fresh = hardware.detect(force=True, wait=QApplication.processEvents)
        finally:
            QApplication.restoreOverrideCursor()
            self.btn_check.setEnabled(True)
        self.refresh()
