"""
exporting.py — part of MainWindow: File → Export figure…, Export animation (GIF / MP4)… and Export data
(CSV)….

The options chosen last time and the folder are remembered (QSettings "export/*").
"""
import json
import os

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QFileDialog, QProgressDialog

from ..dialogs import dispose
from ..export import (Cancelled, ExportAnimationDialog, ExportDataDialog, ExportFigureDialog, export_data,
                      render_animation, render_figure)
from .files import safe_file_name


class ExportMixin:

    def export_figure(self):
        """File → Export figure…: options dialog, then where to save."""
        dlg = ExportFigureDialog(self.canvas, self._export_settings("figure"), self)
        try:
            if not self._run_dialog(dlg):
                return False
            opt = dlg.options()
        finally:
            dispose(dlg)
        fmt = opt["format"]
        path = self._ask_export_path(self._export_suggestion("." + fmt), f"{fmt.upper()} files (*.{fmt})")
        if not path:
            return False
        if not os.path.splitext(path)[1]:
            path += "." + fmt
        try:
            render_figure(self.canvas, path, fmt, opt["scale"], opt["background"], opt["light"],
                          opt.get("mirror", True), opt.get("mirror_numbers", True))
        except (OSError, ValueError) as exc:
            self._notify_user("warning", "Cannot export the figure", str(exc))
            return False
        self._save_export_settings("figure", opt, path)
        self.flash(f"Figure saved: {os.path.basename(path)}")
        return True

    def export_animation(self):
        """File → Export animation…: options dialog, where to save, then the frames (with a progress
        dialog that can cancel). The plot switches to the chosen animation and stays there."""
        settings = self._export_settings("animation")
        dlg = ExportAnimationDialog(self.canvas, settings, self)
        try:
            if not self._run_dialog(dlg):
                return False
            opt = dlg.options()
        finally:
            dispose(dlg)
        fmt = opt["format"]
        path = self._ask_export_path(self._export_suggestion("." + fmt), f"{fmt.upper()} files (*.{fmt})")
        if not path:
            return False
        if not os.path.splitext(path)[1]:
            path += "." + fmt
        cv = self.canvas
        cv.set_view_mode(opt["view"])
        if cv.paused:
            cv.set_paused(False)
        progress = self._progress_dialog("Recording the animation…")

        def step(done, total):
            if progress is None:
                return True
            progress.setMaximum(total)
            progress.setValue(done)
            QApplication.processEvents()
            return not progress.wasCanceled()
        try:
            render_animation(cv, path, fmt, opt["seconds"], opt["fps"], opt["scale"], opt["background"],
                             opt["light"], opt["mirror"], opt["mirror_numbers"], progress=step)
        except Cancelled:
            self.flash("Animation export cancelled.")
            return False
        except (OSError, ValueError, RuntimeError) as exc:
            self._notify_user("warning", "Cannot export the animation", str(exc))
            return False
        finally:
            if progress is not None:
                progress.close()
                progress.deleteLater()
        per_format = dict(settings.get(fmt, {}), fps=opt["fps"], scale=opt["scale"])
        saved = {k: v for k, v in settings.items() if k in ("gif", "mp4")}
        saved.update(opt, **{fmt: per_format})
        self._save_export_settings("animation", saved, path)
        self.flash(f"Animation saved: {os.path.basename(path)}")
        return True

    def _progress_dialog(self, text):
        """Progress with a Cancel button (None in the tests: no window to show)."""
        dlg = QProgressDialog(text, "Cancel", 0, 1, self)
        dlg.setWindowTitle("Export")
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(300)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        return dlg

    def export_data(self):
        """File → Export data (CSV)…: which tables, then where to save."""
        dlg = ExportDataDialog(self._export_settings("data"), self)
        try:
            if not self._run_dialog(dlg):
                return False
            opt = dlg.options()
        finally:
            dispose(dlg)
        path = self._ask_export_path(self._export_suggestion(".csv"), "CSV files (*.csv)")
        if not path:
            return False
        cv = self.canvas
        try:
            written = export_data(path, opt["datasets"], self.elements, cv.view(), cv.stagnation_points,
                                  cv.last_result.lines if cv.last_result else [], cv.settings.cp_reference,
                                  opt["grid"], opt["separator"], self._surfaces_if_ready())
        except OSError as exc:
            self._notify_user("warning", "Cannot export the data", str(exc))
            return False
        self._save_export_settings("data", opt, path)
        self.flash("Saved " + ", ".join(os.path.basename(p) for p in written))
        return True

    def export_surface(self):
        """Surface pressure panel → Export CSV…: Cp along all surfaces, one table."""
        opt = self._export_settings("data")
        path = self._ask_export_path(self._export_suggestion("_surface_cp.csv"), "CSV files (*.csv)")
        if not path:
            return False
        cv = self.canvas
        try:
            export_data(path, ["surface"], self.elements, cv.view(), v_ref=cv.settings.cp_reference,
                        separator=opt.get("separator", ","), surfaces=self._surfaces_if_ready())
        except OSError as exc:
            self._notify_user("warning", "Cannot export the data", str(exc))
            return False
        QSettings().setValue("export/folder", os.path.dirname(os.path.abspath(path)))
        self.flash("Saved " + os.path.basename(path))
        return True

    def _surfaces_if_ready(self):
        """The surfaces as on the plot, if they are up to date (else None: export_data computes them)."""
        layer = self.canvas.surfaces
        if layer.wanted and not layer._stale and not layer.computing:
            return layer.surfaces()
        return None

    def _export_suggestion(self, extension: str) -> str:
        """Last export folder + the scene's file name (or title)."""
        folder = QSettings().value("export/folder", "") or self.recent.last_folder
        base = os.path.splitext(os.path.basename(self.current_path))[0] if self.current_path else self.scene_title
        return os.path.join(folder, safe_file_name(base, "figure") + extension)

    @staticmethod
    def _export_settings(kind: str) -> dict:
        raw = QSettings().value(f"export/{kind}")
        try:
            return json.loads(raw) if raw else {}
        except (TypeError, ValueError):
            return {}

    @staticmethod
    def _save_export_settings(kind: str, options: dict, path: str):
        s = QSettings()
        s.setValue(f"export/{kind}", json.dumps(options))
        s.setValue("export/folder", os.path.dirname(os.path.abspath(path)))

    # dialogs (separate methods so the tests can answer them)
    def _run_dialog(self, dlg) -> bool:
        return bool(dlg.exec())

    def _ask_export_path(self, suggested: str, file_filter: str) -> str:
        path, _ = QFileDialog.getSaveFileName(self, "Export", suggested, file_filter)
        return path
