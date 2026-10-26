"""
scene.py — the scene shown at start-up and the preset scenes (Presets menu).

Presets are ordinary scene files (.pflow, same format as File → Save) in the folder `presets/`:
    presets/<group folder>/<file>.pflow
A group folder name may start with a number for ordering ("1 Verification cases (assignment)");
the number is not shown in the menu. A new preset = a scene saved into one of these folders.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass

from model import EXTENSION, SceneFileError, load_scene
from physics import Doublet, Uniform, Vortex

ROOT = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # exe: bundle dir
PRESETS_DIR = os.path.join(ROOT, "presets")


def starter_scene():
    """Lifting cylinder of the course notes: V∞ = 1, μ = 1 (a = 1), clockwise circulation 2."""
    return [Uniform(V=1.0, alpha=0.0), Doublet(mu=1.0), Vortex(Gamma=-2.0)]


@dataclass(frozen=True)
class Preset:
    title: str
    path: str


def list_presets(folder: str = PRESETS_DIR) -> list[tuple[str, list[Preset]]]:
    """[(group label, [Preset, ...]), ...] sorted by folder / file name. Unreadable files are skipped."""
    groups = []
    if not os.path.isdir(folder):
        return groups
    for name in sorted(os.listdir(folder)):
        gdir = os.path.join(folder, name)
        if not os.path.isdir(gdir):
            continue
        items = []
        for fname in sorted(os.listdir(gdir)):
            if not fname.lower().endswith(EXTENSION):
                continue
            path = os.path.join(gdir, fname)
            try:
                title = load_scene(path).title
            except SceneFileError:
                continue
            items.append(Preset(title or os.path.splitext(fname)[0], path))
        if items:
            groups.append((re.sub(r"^\d+\s*", "", name), items))
    return groups
