"""This computer (app/hardware.py), the loading screen (app/splash.py) and the start (main.open_window):
found once, remembered, found again when the computer changes; the OpenGL check never crashes the program."""
import pytest


# ---------------------------------------------------------------------------------------------- the parts
def test_graphics_vendors_and_software_renderers():
    from app.hardware import vendor_of
    assert vendor_of("NVIDIA GeForce RTX 3050 Ti Laptop GPU") == "nvidia"
    assert vendor_of("AMD Radeon(TM) Graphics") == "amd"
    assert vendor_of("Intel(R) Iris(R) Xe Graphics") == "intel"
    assert vendor_of("Intel(R) UHD Graphics 630") == "intel"
    assert vendor_of("llvmpipe (LLVM 20.1.2, 256 bits)") == "software"
    assert vendor_of("GDI Generic") == "software" and vendor_of("Microsoft Basic Render Driver") == "software"
    assert vendor_of("") == "other"


class _FakeWinreg:
    """The registry part display_adapters reads (a laptop: Intel + NVIDIA, a basic display adapter, a
    Properties key that cannot be opened)."""
    HKEY_LOCAL_MACHINE = "HKLM"
    KEYS = {"0000": {"DriverDesc": "Intel(R) Iris(R) Xe Graphics", "HardwareInformation.MemorySize": 1 << 30},
            "0001": {"DriverDesc": "NVIDIA GeForce RTX 3050 Ti Laptop GPU",
                     "HardwareInformation.qwMemorySize": (4 << 30).to_bytes(8, "little")},
            "0002": {"DriverDesc": "Microsoft Basic Display Adapter"},
            "Properties": None}

    class _Key:
        def __init__(self, name):
            self.name = name

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def OpenKey(self, root, sub):
        if root == self.HKEY_LOCAL_MACHINE:
            return self._Key("root")
        if self.KEYS.get(sub) is None:
            raise PermissionError("access denied")
        return self._Key(sub)

    def EnumKey(self, key, i):
        names = list(self.KEYS)
        if i >= len(names):
            raise OSError("no more")
        return names[i]

    def QueryValueEx(self, key, name):
        values = self.KEYS[key.name]
        if name not in values:
            raise FileNotFoundError(name)
        return values[name], 0


def test_display_adapters_from_the_registry():
    from app.hardware import display_adapters, strong_adapter
    ads = display_adapters(_FakeWinreg())
    assert [a["name"] for a in ads] == ["Intel(R) Iris(R) Xe Graphics", "NVIDIA GeForce RTX 3050 Ti Laptop GPU"]
    assert ads[0]["memory_mb"] == 1024 and ads[1]["memory_mb"] == 4096
    assert strong_adapter(ads)["name"].startswith("NVIDIA")


def test_the_laptop_case_opengl_on_the_intel_card_is_noticed():
    from app.hardware import opengl_uses_weak_card
    ads = [{"name": "Intel(R) Iris(R) Xe Graphics", "memory_mb": None},
           {"name": "NVIDIA GeForce RTX 3050 Ti Laptop GPU", "memory_mb": 4096}]
    on_intel = {"adapters": ads, "opengl": {"ok": True, "renderer": "Intel(R) Iris(R) Xe Graphics"}}
    on_nvidia = {"adapters": ads, "opengl": {"ok": True, "renderer": "NVIDIA GeForce RTX 3050 Ti Laptop GPU/PCIe/SSE2"}}
    assert opengl_uses_weak_card(on_intel)["name"].startswith("NVIDIA")
    assert opengl_uses_weak_card(on_nvidia) is None
    assert opengl_uses_weak_card({"adapters": ads[:1], "opengl": on_intel["opengl"]}) is None    # no strong card


def test_fingerprint_changes_with_the_computer_only():
    from app.hardware import fingerprint
    b = {"cpu": "X", "cores": 16, "adapters": [{"name": "A"}], "screens": [{"name": "S", "refresh_hz": 60.0}],
         "versions": {"program": "1"}}
    same = dict(b, screens=[{"name": "S", "refresh_hz": 60.0, "size": [1, 2]}])
    assert fingerprint(b) == fingerprint(same)
    assert fingerprint(b) != fingerprint(dict(b, screens=[{"name": "S", "refresh_hz": 144.0}]))
    assert fingerprint(b) != fingerprint(dict(b, adapters=[{"name": "A"}, {"name": "B"}]))
    assert fingerprint(b) != fingerprint(dict(b, versions={"program": "2"}))


def test_the_opengl_check_runs_in_its_own_process_and_never_crashes_the_program(qapp):
    """Here there is no OpenGL (offscreen; a context that cannot be made current would crash a process):
    the check says so, the program goes on."""
    from app.hardware import probe_opengl
    calls = []
    r = probe_opengl(timeout=60, wait=lambda: calls.append(1))
    assert set(r) >= {"ok", "probe_ms"}
    if not r["ok"]:
        assert r["error"]
    else:                                                     # (a machine with OpenGL: it says who draws)
        assert r["renderer"]


def test_a_hanging_check_is_stopped(monkeypatch):
    import sys

    from app import hardware
    monkeypatch.setattr(hardware, "probe_command", lambda path: [sys.executable, "-c", "import time; time.sleep(30)"])
    r = hardware.probe_opengl(timeout=1.0)
    assert not r["ok"] and "did not finish" in r["error"]
    monkeypatch.setattr(hardware, "probe_command", lambda path: [sys.executable, "-c", "raise SystemExit(3)"])
    r = hardware.probe_opengl(timeout=10.0)
    assert not r["ok"] and "exit code 3" in r["error"]


def test_detect_remembers_and_finds_again_when_the_computer_changes(qapp, monkeypatch):
    from PySide6.QtCore import QSettings

    from app import hardware
    QSettings().remove(hardware.PROFILE_KEY)
    probes = []

    def fake_probe(wait=None):
        probes.append(1)
        return {"ok": True, "renderer": "NVIDIA GeForce RTX 3050 Ti", "major": 4, "minor": 6, "software": False}
    p, fresh = hardware.detect(probe=fake_probe)
    assert fresh and len(probes) == 1 and p["cores"] >= 1 and p["opengl"]["ok"]
    p2, fresh2 = hardware.detect(probe=fake_probe)                    # the next start: remembered
    assert not fresh2 and len(probes) == 1 and p2["fingerprint"] == p["fingerprint"]
    real = hardware.basics
    monkeypatch.setattr(hardware, "basics", lambda: dict(real(), cores=999))      # another computer
    p3, fresh3 = hardware.detect(probe=fake_probe)
    assert fresh3 and len(probes) == 2
    p4, fresh4 = hardware.detect(force=True, probe=fake_probe)        # Help → Your computer → Check again
    assert fresh4 and len(probes) == 3
    assert any("999 threads" in line for line in hardware.summary_lines(p4))
    QSettings().remove(hardware.PROFILE_KEY)


def test_a_broken_profile_is_ignored(qapp):
    from PySide6.QtCore import QSettings

    from app import hardware
    QSettings().setValue(hardware.PROFILE_KEY, "{not json")
    assert hardware.load_profile() is None
    QSettings().setValue(hardware.PROFILE_KEY, '{"profile_version": -1}')
    assert hardware.load_profile() is None
    QSettings().remove(hardware.PROFILE_KEY)


# ------------------------------------------------------------------------------------- the loading screen
def test_the_loading_screen_paints_runs_work_and_reports_errors(qapp):
    from app.splash import LoadingScreen
    s = LoadingScreen()
    s.show()
    s.set_step("Looking at this computer…", 0.1)
    s.add_line("Processor: test — 16 threads")
    assert s.run(lambda: 42, "Preparing…", 0.2, 0.5) == 42
    assert s.fraction >= 0.5
    with pytest.raises(ValueError):
        s.run(lambda: (_ for _ in ()).throw(ValueError("x")), "Preparing…", 0.5, 0.6)
    img = s.grab().toImage()
    assert img.width() > 100 and not img.isNull()
    s.close()


def test_the_start_finds_the_computer_prepares_the_kernels_and_opens_the_window(qapp, monkeypatch):
    """main.open_window: what main.py does between the loading screen and the window."""
    from PySide6.QtCore import QSettings

    import main
    from app import hardware
    from app.splash import LoadingScreen
    QSettings().remove(hardware.PROFILE_KEY)
    monkeypatch.setattr(hardware, "probe_opengl",
                        lambda timeout=0, wait=None: {"ok": False, "error": "no OpenGL here (test)"})
    s = LoadingScreen()
    s.show()
    win = main.open_window(s)
    try:
        assert win.hardware is not None and win.hardware["cores"] >= 1
        assert any(line.startswith("Processor") for line in s.lines) and s.fraction == 1.0
        assert "cpu_ms" in win.hardware or not __import__("physics.kernel", fromlist=["x"]).HAVE_NUMBA
        assert hardware.load_profile()["fingerprint"] == win.hardware["fingerprint"]
    finally:
        s.close()
        win.model.mark_clean()
        win.close()
        QSettings().remove(hardware.PROFILE_KEY)


def test_help_your_computer_shows_it_and_checks_again(qapp, monkeypatch):
    from app import hardware
    from app.hardware_dialog import HardwareDialog
    from app.main_window import MainWindow
    win = MainWindow()
    try:
        win.hardware = {"cpu": "Test CPU", "cores": 8, "date": "today", "screens": [],
                        "adapters": [{"name": "Intel(R) Iris(R) Xe Graphics", "memory_mb": None},
                                     {"name": "NVIDIA GeForce RTX 3050 Ti Laptop GPU", "memory_mb": 4096}],
                        "opengl": {"ok": True, "renderer": "Intel(R) Iris(R) Xe Graphics", "major": 4, "minor": 6}}
        dlg = HardwareDialog(win)
        assert "Test CPU" in dlg.text.text() and "NVIDIA" in dlg.text.text() and "Note" in dlg.text.text()
        monkeypatch.setattr(hardware, "probe_opengl", lambda timeout=0, wait=None: {"ok": False, "error": "test"})
        dlg.check_again()
        assert win.hardware["cpu"] != "Test CPU" and "not available" in dlg.text.text()
        dlg.close()
    finally:
        win.close()
        from PySide6.QtCore import QSettings
        QSettings().remove(hardware.PROFILE_KEY)


def test_warm_up_steps_compile_everything_the_window_uses():
    from physics import kernel, warmup
    steps = warmup.steps()
    if not kernel.HAVE_NUMBA:
        assert steps == []
        return
    assert len(steps) == 2 and all(callable(fn) for _label, fn in steps)
    assert warmup.streamline_engine() > 0
