"""
smoothness.py — how smooth does the window feel while the user pans and zooms?

    python scripts/smoothness.py                 (runs in a real window)
    QT_QPA_PLATFORM=offscreen python scripts/smoothness.py

A timer in the GUI thread fires every 16 ms (60 fps) and moves the view a little, like a hand
dragging the plot; part of the run zooms in and out. Measured:
  frame gap   time between two timer ticks; ideally 16 ms. Long gaps = the window stutters
              (e.g. while the GUI thread waits for the streamline computation).
  stale       share of ticks where the drawn streamlines do not cover the visible region yet
              (empty edges after a pan / zoom).
"""
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from physics import Doublet, SymmetryWall, Source, Uniform, Vortex  # noqa: E402

SCENES = {
    "lifting cylinder": [Uniform(), Doublet(mu=1.0), Vortex(Gamma=-2.0)],
    "channel": [SymmetryWall(yw=-1.0), SymmetryWall(yw=1.0, side=1), Uniform(),
                Source(m=1.0, x0=-1.5, y0=0.3), Vortex(Gamma=1.0, x0=1.5, y0=-0.3)],
}
DURATION_S = 4.0


def run(win, app, elements):
    from app.main_window import MainWindow  # noqa: F401
    win.load_scene(list(elements), ((-4.0, 4.0), (-3.0, 3.0)), title="smoothness")
    for _ in range(40):
        win.canvas.wait_idle(50)
        app.processEvents()
    cv = win.canvas
    ticks, stale, phases = [], [], []
    computed = []
    cv.computed.connect(lambda n, ms: computed.append(ms))
    t_start = time.perf_counter()
    state = {"k": 0}

    def tick():
        now = time.perf_counter()
        ticks.append(now)
        k = state["k"]
        state["k"] += 1
        (x0, x1), (y0, y1) = cv.vb.viewRange()
        w = x1 - x0
        phase = (now - t_start) / DURATION_S
        phases.append(phase < 0.5)
        if phase < 0.5:                                   # pan right / up
            dx, dy, s = 0.006 * w, 0.002 * w, 1.0
        else:                                             # zoom in and out
            dx, dy, s = 0.0, 0.0, 1.0 + 0.01 * np.sin(k / 8.0)
        cx, cy = 0.5 * (x0 + x1) + dx, 0.5 * (y0 + y1) + dy
        hw, hh = 0.5 * w * s, 0.5 * (y1 - y0) * s
        cv.set_view((cx - hw, cx + hw), (cy - hh, cy + hh))
        stale.append(not cv.covers_view() if hasattr(cv, "covers_view") else None)
        if now - t_start > DURATION_S:
            timer.stop()
            app.quit()

    timer = QTimer()
    timer.setInterval(16)
    timer.timeout.connect(tick)
    timer.start()
    app.exec()
    gaps = np.diff(ticks) * 1000.0
    pan = np.array(phases[1:])
    st = [s for s in stale if s is not None]
    out = {"frames": len(ticks), "computations": len(computed),
           "stale %": 100.0 * float(np.mean(st)) if st else float("nan")}
    for name, sel in (("pan", pan), ("zoom", ~pan)):
        g = gaps[sel]
        out[name] = (float(np.median(g)), float(np.percentile(g, 95)), float(np.max(g)))
    return out


def main():
    from app.main_window import MainWindow, setup_application
    app = QApplication.instance() or QApplication(sys.argv)
    setup_application(app)
    win = MainWindow()
    win._ask_save_changes = lambda: "discard"
    win.resize(1400, 860)
    win.show()
    app.processEvents()
    print(f"{'scene':<18}{'frames':>7}{'jobs':>6}   {'pan: median / p95 / max':<26}"
          f"{'zoom: median / p95 / max':<27}{'stale %':>8}   (frame gaps in ms)")
    for name, els in SCENES.items():
        r = run(win, app, els)
        pan = " / ".join(f"{v:.0f}" for v in r["pan"])
        zoom = " / ".join(f"{v:.0f}" for v in r["zoom"])
        print(f"{name:<18}{r['frames']:>7}{r['computations']:>6}   {pan:<26}{zoom:<27}{r['stale %']:>8.1f}")
    win.close()


if __name__ == "__main__":
    main()
