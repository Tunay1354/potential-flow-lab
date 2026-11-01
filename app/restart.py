"""
restart.py — starting the program again without losing anything (the GPU box: the graphics card can only be
chosen when the program starts, see app/gpu.py).

The running program writes its state into the data folder (restart/): the scene as a scene file, and next to
it what is not in a scene file — its file name, whether it had unsaved changes, the layers, the view mode,
the open Surface pressure panel. It starts itself again with  --resume <state file>  and closes WITHOUT the
"unsaved changes" question (nothing is lost: the new program opens exactly that state, unsaved changes still
unsaved). The new program reads the state and deletes it (MainWindow.resume_from, app/window/files.py).

The environment of the new program is cleaned of the NVIDIA switch (SHIM_MCCOMPAT, PFL_STRONG_CARD): it
decides itself, from the saved GPU setting, whether to start again on the NVIDIA card (gpu.relaunch_on_strong_card).
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time

from .paths import data_folder

log = logging.getLogger("pflab")

RESUME_ARG = "--resume"
STATE_VERSION = 1


def folder() -> str:
    return data_folder("restart")


def write_state(doc, state: dict) -> str:
    """The scene (SceneDocument) and the rest of the state; returns the state file to pass to --resume."""
    from model import save_scene
    os.makedirs(folder(), exist_ok=True)
    for name in os.listdir(folder()):                  # left by a restart that never started (a day old)
        old = os.path.join(folder(), name)
        try:
            if time.time() - os.path.getmtime(old) > 86400:
                os.remove(old)
        except OSError:
            pass
    stem = os.path.join(folder(), f"restart-{os.getpid()}-{int(time.time() * 1000)}")
    save_scene(stem + ".pflow", doc)
    data = dict(state, version=STATE_VERSION, scene=stem + ".pflow")
    with open(stem + ".json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    return stem + ".json"


def read_state(path: str):
    """(SceneDocument, state dict) of a --resume file; both files are deleted. Raises OSError / ValueError /
    SceneFileError when they cannot be read."""
    from model import load_scene
    try:
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
        if not isinstance(state, dict) or "scene" not in state:
            raise ValueError("not a restart state")
        doc = load_scene(state["scene"])
    finally:
        discard(path)
    return doc, state


def discard(path: str):
    for p in (path, os.path.splitext(path)[0] + ".pflow"):
        try:
            os.remove(p)
        except OSError:
            pass


def command(state_path: str) -> tuple[str, list[str]]:
    """(program, arguments) that start the program again with this state."""
    extra = [RESUME_ARG, state_path]
    if getattr(sys, "frozen", False):
        return sys.executable, extra
    main = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
    return sys.executable, [main] + extra


def split_resume(args: list[str]) -> tuple[list[str], str | None]:
    """The command line without  --resume FILE , and FILE (None if not there)."""
    if RESUME_ARG not in args:
        return list(args), None
    i = args.index(RESUME_ARG)
    path = args[i + 1] if i + 1 < len(args) else None
    return args[:i] + args[i + 2:], path


def start_again(state_path: str) -> bool:
    """Start the program again (detached), without the NVIDIA switch in its environment. True if started."""
    from PySide6.QtCore import QProcess, QProcessEnvironment

    from .gpu import RELAUNCH_ENV, SHIM_ENV
    program, args = command(state_path)
    env = QProcessEnvironment.systemEnvironment()
    for key in (SHIM_ENV, RELAUNCH_ENV):
        env.remove(key)
    p = QProcess()
    p.setProgram(program)
    p.setArguments(args)
    p.setProcessEnvironment(env)
    p.setWorkingDirectory(os.getcwd())
    result = p.startDetached()
    ok = result[0] if isinstance(result, tuple) else bool(result)
    if not ok:
        log.error("could not start again: %s %s", program, args)
    return ok
