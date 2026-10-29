"""
gpu_check.py — which graphics card does the program get, and which way of asking for the fast one works on
this computer? (Laptops with Intel + NVIDIA.) Prints a short report; changes nothing unless --write-registry.

    python scripts/gpu_check.py                    which card OpenGL gives the program, asked in 3 ways
    python scripts/gpu_check.py --write-registry   also: tell Windows "high performance" for the real Python
                                                   file (the same as Settings → Display → Graphics), ask again

Ways asked (each in its own process, like the program's own OpenGL check):
    A  as the program starts today
    B  with SHIM_MCCOMPAT=0x800000001 given at process start (NVIDIA Optimus' own switch)
    C  with SHIM_MCCOMPAT set inside the process, before any graphics (what main.py does after "Use NVIDIA")
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app import gpu, hardware  # noqa: E402

INSIDE = ("import os, sys; os.environ['SHIM_MCCOMPAT'] = '0x800000001'; sys.path.insert(0, {root!r}); "
          "from app.hardware import run_probe; run_probe({out!r})")


def probe(cmd_for, env=None) -> dict:
    fd, path = tempfile.mkstemp(prefix="pfl-gpucheck-", suffix=".json")
    os.close(fd)
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        t = time.perf_counter()
        p = subprocess.run(cmd_for(path), env=env, cwd=ROOT, capture_output=True, text=True, timeout=60,
                           creationflags=flags)
        try:
            with open(path, encoding="utf-8") as f:
                r = json.load(f)
        except (OSError, ValueError):
            r = {"ok": False, "error": f"no answer (exit code {p.returncode}) {p.stderr[-300:]}"}
        r["ms"] = round((time.perf_counter() - t) * 1000)
        return r
    except Exception as exc:                              # noqa: BLE001
        return {"ok": False, "error": str(exc)}
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def line(label, r):
    if r.get("ok"):
        print(f"  {label:<44} {r.get('renderer')}  [{hardware.vendor_of(r.get('renderer', ''))}]   "
              f"(process file: {r.get('exe', '?')})")
    else:
        print(f"  {label:<44} ERROR: {r.get('error')}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write-registry", action="store_true")
    a = ap.parse_args()

    print("Potential Flow Lab — graphics card check\n")
    print("Program files Windows may know this program by:")
    for p in gpu.program_paths():
        print(f"  {p}\n      Windows setting: GpuPreference = {gpu.read_preference(p)}")
    print(f"  Microsoft Store Python: {'YES' if gpu.store_python() else 'no'}")
    print("Graphics cards: " + (", ".join(ad["name"] for ad in hardware.display_adapters()) or "?"))
    print(f"SHIM_MCCOMPAT in this terminal: {os.environ.get('SHIM_MCCOMPAT')}\n")

    plain = {k: v for k, v in os.environ.items() if k != "SHIM_MCCOMPAT"}
    shim = dict(plain, SHIM_MCCOMPAT="0x800000001")
    print("Which card OpenGL gives:")
    line("A  as today", probe(hardware.probe_command, plain))
    line("B  SHIM_MCCOMPAT at process start", probe(hardware.probe_command, shim))
    line("C  SHIM_MCCOMPAT set inside the process", probe(
        lambda out: [sys.executable, "-c", INSIDE.format(root=ROOT, out=out)], plain))
    if a.write_registry:
        done, msg = gpu.ask_for_strong_card()
        print(f"\nWindows setting written for every file above: {done} ({msg})")
        line("D  as today, after the Windows setting", probe(hardware.probe_command, plain))
    print("\nCopy everything above and send it.")


if __name__ == "__main__":
    main()
