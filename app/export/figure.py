"""
figure.py — the plot as a figure file (PNG / SVG / PDF), as it is on the screen (view, layers,
selection), axes included, without the program around it.

PNG can be 1×–4× the screen resolution: line widths, arrows, symbols and the animation picture
(particles / pulses, drawn again at that resolution) grow with it, so a 3× PNG looks like the screen,
only sharper. SVG and PDF are vector files (lines stay sharp at any zoom, good for the
report). Option: light colors for a figure exported from the dark theme.
"""
import os
from contextlib import contextmanager, nullcontext

import pyqtgraph as pg
from PySide6.QtCore import QMarginsF, QRect, QRectF, QSize, QSizeF, Qt
from PySide6.QtGui import QColor, QImage, QPageSize, QPainter, QPdfWriter, QPen
from PySide6.QtWidgets import QGraphicsItem

from ..theme import LIGHT

FORMATS = {"png": "PNG image", "svg": "SVG (vector)", "pdf": "PDF (vector)"}
ANIMATION_WARMUP_FRAMES = 60          # animating: 1 s at 60 fps unseen before the figure (trails)
VECTOR_PICTURE_SCALE = 2.0            # the particle / pulse picture inside an SVG / PDF (pixels there)
BACKGROUNDS = {"paper": "Plot color", "white": "White", "transparent": "Transparent"}


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


def _pinned_items(scene) -> list:
    """Items drawn at a fixed screen size (the color legends): in a k× export they must grow with the
    rest, so the flag is cleared during the export and set again afterwards (restore_pinned)."""
    flag = QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations
    out = [it for it in scene.items() if it.flags() & flag]
    for it in out:
        it.setFlag(flag, False)
    return out


def restore_pinned(items):
    for it in items:
        it.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)


def render_figure(canvas, path: str, fmt: str, scale: float = 2.0, background: str = "paper",
                  light: bool = False, mirror: bool = True, mirror_numbers: bool = True):
    """Write the plot to `path` (png / svg / pdf). Raises OSError if the file cannot be written.
    mirror: axes on all four sides (centered plot area), see mirrored_axes."""
    fmt = fmt.lower()
    theme_before = canvas.theme
    cached = getattr(canvas, "static_cache", False)
    if cached:
        canvas.set_static_cache(False)                     # animating: draw the items, not screen pictures
    if light and canvas.theme["name"] != "light":
        canvas.apply_theme(LIGHT)                          # print colors; the screen theme comes back
    try:
        with mirrored_axes(canvas, mirror_numbers) if mirror else nullcontext():
            with _sharp_animation(canvas, float(scale) if fmt == "png" else VECTOR_PICTURE_SCALE):
                _render(canvas, path, fmt, scale, background)
    finally:
        if canvas.theme is not theme_before:
            canvas.apply_theme(theme_before)
        if cached:
            canvas.set_static_cache(True)


@contextmanager
def _sharp_animation(canvas, scale: float):
    """Animating: the particle / pulse picture is drawn again at the resolution of the figure (a 3×
    PNG gets sharp trails, not the screen picture enlarged); the animation runs ~1 s unseen for the
    trails. Paused: the pulses are drawn as they are; the particles keep the screen picture (moving
    them would lose the paused moment)."""
    layer = canvas.animation if getattr(canvas, "animated", False) else None
    if layer is None or (layer.paused and not layer.DRAW_WHILE_PAUSED):
        yield
        return
    layer.set_export_scale(scale)
    try:
        if layer.paused:
            layer.advance(0.0)
        else:
            for _ in range(ANIMATION_WARMUP_FRAMES):
                layer.advance(1.0 / 60.0)
        yield
    finally:
        layer.set_export_scale(None)


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
    pinned = _pinned_items(scene)
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
        restore_pinned(pinned)
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
