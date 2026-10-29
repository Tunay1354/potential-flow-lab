"""Drawing with the graphics card (ROADMAP 20.3): the rules (app/gpu.py), the Windows card setting with a fake
registry, the crash guard, the window's GPU box / panel and its fallback to the normal drawing.

The OpenGL picture itself cannot be made on the 'offscreen' test platform; there, switching on must FAIL
cleanly (back to the normal drawing, a message) — which is what is tested. The real picture is checked by
scripts/benchmark.py --gpu and, on a server with Xvfb + Mesa, by test_opengl_draws_the_plot (skipped elsewhere)."""
import os
import subprocess
import sys

import pytest

from app import gpu
from app.hardware import runs_on_weak_card, strong_adapter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GL_PROFILE = {"opengl": {"ok": True, "renderer": "NVIDIA GeForce RTX 3050 Ti Laptop GPU/PCIe/SSE2",
                         "vendor": "NVIDIA Corporation", "major": 4, "minor": 6, "software": False},
              "adapters": [{"name": "Intel(R) UHD Graphics", "memory_mb": 128},
                           {"name": "NVIDIA GeForce RTX 3050 Ti Laptop GPU", "memory_mb": 4096}]}


# ------------------------------------------------------------------------------------------- the rules
def test_support():
    assert gpu.support(None)[0] is False
    assert gpu.support({"opengl": {"ok": False, "error": "driver"}}) == (False, "OpenGL is not available here (driver).")
    old = {"opengl": {"ok": True, "renderer": "x", "major": 1, "minor": 4}}
    assert gpu.support(old)[0] is False and "too old" in gpu.support(old)[1]
    soft = {"opengl": {"ok": True, "renderer": "llvmpipe", "major": 4, "minor": 5, "software": True}}
    os.environ.pop("PFL_GPU_ALLOW_SOFTWARE", None)
    assert gpu.support(soft)[0] is False and "without a graphics card" in gpu.support(soft)[1]
    os.environ["PFL_GPU_ALLOW_SOFTWARE"] = "1"
    try:
        assert gpu.support(soft)[0] is True
    finally:
        del os.environ["PFL_GPU_ALLOW_SOFTWARE"]
    assert gpu.support(GL_PROFILE) == (True, GL_PROFILE["opengl"]["renderer"])


def test_frame_interval():
    assert gpu.frame_ms("60", 144) == 16
    assert gpu.frame_ms("120", 144) == 8
    assert gpu.frame_ms("144", 144) == 6
    assert gpu.frame_ms("screen", 144) == 6
    assert gpu.frame_ms("screen", 59.94) == 16
    assert gpu.frame_ms("screen", 0) == 16                  # unknown refresh rate: 60 Hz
    assert gpu.cap_hz("screen", 165) == 165 and gpu.cap_hz("60", 165) == 60
    assert gpu.RASTER_FRAME_MS == 16


def test_merge_preference_keeps_other_entries():
    assert gpu.merge_preference(None) == "GpuPreference=2;"
    assert gpu.merge_preference("") == "GpuPreference=2;"
    assert gpu.merge_preference("SwapEffectUpgradeEnable=1;") == "GpuPreference=2;SwapEffectUpgradeEnable=1;"
    assert gpu.merge_preference("GpuPreference=1;VRROptimizeEnable=0;") == "GpuPreference=2;VRROptimizeEnable=0;"
    assert gpu.merge_preference("gpupreference=0;GpuPreference=1;") == "GpuPreference=2;"


class FakeWinreg:
    """The few winreg functions app/gpu.py uses, on a dict."""
    HKEY_CURRENT_USER, KEY_READ, KEY_WRITE, REG_SZ = "HKCU", 1, 2, 1

    def __init__(self, fail=False):
        self.keys = {}
        self.fail = fail

    class _Key:
        def __init__(self, store):
            self.store = store

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def CreateKeyEx(self, root, path, _reserved, _access):
        if self.fail:
            raise PermissionError("access denied")
        return self._Key(self.keys.setdefault((root, path), {}))

    def OpenKey(self, root, path):
        if (root, path) not in self.keys:
            raise FileNotFoundError(path)
        return self._Key(self.keys[(root, path)])

    def QueryValueEx(self, key, name):
        if name not in key.store:
            raise FileNotFoundError(name)
        return key.store[name], self.REG_SZ

    def SetValueEx(self, key, name, _reserved, _kind, value):
        key.store[name] = value


def test_windows_card_setting_with_a_fake_registry():
    reg = FakeWinreg()
    exe, base = r"C:\proj\.venv\Scripts\python.exe", r"C:\Python313\python.exe"
    store = reg.keys.setdefault(("HKCU", gpu.PREF_KEY), {})
    store[base] = "SwapEffectUpgradeEnable=1;"                      # Windows' own entry is kept
    done, msg = gpu.ask_for_strong_card([exe, base], winreg_module=reg)
    assert done and "next start" in msg
    assert store[exe] == "GpuPreference=2;"
    assert store[base] == "GpuPreference=2;SwapEffectUpgradeEnable=1;"
    assert gpu.read_preference(exe, reg) == "2" and gpu.read_preference(r"C:\other.exe", reg) is None
    done, msg = gpu.ask_for_strong_card([exe], winreg_module=FakeWinreg(fail=True))
    assert not done and "did not accept" in msg
    if sys.platform != "win32":
        assert gpu.ask_for_strong_card([exe])[0] is False        # no registry on this system
        assert gpu.read_preference(exe) is None


def test_program_paths_and_restart_command():
    paths = gpu.program_paths()
    assert paths[0] == os.path.abspath(sys.executable)
    program, args = gpu.restart_command("/x/scene.pflow")
    assert program == sys.executable and args[-1] == "/x/scene.pflow" and args[0].endswith("main.py")
    assert gpu.restart_command(None)[1] == [args[0]]


def test_store_python_and_optimus_switch(qapp, monkeypatch):
    from PySide6.QtCore import QSettings
    assert gpu.store_python([r"C:\Users\x\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation"
                             r".Python.3.13_qbz5n2kfra8p0\python.exe"])
    assert not gpu.store_python([r"C:\Python313\python.exe"])
    monkeypatch.delenv("SHIM_MCCOMPAT", raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    gpu.apply_startup_env()
    assert "SHIM_MCCOMPAT" not in os.environ                   # only after "Use NVIDIA"
    QSettings().setValue(gpu.KEY_OPTIMUS, True)
    gpu.apply_startup_env()
    assert os.environ.pop("SHIM_MCCOMPAT") == "0x800000001"
    QSettings().remove(gpu.KEY_OPTIMUS)


def test_strong_and_weak_cards():
    intel = {"name": "Intel(R) UHD Graphics", "memory_mb": 128}
    nvidia = {"name": "NVIDIA GeForce RTX 3050 Ti Laptop GPU", "memory_mb": 4096}
    amd_apu = {"name": "AMD Radeon(TM) Graphics", "memory_mb": 512}
    amd_rx = {"name": "AMD Radeon RX 6600M", "memory_mb": 8192}
    assert strong_adapter([intel, nvidia]) is nvidia
    assert strong_adapter([amd_apu, nvidia]) is nvidia                  # the built-in AMD card is not "strong"
    assert strong_adapter([amd_apu]) is None and strong_adapter([intel]) is None
    assert strong_adapter([intel, amd_rx]) is amd_rx
    assert runs_on_weak_card("Intel(R) UHD Graphics", "Intel", [intel, nvidia]) is nvidia
    assert runs_on_weak_card("NVIDIA GeForce RTX 3050 Ti/PCIe/SSE2", "NVIDIA Corporation", [intel, nvidia]) is None
    assert runs_on_weak_card("AMD Radeon(TM) Graphics", "ATI Technologies Inc.", [amd_apu, nvidia]) is nvidia
    assert runs_on_weak_card("NVIDIA GeForce RTX 3050 Ti", "NVIDIA", [amd_apu, nvidia]) is None
    assert runs_on_weak_card("AMD Radeon RX 6600M", "ATI", [intel, amd_rx]) is None
    assert runs_on_weak_card("Intel(R) Iris(R) Xe Graphics", "Intel", [intel]) is None    # only one card


def test_session_guard_finds_a_crashed_program(qapp, tmp_path):
    from PySide6.QtCore import QSysInfo
    folder = str(tmp_path / "gpu")
    g = gpu.SessionGuard(folder)
    g.hold()
    assert os.path.exists(g.path)
    other = gpu.SessionGuard(folder)
    assert not other.crashed_before()                                 # g's program (this one) still runs
    g.release()
    assert not os.path.exists(g.path)
    # a lock file left by a program that is gone (pid that does not exist) = it crashed while drawing
    dead = os.path.join(folder, "session-999999-dead.lock")
    with open(dead, "w") as f:
        f.write(f"999999\n{qapp.applicationName()}\n{QSysInfo.machineHostName()}\n")
    assert other.crashed_before()
    assert not os.path.exists(dead) and not other.crashed_before()      # reported once


# ------------------------------------------------------------------------------------------- the window
@pytest.fixture
def window(qapp):
    from PySide6.QtCore import QSettings
    QSettings().remove("gpu")
    from app.main_window import MainWindow
    w = MainWindow()
    w._ask_save_changes = lambda: "discard"
    w.messages = []
    w._notify_user = lambda kind, title, text: w.messages.append((kind, title, text))
    yield w
    w.close()
    w.deleteLater()
    QSettings().remove("gpu")


def test_gpu_box_off_where_it_cannot_work(window):
    w = window
    w.hardware = {"opengl": {"ok": True, "renderer": "llvmpipe", "major": 4, "minor": 5, "software": True}}
    w._update_gpu_controls()
    box = w.header.plank.gpu
    assert not box.isChecked() and not box.isEnabled() and not w.act_gpu.isEnabled()
    assert "without a graphics card" in box.toolTip()
    assert not w.set_gpu(True) and not w.canvas.gpu
    assert w.messages and "without a graphics card" in w.messages[-1][2]
    assert not w.dock_gpu.isVisible() and not w.dock_gpu.toggleViewAction().isEnabled()
    w.hardware = GL_PROFILE
    w._update_gpu_controls()
    assert box.isEnabled() and "NVIDIA" in box.toolTip()


def test_switching_on_fails_cleanly_without_opengl(window, qapp):
    """The test platform has no OpenGL: switching on must fall back to the normal drawing (no crash)."""
    w = window
    w.hardware = GL_PROFILE
    w.show()
    qapp.processEvents()
    assert w.set_gpu(True)                                   # the viewport is made …
    assert w.canvas.gpu and gpu.enabled() and w.dock_gpu.isVisible()
    assert os.path.exists(w._gpu_guard.path)                 # … and the crash guard is held
    w._gpu_check_started()                                   # (the timer's look after CHECK_MS)
    assert not w.canvas.gpu and not gpu.enabled()
    assert not w.dock_gpu.isVisible() and not w.header.plank.gpu.isChecked()
    assert not os.path.exists(w._gpu_guard.path)
    qapp.processEvents()
    assert w.messages and w.messages[-1][1] == "Graphics card drawing did not start"
    assert w.canvas.particles.frame_interval == gpu.RASTER_FRAME_MS


def test_viewport_switch_keeps_the_mouse_handling(window, qapp):
    """After a switch (on and back off) the plot's new viewport takes drops and the mouse as before."""
    from PySide6.QtWidgets import QGraphicsView
    from PySide6.QtOpenGLWidgets import QOpenGLWidget
    cv = window.canvas
    cv.set_mode("pan")
    vp = cv.set_gpu(True)
    assert isinstance(vp, QOpenGLWidget) and cv.gpu and cv.interaction._viewport is vp
    assert cv.plot.viewportUpdateMode() == QGraphicsView.FullViewportUpdate
    cv.set_gpu(False)
    vp = cv.plot.viewport()
    assert not cv.gpu and cv.interaction._viewport is vp and vp.acceptDrops()
    assert cv.plot.viewportUpdateMode() == QGraphicsView.MinimalViewportUpdate
    assert vp.autoFillBackground() and vp.cursor().shape() == cv.interaction._viewport.cursor().shape()
    cv.set_mode("select")


def test_fps_cap_setting(window):
    w = window
    w.set_fps_cap("120")
    assert gpu.fps_cap() == "120" and w.gpu_panel.cap.currentData() == "120"
    assert w.canvas.particles.frame_interval == gpu.RASTER_FRAME_MS        # GPU off: as before
    w.set_fps_cap("nonsense")
    assert gpu.fps_cap() == gpu.DEFAULT_CAP
    w.gpu_panel.set_screen_hz(60)
    w.gpu_panel.set_cap("144")
    assert w.gpu_panel.cap_note.text().startswith("Your screen shows at most 60")
    assert "60 Hz" in w.gpu_panel.cap.itemText(w.gpu_panel.cap.findData("screen"))


def test_crash_guard_starts_without_gpu(qapp):
    from PySide6.QtCore import QSettings, QSysInfo
    from app.main_window import MainWindow
    folder = gpu.guard_folder()
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "session-999998-dead.lock"), "w") as f:
        f.write(f"999998\n{qapp.applicationName()}\n{QSysInfo.machineHostName()}\n")
    gpu.set_enabled(True)
    w = MainWindow()
    try:
        assert not gpu.enabled() and not w.canvas.gpu and not w.header.plank.gpu.isChecked()
    finally:
        w._ask_save_changes = lambda: "discard"
        w.close()
        w.deleteLater()
        QSettings().remove("gpu")


def test_faster_card_offer_and_check_after_restart(window, monkeypatch):
    from PySide6.QtCore import QSettings
    w = window
    w.hardware = GL_PROFILE
    w._gpu_weak = GL_PROFILE["adapters"][1]
    w.canvas.gpu_info = {"renderer": "Intel(R) UHD Graphics", "vendor": "Intel"}
    asked, restarted = [], []
    monkeypatch.setattr(gpu, "ask_for_strong_card", lambda: (True, "ok"))
    monkeypatch.delenv("SHIM_MCCOMPAT", raising=False)
    w._ask_strong_card = lambda strong: asked.append(strong) or "yes"
    w.restart_program = lambda: restarted.append(True) or True
    w.offer_strong_card()
    assert asked and restarted
    s = QSettings()
    assert s.value(gpu.KEY_SWITCHING) == GL_PROFILE["adapters"][1]["name"]
    assert s.value(gpu.KEY_REPROBE, False, bool) and s.value(gpu.KEY_OPTIMUS, False, bool)     # NVIDIA: also Optimus
    # after the restart: the new profile says NVIDIA -> a note, the flag is gone
    flashed = []
    w.flash = flashed.append
    w._gpu_check_switch()
    assert flashed and "NVIDIA" in flashed[-1] and not s.value(gpu.KEY_SWITCHING, "")
    # Windows did not do it: how to do it by hand
    s.setValue(gpu.KEY_SWITCHING, "NVIDIA GeForce RTX 3050 Ti Laptop GPU")
    w.hardware = {**GL_PROFILE, "opengl": {**GL_PROFILE["opengl"], "renderer": "Intel(R) UHD Graphics"}}
    helped = []
    w._show_switch_help = lambda reason: helped.append(reason) or False
    w._gpu_check_switch()
    assert helped and "Intel" in helped[-1]
    s.remove(gpu.KEY_REPROBE)
    # Windows refused the setting: the manual way at once, no restart
    restarted.clear()
    monkeypatch.setattr(gpu, "ask_for_strong_card", lambda: (False, "Windows did not accept the setting (x)."))
    w.offer_strong_card()
    assert not restarted and "did not accept" in helped[-1]


def test_weak_card_seen_from_the_viewport(window):
    w = window
    w.hardware = GL_PROFILE
    w._gpu_ready({"renderer": "Intel(R) UHD Graphics", "vendor": "Intel", "version": "4.6.0 - Build 31", "samples": 4})
    assert w._gpu_weak["name"].startswith("NVIDIA")
    assert w.gpu_panel.btn_switch.text() == "Use NVIDIA…" and not w.gpu_panel.btn_switch.isHidden()
    w._gpu_ready({"renderer": "NVIDIA GeForce RTX 3050 Ti/PCIe/SSE2", "vendor": "NVIDIA", "version": "4.6.0",
                  "samples": 4})
    assert w._gpu_weak is None and w.gpu_panel.btn_switch.isHidden()
    assert w.gpu_panel.detail.text() == "OpenGL 4.6.0 · 4× smoothing"


def test_frame_meter():
    from app.canvas.gl_viewport import FrameMeter
    m = FrameMeter()
    for k in range(30):
        m.add(10.0 + k / 60.0 - 0.004, 10.0 + k / 60.0)
    assert m.fps(10.0 + 29 / 60.0) == pytest.approx(30, abs=1)
    assert m.fps(20.0) == 0
    assert m.paint_median() == pytest.approx(4.0, abs=0.01)
    m.clear()
    assert m.paint_median() is None


# ------------------------------------------------------------------- a real OpenGL picture (Xvfb + Mesa)
def _xvfb_display():
    disp = os.environ.get("PFL_GL_DISPLAY", ":99")
    sock = f"/tmp/.X11-unix/X{disp.lstrip(':').split('.')[0]}"
    if not sys.platform.startswith("linux") or not os.path.exists(sock):
        return None
    import socket
    try:                                                      # the server must be running, not only its file
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            s.connect(sock)
    except OSError:
        return None
    return disp


@pytest.mark.skipif(_xvfb_display() is None, reason="needs an X server with OpenGL (Xvfb + Mesa)")
def test_opengl_draws_the_plot(tmp_path):
    """In a separate process on the X server: the plot with the OpenGL viewport looks like the normal one
    (screen pixels), an element selected afterwards (a small change) leaves the rest of the plot intact."""
    script = tmp_path / "gl.py"
    script.write_text(GL_SCRIPT % {"root": ROOT, "out": str(tmp_path)})
    env = dict(os.environ, DISPLAY=_xvfb_display(), QT_QPA_PLATFORM="xcb", PFL_GPU_ALLOW_SOFTWARE="1")
    out = subprocess.run([sys.executable, str(script)], env=env, capture_output=True, text=True, timeout=240)
    assert "RESULT" in out.stdout, out.stdout[-2000:] + out.stderr[-2000:]
    line = next(ln for ln in out.stdout.splitlines() if ln.startswith("RESULT"))
    _, frames, differ_on, differ_sel, back = line.split()
    assert int(frames) >= 2
    assert float(differ_on) < 3.0            # % of plot pixels clearly different (smoothing differs a little)
    assert float(differ_sel) < 3.0
    assert back == "raster"


GL_SCRIPT = r'''
import os, sys, time
sys.path.insert(0, %(root)r); os.chdir(%(root)r)
from PySide6.QtCore import QSettings, QStandardPaths
QStandardPaths.setTestModeEnabled(True)
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, %(out)r)
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
import numpy as np
app = QApplication([])
from app.startup import setup_application
setup_application(app); QSettings().setValue("beaver/tour_offered", True); QSettings().setValue("beaver/enabled", False)
from app import gpu
gpu.support = lambda p: (True, "test")
from app.main_window import MainWindow
w = MainWindow(); w._ask_save_changes = lambda: "discard"; w._notify_user = lambda *a: print("NOTE", a)
w.resize(1400, 800); w.move(0, 0); w.show()
def pump(s):
    t = time.perf_counter()
    while time.perf_counter() - t < s:
        app.processEvents(); time.sleep(0.005)
def plot_pixels():
    pump(0.6)
    vp = w.canvas.plot.viewport()
    r = vp.rect(); p = vp.mapToGlobal(r.topLeft())
    img = app.primaryScreen().grabWindow(0, p.x(), p.y(), r.width(), r.height()).toImage()
    img = img.convertToFormat(QImage.Format_RGB888)
    a = np.frombuffer(img.constBits(), np.uint8).reshape(img.height(), img.bytesPerLine())[:, :img.width() * 3]
    return a.reshape(img.height(), img.width(), 3).astype(int)
def differ(a, b):
    return 100.0 * float((np.abs(a - b).max(axis=2) > 60).mean()) if a.shape == b.shape else 100.0
pump(2.0)
w.canvas.wait_idle(20000); pump(0.5)
raster = plot_pixels()
w.set_gpu(True, user=False); pump(1.5)
on = plot_pixels()
w.select_element(1); pump(0.5)
sel_gl = plot_pixels()
w.set_gpu(False, user=True); pump(0.8)
sel_raster = plot_pixels()
print("RESULT", w._gpu_frames, round(differ(raster, on), 3), round(differ(sel_raster, sel_gl), 3),
      "raster" if not w.canvas.gpu else "gl")
w.model.mark_clean(); w.close()
'''
