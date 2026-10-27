"""
export.py — File → Export figure… (PNG / SVG / PDF) and File → Export data (CSV)…

Figure: the plot as it is on the screen (view, layers, selection), axes included, without the program
around it. PNG can be 1×–4× the screen resolution: line widths, arrows and symbols grow with it, so
a 3× PNG looks like the screen, only sharper. SVG and PDF are vector files (lines stay sharp at any
zoom, good for the report). Option: light colors for a figure exported from the dark theme.

Data: CSV tables for spreadsheets / MATLAB / Python — elements, stagnation points, the streamlines
in view, and u, v, |V|, Cp, φ, ψ on a grid over the view.
"""
import csv
import os
from contextlib import contextmanager, nullcontext

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QMarginsF, QRect, QRectF, QSize, QSizeF, Qt
from PySide6.QtGui import QColor, QImage, QPageSize, QPainter, QPdfWriter, QPen
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
                               QPushButton, QRadioButton, QSpinBox, QVBoxLayout, QWidget)

from physics.field import complex_potential, fluid_mask, reference_speed, singularity_mask, velocity

from .chrome import themed_combo
from .theme import LIGHT

FORMATS = ("png", "svg", "pdf")
BACKGROUNDS = ("paper", "white", "transparent")


# ---------------------------------------------------------------------------------------- figure
def figure_size(canvas) -> QSize:
    """Size (screen pixels) of the exported region: plot area with axes and axis labels (the same with
    mirrored axes: the plot area gets smaller instead)."""
    r = canvas.plot.getPlotItem().sceneBoundingRect()
    return QSize(int(round(r.width())), int(round(r.height())))


@contextmanager
def mirrored_axes(canvas, numbers: bool = True):
    """For the export only: axes also on the top and the right, as wide as the left / bottom ones, so
    the plot area sits in the middle of the figure (closed frame). numbers = also tick values and
    axis titles there. The screen layout and the visible region come back afterwards."""
    from PySide6.QtWidgets import QApplication
    pi, vb = canvas.plot.getPlotItem(), canvas.vb
    (x0, x1), (y0, y1) = vb.viewRange()
    left, bottom = pi.getAxis("left"), pi.getAxis("bottom")
    pi.showAxis("top")
    pi.showAxis("right")
    pairs = ((pi.getAxis("right"), left), (pi.getAxis("top"), bottom))
    try:
        for ax, twin in pairs:
            ax.setPen(twin.pen())
            ax.setTextPen(twin.textPen())
            ax.setTickFont(twin.style["tickFont"])
            ax.setStyle(showValues=numbers)
            ax.setLabel(twin.labelText if numbers else None, **twin.labelStyle)
            if not numbers:
                ax.showLabel(False)
        right, top = pairs[0][0], pairs[1][0]
        right.setWidth(left.width())
        top.setHeight(bottom.height())
        pi.layout.activate()
        QApplication.processEvents()
        for _ in range(3):              # equal paper on both sides of the plot area (layout margins differ)
            r, area = pi.sceneBoundingRect(), vb.sceneBoundingRect()
            dx = (r.right() - area.right()) - (area.left() - r.left())
            dy = (area.top() - r.top()) - (r.bottom() - area.bottom())
            if abs(dx) < 0.5 and abs(dy) < 0.5:
                break
            right.setWidth(max(1.0, right.width() - dx))
            top.setHeight(max(1.0, top.height() - dy))
            pi.layout.activate()
            QApplication.processEvents()
        vb.setRange(xRange=(x0, x1), yRange=(y0, y1), padding=0)   # the same region (or a bit more)
        QApplication.processEvents()
        yield
    finally:
        pi.hideAxis("top")
        pi.hideAxis("right")
        pi.getAxis("right").setWidth(None)
        pi.getAxis("top").setHeight(None)
        pi.layout.activate()
        QApplication.processEvents()
        vb.setRange(xRange=(x0, x1), yRange=(y0, y1), padding=0)
        QApplication.processEvents()


def _scale_pens(scene, k: float) -> list:
    """Make every line k times wider (for a k× PNG); returns what to restore."""
    saved = []
    if k == 1.0:
        return saved
    for it in scene.items():
        if isinstance(it, (pg.PlotCurveItem, pg.GridItem)):
            old = QPen(it.opts["pen"])
        elif isinstance(it, pg.AxisItem):
            old = QPen(it.pen())
        else:
            continue
        pen = QPen(old)
        pen.setWidthF(max(pen.widthF(), 1.0) * k)
        it.setPen(pen)
        saved.append((it, old))
    return saved


def render_figure(canvas, path: str, fmt: str, scale: float = 2.0, background: str = "paper",
                  light: bool = False, mirror: bool = True, mirror_numbers: bool = True):
    """Write the plot to `path` (png / svg / pdf). Raises OSError if the file cannot be written.
    mirror: axes on all four sides (centered plot area), see mirrored_axes."""
    fmt = fmt.lower()
    theme_before = canvas.theme
    if light and canvas.theme["name"] != "light":
        canvas.apply_theme(LIGHT)                          # print colors; the screen theme comes back
    try:
        with mirrored_axes(canvas, mirror_numbers) if mirror else nullcontext():
            _render(canvas, path, fmt, scale, background)
    finally:
        if canvas.theme is not theme_before:
            canvas.apply_theme(theme_before)


def _render(canvas, path, fmt, scale, background):
    """Draw the plot region into the file (see render_figure)."""
    plot_item = canvas.plot.getPlotItem()
    scene = canvas.plot.scene()
    source = plot_item.sceneBoundingRect()
    w, h = source.width(), source.height()
    bg = None if background == "transparent" else \
        QColor("#FFFFFF" if background == "white" else canvas.theme["plot_bg"])
    k = float(scale) if fmt == "png" else 1.0
    items = [it for it in scene.items() if hasattr(it, "setExportMode")]
    saved = _scale_pens(scene, k)
    for it in items:
        it.setExportMode(True, {"antialias": True, "resolutionScale": k, "background": bg})
    try:
        if fmt == "png":
            img = QImage(int(round(w * k)), int(round(h * k)), QImage.Format_ARGB32)
            img.fill(bg if bg is not None else Qt.transparent)
            p = QPainter(img)
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setRenderHint(QPainter.TextAntialiasing, True)
            scene.render(p, QRectF(0, 0, img.width(), img.height()), source)
            p.end()
            if not img.save(path, "PNG"):
                raise OSError(f"Could not write {path}")
        elif fmt == "svg":
            _write_svg(canvas, path, source, bg)
        elif fmt == "pdf":
            writer = QPdfWriter(path)
            writer.setResolution(96)                    # 1 screen pixel = 1/96 inch: lines as on screen
            writer.setPageSize(QPageSize(QSizeF(w * 72.0 / 96.0, h * 72.0 / 96.0), QPageSize.Point))
            writer.setPageMargins(QMarginsF(0, 0, 0, 0))
            writer.setTitle("Potential Flow Lab figure")
            p = QPainter(writer)
            if bg is not None:
                p.fillRect(QRectF(0, 0, w, h), bg)
            scene.render(p, QRectF(0, 0, w, h), source)
            p.end()
        else:
            raise ValueError(f"Unknown format: {fmt}")
    finally:
        for it in items:
            it.setExportMode(False)
        for it, pen in saved:
            it.setPen(pen)
    if fmt != "png" and not os.path.exists(path):
        raise OSError(f"Could not write {path}")


def _svg_body(scene, source) -> str:
    """SVG elements (no header) of the scene region `source`, drawn by Qt's SVG generator."""
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    from PySide6.QtSvg import QSvgGenerator
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.WriteOnly)
    gen = QSvgGenerator()
    gen.setOutputDevice(buf)
    w, h = int(round(source.width())), int(round(source.height()))
    gen.setSize(QSize(w, h))
    gen.setViewBox(QRect(0, 0, w, h))
    gen.setResolution(96)
    p = QPainter(gen)
    scene.render(p, QRectF(0, 0, source.width(), source.height()), source)
    p.end()
    buf.close()
    text = bytes(data).decode("utf-8")
    start = text.find("</defs>")
    start = text.find(">", text.find("</desc>")) + 1 if start < 0 else start + len("</defs>")
    return text[start:text.rfind("</svg>")]


def _write_svg(canvas, path, source, bg):
    """Qt's SVG generator cannot clip, so lines would stick out of the plot area over the axes. The
    plot area and the axes are therefore drawn separately and the plot area is clipped in the file."""
    plot_item = canvas.plot.getPlotItem()
    scene, vb = canvas.plot.scene(), canvas.vb
    axes = [ax for ax in (plot_item.getAxis(n) for n in ("left", "bottom", "top", "right")) if ax.isVisible()]
    for ax in axes:
        ax.setVisible(False)
    try:
        plot_body = _svg_body(scene, source)
    finally:
        for ax in axes:
            ax.setVisible(True)
    vb.setVisible(False)
    try:
        axes_body = _svg_body(scene, source)
    finally:
        vb.setVisible(True)
    w, h = source.width(), source.height()
    clip = vb.sceneBoundingRect().translated(-source.topLeft())
    back = "" if bg is None else \
        f'<rect x="0" y="0" width="{w:g}" height="{h:g}" fill="{bg.name()}" stroke="none"/>\n'
    svg = (f'<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
           f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
           f'version="1.2" width="{w:g}px" height="{h:g}px" viewBox="0 0 {w:g} {h:g}">\n'
           f'<title>Potential Flow Lab figure</title>\n'
           f'<defs><clipPath id="plot-area"><rect x="{clip.x():g}" y="{clip.y():g}" '
           f'width="{clip.width():g}" height="{clip.height():g}"/></clipPath></defs>\n'
           f'{back}{axes_body}\n<g clip-path="url(#plot-area)">\n{plot_body}\n</g>\n</svg>\n')
    # the program's fonts are not installed on other computers: give every font a common fallback
    for family, fallback in (("IBM Plex Mono", "Consolas, 'Courier New', monospace"),
                             ("Barlow Condensed", "'Arial Narrow', sans-serif"),
                             ("Barlow", "'Segoe UI', Arial, sans-serif")):
        svg = svg.replace(f'font-family="{family}"', f'font-family="{family}, {fallback}"')
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)


# ---------------------------------------------------------------------------------------- data
DATASETS = (("elements", "Elements (parameters)"),
            ("stagnation", "Stagnation points"),
            ("streamlines", "Streamlines in view (x, y of every point)"),
            ("field", "Velocity field on a grid (u, v, |V|, Cp, φ, ψ)"))


def _fmt(v) -> str:
    if isinstance(v, (float, np.floating)):
        return "" if not np.isfinite(v) else repr(round(float(v), 10))
    return str(v)


def element_rows(elements):
    """Wide table: one row per element, one column per parameter name (empty if not used)."""
    keys = []
    for e in elements:
        for p in e.PARAMS:
            if p.key not in keys:
                keys.append(p.key)
    header = ["index", "type", "enabled"] + keys + ["summary"]
    rows = []
    for i, e in enumerate(elements, 1):
        own = {p.key for p in e.PARAMS}
        rows.append([i, e.TYPE, int(e.enabled)] + [_fmt(getattr(e, k)) if k in own else "" for k in keys]
                    + [e.summary()])
    return header, rows


def stagnation_rows(points):
    header = ["index", "x [m]", "y [m]", "kind", "description"]
    return header, [[i, _fmt(p.x), _fmt(p.y), p.kind, p.describe()] for i, p in enumerate(points, 1)]


def streamline_rows(lines, view):
    """Points of the streamlines that are (partly) in view; one row per point."""
    (x0, x1), (y0, y1) = view
    header = ["line", "point", "x [m]", "y [m]"]
    rows, n = [], 0
    for ln in lines:
        ln = np.asarray(ln)
        if not len(ln) or not np.any((ln[:, 0] >= x0) & (ln[:, 0] <= x1) & (ln[:, 1] >= y0) & (ln[:, 1] <= y1)):
            continue
        n += 1
        rows += [[n, k, _fmt(x), _fmt(y)] for k, (x, y) in enumerate(ln, 1) if np.isfinite(x) and np.isfinite(y)]
    return header, rows


def field_rows(elements, view, nx: int):
    """u, v, |V|, Cp, φ, ψ on an nx × ny grid over the view (same spacing in x and y). Points in the
    solid or on a singularity are left empty. ψ (and φ) of a vortex (source) are multi-valued: they
    jump across a branch cut, as in the textbook formulas."""
    (x0, x1), (y0, y1) = view
    ny = max(2, int(round((nx - 1) * (y1 - y0) / (x1 - x0))) + 1)
    X, Y = np.meshgrid(np.linspace(x0, x1, nx), np.linspace(y0, y1, ny))
    z = (X + 1j * Y).ravel()
    u, v = velocity(elements, z.real, z.imag)
    u, v = np.asarray(u, float).ravel(), np.asarray(v, float).ravel()
    F = np.asarray(complex_potential(elements, z)).ravel()
    bad = ~np.asarray(fluid_mask(elements, z), bool).ravel()
    bad |= np.asarray(singularity_mask(elements, z, 1e-9 * (x1 - x0)), bool).ravel()
    speed = np.hypot(u, v)
    v_ref = reference_speed(elements)
    cp = 1.0 - (speed / v_ref) ** 2 if v_ref else np.full_like(speed, np.nan)
    cols = [z.real, z.imag, u, v, speed, cp, F.real, F.imag]
    for c in cols[2:]:
        c[bad] = np.nan
    header = ["x [m]", "y [m]", "u [m/s]", "v [m/s]", "|V| [m/s]", "Cp", "phi [m2/s]", "psi [m2/s]"]
    rows = [[_fmt(c[i]) for c in cols] for i in range(z.size)]
    return header, rows


def write_csv(path: str, header, rows, separator: str = ","):
    """UTF-8 with BOM (Excel shows Γ, μ correctly). separator ',' -> numbers with a decimal point
    (Python, MATLAB, English Excel); ';' -> decimal comma, as Excel with Turkish settings expects."""
    def cell(v):
        if separator == ";" and isinstance(v, str) and v and v[0] in "-0123456789" and _is_number(v):
            return v.replace(".", ",")
        return v
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.writer(f, delimiter=separator)
        wr.writerow(header)
        wr.writerows([[cell(v) for v in row] for row in rows])


def _is_number(text: str) -> bool:
    try:
        float(text)
        return True
    except ValueError:
        return False


def export_data(path: str, datasets, elements, canvas, grid_nx: int = 101, separator: str = ","):
    """Write the chosen tables. One table -> `path`; several -> path stem + '_elements.csv' etc.
    Returns the written paths."""
    view = canvas.vb.viewRange()
    view = ((float(view[0][0]), float(view[0][1])), (float(view[1][0]), float(view[1][1])))
    tables = {
        "elements": lambda: element_rows(elements),
        "stagnation": lambda: stagnation_rows(canvas.stagnation_points),
        "streamlines": lambda: streamline_rows(canvas.last_result.lines if canvas.last_result else [], view),
        "field": lambda: field_rows(elements, view, grid_nx),
    }
    chosen = [d for d in datasets if d in tables]
    stem, ext = os.path.splitext(path)
    ext = ext or ".csv"
    written = []
    for d in chosen:
        out = stem + ext if len(chosen) == 1 else f"{stem}_{d}{ext}"
        header, rows = tables[d]()
        write_csv(out, header, rows, separator)
        written.append(out)
    return written


# ---------------------------------------------------------------------------------------- dialogs
class ExportFigureDialog(QDialog):
    """Format, resolution (PNG), background and colors of the exported figure."""

    def __init__(self, canvas, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export figure")
        self.canvas = canvas
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)
        title = QLabel("Export figure")
        title.setObjectName("DialogTitle")
        lay.addWidget(title)
        note = QLabel("The plot as shown (view, layers, selection), with its axes.")
        note.setObjectName("Muted")
        lay.addWidget(note)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(18)
        self.fmt_buttons = {}
        group = QButtonGroup(self)
        for key, text in (("png", "PNG image"), ("svg", "SVG (vector)"), ("pdf", "PDF (vector)")):
            b = QRadioButton(text)
            group.addButton(b)
            fmt_row.addWidget(b)
            self.fmt_buttons[key] = b
            b.toggled.connect(self._update)
        fmt_row.addStretch(1)
        form.addRow("Format", fmt_row)

        self.scale = themed_combo(QComboBox())
        for k in (1, 2, 3, 4):
            self.scale.addItem(f"{k}×", k)
        self.scale.currentIndexChanged.connect(self._update)
        self.size_label = QLabel("")
        self.size_label.setObjectName("Muted")
        res = QHBoxLayout()
        res.addWidget(self.scale)
        res.addWidget(self.size_label, 1)
        self.res_row = QWidget()
        self.res_row.setLayout(res)
        res.setContentsMargins(0, 0, 0, 0)
        form.addRow("Resolution", self.res_row)

        self.background = themed_combo(QComboBox())
        for key, text in (("paper", "Plot color"), ("white", "White"), ("transparent", "Transparent")):
            self.background.addItem(text, key)
        form.addRow("Background", self.background)

        self.mirror = QCheckBox("Axes on all four sides (plot area centered)")
        self.mirror.setToolTip("The figure gets the same axis bar on the top and the right as on the bottom "
                               "and the left (only in the file; the screen does not change)")
        self.mirror_numbers = QCheckBox("with numbers and axis titles")
        self.mirror.toggled.connect(self._update)
        form.addRow("Frame", self.mirror)
        form.addRow("", self.mirror_numbers)

        self.light = QCheckBox("Light colors (for printing)")
        self.light.setToolTip("The dark theme is exported with the colors of the light theme")
        self.light.setVisible(canvas.theme["name"] != "light")
        form.addRow("", self.light)
        lay.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Export…")
        ok.setObjectName("Primary")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(ok)
        lay.addLayout(buttons)

        self.fmt_buttons.get(settings.get("format", "png"), self.fmt_buttons["png"]).setChecked(True)
        self.scale.setCurrentIndex(max(0, self.scale.findData(int(settings.get("scale", 2)))))
        self.background.setCurrentIndex(max(0, self.background.findData(settings.get("background", "paper"))))
        self.light.setChecked(bool(settings.get("light", True)))
        self.mirror.setChecked(bool(settings.get("mirror", True)))
        self.mirror_numbers.setChecked(bool(settings.get("mirror_numbers", True)))
        self._update()

    def fmt(self) -> str:
        return next(k for k, b in self.fmt_buttons.items() if b.isChecked())

    def options(self) -> dict:
        return {"format": self.fmt(), "scale": int(self.scale.currentData()),
                "background": self.background.currentData(),
                "light": self.light.isChecked() and self.light.isVisible(),
                "mirror": self.mirror.isChecked(), "mirror_numbers": self.mirror_numbers.isChecked()}

    def _update(self, *_):
        png = self.fmt() == "png" if any(b.isChecked() for b in self.fmt_buttons.values()) else True
        self.res_row.setEnabled(png)
        if hasattr(self, "mirror"):
            self.mirror_numbers.setEnabled(self.mirror.isChecked())
        s = figure_size(self.canvas)
        k = int(self.scale.currentData() or 1)
        self.size_label.setText(f"→ {s.width() * k} × {s.height() * k} px" if png
                                else "vector: sharp at any size")


class ExportDataDialog(QDialog):
    """Which tables to write, grid size of the field, CSV separator."""

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export data")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)
        title = QLabel("Export data (CSV)")
        title.setObjectName("DialogTitle")
        lay.addWidget(title)
        note = QLabel("Several tables are written as separate files: name_elements.csv, name_field.csv …")
        note.setObjectName("Muted")
        note.setWordWrap(True)
        lay.addWidget(note)
        chosen = settings.get("datasets", ["elements", "stagnation"])
        self.boxes = {}
        for key, text in DATASETS:
            c = QCheckBox(text)
            c.setChecked(key in chosen)
            c.toggled.connect(self._update)
            lay.addWidget(c)
            self.boxes[key] = c
        form = QFormLayout()
        self.grid = QSpinBox()
        self.grid.setRange(11, 1001)
        self.grid.setSingleStep(10)
        self.grid.setValue(int(settings.get("grid", 101)))
        self.grid.setSuffix("  points across")
        form.addRow("Field grid", self.grid)
        self.separator = themed_combo(QComboBox())
        self.separator.addItem("Comma  ,", ",")
        self.separator.addItem("Semicolon ;  decimal comma  (Excel with Turkish settings)", ";")
        self.separator.setCurrentIndex(max(0, self.separator.findData(settings.get("separator", ","))))
        form.addRow("Separator", self.separator)
        lay.addLayout(form)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        self.ok = QPushButton("Export…")
        self.ok.setObjectName("Primary")
        self.ok.setDefault(True)
        self.ok.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(self.ok)
        lay.addLayout(buttons)
        self._update()

    def options(self) -> dict:
        return {"datasets": [k for k, c in self.boxes.items() if c.isChecked()],
                "grid": self.grid.value(), "separator": self.separator.currentData()}

    def _update(self, *_):
        self.ok.setEnabled(any(c.isChecked() for c in self.boxes.values()))
        self.grid.setEnabled(self.boxes["field"].isChecked())
