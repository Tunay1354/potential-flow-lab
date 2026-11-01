"""
benchmark.py — how fast is everything? One run measures the whole program as the user feels it, so that
a later change (e.g. drawing with the graphics card, OpenGL) can be compared number by number.

    python scripts/benchmark.py                      (a real window: the honest numbers for this PC)
    python scripts/benchmark.py --out results.json   (also writes every number to a JSON file)
    python scripts/benchmark.py --quick              (shorter runs, fewer repeats)
    python scripts/benchmark.py --only startup,compute,paint,interact,anim,limits,export,verify
    QT_QPA_PLATFORM=offscreen python scripts/benchmark.py   (no window, e.g. on a server)
    python scripts/benchmark.py --full --out benchmarks/NAME.json
                                    (THE ONE TO RUN: everything, then paint / interact / anim / limits again with
                                     the graphics card — one file, ~8–10 min)
    python scripts/benchmark.py --gpu --out after.json        (the plot drawn by the graphics card, OpenGL)
    python scripts/benchmark.py --gpu --fps-cap screen        (animations as fast as the screen shows)

Compare a run without and with --gpu on the same computer: the sections paint, interact and anim show what
the graphics card changes (compute and export do not use it). --fps-cap: the frame rate limit of the
animations with --gpu (default 60, the same as without the graphics card, so the numbers compare).

The program itself is not changed: the script opens the normal window (1536 × 830, the owner's screen at
125 %), loads scenes and drives it like a user. It never touches your settings or files (Qt test folders,
the exports go to a temporary folder).

Sections
  startup   start the program in a fresh process: imports, window, first streamlines; Numba cold (first
            start ever, the kernels are compiled) and warm (compiled kernels from the cache)
  compute   the computations alone, per scene (median of repeats): streamlines, field layers φ / |V| / Cp
            (grid Medium and High), solid bodies, surface pressure, everything at once
  paint     drawing the plot once (what a graphics card would speed up): default layers / every layer;
            "plot frame" = update → painted (→ finished by the graphics card), "paint (CPU part)" = the time
            inside the plot's paint (with OpenGL the graphics card works on after it)
  interact  the window as a hand moves it: a 60 fps timer pans, zooms, drags an element (Move mode, live
            update on / off), and how long until the plot follows a slider, an added element, an undo,
            a window resize. Frame gap = time between two timer ticks (16.7 ms = 60 fps; long gaps =
            stutter)
  anim      Particles and Pulses at the default and the maximum settings: frames per second actually
            drawn, the render time of one frame, and how smooth the window stays
  export    PNG 1× / 2× / 4×, SVG, PDF, CSV (all tables), GIF and MP4 (2 s)
  limits    the heaviest a user can do (a few seconds each): 16 elements at the densest streamlines with every
            layer — computing, pan / zoom / dragging an element, the most particles the slider allows and the
            longest, densest pulses (with the card: as fast as the screen), PNG 4× and MP4 2× of it
  verify    Help → Run verification (102 checks), without and with figures
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

WINDOW = (1536, 830)
FRAME_MS = 1000.0 / 60.0
SCENES = {          # name: preset file (relative to presets/), or a list of elements made below
    "lifting cylinder": "1 Verification cases (assignment)/08_lifting_cylinder.pflow",
    "Rankine oval": "2 Bodies/02_rankine_oval.pflow",
    "vortex in 60° corner": "4 Walls/03_vortex_in_60_corner.pflow",
    "channel": "4 Walls/04_channel.pflow",
    "source in corner flow": "3 Sector flows/05_source_in_corner_flow.pflow",
    "busy (8 elements)": None,
}
STRESS = "stress (16 elements)"                # the limits section's scene (stress_scene)
SECTIONS = ("startup", "compute", "paint", "interact", "anim", "limits", "export", "verify")
GPU_SECTIONS = ("paint", "interact", "anim", "limits")      # --full: these again with the graphics card


# ---------------------------------------------------------------------------------------------- helpers
def stats(values) -> dict:
    a = np.asarray([v for v in values if v is not None and np.isfinite(v)], float)
    if a.size == 0:
        return {"n": 0}
    return {"n": int(a.size), "median": float(np.median(a)), "p95": float(np.percentile(a, 95)),
            "max": float(a.max()), "min": float(a.min())}


def timed(fn, repeats=5, warm=1) -> dict:
    for _ in range(warm):
        fn()
    out = []
    for _ in range(repeats):
        t = time.perf_counter()
        fn()
        out.append((time.perf_counter() - t) * 1000.0)
    return stats(out)


def busy_scene():
    from physics import Doublet, Source, Uniform, Vortex
    return [Uniform(V=1.0, alpha=10.0), Source(m=2.0, x0=-2.5, y0=0.8), Source(m=-2.0, x0=-1.0, y0=0.8),
            Source(m=1.0, x0=2.0, y0=-1.2), Vortex(Gamma=2.0, x0=1.5, y0=1.0), Vortex(Gamma=-1.5, x0=-2.0, y0=-1.0),
            Doublet(mu=0.6, x0=0.5, y0=-0.2, delta=10.0), Source(m=-1.0, x0=3.0, y0=0.5)]


def stress_scene():
    """16 elements of every kind with a free stream at an angle: the heaviest ordinary scene."""
    from physics import Doublet, Source, Uniform, Vortex
    return [Uniform(V=1.0, alpha=15.0),
            Source(m=2.0, x0=-4.0, y0=1.5), Source(m=-1.5, x0=-3.0, y0=-1.8), Source(m=1.2, x0=3.5, y0=2.0),
            Source(m=-2.0, x0=4.0, y0=-1.0), Source(m=0.8, x0=0.5, y0=2.4), Source(m=-0.8, x0=-0.5, y0=-2.4),
            Vortex(Gamma=2.5, x0=-2.0, y0=0.5), Vortex(Gamma=-2.0, x0=2.0, y0=-0.5), Vortex(Gamma=1.0, x0=0.0, y0=1.2),
            Vortex(Gamma=-1.2, x0=-1.0, y0=-1.0),
            Doublet(mu=0.8, x0=0.0, y0=0.0, delta=15.0), Doublet(mu=0.4, x0=-3.0, y0=0.0, delta=60.0),
            Doublet(mu=0.5, x0=3.0, y0=0.5, delta=-30.0), Source(m=1.0, x0=1.5, y0=-2.0), Vortex(Gamma=0.8, x0=2.8, y0=1.5)]


def load(name):
    from model.scene_file import load_scene as read_scene_file
    if name == STRESS:
        return stress_scene(), ((-5.0, 5.0), (-3.0, 3.0))
    path = SCENES[name]
    if path is None:
        return busy_scene(), ((-4.0, 4.0), (-2.6, 2.6))
    doc = read_scene_file(os.path.join(ROOT, "presets", path))
    return doc.elements, doc.view


class Bench:
    def __init__(self, quick: bool, use_gpu: bool = False, fps_cap: str = "60"):
        self.quick = quick
        self.use_gpu = use_gpu
        self.fps_cap = fps_cap
        self.gpu_info = None
        self.tag = ""                         # " [GPU]" while --full repeats sections with the graphics card
        self.results: dict = {}
        self.app = self.win = None

    # ------------------------------------------------------------------ the window
    def open(self):
        from PySide6.QtCore import QSettings, QStandardPaths
        QStandardPaths.setTestModeEnabled(True)                      # never the user's settings / files
        from PySide6.QtWidgets import QApplication
        self.app = QApplication.instance() or QApplication(sys.argv)
        from app.main_window import MainWindow
        from app.startup import setup_application
        setup_application(self.app)
        try:
            from app import hardware
            hardware.detect()                              # (this computer, for the report; remembered)
        except Exception:                                  # noqa: BLE001
            pass
        QSettings().setValue("beaver/tour_offered", True)
        QSettings().setValue("gpu/enabled", False)              # switched on below (--gpu), never left over
        from app.scene import starter_scene                     # (the scene the numbers were always taken with)
        MainWindow.START_SCENE = ("Lifting (rotating) cylinder", starter_scene)
        self.win = MainWindow()
        w = self.win
        w._ask_save_changes = lambda: "discard"
        w._notify_user = lambda *a: print("   note:", *a[1:], flush=True)
        w._ask_strong_card = lambda strong: "no"
        w.setFixedSize(*WINDOW)
        w.show()
        w.activateWindow()
        self.pump(1.0)
        if self.use_gpu:
            self.gpu_on()
        from physics.warmup import warm_up
        warm_up()                                                    # compiled kernels ready (startup measures that)

    def gpu_on(self, must: bool = True) -> bool:
        """--gpu: the plot drawn by the graphics card, as when the GPU box is ticked (also on software
        OpenGL, which the box would refuse: the numbers say how it compares)."""
        from app import gpu
        w = self.win
        support = gpu.support
        gpu.support = lambda p: (True, "benchmark")
        try:
            w.set_gpu(True, user=False)
        finally:
            gpu.support = support
        end = time.perf_counter() + 15
        while w._gpu_frames < 2 and w.canvas.gpu and time.perf_counter() < end:
            self.pump(0.1)
        if not w.canvas.gpu or w._gpu_frames < 2:
            if not must:
                print("   the graphics card did not draw the plot: the [GPU] part is skipped", flush=True)
                return False
            raise SystemExit("--gpu: the graphics card did not draw the plot (see the note above); "
                             "run without --gpu")
        w.set_fps_cap(self.fps_cap)
        self.gpu_info = dict(w.canvas.gpu_info or {})
        from app import hardware
        weak = hardware.runs_on_weak_card(self.gpu_info.get("renderer", ""), self.gpu_info.get("vendor", ""),
                                          hardware.display_adapters())
        if weak is not None:
            print(f"   WARNING: drawn by {self.gpu_info.get('renderer')}, not by {weak['name']}: the [GPU] numbers "
                  "are the slower card's", flush=True)
        print(f"   graphics card: {self.gpu_info.get('renderer')} ({self.gpu_info.get('samples')}× smoothing), "
              f"animation frames every {w.canvas.particles.frame_interval} ms", flush=True)
        self.use_gpu = True
        return True

    def finish_gl(self, vp):
        """Wait until the graphics card has really drawn (OpenGL works asynchronously)."""
        from PySide6.QtOpenGLWidgets import QOpenGLWidget
        if isinstance(vp, QOpenGLWidget) and vp.isValid():
            vp.makeCurrent()
            vp.context().functions().glFinish()
            vp.doneCurrent()

    def pump(self, seconds):
        end = time.perf_counter() + seconds
        while time.perf_counter() < end:
            self.app.processEvents()
            time.sleep(0.002)

    def settle(self, timeout=20.0):
        cv = self.win.canvas
        end = time.perf_counter() + timeout
        while time.perf_counter() < end:
            idle = cv.wait_idle(20)
            self.app.processEvents()
            if idle:
                break
        self.pump(0.05)

    def show(self, name, layers=()):
        from app.canvas import LAYERS
        els, view = load(name)
        w, cv = self.win, self.win.canvas
        cv.set_view_mode("static")
        cv.set_mode("select")
        for key, _label, default in LAYERS:
            w.settings_panel.layer_boxes[key].setChecked(key in layers or (default and key not in ("dividing",)))
        w.load_scene(list(els), view, title=name)
        self.settle()

    def record(self, section, key, value):
        self.results.setdefault(section + self.tag, {})[key] = value

    # ------------------------------------------------------------------ sections
    def startup(self):
        code = r"""
import os, sys, time, json
t0 = time.perf_counter()
sys.path.insert(0, %r)
from PySide6.QtCore import QStandardPaths, QSettings
QStandardPaths.setTestModeEnabled(True)
from PySide6.QtWidgets import QApplication
app = QApplication([])
from app.startup import setup_application
setup_application(app); QSettings().setValue("beaver/tour_offered", True)
QSettings().setValue("gpu/enabled", False)
t_import = time.perf_counter()
import main as M                                   # the real start: detect the computer, prepare the kernels
w = M.open_window(None); w._ask_save_changes = lambda: "discard"; w.setFixedSize(%d, %d); w.show()
app.processEvents()
t_window = time.perf_counter()
cv = w.canvas
while cv.last_result is None and time.perf_counter() - t0 < 300:
    cv.wait_idle(20); app.processEvents()
t_lines = time.perf_counter()
from physics.warmup import warm_up
warm_up()
t_warm = time.perf_counter()
print(json.dumps({"import_ms": (t_import - t0) * 1e3, "window_ms": (t_window - t_import) * 1e3,
                  "first_lines_ms": (t_lines - t_window) * 1e3, "to_first_lines_ms": (t_lines - t0) * 1e3,
                  "all_kernels_ready_ms": (t_warm - t0) * 1e3}))
w.model.mark_clean(); w.close()
""" % (ROOT, *WINDOW)
        cache = tempfile.mkdtemp(prefix="pfl-numba-")
        env = dict(os.environ, NUMBA_CACHE_DIR=cache)
        for label in ("cold (first start: Numba compiles)", "warm (kernels from the cache)"):
            t = time.perf_counter()
            out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True,
                                 timeout=900)
            total = (time.perf_counter() - t) * 1000.0
            line = next((ln for ln in out.stdout.splitlines() if ln.startswith("{")), None)
            if line is None:
                self.record("startup", label, {"error": out.stderr[-500:]})
                continue
            r = json.loads(line)
            r["process_total_ms"] = total
            self.record("startup", label, r)

    def compute(self):
        reps = 3 if self.quick else 5
        cv = self.win.canvas
        for name in SCENES:
            self.show(name)
            row = {"streamlines": timed(cv.streamlines.recompute, reps)}
            for key in ("equipotential", "speed", "cp"):
                for q, qname in ((2, "Medium"), (3, "High")):
                    cv.set_field_quality(q)
                    cv.set_layer(key, True)
                    row[f"{key} ({qname})"] = timed(lambda: cv.fields.schedule(force=True, now=True), reps)
                    cv.set_layer(key, False)
                cv.set_field_quality(2)
            cv.set_layer("bodies", True)
            row["solid bodies"] = timed(cv.bodies.update, reps)
            cv.set_layer("surface", True)
            surf = cv.surfaces

            def surface_now():
                bg, surf.background = surf.background, False
                surf.refresh()
                surf.background = bg
            row["surface pressure"] = timed(surface_now, reps)
            for key in ("equipotential", "speed", "dividing"):
                cv.set_layer(key, True)
            row["everything at once"] = timed(cv.compute_now, reps)
            self.record("compute", name, row)
            self.show(name)                                          # layers back to the defaults

    def paint(self):
        reps = 5 if self.quick else 10
        cv = self.win.canvas
        vp = cv.plot.viewport()
        for name in ("lifting cylinder", "channel", "busy (8 elements)"):
            row = {}
            for label, layers in (("default layers", ()),
                                  ("every layer", ("dividing", "equipotential", "speed", "bodies", "surface"))):
                self.show(name, layers)
                cv.compute_now()
                self.settle()
                cv.plot.meter.clear()
                row[f"plot frame, {label}"] = timed(lambda: self.frame(vp), reps)
                row[f"plot paint (CPU part), {label}"] = stats(list(cv.plot.meter.paint_ms))
                row[f"whole window, {label}"] = timed(lambda: self.frame(self.win), reps)
            self.record("paint", name, row)

    def frame(self, widget):
        """One frame as the user sees it: widget.update(), the event loop until the plot has painted
        (and, with OpenGL, until the graphics card has finished). Same way with and without --gpu."""
        cv = self.win.canvas
        vp = cv.plot.viewport()
        meter = cv.plot.meter
        n = len(meter.stamps)
        widget.update()
        vp.update()
        end = time.perf_counter() + 2.0
        while len(meter.stamps) == n and time.perf_counter() < end:
            self.app.processEvents()
        self.finish_gl(vp)

    def _ticks(self, seconds, step):
        """A 60 fps timer calls step(k, phase); returns the gaps between ticks (ms)."""
        from PySide6.QtCore import QTimer
        ticks = []
        t0 = time.perf_counter()
        state = {"k": 0, "done": False}

        def tick():
            now = time.perf_counter()
            ticks.append(now)
            if now - t0 > seconds:
                state["done"] = True
                timer.stop()
                return
            step(state["k"], (now - t0) / seconds)
            state["k"] += 1

        timer = QTimer()
        timer.setInterval(16)
        timer.timeout.connect(tick)
        timer.start()
        while not state["done"]:
            self.app.processEvents()
            time.sleep(0.0005)
        return list(np.diff(ticks) * 1000.0)

    def interact(self):
        secs = 2.0 if self.quick else 4.0
        w, cv = self.win, self.win.canvas
        jobs = []
        cv.computed.connect(lambda n, ms: jobs.append(ms))

        def pan(k, ph):
            (x0, x1), (y0, y1) = cv.vb.viewRange()
            d = 0.006 * (x1 - x0)
            cv.set_view((x0 + d, x1 + d), (y0 + d / 3, y1 + d / 3))

        def zoom(k, ph):
            (x0, x1), (y0, y1) = cv.vb.viewRange()
            s = 1.0 + 0.012 * np.sin(k / 8.0)
            cx, cy, hw, hh = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2 * s, (y1 - y0) / 2 * s
            cv.set_view((cx - hw, cx + hw), (cy - hh, cy + hh))

        for name in ("lifting cylinder", "channel", "busy (8 elements)"):
            row = {}
            for label, layers in (("", ()), (", every layer", ("equipotential", "speed", "bodies"))):
                for what, fn in (("pan", pan), ("zoom", zoom)):
                    self.show(name, layers)
                    jobs.clear()
                    row[what + label] = {"frame gap": stats(self._ticks(secs, fn)), "computations": len(jobs),
                                         "computation ms": stats(jobs)}
            self.record("interact", name, row)

        # dragging the doublet of the lifting cylinder (Move mode), live update on and off
        it = cv.interaction
        for live in (True, False):
            self.show("lifting cylinder")
            cv.set_live_drag(live)
            cv.set_mode("move")
            el = cv.elements[1]
            start = cv.vb.mapViewToScene(__import__("PySide6.QtCore", fromlist=["QPointF"]).QPointF(el.x0, el.y0))
            ok = it.begin_drag(start)

            def drag(k, ph, start=start):
                from PySide6.QtCore import QPointF
                r = 60.0
                it.drag_to(QPointF(start.x() + r * np.sin(k / 10.0), start.y() + r * (1 - np.cos(k / 10.0))))
            jobs.clear()
            gaps = self._ticks(secs, drag) if ok else []
            it.end_drag()
            self.settle()
            self.record("interact", f"drag the doublet (live update {'on' if live else 'off'})",
                        {"frame gap": stats(gaps), "computations": len(jobs), "started": bool(ok)})
        cv.set_live_drag(True)
        cv.set_mode("select")

        # how long until the plot follows a change (until the streamlines are drawn again)
        def latency(action, n):
            out = []
            for k in range(n):
                done = []
                conn = cv.computed.connect(lambda nn, ms: done.append(time.perf_counter()))
                t = time.perf_counter()
                action(k)
                end = t + 20.0
                while not done and time.perf_counter() < end:
                    self.app.processEvents()
                    time.sleep(0.0005)
                cv.computed.disconnect(conn)
                out.append((done[0] - t) * 1000.0 if done else None)
                self.settle()
            return stats(out)

        n = 3 if self.quick else 6
        self.show("lifting cylinder")
        sl = w.settings_panel.sliders["density"]
        base = sl.value()
        row = {"density slider": latency(lambda k: sl.setValue(base + (1 if k % 2 == 0 else 0)), n)}
        sl.setValue(base)
        self.settle()
        from physics import Source
        row["add an element"] = latency(lambda k: w.model.add(Source(m=0.5, x0=2.0 + 0.1 * k, y0=1.5)), n)
        row["undo"] = latency(lambda k: w.model.undo(), n)
        self.settle()
        row["layer on: speed bands"] = timed(lambda: (w.settings_panel.layer_boxes["speed"].toggle(), self.settle()),
                                            n, warm=1)
        sizes = [(1536, 830), (1200, 700)]

        def resize(k):
            w.setFixedSize(*sizes[(k + 1) % 2])
            self.app.processEvents()
            w.repaint()
        row["window resize (1536×830 ↔ 1200×700)"] = timed(lambda: resize(0) or resize(1), n, warm=1)
        w.setFixedSize(*WINDOW)
        self.record("interact", "reaction time (ms)", row)

    def anim(self):
        secs = 2.5 if self.quick else 5.0
        w, cv = self.win, self.win.canvas
        sp = w.settings_panel.sliders
        cases = [("particles", {"particles": 1500, "trail": 4}),          # the defaults
                 ("particles", {"particles": 5000, "trail": 10}),         # the maximum without the card
                 ("pulses", {"pulse_length": 4, "pulse_spacing": 4}),
                 ("pulses", {"pulse_length": 10, "pulse_spacing": 1})]
        top = sp["particles"].maximum()
        if top > 5000:                                                     # --gpu: the card's maximum too
            cases.insert(2, ("particles", {"particles": top, "trail": 10}))
        for mode, settings in cases:
            for name in ("lifting cylinder", "busy (8 elements)", "lifting cylinder + φ, |V|, dense"):
                if name.endswith("dense"):                    # the owner's view: many layers under the animation
                    self.show("lifting cylinder", ("equipotential", "speed"))
                    sp["density"].setValue(8)
                    self.settle()
                else:
                    self.show(name)
                for key, val in settings.items():
                    if key in sp:
                        sp[key].setValue(val)
                cv.set_view_mode(mode)
                self.pump(1.0)
                lay = cv.animation
                stamps = []
                conn = lay._timer.timeout.connect(lambda: stamps.append(time.perf_counter()))
                lay.frame_ms.clear()
                cv.plot.meter.clear()
                t_start = time.perf_counter()
                gaps = self._ticks(secs, lambda k, ph: None)
                shown = sum(1 for t in cv.plot.meter.stamps if t >= t_start) / (time.perf_counter() - t_start)
                painted = stats(list(cv.plot.meter.paint_ms))
                lay._timer.timeout.disconnect(conn)
                fps = (len(stamps) - 1) / (stamps[-1] - stamps[0]) if len(stamps) > 2 else 0.0
                label = f"{mode} " + ", ".join(f"{k}={v}" for k, v in settings.items())
                self.record("anim", f"{label} | {name}", {"fps drawn": fps, "plot frames per s": shown,
                                                          "plot paint ms": painted, "render ms": stats(lay.frame_ms),
                                                          "window frame gap": stats(gaps)})
                cv.set_view_mode("static")
                if name.endswith("dense"):
                    sp["density"].setValue(5)
                for key in settings:
                    if key in sp:
                        default = {"particles": 1500, "trail": 4, "pulse_length": 4, "pulse_spacing": 4}[key]
                        sp[key].setValue(default)

    def limits(self):
        """The heaviest things a user can do, a few seconds each: 16 elements, densest streamlines, every layer,
        the most particles / the longest and densest pulses, the biggest exports."""
        secs = 2.0 if self.quick else 3.0
        w, cv = self.win, self.win.canvas
        sp = w.settings_panel.sliders
        layers = ("equipotential", "speed", "bodies", "surface")
        dense = sp["density"].maximum()
        row = {}

        # computing: the whole scene at the densest streamlines, then every layer at once
        self.show(STRESS)
        sp["density"].setValue(dense)
        self.settle()
        row["streamlines, density max"] = timed(lambda: cv.streamlines.recompute(), 2, warm=0)
        for k in layers:
            w.settings_panel.layer_boxes[k].setChecked(True)
        row["everything at once (every layer)"] = timed(lambda: (cv.compute_now(), self.settle()), 2, warm=0)
        self.settle()
        self.record("limits", "compute (ms)", row)

        # moving the view and an element with everything on
        jobs = []
        cv.computed.connect(lambda n, ms: jobs.append(ms))

        def pan(k, ph):
            (x0, x1), (y0, y1) = cv.vb.viewRange()
            d = 0.006 * (x1 - x0)
            cv.set_view((x0 + d, x1 + d), (y0 + d / 3, y1 + d / 3))

        def zoom(k, ph):
            (x0, x1), (y0, y1) = cv.vb.viewRange()
            s_ = 1.0 + 0.012 * np.sin(k / 8.0)
            cx, cy, hw, hh = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2 * s_, (y1 - y0) / 2 * s_
            cv.set_view((cx - hw, cx + hw), (cy - hh, cy + hh))

        moves = {}
        for what, fn in (("pan", pan), ("zoom", zoom)):
            cv.set_view((-5.0, 5.0), (-3.0, 3.0))
            self.settle()
            jobs.clear()
            moves[what] = {"frame gap": stats(self._ticks(secs, fn)), "computations": len(jobs)}
        from PySide6.QtCore import QPointF
        cv.set_view((-5.0, 5.0), (-3.0, 3.0))
        self.settle()
        cv.set_mode("move")
        el = cv.elements[11]                                  # the doublet in the middle
        start = cv.vb.mapViewToScene(QPointF(el.x0, el.y0))
        ok = cv.interaction.begin_drag(start)

        def drag(k, ph):
            cv.interaction.drag_to(QPointF(start.x() + 60.0 * np.sin(k / 10.0), start.y() + 60.0 * (1 - np.cos(k / 10.0))))
        jobs.clear()
        gaps = self._ticks(secs, drag) if ok else []
        cv.interaction.end_drag()
        cv.set_mode("select")
        moves["drag an element (live update)"] = {"frame gap": stats(gaps), "computations": len(jobs)}
        self.settle()
        self.record("limits", STRESS + ", density max, every layer", moves)

        # animations at their maximum (the most particles the slider allows; graphics card: as fast as the screen)
        cap = None
        if self.tag and self.win.canvas.gpu:
            cap = w.gpu_panel.cap.currentData()
            w.set_fps_cap("screen")
        anims = {}
        for mode, settings in (("particles", {"particles": sp["particles"].maximum(), "trail": 10}),
                               ("pulses", {"pulse_length": 10, "pulse_spacing": 1})):
            for key, val in settings.items():
                sp[key].setValue(val)
            cv.set_view_mode(mode)
            self.pump(1.0)
            lay = cv.animation
            lay.frame_ms.clear()
            cv.plot.meter.clear()
            t0 = time.perf_counter()
            gaps = self._ticks(secs + 1.0, lambda k, ph: None)
            shown = sum(1 for t in cv.plot.meter.stamps if t >= t0) / (time.perf_counter() - t0)
            label = mode + " " + ", ".join(f"{k}={v}" for k, v in settings.items())
            anims[label] = {"fps drawn": shown, "plot frames per s": shown, "plot paint ms": stats(list(cv.plot.meter.paint_ms)),
                            "render ms": stats(lay.frame_ms), "window frame gap": stats(gaps)}
            cv.set_view_mode("static")
        for key, val in (("particles", 1500), ("trail", 4), ("pulse_length", 4), ("pulse_spacing", 4)):
            sp[key].setValue(val)
        if cap is not None:
            w.set_fps_cap(cap)
        self.record("limits", "animation (" + STRESS + ", every layer)", anims)

        # the biggest exports of that scene
        if not self.tag:
            from app.export.animation import missing_package, render_animation
            from app.export.figure import render_figure
            out = tempfile.mkdtemp(prefix="pfl-bench-")
            ex = {"PNG 4×, every layer": timed(lambda: render_figure(cv, os.path.join(out, "big.png"), "png", scale=4),
                                              1, warm=0)}
            if not missing_package("mp4"):
                cv.set_view_mode("particles")
                self.pump(0.5)
                ex["MP4 2 s, 30 fps, 2×"] = timed(lambda: render_animation(cv, os.path.join(out, "big.mp4"), "mp4",
                                                                          seconds=2, fps=30, scale=2), 1, warm=0)
                cv.set_view_mode("static")
            self.record("limits", "export (ms)", ex)
        for k in layers:
            w.settings_panel.layer_boxes[k].setChecked(False)
        sp["density"].setValue(5)
        self.settle()

    def export(self):
        from app.export.animation import missing_package, render_animation
        from app.export.data import DATASETS, export_data
        from app.export.figure import render_figure
        out = tempfile.mkdtemp(prefix="pfl-bench-")
        w, cv = self.win, self.win.canvas
        reps = 2 if self.quick else 3
        self.show("lifting cylinder")
        row = {}
        for fmt, scale in (("png", 1), ("png", 2), ("png", 4), ("svg", 1), ("pdf", 1)):
            path = os.path.join(out, f"fig_{scale}.{fmt}")
            row[f"{fmt.upper()} {scale}×" if fmt == "png" else fmt.upper()] = timed(
                lambda: render_figure(cv, path, fmt, scale=scale), reps, warm=1)
        path = os.path.join(out, "data.csv")
        row["CSV (all tables)"] = timed(lambda: export_data(path, [k for k, _ in DATASETS], w.elements, cv.view(),
                                                            cv.stagnation_points, cv.last_result.lines),
                                       reps, warm=1)
        for fmt, fps, scale in (("gif", 20, 1), ("mp4", 30, 1), ("mp4", 30, 2)):
            if missing_package(fmt):
                row[f"{fmt.upper()} 2 s"] = {"skipped": missing_package(fmt)}
                continue
            cv.set_view_mode("particles")
            self.pump(0.5)
            path = os.path.join(out, f"anim_{scale}.{fmt}")
            row[f"{fmt.upper()} 2 s, {fps} fps, {scale}×"] = timed(
                lambda: render_animation(cv, path, fmt, seconds=2, fps=fps, scale=scale), 1, warm=0)
            cv.set_view_mode("static")
        self.record("export", "lifting cylinder", row)

    def verify(self):
        from app.cli import report
        out = tempfile.mkdtemp(prefix="pfl-verify-")
        row = {"102 checks, no figures": timed(lambda: report.collect(None, log=lambda *a: None), 1, warm=0),
               "102 checks + 9 figures": timed(lambda: report.collect(os.path.join(out, "figures"),
                                                                      log=lambda *a: None), 1, warm=0)}
        self.record("verify", "Help → Run verification", row)

    # ------------------------------------------------------------------ report
    def machine(self) -> dict:
        import numba
        import PySide6
        info = {"platform": platform.platform(), "machine": platform.machine(), "cpus": os.cpu_count(),
                "python": platform.python_version(), "pyside6": PySide6.__version__, "numba": numba.__version__,
                "numpy": np.__version__, "qt_platform": self.app.platformName() if self.app else "",
                "window": list(WINDOW), "screen_dpr": self.win.devicePixelRatioF() if self.win else None,
                "date": time.strftime("%Y-%m-%d %H:%M"), "quick": self.quick}
        try:
            from app import hardware
            prof = getattr(self.win, "hardware", None) if self.win is not None else None
            info["computer"] = hardware.summary_lines(prof) if prof else []
        except Exception:                              # noqa: BLE001
            info["computer"] = []
        if self.win is not None:                       # QWidget = drawn by the CPU; PlotGLViewport = graphics card
            info["opengl_viewport"] = type(self.win.canvas.plot.viewport()).__name__
            info["gpu"] = self.gpu_info
            info["fps_cap"] = self.fps_cap if self.use_gpu else None
            info["screen_hz"] = self.win.screen_hz()
        return info


def verdict(ms, kind):
    if ms is None or not np.isfinite(ms):
        return ""
    if kind == "frame":
        return "smooth" if ms <= FRAME_MS * 1.15 else ("ok (30+ fps)" if ms <= 34 else "STUTTER")
    return "instant" if ms <= 100 else ("ok" if ms <= 300 else ("slow" if ms <= 1000 else "SLOW"))


def _ms(v):
    return f"{v:9.1f}" if isinstance(v, (int, float)) else f"{'—':>9}"


def _print_frames(name, row):
    if "frame gap" in row:
        row = {"": row}
    for k, r in row.items():
        g = r["frame gap"]
        print(f"  {(name + ' ' + k).strip():<52}{_ms(g.get('median'))}{_ms(g.get('p95'))}{_ms(g.get('max'))}"
              f"  jobs {r.get('computations', 0):>4}   {verdict(g.get('p95'), 'frame')}")


def _print_anim(rows):
    print(f"  {'':<70}  fps   paint ms  render ms (med/p95)   window gap p95")
    for k, r in rows.items():
        shown = r.get("plot frames per s", r["fps drawn"])
        print(f"  {k:<70}{shown:5.1f}{_ms(r.get('plot paint ms', {}).get('median'))}"
              f"  {_ms(r['render ms'].get('median'))}{_ms(r['render ms'].get('p95'))}"
              f"   {_ms(r['window frame gap'].get('p95'))}  {verdict(r['window frame gap'].get('p95'), 'frame')}")


def print_report(res: dict):
    print("\n" + "=" * 110)
    m = res["machine"]
    print(f"Flowy benchmark  {m['date']}  |  {m['platform']}  |  {m['cpus']} CPUs  |  Qt: "
          f"{m['qt_platform']}  |  viewport: {m.get('opengl_viewport', '?')}")
    for line in m.get("computer", []):
        print("  " + line)
    if m.get("gpu"):
        print(f"graphics card: {m['gpu'].get('renderer')}  |  {m['gpu'].get('samples')}× smoothing  |  "
              f"animation limit {m.get('fps_cap')}  |  screen {m.get('screen_hz', 0):.0f} Hz")
    if "startup" in res:
        print("\nSTARTUP (fresh process; since 29 Oct the kernels are prepared before the window opens)\n"
              "                                              to window   first lines   all kernels ready")
        for k, r in res["startup"].items():
            if "error" in r:
                print(f"  {k:<44} ERROR {r['error'][:60]}")
                continue
            print(f"  {k:<44}{_ms(r['import_ms'] + r['window_ms'])}   {_ms(r['to_first_lines_ms'])}"
                  f"   {_ms(r['all_kernels_ready_ms'])}   ms")
    if "compute" in res:
        keys = list(next(iter(res["compute"].values())).keys())
        print("\nCOMPUTE (median ms)" + "".join(f"{k[:13]:>14}" for k in keys))
        for name, row in res["compute"].items():
            print(f"  {name:<22}" + "".join(f"{row[k].get('median', float('nan')):14.1f}" for k in keys))
    for tag in ("", " [GPU]"):
        if "paint" + tag in res:
            print(f"\nPAINT{tag} (median ms, one full redraw)")
            for name, row in res["paint" + tag].items():
                for k, s in row.items():
                    print(f"  {name:<22}{k:<38}{_ms(s.get('median'))}  p95{_ms(s.get('p95'))}  "
                          f"{verdict(s.get('median'), 'frame')}")
        if "interact" + tag in res:
            print(f"\nINTERACT{tag} (60 fps timer: frame gap median / p95 / max ms; computations)")
            for name, row in res["interact" + tag].items():
                if name != "reaction time (ms)":
                    _print_frames(name, row)
            rt = res["interact" + tag].get("reaction time (ms)", {})
            if rt:
                print(f"\nREACTION TIME{tag} (until the plot shows the change; median / max ms)")
                for k, s in rt.items():
                    print(f"  {k:<52}{_ms(s.get('median'))}{_ms(s.get('max'))}   {verdict(s.get('median'), 'latency')}")
        if "anim" + tag in res:
            print(f"\nANIMATION{tag}  (fps = frames the plot really showed; paint = one frame's drawing, median)")
            _print_anim(res["anim" + tag])
        if "limits" + tag in res:
            print(f"\nLIMITS{tag}  (the heaviest: {STRESS}, densest streamlines, every layer, the most particles)")
            for name, row in res["limits" + tag].items():
                if name.startswith("compute") or name.startswith("export"):
                    for k, s in row.items():
                        print(f"  {name.split(' (')[0] + ': ' + k:<52}{_ms(s.get('median'))} ms")
                elif name.startswith("animation"):
                    _print_anim(row)
                else:
                    _print_frames("", row)
    if "export" in res:
        print("\nEXPORT (ms)")
        for name, row in res["export"].items():
            for k, s in row.items():
                print(f"  {k:<30}{_ms(s.get('median')) if 'median' in s else '  ' + str(s.get('skipped'))}")
    if "verify" in res:
        print("\nVERIFY (ms)")
        for name, row in res["verify"].items():
            for k, s in row.items():
                print(f"  {k:<30}{_ms(s.get('median'))}")
    print("=" * 110)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", help="also write every number to this JSON file")
    p.add_argument("--quick", action="store_true", help="shorter runs, fewer repeats")
    p.add_argument("--only", default=",".join(SECTIONS), help="comma separated sections: " + ",".join(SECTIONS))
    p.add_argument("--gpu", action="store_true", help="draw the plot with the graphics card (OpenGL)")
    p.add_argument("--fps-cap", default="60", choices=["screen", "60", "120", "144"],
                   help="with --gpu: the animations' frame rate limit (default 60)")
    p.add_argument("--full", action="store_true",
                   help="everything, then paint / interact / anim / limits again with the graphics card (one file)")
    p.add_argument("--integrated", action="store_true",
                   help="laptops: leave the graphics card to Windows (default with --gpu / --full: the NVIDIA card)")
    a = p.parse_args()
    if (a.gpu or a.full) and not a.integrated:
        from app.gpu import relaunch_on_strong_card
        code = relaunch_on_strong_card(force=True)          # (the Optimus switch must be there at the start)
        if code is not None:
            sys.exit(code)
    only = [s.strip() for s in a.only.split(",") if s.strip()]
    b = Bench(a.quick, a.gpu and not a.full, a.fps_cap)
    t_all = time.perf_counter()
    if "startup" in only:
        print("startup …", flush=True)
        b.startup()

    def run(sections):
        for s in sections:
            if s in only:
                print(f"{s}{b.tag} …", flush=True)
                t = time.perf_counter()
                getattr(b, s)()
                print(f"   ({time.perf_counter() - t:.0f} s)", flush=True)

    if any(s in only for s in SECTIONS[1:]):
        b.open()
        run(SECTIONS[1:])
        if a.full and any(s in only for s in GPU_SECTIONS):
            print("graphics card on …", flush=True)
            if b.gpu_on(must=False):
                b.tag = " [GPU]"
                run(GPU_SECTIONS)
    print(f"total: {(time.perf_counter() - t_all) / 60:.1f} min", flush=True)
    res = {"machine": b.machine(), **b.results}
    print_report(res)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1, ensure_ascii=False)
        print(f"written: {a.out}")
    if b.win is not None:
        b.win.model.mark_clean()
        b.win.close()


if __name__ == "__main__":
    main()
