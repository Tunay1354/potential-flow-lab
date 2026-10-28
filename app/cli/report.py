"""
report.py — `python main.py --verify`: every check of the program in one report.

  1  Analytic formulas            physics/verification.py: the velocity formulas against the closed-form
                                  solutions of the course (exact to round-off)
  2  The verification scenes      the assignment's scenes (presets/1 Verification cases): what the
                                  program draws and computes for each (physics/program_checks.py), the
                                  scene saved and opened again (same elements, same streamlines), and
                                  its figure
  3  Accuracy                     the numerical methods on their own (ψ along the lines, stagnation point
                                  search, body shapes, lift from the pressure integral)

Written to the output folder: verification.md (Markdown with the figures), verification.csv (one row per
check) and figures/*.png. The process exits with 0 only if every check holds.
"""
from __future__ import annotations

import csv
import datetime
import glob
import os
import platform
import time

import numpy as np

from app.paths import PRESETS_DIR
from physics.field import active
from physics.program_checks import ACCURACY, SCENES, accuracy_checks, scene_checks
from physics.verification import TOLERANCE, Check, verification_checks

ASSIGNMENT_DIR = os.path.join(PRESETS_DIR, "1 Verification cases (assignment)")
ANALYTIC = "Analytic formulas"
FIGURE_LAYERS = {"bodies": True}              # added to the default layers in the report figures
CSV_HEADER = ["section", "case", "quantity", "analytic", "numerical", "error", "tolerance", "ok"]


def assignment_scenes() -> list[tuple[str, object]]:
    """(file name, SceneDocument) of the assignment's verification scenes, in their order."""
    from model.scene_file import load_scene
    return [(os.path.basename(p), load_scene(p)) for p in sorted(glob.glob(os.path.join(ASSIGNMENT_DIR, "*.pflow")))]


# ---------------------------------------------------------------------- save → reopen
def roundtrip_checks(title: str, doc) -> list[Check]:
    """The scene written to a file and read back (the program's own format): the same elements with the
    same parameters, the same title and view, and the same streamlines computed from it."""
    from model.scene_file import _element_to_data, dumps, loads
    from physics.streamlines import StreamlineCache
    back = loads(dumps(doc), "the saved scene")
    rows = []

    def add(quantity, numerical, tol):
        rows.append(Check(title, quantity, 0.0, float(numerical), tol, SCENES))

    a = [_element_to_data(e) for e in doc.elements]
    b = [_element_to_data(e) for e in back.elements]
    differing = abs(len(a) - len(b)) + sum(x != y for x, y in zip(a, b))
    add(f"saved → reopened: elements that differ (of {len(a)}, every parameter compared)", differing, 0.5)
    same = (back.title == doc.title) + (back.view == doc.view) + (back.settings == doc.settings)
    add("saved → reopened: title, view, plot settings that differ (of 3)", 3 - same, 0.5)
    view = doc.view or ((-4.0, 4.0), (-3.0, 3.0))
    lines = [StreamlineCache(tuple(active(els))).update(view, force=True).lines for els in (doc.elements, back.elements)]
    if len(lines[0]) != len(lines[1]) or any(p.shape != q.shape for p, q in zip(*lines)):
        diff = np.inf
    else:
        diff = max((float(np.max(np.abs(p - q))) for p, q in zip(*lines) if p.size), default=0.0)
    add(f"saved → reopened: the {len(lines[0])} streamlines, largest |Δx|, |Δy| between them [m]", diff, 1e-12)
    return rows


# ---------------------------------------------------------------------- collecting
def collect(figures_dir: str | None = None, log=print):
    """All checks, and the figure of each verification scene (written to figures_dir; None: no
    figures). Returns (checks, {scene title: figure path}, [(file name, title)])."""
    checks, figures, scenes = [], {}, []
    t0 = time.perf_counter()
    rows = verification_checks()
    checks += rows
    log(f"  analytic formulas          {len(rows):3d} checks   {time.perf_counter() - t0:5.1f} s")
    canvas = None
    if figures_dir:
        from .headless import make_canvas
        os.makedirs(figures_dir, exist_ok=True)
        canvas = make_canvas()
    for name, doc in assignment_scenes():
        t1 = time.perf_counter()
        title = doc.title or os.path.splitext(name)[0]
        scenes.append((name, title))
        view = doc.view or ((-4.0, 4.0), (-3.0, 3.0))
        rows = scene_checks(title, doc.elements, view) + roundtrip_checks(title, doc)
        checks += rows
        if canvas is not None:
            figures[title] = _figure(canvas, doc, os.path.join(figures_dir, os.path.splitext(name)[0] + ".png"))
        log(f"  {name:<26} {len(rows):3d} checks   {time.perf_counter() - t1:5.1f} s")
    t1 = time.perf_counter()
    rows = accuracy_checks()
    checks += rows
    log(f"  accuracy of the methods    {len(rows):3d} checks   {time.perf_counter() - t1:5.1f} s")
    if canvas is not None:
        canvas.shutdown()
        canvas.deleteLater()
    return checks, figures, scenes


def _figure(canvas, doc, path):
    from app.canvas.canvas import LAYERS
    from app.export.figure import render_figure

    from .headless import show_scene
    layers = {key: on for key, _label, on in LAYERS} | FIGURE_LAYERS
    show_scene(canvas, doc, layers=layers)
    render_figure(canvas, path, "png", 2.0, "white")
    return path


# ---------------------------------------------------------------------- writing
def _num(v: float) -> str:
    if not np.isfinite(v):
        return str(v)
    if v == 0.0:
        return "0"
    return f"{v:.10g}" if 1e-4 <= abs(v) < 1e6 else f"{v:.6e}"


def write_csv(path: str, checks):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:            # (Excel reads the BOM as UTF-8)
        w = csv.writer(f)
        w.writerow(CSV_HEADER)
        for c in checks:
            w.writerow([c.section, c.case, c.quantity, repr(c.analytic), repr(c.numerical), f"{c.error:.3e}",
                        f"{c.tolerance:g}", "OK" if c.ok else "FAIL"])


def _md(text: str) -> str:
    return text.replace("|", "\\|")


def _table(checks, with_case: bool) -> list[str]:
    head = (["Case"] if with_case else []) + ["Quantity", "Analytic", "Program", "Error", "Tolerance", ""]
    out = ["| " + " | ".join(head) + " |", "|" + "|".join(["---"] * len(head)) + "|"]
    for c in checks:
        cells = ([_md(c.case)] if with_case else []) + [
            _md(c.quantity), _num(c.analytic), _num(c.numerical), f"{c.error:.1e}", f"{c.tolerance:g}",
            "OK" if c.ok else "**FAIL**"]
        out.append("| " + " | ".join(cells) + " |")
    return out


def markdown(checks, figures, scenes, out_dir) -> str:
    from app_info import APP_NAME, APP_VERSION
    n_ok = sum(c.ok for c in checks)
    versions = [f"Python {platform.python_version()}", f"NumPy {np.__version__}"]
    try:
        import numba
        versions.append(f"Numba {numba.__version__}")
    except ImportError:                               # pragma: no cover - optional
        versions.append("without Numba")
    lines = [f"# {APP_NAME} — verification report", "",
             f"{APP_NAME} {APP_VERSION} · {datetime.datetime.now():%Y-%m-%d %H:%M} · {', '.join(versions)} · "
             f"{platform.system()}", "",
             f"Written by `python main.py --verify`. **Result: {n_ok} of {len(checks)} checks OK"
             + ("." if n_ok == len(checks) else f" — {len(checks) - n_ok} FAILED.") + "**", "",
             "Error = |program − analytic|; a row is OK when the error is below its tolerance. "
             "Every row is also in verification.csv.", ""]

    def part(section):
        return [c for c in checks if c.section == section]

    analytic = part(ANALYTIC)
    lines += ["## 1. Analytic formulas", "",
              "The velocity formulas of the program against the closed-form solutions of the course, at sample "
              f"points (velocity components, flux and circulation around circles, forces on the cylinder, walls "
              f"and images, sector flows). These are exact up to round-off: tolerance {TOLERANCE:.0e}.", ""]
    lines += _table(analytic, True) + [""]

    lines += ["## 2. The verification scenes of the assignment", "",
              "Each scene as the program opens it (presets → *1 Verification cases*). The checks compare what "
              "the program draws and finds — the streamlines as integrated (RK4), the stagnation points from "
              "the search (Newton), the body surface as traced, Cp on it and the force from the pressure "
              "integral — with the theory. *Saved → reopened*: the scene written to a .pflow file and opened "
              "again gives the same elements and the same streamlines (assignment, verification case 5).", ""]
    scene_rows = part(SCENES)
    for k, (name, title) in enumerate(scenes, 1):
        lines += [f"### 2.{k} {title}", "", f"Scene file: `{name}`", ""]
        if title in figures:
            rel = os.path.relpath(figures[title], out_dir).replace(os.sep, "/")
            lines += [f"![{_md(title)}]({rel})", ""]
        lines += _table([c for c in scene_rows if c.case == title], False) + [""]

    lines += ["## 3. Accuracy of the numerical methods", "",
              "Scenes with a known answer, beyond the assignment's: ψ along the drawn streamlines (constant on "
              "a streamline; the error is given in units of the ψ step between two drawn lines), stagnation "
              "points from the search, body shapes from the traced surfaces, and the lift from the surface "
              "pressure for several Γ (Kutta–Joukowski).", ""]
    lines += _table(part(ACCURACY), True) + [""]
    return "\n".join(lines)


def run(out_dir: str, figures: bool = True, log=print) -> int:
    """The whole report into out_dir. Returns the exit code: 0 if every check holds, 1 otherwise."""
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.perf_counter()
    log(f"Verification → {os.path.abspath(out_dir)}")
    checks, figs, scenes = collect(os.path.join(out_dir, "figures") if figures else None, log)
    md_path, csv_path = os.path.join(out_dir, "verification.md"), os.path.join(out_dir, "verification.csv")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown(checks, figs, scenes, out_dir))
    write_csv(csv_path, checks)
    bad = [c for c in checks if not c.ok]
    for c in bad:
        log(f"  FAIL  {c.case}: {c.quantity}  (error {c.error:.2e} ≥ {c.tolerance:g})")
    log(f"{len(checks) - len(bad)} of {len(checks)} checks OK  ({time.perf_counter() - t0:.1f} s)")
    log(f"  {md_path}\n  {csv_path}" + (f"\n  {len(figs)} figures in {os.path.join(out_dir, 'figures')}" if figs else ""))
    return 0 if not bad else 1
