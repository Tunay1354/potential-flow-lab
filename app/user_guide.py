"""
user_guide.py — Help → User guide (F1): the chapters of user_guide_text.py in a window that can stay open
next to the program (not modal): the chapters on the left, the text on the right, a search field
(Enter = next match, nothing else), and "Save as web page…" (the whole guide as one HTML page, e.g. to print it).
"""
from __future__ import annotations

import html
import os

from PySide6.QtCore import QSize, QStandardPaths, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut, QTextDocument
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QPushButton, QTextBrowser,
                               QVBoxLayout)

from .user_guide_text import CHAPTERS


def shortcut_table(shortcuts) -> str:
    """The keyboard shortcuts as they are set now (Shortcuts registry), grouped, as an HTML table."""
    if shortcuts is None:
        return ""
    rows, group = [], None
    for ident in shortcuts.entries:
        e = shortcuts.entries[ident]
        keys = [k for k in shortcuts.keys(ident) if k]
        if not keys:
            continue
        if e["group"] != group:
            group = e["group"]
            rows.append(f"<tr><th colspan='2'>{html.escape(group)}</th></tr>")
        rows.append(f"<tr><td><code>{html.escape(', '.join(keys))}</code></td><td>{html.escape(e['label'])}</td></tr>")
    return "<table>" + "".join(rows) + "</table>"


def style_sheet(t: dict) -> str:
    """CSS of the guide (QTextBrowser's subset), from the theme."""
    return f"""
        body {{ color: {t['text']}; }}
        h2 {{ font-size: 16pt; margin-bottom: 6px; }}
        h3 {{ font-size: 12pt; margin-top: 14px; margin-bottom: 4px; }}
        p, li, td {{ line-height: 135%; }}
        table {{ border-collapse: collapse; margin-top: 4px; margin-bottom: 8px; }}
        td, th {{ padding: 4px 10px 4px 0px; vertical-align: top; }}
        th {{ text-align: left; color: {t['text_muted']}; padding-top: 10px; }}
        code {{ background-color: {t['panel_header']}; }}
        .warn {{ color: {t['el_doublet']}; }}
        .err {{ color: {t['danger']}; }}
    """


def chapter_html(key: str, shortcuts=None) -> str:
    for k, _title, text in CHAPTERS:
        if k == key:
            return text.replace("{keys}", shortcut_table(shortcuts))
    return ""


def full_html(theme: dict, shortcuts=None) -> str:
    """The whole guide as one web page (Save as web page…)."""
    body = "\n<hr>\n".join(chapter_html(k, shortcuts) for k, _t, _x in CHAPTERS)
    toc = "".join(f"<li>{html.escape(t)}</li>" for _k, t, _x in CHAPTERS)
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>Potential Flow Lab — User guide</title>"
            f"<style>body {{ font-family: sans-serif; max-width: 860px; margin: 32px auto; padding: 0 16px; "
            f"background: {theme['panel_bg']}; }} {style_sheet(theme)}</style></head><body>"
            f"<h1>Potential Flow Lab — User guide</h1><ol>{toc}</ol><hr>{body}</body></html>")


class UserGuideDialog(QDialog):
    def __init__(self, theme: dict, shortcuts=None, parent=None):
        super().__init__(parent)
        self.t, self.shortcuts = theme, shortcuts
        self.setWindowTitle("User guide")
        self.setModal(False)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 12)
        lay.setSpacing(8)
        top = QHBoxLayout()
        title = QLabel("User guide")
        title.setObjectName("DialogTitle")
        top.addWidget(title)
        top.addStretch(1)
        self.find = QLineEdit()
        self.find.setPlaceholderText("Search the guide…")
        self.find.setClearButtonEnabled(True)
        self.find.setFixedWidth(240)
        self.find.returnPressed.connect(self.find_next)
        top.addWidget(self.find)
        lay.addLayout(top)

        row = QHBoxLayout()
        row.setSpacing(12)
        self.toc = QListWidget()
        self.toc.setObjectName("GuideContents")
        self.toc.setFixedWidth(230)
        for _k, t, _x in CHAPTERS:
            self.toc.addItem(t)
            self.toc.item(self.toc.count() - 1).setSizeHint(QSize(0, 30))
        self.toc.currentRowChanged.connect(self.show_chapter)
        row.addWidget(self.toc)
        self.text = QTextBrowser()
        self.text.setObjectName("GuideText")
        self.text.setOpenExternalLinks(True)
        row.addWidget(self.text, 1)
        lay.addLayout(row, 1)

        bottom = QHBoxLayout()
        self.note = QLabel("")
        self.note.setObjectName("Muted")
        bottom.addWidget(self.note, 1)
        browser = QPushButton("Save as web page…")
        browser.setToolTip("The whole guide as one web page (to read it in the browser or print it)")
        browser.clicked.connect(self.save_web_page)
        close = QPushButton("Close")
        close.setObjectName("Primary")
        close.clicked.connect(self.close)
        for b in (browser, close):
            b.setCursor(Qt.PointingHandCursor)
            b.setAutoDefault(False)                      # (Enter in the search field searches, nothing else)
            b.setDefault(False)
            bottom.addWidget(b)
        lay.addLayout(bottom)
        QShortcut(QKeySequence.Find, self, activated=lambda: (self.find.setFocus(), self.find.selectAll()))
        self.apply_theme(theme)
        self.resize(980, 680)
        self.toc.setCurrentRow(0)

    def apply_theme(self, theme: dict):
        self.t = theme
        t = theme
        self.setStyleSheet(f"""
            QListWidget#GuideContents {{ background: {t['panel_bg']}; border: 1px solid {t['border']};
                padding: 4px; outline: none; }}
            QListWidget#GuideContents::item {{ padding: 0px 8px; color: {t['text']}; border-left: 3px solid transparent; }}
            QListWidget#GuideContents::item:selected {{ background: {t['accent_soft']}; color: {t['text']};
                border-left: 3px solid {t['accent_strong']}; }}
            QListWidget#GuideContents::item:hover {{ background: {t['panel_header']}; }}
            QTextBrowser#GuideText {{ background: {t['panel_bg']}; border: 1px solid {t['border']};
                padding: 10px 16px; }}
        """)
        self.text.document().setDefaultStyleSheet(style_sheet(theme))
        self.show_chapter(self.toc.currentRow())

    def show_chapter(self, row: int):
        if not 0 <= row < len(CHAPTERS):
            return
        key = CHAPTERS[row][0]
        self.text.setHtml(chapter_html(key, self.shortcuts))
        self.note.setText("")

    def show_key(self, key: str):
        for i, (k, _t, _x) in enumerate(CHAPTERS):
            if k == key:
                self.toc.setCurrentRow(i)

    def find_next(self):
        """The next match in this chapter, then in the following chapters (wrapping round)."""
        word = self.find.text().strip()
        if not word:
            return
        if self.text.find(word):
            self.note.setText("")
            return
        start = self.toc.currentRow()
        n = len(CHAPTERS)
        for step in range(1, n + 1):
            row = (start + step) % n
            body = QTextDocument()
            body.setHtml(chapter_html(CHAPTERS[row][0], self.shortcuts))
            if word.lower() in body.toPlainText().lower():
                self.toc.setCurrentRow(row)
                self.text.find(word)
                self.note.setText("" if row != start else "(from the top again)")
                return
        self.note.setText(f"“{word}” is not in the guide.")

    def save_web_page(self, path: str | None = None) -> str | None:
        """The whole guide as one HTML file where the user chooses (Documents by default), then opened in the
        browser. (A file in the program's own data folder could not be opened by the browser with Microsoft
        Store Python: Windows keeps that folder private to it.)"""
        if path is None:
            from PySide6.QtWidgets import QFileDialog
            start = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation) or os.path.expanduser("~")
            path, _ = QFileDialog.getSaveFileName(self, "Save the user guide", os.path.join(
                start, "Potential Flow Lab - User guide.html"), "Web page (*.html)")
            if not path:
                return None
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(full_html(self.t, self.shortcuts))
        except OSError as exc:
            self.note.setText(f"Could not save it: {exc.strerror or exc}")
            return None
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        self.note.setText(f"Saved as {path}")
        return path
