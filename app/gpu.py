"""
gpu.py — "draw with the graphics card" (the GPU box in the header): the rules, the remembered settings and
the Windows part (which card a laptop gives this program). No widgets here; the plot's OpenGL viewport is
app/canvas/gl_viewport.py, the panel app/gpu_panel.py, the window's part app/window/graphics.py.

Settings (QSettings)
    gpu/enabled     the box is ticked (off on a first start)
    gpu/fps_cap     "screen" (match the screen's refresh rate), "60", "120", "144"
    gpu/switching   name of the card the user chose (Intel -> NVIDIA); checked after the restart

Crash guard (SessionGuard): while the graphics card draws, the program holds a lock file; a lock left by a
program that is gone means it ended abnormally while drawing with the graphics card (a driver crash) ->
the next start begins with the normal drawing and says so. A start that shows no picture within a few
seconds goes back to the normal drawing too (app/window/graphics.py).

When the box can be ticked (support()): OpenGL 2.0 or newer from a real graphics card. Software OpenGL
(llvmpipe, Microsoft Basic Render) is slower than the normal drawing, so the box stays off there
(PFL_GPU_ALLOW_SOFTWARE=1 allows it, for tests on a server).

Laptops with two cards (Intel + NVIDIA / AMD): Windows decides which card a program gets. The program can
ask Windows for the strong card the way Settings → Display → Graphics does it: a value under
HKEY_CURRENT_USER\\Software\\Microsoft\\DirectX\\UserGpuPreferences, name = the program's path,
data "GpuPreference=2;" (high performance). Only for the current user, no administrator rights; it takes
effect when the program starts again.
"""
from __future__ import annotations

import logging
import os
import sys

log = logging.getLogger("pflab")

KEY_ENABLED = "gpu/enabled"
KEY_CAP = "gpu/fps_cap"
KEY_SWITCHING = "gpu/switching"
KEY_REPROBE = "hardware/reprobe"          # main.py: find the OpenGL renderer again at the next start

FPS_CAPS = (("screen", "Match screen"), ("60", "60 fps"), ("120", "120 fps"), ("144", "144 fps"))
DEFAULT_CAP = "screen"
RASTER_FRAME_MS = 16                      # the animation without the graphics card: ~60 fps (as before)
MSAA_SAMPLES = 4                          # smooth lines on the graphics card (multisampling)
MIN_GL = (2, 0)                           # Qt's OpenGL painter needs OpenGL 2.0

PREF_KEY = r"Software\Microsoft\DirectX\UserGpuPreferences"
PREF_HIGH = "2"                           # GpuPreference: 0 = let Windows decide, 1 = power saving, 2 = high performance
SETTINGS_URL = "ms-settings:display-advancedgraphics"


# --------------------------------------------------------------------------------------------- settings
def _settings():
    from PySide6.QtCore import QSettings
    return QSettings()


def enabled() -> bool:
    return _settings().value(KEY_ENABLED, False, bool)


def set_enabled(on: bool):
    _settings().setValue(KEY_ENABLED, bool(on))


def fps_cap() -> str:
    cap = str(_settings().value(KEY_CAP, DEFAULT_CAP) or DEFAULT_CAP)
    return cap if cap in dict(FPS_CAPS) else DEFAULT_CAP


def set_fps_cap(cap: str):
    _settings().setValue(KEY_CAP, cap if cap in dict(FPS_CAPS) else DEFAULT_CAP)


# ------------------------------------------------------------------------------------------------- rules
def support(profile: dict | None) -> tuple[bool, str]:
    """(can the box be ticked, why not / what draws). From the hardware profile (app/hardware.py)."""
    if profile is None:
        return False, "This computer was not checked yet (Help → Your computer… → Check again)."
    gl = profile.get("opengl") or {}
    if not gl.get("ok"):
        return False, f"OpenGL is not available here ({gl.get('error', 'unknown reason')})."
    version = (int(gl.get("major") or 0), int(gl.get("minor") or 0))
    if version < MIN_GL:
        return False, f"OpenGL {version[0]}.{version[1]} is too old (2.0 or newer is needed)."
    if gl.get("software") and os.environ.get("PFL_GPU_ALLOW_SOFTWARE") != "1":
        return False, (f"OpenGL runs without a graphics card here ({gl.get('renderer', 'software')}): "
                       "that would be slower than the normal drawing.")
    return True, str(gl.get("renderer") or "graphics card")


def cap_hz(cap: str, screen_hz: float) -> float:
    """Frames per second aimed at: the screen's refresh rate, or the chosen number."""
    screen_hz = float(screen_hz) if screen_hz and screen_hz > 1 else 60.0
    return screen_hz if cap == "screen" else float(cap)


def frame_ms(cap: str, screen_hz: float) -> int:
    """The animation timer's interval for a cap: rounded DOWN (at least the chosen rate; the screen's
    vertical sync keeps it from going faster than the screen can show), at least 4 ms."""
    return max(4, int(1000.0 / cap_hz(cap, screen_hz)))


# ------------------------------------------------------------------------------- Windows: which card
def program_paths() -> list[str]:
    """The files Windows sees as "this program": the exe; with Python, python.exe — in a virtual
    environment also the Python it starts (the window belongs to that process)."""
    paths = [sys.executable]
    if not getattr(sys, "frozen", False):
        base = getattr(sys, "_base_executable", None)
        if base and os.path.normcase(os.path.abspath(base)) != os.path.normcase(os.path.abspath(sys.executable)):
            paths.append(base)
    return [os.path.abspath(p) for p in paths if p]


def merge_preference(old: str | None, value: str = PREF_HIGH) -> str:
    """The registry text with GpuPreference=value; other entries (Windows keeps more, e.g.
    SwapEffectUpgradeEnable=1;) are kept as they were."""
    parts = [p for p in (old or "").split(";") if p.strip()]
    out, done = [], False
    for p in parts:
        k = p.split("=", 1)[0].strip()
        if k.lower() == "gpupreference":
            if not done:
                out.append(f"GpuPreference={value}")
                done = True
        else:
            out.append(p.strip())
    if not done:
        out.insert(0, f"GpuPreference={value}")
    return ";".join(out) + ";"


def read_preference(path: str, winreg_module=None) -> str | None:
    """The GpuPreference Windows has for this file ("0", "1", "2"), None if none or not Windows."""
    reg = _winreg(winreg_module)
    if reg is None:
        return None
    try:
        with reg.OpenKey(reg.HKEY_CURRENT_USER, PREF_KEY) as k:
            text = str(reg.QueryValueEx(k, path)[0])
    except OSError:
        return None
    for p in text.split(";"):
        if "=" in p and p.split("=", 1)[0].strip().lower() == "gpupreference":
            return p.split("=", 1)[1].strip()
    return None


def ask_for_strong_card(paths=None, winreg_module=None) -> tuple[bool, str]:
    """Tell Windows to give this program the high-performance card (see the module text).
    Returns (done, message). Nothing raises."""
    reg = _winreg(winreg_module)
    if reg is None:
        return False, "Only Windows lets a program choose its graphics card this way."
    paths = program_paths() if paths is None else paths
    try:
        with reg.CreateKeyEx(reg.HKEY_CURRENT_USER, PREF_KEY, 0, reg.KEY_READ | reg.KEY_WRITE) as k:
            for path in paths:
                try:
                    old = str(reg.QueryValueEx(k, path)[0])
                except OSError:
                    old = ""
                reg.SetValueEx(k, path, 0, reg.REG_SZ, merge_preference(old))
                log.info("GPU preference 'high performance' set for %s", path)
    except OSError as exc:
        log.warning("GPU preference not written: %s", exc)
        return False, f"Windows did not accept the setting ({exc})."
    return True, "Windows will give the program the high-performance graphics card from its next start."


def _winreg(module):
    if module is not None:
        return module
    if sys.platform != "win32":
        return None
    import winreg
    return winreg


# ------------------------------------------------------------------------------------- crash guard
def guard_folder() -> str:
    from PySide6.QtCore import QStandardPaths
    base = QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation) or os.path.expanduser("~")
    return os.path.join(base, "gpu")


class SessionGuard:
    """A lock file held while this program draws with the graphics card (like app/recovery.py's). A lock
    left behind by a program that is not running any more = that program ended abnormally while the
    graphics card drew (a driver crash, a hang that was killed): the next start begins without it."""

    def __init__(self, folder: str | None = None):
        from PySide6.QtCore import QLockFile
        self.folder = folder or guard_folder()
        self.path = os.path.join(self.folder, f"session-{os.getpid()}-{id(self):x}.lock")
        self.lock = QLockFile(self.path)
        self.lock.setStaleLockTime(0)                    # stale only when its program is gone

    def hold(self):
        try:
            os.makedirs(self.folder, exist_ok=True)
            if not self.lock.isLocked():
                self.lock.tryLock(0)
        except OSError as exc:
            log.info("GPU session lock not written: %s", exc)

    def release(self):
        if self.lock.isLocked():
            self.lock.unlock()                           # (removes the file)

    def crashed_before(self) -> bool:
        """A lock of a program that is gone (removed now, so it is reported once)."""
        import glob
        from PySide6.QtCore import QLockFile
        found = False
        for path in glob.glob(os.path.join(self.folder, "session-*.lock")):
            if os.path.abspath(path) == os.path.abspath(self.path):
                continue
            other = QLockFile(path)
            other.setStaleLockTime(0)
            if other.tryLock(0):                         # its program is not running any more
                other.unlock()
                found = True
        return found


# --------------------------------------------------------------------------------------------- restart
def restart_command(scene_path: str | None = None) -> tuple[str, list[str]]:
    """(program, arguments) that start the program again, with the open scene file (if saved)."""
    extra = [scene_path] if scene_path else []
    if getattr(sys, "frozen", False):
        return sys.executable, extra
    main = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
    return sys.executable, [main] + extra
