"""
scene_file.py — saving and opening scenes (File → Save / Open, and the preset files).

A scene file is UTF-8 JSON with the extension .pflow:

    {
      "format": "potential-flow-lab-scene",
      "version": 1,
      "saved_with": "Potential Flow Lab 0.4.0",
      "title": "Lifting cylinder",
      "view": {"x": [-4.0, 4.0], "y": [-3.0, 3.0]},                 (optional)
      "settings": {"density": 1.0, "line_width": 1.4,               (optional)
                   "show_arrows": true, "arrow_density": 1.0},
      "elements": [
        {"type": "uniform", "enabled": true, "V": 1.0, "alpha": 0.0},
        {"type": "doublet", "enabled": true, "mu": 1.0, "x0": 0.0, "y0": 0.0, "delta": 0.0}
      ]
    }

* Numbers are written with full precision, so a saved and reopened scene is EXACTLY the same
  (the assignment's verification case 5).
* Element parameters are the same names as in the physics classes (registry.py), so a new element
  type is saved / opened without changing this file.
* "version" is the file format version. When the format changes, VERSION is increased and a
  function that converts the old layout is added to MIGRATIONS, so old files keep opening.
* Problems that make the file unusable raise SceneFileError with a message for the user;
  small problems (an unknown setting, a missing parameter that has a default) are collected in
  SceneDocument.warnings and the file is still opened.

No Qt here: the module can be used and tested without the GUI.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field, fields
from typing import Callable

from app_info import APP_NAME, APP_VERSION
from physics import ELEMENT_TYPES, FlowElement

FORMAT = "potential-flow-lab-scene"
VERSION = 1
EXTENSION = ".pflow"

# plot settings stored with a scene: name -> type
SETTINGS = {"density": float, "line_width": float, "show_arrows": bool, "arrow_density": float,
            "field_quality": float, "cp_reference": float, "particles": float, "anim_speed": float, "trail": float,
            "pulse_speed": float, "pulse_length": float, "pulse_spacing": float}
ZERO_ALLOWED = {"trail", "pulse_length"}            # settings that may be 0 (the others must be > 0)
IGNORED = {"anim_style"}            # older settings, now not saved (no warning when a file has them)

# MIGRATIONS[n] converts the dict of a version-n file into version n + 1
MIGRATIONS: dict[int, Callable[[dict], dict]] = {}


class SceneFileError(Exception):
    """The file cannot be opened / saved; str(error) is a message for the user."""


@dataclass
class SceneDocument:
    elements: list[FlowElement]
    title: str = ""
    view: tuple[tuple[float, float], tuple[float, float]] | None = None
    settings: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)       # filled when a file is opened


# ---------------------------------------------------------------------- writing
def to_data(doc: SceneDocument) -> dict:
    data = {"format": FORMAT, "version": VERSION, "saved_with": f"{APP_NAME} {APP_VERSION}",
            "title": doc.title}
    if doc.view is not None:
        (x0, x1), (y0, y1) = doc.view
        data["view"] = {"x": [float(x0), float(x1)], "y": [float(y0), float(y1)]}
    settings = {k: SETTINGS[k](v) for k, v in doc.settings.items() if k in SETTINGS}
    if settings:
        data["settings"] = settings
    data["elements"] = [_element_to_data(e) for e in doc.elements]
    return data


def _element_to_data(e: FlowElement) -> dict:
    out = {"type": e.TYPE, "enabled": bool(e.enabled)}
    for p in e.PARAMS:
        v = getattr(e, p.key)
        out[p.key] = int(v) if p.choices else float(v)
    return out


def dumps(doc: SceneDocument) -> str:
    """JSON text, easy to read by eye: one line per setting and per element."""
    try:
        parts = []
        for key, value in to_data(doc).items():
            if key == "elements" and value:
                rows = ",\n".join("    " + _compact(e) for e in value)
                parts.append(f'  "elements": [\n{rows}\n  ]')
            else:
                parts.append(f"  {_compact(key)}: {_compact(value)}")
        return "{\n" + ",\n".join(parts) + "\n}\n"
    except ValueError:
        raise SceneFileError("The scene contains a value that is not a finite number "
                             "(infinity or NaN) and cannot be saved.") from None


def _compact(value) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(", ", ": "))


def save_scene(path: str, doc: SceneDocument) -> None:
    """Write the scene. The file is written to a temporary file first and then renamed,
    so an existing file is never left half-written (e.g. if the disk is full)."""
    text = dumps(doc)
    tmp = f"{path}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    except OSError as exc:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise SceneFileError(f"Could not save “{os.path.basename(path)}”: {exc.strerror or exc}") from None


# ---------------------------------------------------------------------- reading
def load_scene(path: str) -> SceneDocument:
    name = os.path.basename(path)
    try:
        with open(path, encoding="utf-8-sig") as f:
            text = f.read()
    except OSError as exc:
        raise SceneFileError(f"Could not open “{name}”: {exc.strerror or exc}") from None
    except UnicodeDecodeError:
        raise SceneFileError(f"“{name}” is not a Potential Flow Lab scene file (not a text file).") from None
    return loads(text, name)


def loads(text: str, name: str = "the file") -> SceneDocument:
    try:
        data = json.loads(text, parse_constant=_no_constants)
    except json.JSONDecodeError as exc:
        raise SceneFileError(f"“{name}” is damaged or not a scene file "
                             f"(JSON error in line {exc.lineno}: {exc.msg}).") from None
    except ValueError as exc:
        raise SceneFileError(f"“{name}”: {exc}") from None
    return from_data(data, name)


def _no_constants(token):
    raise ValueError(f"the value {token} is not allowed (numbers must be finite)")


def from_data(data, name: str = "the file") -> SceneDocument:
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise SceneFileError(f"“{name}” is not a Potential Flow Lab scene file.")
    version = data.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise SceneFileError(f"“{name}” has an invalid format version ({version!r}).")
    if version > VERSION:
        raise SceneFileError(f"“{name}” was saved by a newer version of the program "
                             f"(file format {version}, this program reads up to {VERSION}). "
                             f"Please update {APP_NAME}.")
    while version < VERSION:                       # convert old files step by step
        data = MIGRATIONS[version](dict(data))
        version += 1

    warnings: list[str] = []
    title = data.get("title", "")
    if not isinstance(title, str):
        warnings.append("The scene title is not text and was ignored.")
        title = ""

    raw = data.get("elements")
    if not isinstance(raw, list):
        raise SceneFileError(f"“{name}” has no element list.")
    elements = [_element_from_data(item, i + 1, warnings) for i, item in enumerate(raw)]

    view = None
    if "view" in data:
        view = _view_from_data(data["view"])
        if view is None:
            warnings.append("The saved view range is invalid and was ignored.")

    settings = {}
    raw_settings = data.get("settings", {})
    if not isinstance(raw_settings, dict):
        warnings.append("The saved plot settings are invalid and were ignored.")
        raw_settings = {}
    for key, value in raw_settings.items():
        kind = SETTINGS.get(key)
        if key in IGNORED:
            continue
        if kind is None:
            warnings.append(f"Unknown plot setting “{key}” was ignored.")
        elif kind is bool and isinstance(value, bool):
            settings[key] = value
        elif kind is float and _is_number(value) and math.isfinite(value) and (
                value > 0 or (value == 0 and key in ZERO_ALLOWED)):
            settings[key] = float(value)
        else:
            warnings.append(f"Plot setting “{key}” has an invalid value and was ignored.")
    return SceneDocument(elements, title, view, settings, warnings)


def _element_from_data(item, number: int, warnings: list[str]) -> FlowElement:
    where = f"Element {number}"
    if not isinstance(item, dict):
        raise SceneFileError(f"{where} in the file is not a valid element.")
    kind = item.get("type")
    cls = ELEMENT_TYPES.get(kind) if isinstance(kind, str) else None
    if cls is None:
        raise SceneFileError(f"{where} has an unknown type “{kind}”. "
                             f"It may have been saved by a newer version of the program.")
    where = f"{where} ({cls.NAME})"
    values = {}
    known = {f.name for f in fields(cls)}
    for p in cls.PARAMS:
        if p.key not in item:
            warnings.append(f"{where}: “{p.name}” was missing; the default {p.default:g} is used.")
            continue
        v = item[p.key]
        if not _is_number(v):
            raise SceneFileError(f"{where}: “{p.name}” must be a number (found {v!r}).")
        if not math.isfinite(v):
            raise SceneFileError(f"{where}: “{p.name}” must be a finite number.")
        if p.choices:
            if float(v) != int(v) or not 0 <= int(v) < len(p.choices):
                raise SceneFileError(f"{where}: “{p.name}” must be one of 0 … {len(p.choices) - 1}.")
            values[p.key] = int(v)
        else:
            values[p.key] = float(v)
    enabled = item.get("enabled", True)
    if not isinstance(enabled, bool):
        warnings.append(f"{where}: “enabled” is not true / false; the element is shown.")
        enabled = True
    for key in item:
        if key not in known and key != "type":
            warnings.append(f"{where}: unknown parameter “{key}” was ignored.")
    return cls(enabled=enabled, **values)


def _view_from_data(v):
    try:
        x0, x1 = v["x"]
        y0, y1 = v["y"]
    except (TypeError, KeyError, ValueError):
        return None
    nums = (x0, x1, y0, y1)
    if not all(_is_number(n) and math.isfinite(n) for n in nums) or not (x0 < x1 and y0 < y1):
        return None
    return (float(x0), float(x1)), (float(y0), float(y1))


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)
