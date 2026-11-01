"""
verification_dialog.py — Help → Run verification…: the verification report (app/cli/report.py) made from
inside the program.

The checks run in a background thread (the window stays usable), the figures of the 9 assignment scenes
are drawn afterwards in the GUI thread on a canvas that is never shown. Then the result:

  - one line: "102 of 102 checks OK"
  - a tree, folded: the 3 sections with their counts → the cases → the checks (analytic, program, error)
  - on the right, for the selected row: how it is computed (theory, what the program does, why that
    tolerance, the numbers), the figure of a scene, the description of a section
  - Open full report (verification.html in the browser, every explanation folded under its check),
    Open folder, Save report to…, Run again

The report is written to the program's data folder (verification/), replaced at every run.
"""
from __future__ import annotations

import html
import logging
import os
import shutil

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QImage, QTextDocument
from PySide6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QProgressBar,
                               QPushButton, QSplitter, QTextBrowser, QTreeWidget, QTreeWidgetItem, QVBoxLayout)

from app_info import LOGGER
from app.cli import report as rp
from app.paths import data_folder, outside_path

ROLE = Qt.UserRole + 1                   # what a tree row is: ("section", name) / ("case", …) / ("check", Check)
HINT = ("<p>Select a row on the left.</p><p><b>Section</b>: what it checks. <b>Scene</b>: its figure. "
        "<b>Check</b>: how it is computed — the theory, what the program does, why the tolerance is what it "
        "is — and the numbers.</p>")


def report_folder() -> str:
    return data_folder("verification")


class _Signals(QObject):
    step = Signal(int, str)                  # index of the job, its label
    done = Signal(object)                    # list of Check
    failed = Signal(str)


class _Checks(QRunnable):
    """The checks (no Qt), one job after the other; stops between jobs when cancelled."""

    def __init__(self, jobs, signals):
        super().__init__()
        self.jobs, self.signals, self.cancelled = jobs, signals, False
        self.setAutoDelete(False)

    def run(self):
        out = []
        try:
            for k, (label, job) in enumerate(self.jobs):
                if self.cancelled:
                    return
                self.signals.step.emit(k, label)
                out += job()
        except Exception as exc:                                     # noqa: BLE001 - shown in the dialog
            logging.getLogger(LOGGER).exception("verification failed")
            self.signals.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.signals.done.emit(out)


class _Detail(QTextBrowser):
    """The explanation pane. Figures (src="fig:<path>") are scaled smoothly to the pane's width (Qt's own
    scaling of an <img> drops the thin streamlines)."""

    def loadResource(self, kind, url):
        if kind == QTextDocument.ImageResource and url.scheme() == "fig":
            img = QImage(url.path())
            if img.isNull():
                return img
            dpr = self.devicePixelRatioF()
            w = max(200, self.viewport().width() - 28)
            out = img.scaledToWidth(int(w * dpr), Qt.SmoothTransformation)
            out.setDevicePixelRatio(dpr)
            return out
        return super().loadResource(kind, url)


class VerificationDialog(QDialog):
    def __init__(self, theme: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Verification")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.theme = theme
        self.folder = report_folder()
        self.report: rp.Report | None = None
        self.paths: dict = {}
        self._worker = None
        self._canvas = None
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._build()
        self.resize(1080, 700)

    # ------------------------------------------------------------------ layout
    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)
        title = QLabel("Verification")
        title.setObjectName("DialogTitle")
        lay.addWidget(title)
        note = QLabel("Every check of the program against the theory: (1) the analytic formulas, (2) the "
                      "assignment's 9 verification scenes — what the program draws and computes, and saving / "
                      "reopening — and (3) the accuracy of the numerical methods.")
        note.setObjectName("Muted")
        note.setWordWrap(True)
        lay.addWidget(note)

        row = QHBoxLayout()
        self.result = QLabel("")
        self.result.setObjectName("VerificationResult")
        row.addWidget(self.result, 1)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        self.progress.setMaximumWidth(260)
        row.addWidget(self.progress)
        lay.addLayout(row)

        split = QSplitter(Qt.Horizontal)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(5)
        self.tree.setHeaderLabels(["Check", "Analytic", "Program", "Error", ""])
        self.tree.setUniformRowHeights(False)
        self.tree.setAlternatingRowColors(False)
        h = self.tree.header()
        h.setStretchLastSection(False)
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in (1, 2, 3, 4):
            h.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.tree.currentItemChanged.connect(self._show_item)
        split.addWidget(self.tree)
        self.detail = _Detail()
        self.detail.setObjectName("VerificationDetail")
        self.detail.setOpenExternalLinks(True)
        self.detail.document().setDefaultStyleSheet("p { margin-top: 4px; margin-bottom: 6px; }")
        self.detail.setHtml(HINT)
        split.addWidget(self.detail)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        split.setSizes([640, 400])
        lay.addWidget(split, 1)

        buttons = QHBoxLayout()
        self.btn_html = QPushButton("Open full report")
        self.btn_html.setToolTip("verification.html in the browser: every check with its explanation (folded), "
                                 "the figures")
        self.btn_html.clicked.connect(lambda: self._open(self.paths.get("html")))
        self.btn_folder = QPushButton("Open folder")
        self.btn_folder.setToolTip("verification.html / .md / .csv and figures/*.png")
        self.btn_folder.clicked.connect(lambda: self._open(self.folder))
        self.btn_save = QPushButton("Save report to…")
        self.btn_save.setToolTip("Copy the report (HTML, Markdown, CSV, figures) to a folder of your choice")
        self.btn_save.clicked.connect(self._save_copy)
        self.btn_run = QPushButton("Run again")
        self.btn_run.clicked.connect(self.start)
        close = QPushButton("Close")
        close.setObjectName("Primary")
        close.clicked.connect(self.close)
        for b in (self.btn_html, self.btn_folder, self.btn_save):
            buttons.addWidget(b)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_run)
        buttons.addWidget(close)
        lay.addLayout(buttons)
        self.apply_theme(self.theme)
        self._set_busy(False)

    def apply_theme(self, theme: dict):
        self.theme = theme
        self.setStyleSheet(
            f"QTextBrowser#VerificationDetail {{ background: {theme['panel_bg']}; color: {theme['text']};"
            f" border: 1px solid {theme['border_soft']}; padding: 6px; }}"
            f"QTreeWidget {{ border: 1px solid {theme['border_soft']}; }}"
            f"QLabel#VerificationResult {{ font-weight: 600; font-size: 11pt; }}")
        if self.report is not None:
            self._fill_tree()

    # ------------------------------------------------------------------ running
    @property
    def running(self) -> bool:
        return self._worker is not None

    def start(self):
        """Run every check, draw the figures, write the report (again)."""
        if self.running:
            return
        self.report, self.paths = None, {}
        self.tree.clear()
        self.detail.setHtml(HINT)
        self._scenes = rp.scenes()
        jobs = rp.check_jobs(self._scenes)
        self._n_jobs = len(jobs)
        self.progress.setRange(0, len(jobs) + len(self._scenes) + 1)
        self.progress.setValue(0)
        self._set_result("Running the checks…", None)
        self._set_busy(True)
        sig = _Signals(self)                   # its own signals: a stopped earlier run cannot answer
        worker = _Checks(jobs, sig)
        sig.step.connect(lambda k, label: worker is self._worker and self._on_step(k, label))
        sig.done.connect(lambda checks: worker is self._worker and self._on_checks(checks))
        sig.failed.connect(lambda msg: worker is self._worker and self._on_failed(msg))
        self._worker = worker
        self._pool.start(worker)

    def _on_step(self, k, label):
        self.progress.setValue(k)
        self._set_result(f"Checking: {label}  ({k + 1} / {self._n_jobs})", None)

    def _on_failed(self, message):
        self._worker = None
        self._set_busy(False)
        self._set_result("The verification stopped with an error.", False)
        self.detail.setHtml(f"<p><b>Error</b></p><pre>{html.escape(message)}</pre>")

    def _on_checks(self, checks):
        self.report = rp.Report(checks=checks, scenes=self._scenes)
        self._fill_tree()
        self._figure_index = 0
        QTimer.singleShot(0, self._next_figure)

    def _next_figure(self):
        """One figure per event-loop turn (the window keeps reacting in between)."""
        if self._worker is None or self._worker.cancelled:
            self._drop_canvas()
            return
        scenes = self.report.scenes
        k = self._figure_index
        if k < len(scenes):
            self._set_result(f"Drawing the figures  ({k + 1} / {len(scenes)})", None)
            self.progress.setValue(self._n_jobs + k)
            try:
                if self._canvas is None:
                    from app.cli.headless import make_canvas
                    self._canvas = make_canvas()
                sc = scenes[k]
                self.report.figures[sc.title] = rp.render_figure(self._canvas, sc, os.path.join(self.folder, "figures"))
            except Exception:                                        # noqa: BLE001 - a missing figure is no failure
                pass
            self._figure_index += 1
            QTimer.singleShot(0, self._next_figure)
            return
        self._drop_canvas()
        try:
            self.paths = rp.write(self.report, self.folder)
        except OSError as exc:
            self.paths = {}
            QMessageBox.warning(self, "Verification", f"Cannot write the report:\n{exc}")
        self.progress.setValue(self.progress.maximum())
        self._worker = None
        self._set_busy(False)
        self._set_result(rp.summary(self.report), self.report.ok)
        beaver = getattr(self.parent(), "beaver", None)
        if beaver is not None:
            beaver.on_verified(sum(c.ok for c in self.report.checks), len(self.report.checks))
        self._show_item(self.tree.currentItem())

    def _drop_canvas(self):
        if self._canvas is not None:
            self._canvas.shutdown()
            self._canvas.deleteLater()
            self._canvas = None

    def shutdown(self):
        """The window closes: stop the work (a running check finishes first)."""
        if self._worker is not None:
            self._worker.cancelled = True
        self._pool.waitForDone(30000)
        self._drop_canvas()

    def _set_busy(self, busy: bool):
        self.progress.setVisible(busy)
        self.btn_run.setEnabled(not busy)
        have = bool(self.paths) and not busy
        for b in (self.btn_html, self.btn_folder, self.btn_save):
            b.setEnabled(have)

    def _set_result(self, text, ok):
        color = self.theme["text_muted"] if ok is None else (self.theme["el_sector"] if ok else self.theme["danger"])
        self.result.setText(("✓  " if ok else "✗  " if ok is False else "") + text)
        self.result.setStyleSheet(f"color: {color};")

    # ------------------------------------------------------------------ the tree
    def _fill_tree(self):
        current = self._key(self.tree.currentItem())
        expanded = {self._key(it) for it in self._items() if it.isExpanded()}
        self.tree.clear()
        ok_c, bad_c = QColor(self.theme["el_sector"]), QColor(self.theme["danger"])
        rep = self.report
        select = None
        for k, sec in enumerate(rp.SECTIONS, 1):
            rows = rep.section(sec)
            n_ok = sum(c.ok for c in rows)
            top = QTreeWidgetItem([f"{k}. {rp.SECTION_TITLES[sec]}", "", "", "", f"{n_ok} / {len(rows)}"])
            top.setData(0, ROLE, ("section", sec))
            f = top.font(0)
            f.setBold(True)
            top.setFont(0, f)
            top.setForeground(4, ok_c if n_ok == len(rows) else bad_c)
            self.tree.addTopLevelItem(top)
            cases = []
            for c in rows:
                if c.case not in cases:
                    cases.append(c.case)
            for case in cases:
                group = [c for c in rows if c.case == case]
                g_ok = sum(c.ok for c in group)
                sc = next((s for s in rep.scenes if s.title == case), None) if sec == rp.SCENES else None
                it = QTreeWidgetItem([case, "", "", "", f"{g_ok} / {len(group)}"])
                it.setData(0, ROLE, ("case", sec, case, sc))
                it.setForeground(4, ok_c if g_ok == len(group) else bad_c)
                top.addChild(it)
                for c in group:
                    ch = QTreeWidgetItem([c.quantity, rp.num(c.analytic), rp.num(c.numerical), f"{c.error:.1e}",
                                          "OK" if c.ok else "FAIL"])
                    ch.setData(0, ROLE, ("check", c))
                    ch.setToolTip(0, c.quantity)
                    ch.setForeground(4, ok_c if c.ok else bad_c)
                    if not c.ok:                     # a failing check is shown at once
                        top.setExpanded(True)
                        it.setExpanded(True)
                    it.addChild(ch)
        for it in self._items():
            key = self._key(it)
            if key in expanded:
                it.setExpanded(True)
            if key == current:
                select = it
        if select is not None:
            self.tree.setCurrentItem(select)

    def _items(self):
        out = []
        stack = [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())]
        while stack:
            it = stack.pop()
            out.append(it)
            stack += [it.child(i) for i in range(it.childCount())]
        return out

    @staticmethod
    def _key(item):
        if item is None:
            return None
        d = item.data(0, ROLE)
        if not d:
            return None
        if d[0] == "check":
            return ("check", d[1].section, d[1].case, d[1].quantity)
        return d[:3]

    def _show_item(self, item, *_):
        d = item.data(0, ROLE) if item is not None else None
        if not d or self.report is None:
            self.detail.setHtml(HINT)
            return
        if d[0] == "section":
            rows = self.report.section(d[1])
            self.detail.setHtml(f"<h3>{html.escape(rp.SECTION_TITLES[d[1]])}</h3>"
                                f"<p>{html.escape(rp.SECTION_TEXT[d[1]])}</p>"
                                f"<p><b>{sum(c.ok for c in rows)} of {len(rows)} checks OK.</b> Open a case and "
                                f"select a check to see how it is computed.</p>")
        elif d[0] == "case":
            _kind, sec, case, sc = d
            rows = [c for c in self.report.section(sec) if c.case == case]
            parts = [f"<h3>{html.escape(case)}</h3>",
                     f"<p>{sum(c.ok for c in rows)} of {len(rows)} checks OK.</p>"]
            if sc is not None:
                parts.append(f"<p>Scene file: <code>{html.escape(sc.name)}</code> (Presets → 1 Verification "
                             f"cases)</p>")
                path = self.report.figures.get(case)
                if path and os.path.exists(path):
                    url = QUrl()
                    url.setScheme("fig")
                    url.setPath(QUrl.fromLocalFile(path).path())
                    parts.append(f"<p><img src='{url.toString()}'></p>")
                elif self.running:
                    parts.append("<p><i>The figure is being drawn…</i></p>")
            self.detail.setHtml("".join(parts))
        else:
            c = d[1]
            self.detail.setHtml(f"<h3>{html.escape(c.quantity)}</h3><p><i>{html.escape(c.case)}</i></p>"
                                + rp.how_html(c))

    # ------------------------------------------------------------------ files
    def _open(self, path):
        """In the browser / Explorer (at the path they see: outside_path, Microsoft Store Python)."""
        if path and os.path.exists(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(outside_path(path)))

    def _save_copy(self):
        target = QFileDialog.getExistingDirectory(self, "Save the verification report to")
        if not target:
            return
        dest = os.path.join(target, "verification")
        try:
            shutil.copytree(self.folder, dest, dirs_exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(self, "Verification", f"Cannot copy the report:\n{exc}")
            return
        QMessageBox.information(self, "Verification", f"Saved to\n{dest}")

    def closeEvent(self, event):
        """Closing while it runs stops it (the result would be incomplete)."""
        if self._worker is not None:
            self._worker.cancelled = True
            self._worker = None
            self._drop_canvas()
            self._set_busy(False)
            self._set_result("Stopped.", None)
        super().closeEvent(event)
