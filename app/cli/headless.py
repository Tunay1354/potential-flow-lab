"""
headless.py — the plot without a window (command line): a PlotCanvas that is never shown on the
screen, sized so that its plot area has the shape of the view, with everything computed at once
(no background threads) before a figure or the data is written.
"""
from __future__ import annotations

import os
import sys

PLOT_WIDTH = 900                      # plot area width (screen pixels) of a figure; ×scale in a PNG


def application():
    """The QApplication (one per process), set up like the program's. Linux without a display uses
    Qt's 'offscreen' platform; elsewhere the normal one is used, the canvas is simply never shown."""
    if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import qInstallMessageHandler
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        qInstallMessageHandler(_quiet)
        app = QApplication([sys.argv[0]])
        from app.startup import setup_application
        setup_application(app)
    return app


def _quiet(_mode, _context, message):
    """Qt's messages on the console, except the offscreen platform's notes on window sizes."""
    if "propagateSizeHints" not in message:
        print(message, file=sys.stderr)


def make_canvas(dark: bool = False):
    """A PlotCanvas that never appears on the screen and computes in the calling thread."""
    from PySide6.QtCore import Qt

    from app.canvas import PlotCanvas
    from app.theme import DARK, LIGHT
    app = application()
    cv = PlotCanvas(DARK if dark else LIGHT, [])
    cv.setAttribute(Qt.WA_DontShowOnScreen, True)
    cv.bar.setVisible(False)                 # not in a figure; without them any plot size is possible
    cv.title_block.setVisible(False)
    cv.streamlines.background = False
    cv.surfaces.background = False
    cv.resize(PLOT_WIDTH + 120, 760)
    cv.show()
    app.processEvents()
    return cv


def fit_plot_area(cv, view, width: int | None = None, height: int | None = None):
    """Resize the canvas so that its plot area (the view box) has the aspect ratio of the view (the
    aspect is locked: x and y in the same scale), `width` pixels wide (or `height` high), then show
    exactly that view."""
    from PySide6.QtWidgets import QApplication
    (x0, x1), (y0, y1) = view
    aspect = (y1 - y0) / (x1 - x0)
    if width is None and height is None:
        width = PLOT_WIDTH
    w = int(width) if width is not None else max(80, int(round(height / aspect)))
    h = int(height) if height is not None and width is not None else max(80, int(round(w * aspect)))
    for _ in range(4):                       # the bar, the axes and the title block take the rest
        QApplication.processEvents()
        r = cv.vb.sceneBoundingRect()
        dw, dh = w - r.width(), h - r.height()
        if abs(dw) < 1 and abs(dh) < 1:
            break
        cv.resize(int(round(cv.width() + dw)), int(round(cv.height() + dh)))
    cv.set_view((x0, x1), (y0, y1))
    QApplication.processEvents()


def show_scene(cv, doc, view=None, layers=None, size=(None, None)):
    """Put a scene (SceneDocument) on the canvas — its plot settings, its view (or `view`), the layer
    switches `layers` {key: on} — and compute everything now."""
    from PySide6.QtWidgets import QApplication
    settings = cv.settings.updated(doc.settings)
    cv.apply_settings(settings)
    for key, on in (layers or {}).items():
        cv.layers[key] = bool(on)
    if view is None:
        view = doc.view
    cv.set_elements(list(doc.elements))
    if view is None:
        cv.fit_view()
        view = cv.view()
    fit_plot_area(cv, view, *size)
    cv.compute_now()
    cv.apply_visibility()
    QApplication.processEvents()
    return cv
