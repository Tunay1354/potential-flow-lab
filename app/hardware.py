"""
hardware.py — which computer the program runs on: processor (name, cores), display adapters, the OpenGL
renderer the program gets, the screens (refresh rate). Found once and remembered (QSettings
"hardware/profile"); the next starts reuse it, unless the computer changed (a cheap fingerprint: processor,
cores, adapters, screens, program / Numba version).

Safety: asking OpenGL needs a graphics context, and a broken or missing graphics driver can CRASH the
process that does it (seen here: functions of a context that could not be made current → segmentation
fault). So the program never asks itself: probe_opengl() starts a second process (the same program with
--probe-gpu FILE) that writes what it found to FILE. If that process crashes or hangs, the program only
notes "OpenGL not available" and goes on.

Nothing here raises: every part that fails gives "unknown" and is logged.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import subprocess
import sys
import tempfile
import time

log = logging.getLogger("pflab")

PROFILE_KEY = "hardware/profile"
PROFILE_VERSION = 1                    # increase when the profile's contents change: every PC detects again
PROBE_TIMEOUT_S = 25.0
SOFTWARE_RENDERERS = ("llvmpipe", "softpipe", "swrast", "swiftshader", "microsoft basic render",
                      "gdi generic", "mesa offscreen")
GPU_CLASS_KEY = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
IGNORED_ADAPTERS = ("microsoft basic display", "microsoft remote display", "microsoft hyper-v")


# ------------------------------------------------------------------------------------------- processor
def cpu_count() -> int:
    """Logical processors this program may use (Python 3.13: respects an affinity limit)."""
    n = getattr(os, "process_cpu_count", os.cpu_count)()
    return max(1, int(n or 1))


def cpu_name() -> str:
    try:
        if sys.platform == "win32":
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                return " ".join(str(winreg.QueryValueEx(k, "ProcessorNameString")[0]).split())
        if sys.platform.startswith("linux"):
            with open("/proc/cpuinfo", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if line.lower().startswith("model name"):
                        return " ".join(line.split(":", 1)[1].split())
        if sys.platform == "darwin":
            out = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True,
                                 timeout=3)
            if out.stdout.strip():
                return out.stdout.strip()
    except Exception as exc:                          # noqa: BLE001
        log.info("processor name not found: %s", exc)
    return platform.processor() or "unknown processor"


# ------------------------------------------------------------------------------------------ display adapters
def display_adapters(winreg_module=None) -> list[dict]:
    """The graphics cards Windows knows ({"name", "memory_mb"}), e.g. an Intel and an NVIDIA one in a laptop.
    Read from the registry (no admin rights needed, no extra process). Other systems: []."""
    if winreg_module is None:
        if sys.platform != "win32":
            return []
        import winreg as winreg_module
    reg = winreg_module
    out = []
    try:
        root = reg.OpenKey(reg.HKEY_LOCAL_MACHINE, GPU_CLASS_KEY)
    except OSError as exc:
        log.info("display adapters not readable: %s", exc)
        return []
    with root:
        i = 0
        while True:
            try:
                sub = reg.EnumKey(root, i)
            except OSError:
                break
            i += 1
            if not sub.isdigit():                      # "0000", "0001" …; skip "Properties" and the like
                continue
            try:
                with reg.OpenKey(root, sub) as k:
                    name = str(reg.QueryValueEx(k, "DriverDesc")[0]).strip()
                    mem = None
                    for value in ("HardwareInformation.qwMemorySize", "HardwareInformation.MemorySize"):
                        try:
                            raw = reg.QueryValueEx(k, value)[0]
                            mem = int.from_bytes(raw, "little") if isinstance(raw, (bytes, bytearray)) else int(raw)
                            break
                        except (OSError, ValueError, TypeError):
                            continue
            except OSError:
                continue
            if not name or any(s in name.lower() for s in IGNORED_ADAPTERS):
                continue
            if not any(a["name"] == name for a in out):
                out.append({"name": name, "memory_mb": int(mem // 2 ** 20) if mem else None})
    return out


def vendor_of(name: str) -> str:
    """"nvidia", "amd", "intel", "software" or "other" from an adapter / renderer name."""
    n = (name or "").lower()
    if any(s in n for s in SOFTWARE_RENDERERS):
        return "software"
    if "nvidia" in n or "geforce" in n or "quadro" in n or "rtx" in n:
        return "nvidia"
    if "amd" in n or "radeon" in n or "ati " in n:
        return "amd"
    if "intel" in n or "iris" in n or "uhd graphics" in n or "hd graphics" in n or "arc" in n.split():
        return "intel"
    return "other"


def strong_adapter(adapters) -> dict | None:
    """The discrete (fast) card of the computer, if there is one: NVIDIA first, then an AMD card that looks
    discrete (Radeon RX / Pro, or ≥ 2 GB own memory) — an AMD processor's built-in "Radeon Graphics" is not."""
    best = None
    for a in adapters:
        v, n = vendor_of(a["name"]), a["name"].lower()
        if v == "nvidia":
            score = 3
        elif v == "amd" and (" rx" in n or "radeon pro" in n or (a.get("memory_mb") or 0) >= 2048):
            score = 2
        else:
            continue
        if best is None or score > best[0]:
            best = (score, a)
    return best[1] if best else None


def runs_on_weak_card(renderer: str, vendor: str, adapters) -> dict | None:
    """The fast card, when OpenGL (renderer / vendor as the driver says) runs on another one (a laptop's
    Intel or built-in AMD card); None if it runs on the fast card already or there is no fast card."""
    strong = strong_adapter(adapters or [])
    if strong is None:
        return None
    drawn = vendor_of(renderer)
    if drawn == "other":
        drawn = vendor_of(vendor)
    return None if drawn in ("nvidia", vendor_of(strong["name"])) else strong


# -------------------------------------------------------------------------------------------------- screens
def screens() -> list[dict]:
    """Every screen: name, refresh rate (Hz), size (logical px), scale. Needs the QApplication."""
    try:
        from PySide6.QtGui import QGuiApplication
        out = []
        for s in QGuiApplication.screens():
            g = s.geometry()
            out.append({"name": s.name(), "refresh_hz": round(float(s.refreshRate()), 1),
                        "size": [g.width(), g.height()], "scale": round(float(s.devicePixelRatio()), 3)})
        return out
    except Exception as exc:                          # noqa: BLE001
        log.info("screens not readable: %s", exc)
        return []


# --------------------------------------------------------------------------------------------------- OpenGL
def probe_command(out_path: str) -> list[str]:
    """The program itself with --probe-gpu (the exe, or python main.py)."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--probe-gpu", out_path]
    main = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
    return [sys.executable, main, "--probe-gpu", out_path]


def probe_opengl(timeout: float = PROBE_TIMEOUT_S, wait=None) -> dict:
    """What OpenGL gives this program, asked in a separate process (see the module text).
    {"ok": True, "vendor", "renderer", "version", "major", "minor", "software": bool} or
    {"ok": False, "error": "..."}. wait(): called while waiting (the loading screen keeps painting)."""
    fd, path = tempfile.mkstemp(prefix="pfl-gpu-", suffix=".json")
    os.close(fd)
    t0 = time.perf_counter()
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)           # Windows: no console window flashes up
        proc = subprocess.Popen(probe_command(path), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, creationflags=flags)
        while proc.poll() is None:
            if time.perf_counter() - t0 > timeout:
                proc.kill()
                return {"ok": False, "error": f"the OpenGL check did not finish in {timeout:.0f} s"}
            if wait is not None:
                wait()
            time.sleep(0.02)
        try:
            with open(path, encoding="utf-8") as f:
                result = json.load(f)
        except (OSError, ValueError):
            result = {"ok": False, "error": f"the OpenGL check stopped (exit code {proc.returncode}): "
                                            "the graphics driver may be broken"}
    except Exception as exc:                          # noqa: BLE001
        result = {"ok": False, "error": f"the OpenGL check could not start: {exc}"}
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    result["probe_ms"] = round((time.perf_counter() - t0) * 1000.0)
    return result


def run_probe(out_path: str) -> int:
    """The second process (main.py --probe-gpu FILE): make an OpenGL context, read who draws, write FILE
    (written at once: if the driver crashes the process afterwards, the answer is already there)."""
    try:
        from PySide6.QtGui import QGuiApplication
        app = QGuiApplication([sys.argv[0]])
        result = _probe_in(app)
    except Exception as exc:                          # noqa: BLE001
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f)
    return 0


def _probe_in(_app) -> dict:
    """Every step is checked before the next: no OpenGL call on a context that is not current (that call
    is what crashes). _app: the QGuiApplication, alive while the context is used."""
    from PySide6.QtGui import QOffscreenSurface, QOpenGLContext
    ctx = QOpenGLContext()
    if not ctx.create():
        return {"ok": False, "error": "no OpenGL context could be created"}
    surface = QOffscreenSurface()
    surface.setFormat(ctx.format())
    surface.create()
    if not surface.isValid():
        return {"ok": False, "error": "no OpenGL surface could be created"}
    if not ctx.makeCurrent(surface):
        return {"ok": False, "error": "the OpenGL context could not be used"}
    f = ctx.functions()
    vendor, renderer, version = (str(f.glGetString(k) or "") for k in (0x1F00, 0x1F01, 0x1F02))
    fmt = ctx.format()
    ctx.doneCurrent()
    return {"ok": True, "vendor": vendor, "renderer": renderer, "version": version,
            "major": fmt.majorVersion(), "minor": fmt.minorVersion(),
            "software": vendor_of(renderer) == "software" or vendor_of(vendor) == "software"}


# -------------------------------------------------------------------------------------------------- profile
def _versions() -> dict:
    from app_info import APP_VERSION
    out = {"program": APP_VERSION, "python": platform.python_version()}
    try:
        import PySide6
        out["pyside6"] = PySide6.__version__
    except Exception:                                 # noqa: BLE001
        pass
    try:
        import numba
        out["numba"] = numba.__version__
    except Exception:                                 # noqa: BLE001
        out["numba"] = None
    return out


def basics() -> dict:
    """The cheap part (no OpenGL): processor, adapters, screens, versions."""
    return {"cpu": cpu_name(), "cores": cpu_count(), "adapters": display_adapters(), "screens": screens(),
            "os": platform.platform(), "versions": _versions()}


def fingerprint(b: dict) -> str:
    """Changes when the computer does (another screen, a new card, an update of the program / Numba)."""
    key = {"v": PROFILE_VERSION, "cpu": b.get("cpu"), "cores": b.get("cores"),
           "adapters": [a["name"] for a in b.get("adapters", [])],
           "screens": [(s["name"], s["refresh_hz"]) for s in b.get("screens", [])],
           "versions": b.get("versions"), "exe": sys.executable}
    return hashlib.sha1(json.dumps(key, sort_keys=True).encode()).hexdigest()[:16]


def load_profile() -> dict | None:
    from PySide6.QtCore import QSettings
    raw = QSettings().value(PROFILE_KEY, "")
    try:
        p = json.loads(raw) if raw else None
    except (TypeError, ValueError):
        p = None
    return p if isinstance(p, dict) and p.get("profile_version") == PROFILE_VERSION else None


def save_profile(p: dict):
    from PySide6.QtCore import QSettings
    QSettings().setValue(PROFILE_KEY, json.dumps(p))


def detect(force: bool = False, wait=None, probe=None) -> tuple[dict, bool]:
    """The profile of this computer: the remembered one when nothing changed, otherwise found again
    (OpenGL probe included; probe: a replacement for probe_opengl, tests). Returns (profile, fresh)."""
    probe = probe or probe_opengl
    b = basics()
    fp = fingerprint(b)
    old = None if force else load_profile()
    if old is not None and old.get("fingerprint") == fp:
        old.update(b)                                    # (screen sizes etc. as they are today)
        return old, False
    gl = probe(wait=wait)
    p = {"profile_version": PROFILE_VERSION, "fingerprint": fp, "date": time.strftime("%Y-%m-%d %H:%M"),
         **b, "opengl": gl}
    save_profile(p)
    return p, True


# ------------------------------------------------------------------------------------------------- the text
def refresh_hz(p: dict) -> float:
    rates = [s["refresh_hz"] for s in p.get("screens", []) if s.get("refresh_hz")]
    return max(rates) if rates else 60.0


def summary_lines(p: dict) -> list[str]:
    """Short lines for the loading screen, the log and Help → Your computer."""
    try:
        from physics.parallel import workers
        used = f" ({workers()} for computing)"
    except Exception:                                 # noqa: BLE001
        used = ""
    lines = [f"Processor: {p.get('cpu', '?')} — {p.get('cores', '?')} threads{used}"]
    ads = p.get("adapters") or []
    if ads:
        lines.append("Graphics cards: " + ", ".join(
            a["name"] + (f" ({a['memory_mb'] / 1024:.0f} GB)" if a.get("memory_mb") and a["memory_mb"] >= 1024 else "")
            for a in ads))
    gl = p.get("opengl") or {}
    if gl.get("ok"):
        kind = " (software, no graphics card)" if gl.get("software") else ""
        lines.append(f"OpenGL {gl.get('major')}.{gl.get('minor')}: {gl.get('renderer')}{kind}")
    else:
        lines.append(f"OpenGL: not available ({gl.get('error', 'not checked')})")
    scr = p.get("screens") or []
    if scr:
        lines.append("Screen: " + ", ".join(f"{s['size'][0]}×{s['size'][1]} @ {s['refresh_hz']:.0f} Hz"
                                            + (f", {s['scale'] * 100:.0f} %" if s.get("scale", 1) != 1 else "")
                                            for s in scr))
    return lines


def opengl_uses_weak_card(p: dict) -> dict | None:
    """The discrete card (NVIDIA / AMD) when OpenGL runs on another one (a laptop's Intel card): the
    Graphics card mode would then be slow until Windows is told to use the strong card."""
    gl = p.get("opengl") or {}
    if not gl.get("ok"):
        return None
    return runs_on_weak_card(gl.get("renderer", ""), gl.get("vendor", ""), p.get("adapters"))
