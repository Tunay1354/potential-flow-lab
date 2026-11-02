"""
status.py — part of MainWindow: the status bar (probe readout under the mouse, scene check, streamline
count), the red error strip above the plot, the window title and the title block under the plot.
"""
import os

import numpy as np
from PySide6.QtWidgets import QLabel

from physics import check_scene, complex_potential, velocity
from physics.field import fluid_mask, singular_points

from ..theme import LAYOUT
from .issues_popup import IssueButton, IssuesPopup


def _count(n: int, word: str) -> str:
    return f"{n} {word}{'s' if n > 1 else ''}"


class StatusMixin:

    def _build_statusbar(self):
        sb = self.statusBar()
        self.probe_label = QLabel("Move the mouse over the plot")
        self.probe_label.setObjectName("ProbeLabel")
        self.issue_label = IssueButton()          # click: every issue listed (IssuesPopup)
        self.issue_label.clicked.connect(self.show_issues)
        self.count_label = QLabel("")
        sb.addPermanentWidget(self.probe_label)
        # a message (e.g. "Moved vortex — Ctrl+Z to undo") gets the room of the probe text while shown
        sb.messageChanged.connect(lambda text: self.probe_label.setVisible(not text))
        sb.addPermanentWidget(self.issue_label)
        sb.addPermanentWidget(self.count_label)

    def flash(self, text):
        self.statusBar().showMessage(text, 5000)

    # ------------------------------------------------------------------ probe (values under the mouse)
    def _update_probe(self, pos):
        self._last_probe = pos
        self.probe_label.setText(self._probe_text(pos))

    def _probe_text(self, pos) -> str:
        if pos is None:
            return "Move the mouse over the plot"
        x, y = pos
        z = complex(x, y)
        where = f"x = {x:7.3f}   y = {y:7.3f}   │   "
        stag = self.canvas.stagnation_near(x, y)
        if stag is not None:
            return where + stag.describe()
        (x0, x1), _ = self.canvas.view()
        if any(abs(z - p) < 0.5 * (x1 - x0) / 200.0 for p in singular_points(self.elements)):
            return where + "singular point (velocity → ∞)"
        if not fluid_mask(self.elements, z):
            return where + "outside the fluid region"
        u, v = (float(c) for c in velocity(self.elements, x, y))
        V = float(np.hypot(u, v))
        text = where + f"u = {u:7.3f}   v = {v:7.3f}   |V| = {V:7.3f}"
        v_ref = self.canvas.cp_reference()
        text += f"   Cp = {1.0 - (V / v_ref) ** 2:7.3f}" if v_ref else "   Cp: no V_ref"
        F = complex(complex_potential(self.elements, np.array([z]))[0])
        return text + f"   │   φ = {F.real:7.3f}   ψ = {F.imag:7.3f}"

    # ------------------------------------------------------------------ scene check
    def _update_issues(self):
        """Scene check (walls, invalid positions...) in the status bar (details in the tooltip) and,
        for errors, a red strip above the plot."""
        issues = check_scene(self.elements)
        errors = [s for s in issues if s.severity == "error"]
        warnings = [s for s in issues if s.severity == "warning"]
        notes = [s for s in issues if s.severity == "info"]
        if errors:
            text, color = "✖ " + _count(len(errors), "error"), self.theme["danger"]
        elif warnings:
            text, color = "⚠ " + _count(len(warnings), "warning"), self.theme["el_doublet"]
        else:
            text, color = "✓ scene OK", self.theme["el_sector"]
        if notes and not errors:
            text += "  ·  " + _count(len(notes), "note")
        self.issue_label.setText(text)
        self.issue_label.set_look(color, self.theme["panel_header"])
        self._issues = issues

        def who(s):                                    # number in the element list
            return f"[{s.index + 1}] " if s.index is not None else ""
        self.issue_label.setToolTip("Click to read them" if issues else "No problems found.")
        if errors and not getattr(self, "_had_errors", False) and getattr(self, "beaver", None) is not None:
            self.beaver.on_error()
        self._had_errors = bool(errors)
        if errors:
            more = f"   (+{len(errors) - 1} more: click the status bar)" if len(errors) > 1 else ""
            self.canvas.set_banner(f"✖ Not physically consistent — {who(errors[0])}{errors[0].message}{more}")
        else:
            self.canvas.set_banner(None)

    def show_issues(self):
        """Status bar → the scene check, every issue in a panel above it (click one: select its element)."""
        popup = IssuesPopup(getattr(self, "_issues", []), self.elements, self.theme, self)
        popup.select.connect(self.select_element)
        popup.show_above(self.issue_label)
        self._issues_popup = popup
        return popup

    def _update_status(self, n_lines, ms):
        self._update_title_block_counts()
        n = len(self.elements)
        on = sum(e.enabled for e in self.elements)
        self.count_label.setText(f"{n} elements ({on} shown)  |  {n_lines} streamlines in {ms:.0f} ms")

    # ------------------------------------------------------------------ titles
    def _update_title(self):
        star = " *" if self.model.is_modified else ""
        name = os.path.basename(self.current_path) if self.current_path else self.scene_title
        self.setWindowTitle(f"{LAYOUT['window_title']} — {name}{star}")
        self.setWindowFilePath(self.current_path or "")
        file = os.path.basename(self.current_path) if self.current_path else "not saved"
        self.header.plank.file.set_sheet(os.path.basename(self.current_path) if self.current_path else None,
                                         self.model.is_modified)
        self.recovery.changed()                  # saved / changed: the recovery copy follows
        tb = self.canvas.title_block
        tb.set("scene", self.scene_title)
        tb.set("file", file + star)
        self._update_title_block_counts()

    def _update_title_block_counts(self):
        self.canvas.title_block.set("elements", f"{len(self.elements)}  ·  ⊗ {len(self.canvas.stagnation_points)}")

    def _update_title_block_view(self, xr, yr):
        from ..panels import view_number
        w = max(xr[1] - xr[0], yr[1] - yr[0])                   # (zoomed in: enough decimals to tell the ends apart)
        x0, x1, y0, y1 = (view_number(v, w, 100.0) for v in (*xr, *yr))
        self.canvas.title_block.set("view", f"x[{x0}, {x1}]  y[{y0}, {y1}]".replace("-", "−").replace("e−", "e-"))
