"""
report.py — the verification report: every check of the program in one place. Used by the command line
(`python main.py --verify`) and by Help → Run verification… (app/verification_dialog.py).

  1  Analytic formulas            physics/verification.py: the velocity formulas against the closed-form
                                  solutions of the course (exact to round-off)
  2  The verification scenes      the assignment's scenes (presets/1 Verification cases): what the
                                  program draws and computes for each (physics/program_checks.py), the
                                  scene saved and opened again (same elements, same streamlines), and
                                  its figure
  3  Accuracy                     the numerical methods on their own (ψ along the lines, stagnation point
                                  search, body shapes, lift from the pressure integral)

Every check carries `how`: the theory, what the program computes and why the tolerance is what it is.

Written to the output folder: verification.html (the report for a browser: figures, and under every
check its explanation, folded), verification.md (Markdown, the same tables), verification.csv (one row
per check) and figures/*.png.

The work is split into steps (check_jobs: pure computation, may run in a background thread;
render_figure: Qt, in the GUI thread), so the window can show progress.
"""
from __future__ import annotations

import csv
import datetime
import glob
import html
import os
import platform
import time
from dataclasses import dataclass, field

import numpy as np

from app_info import APP_NAME, APP_VERSION
from app.paths import PRESETS_DIR
from physics.field import active
from physics.program_checks import ACCURACY, SCENES, accuracy_checks, scene_checks
from physics.verification import TOLERANCE, Check, verification_checks

ASSIGNMENT_DIR = os.path.join(PRESETS_DIR, "1 Verification cases (assignment)")
ANALYTIC = "Analytic formulas"
SECTIONS = (ANALYTIC, SCENES, ACCURACY)
SECTION_TITLES = {ANALYTIC: "Analytic formulas",
                  SCENES: "The verification scenes of the assignment",
                  ACCURACY: "Accuracy of the numerical methods"}
SECTION_TEXT = {
    ANALYTIC: "The velocity formulas of the program against the closed-form solutions of the course, at sample "
              "points: velocity components, flux and circulation around circles, the cylinder (velocity, Cp, "
              "forces), walls and the method of images, sector flows. These are exact up to round-off: "
              f"tolerance {TOLERANCE:g}.",
    SCENES: "Each scene as the program opens it (Presets → 1 Verification cases). The checks compare what the "
            "program draws and finds — the streamlines as integrated (RK4), the stagnation points from the search "
            "(Newton), the body surface as traced, Cp on it and the force from the pressure integral — with the "
            "theory. Saved → reopened: the scene written to a .pflow file and opened again gives the same elements "
            "and the same streamlines (assignment, verification case 5).",
    ACCURACY: "Scenes with a known answer beyond the assignment's: ψ along the drawn streamlines (constant on a "
              "streamline; the error in units of the ψ step between two drawn lines), stagnation points from the "
              "search (also double and triple roots), body shapes from the traced surfaces, and the lift from the "
              "surface pressure for several Γ (Kutta–Joukowski).",
}
FIGURE_LAYERS = {"bodies": True}              # added to the default layers in the report figures
CSV_HEADER = ["section", "case", "quantity", "analytic", "numerical", "error", "tolerance", "ok", "how"]
DEFAULT_VIEW = ((-4.0, 4.0), (-3.0, 3.0))

_ROUNDTRIP = {
    "elements": "Theory: saving and opening must give the same scene (assignment, verification case 5).\n"
                "Program: the scene is written in the program's file format (model/scene_file.dumps: JSON with "
                "every parameter in full precision) and read back (loads); every parameter of every element is "
                "compared.",
    "settings": "Program: the same save → open; the scene title, the view and the plot settings are compared.",
    "lines": "Program: the streamlines of the original and of the reopened scene, computed for the saved view by "
             "the program's streamline code; every point of every line is compared (they must be the same to "
             "the last bit).",
}


@dataclass
class Scene:
    name: str                 # file name (01_uniform_alpha_0.pflow)
    title: str
    doc: object               # model.scene_file.SceneDocument

    @property
    def stem(self) -> str:
        return os.path.splitext(self.name)[0]


@dataclass
class Report:
    checks: list = field(default_factory=list)
    scenes: list = field(default_factory=list)
    figures: dict = field(default_factory=dict)      # scene title → figure path
    seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def section(self, name) -> list:
        return [c for c in self.checks if c.section == name]


def assignment_scenes() -> list[tuple[str, object]]:
    """(file name, SceneDocument) of the assignment's verification scenes, in their order."""
    from model.scene_file import load_scene
    return [(os.path.basename(p), load_scene(p)) for p in sorted(glob.glob(os.path.join(ASSIGNMENT_DIR, "*.pflow")))]


def scenes() -> list[Scene]:
    return [Scene(name, doc.title or os.path.splitext(name)[0], doc) for name, doc in assignment_scenes()]


# ---------------------------------------------------------------------- save → reopen
def roundtrip_checks(title: str, doc) -> list[Check]:
    """The scene written to a file and read back (the program's own format): the same elements with the
    same parameters, the same title and view, and the same streamlines computed from it."""
    from model.scene_file import _element_to_data, dumps, loads
    from physics.streamlines import StreamlineCache
    back = loads(dumps(doc), "the saved scene")
    rows = []

    def add(quantity, numerical, tol, how):
        rows.append(Check(title, quantity, 0.0, float(numerical), tol, SCENES, _ROUNDTRIP[how]))

    a = [_element_to_data(e) for e in doc.elements]
    b = [_element_to_data(e) for e in back.elements]
    differing = abs(len(a) - len(b)) + sum(x != y for x, y in zip(a, b))
    add(f"saved → reopened: elements that differ (of {len(a)}, every parameter compared)", differing, 0.5,
        "elements")
    same = (back.title == doc.title) + (back.view == doc.view) + (back.settings == doc.settings)
    add("saved → reopened: title, view, plot settings that differ (of 3)", 3 - same, 0.5, "settings")
    view = doc.view or DEFAULT_VIEW
    lines = [StreamlineCache(tuple(active(els))).update(view, force=True).lines for els in (doc.elements, back.elements)]
    if len(lines[0]) != len(lines[1]) or any(p.shape != q.shape for p, q in zip(*lines)):
        diff = np.inf
    else:
        diff = max((float(np.max(np.abs(p - q))) for p, q in zip(*lines) if p.size), default=0.0)
    add(f"saved → reopened: the {len(lines[0])} streamlines, largest |Δx|, |Δy| between them [m]", diff, 1e-12,
        "lines")
    return rows


# ---------------------------------------------------------------------- the steps
def check_jobs(scene_list: list[Scene]) -> list[tuple[str, object]]:
    """(label, function → list of Check): the computation, step by step (no Qt: may run in a thread)."""
    jobs = [("Analytic formulas", verification_checks)]
    for sc in scene_list:
        jobs.append((sc.name, lambda sc=sc: scene_checks(sc.title, sc.doc.elements, sc.doc.view or DEFAULT_VIEW)
                     + roundtrip_checks(sc.title, sc.doc)))
    jobs.append(("Accuracy of the numerical methods", accuracy_checks))
    return jobs


def render_figure(canvas, scene: Scene, figures_dir: str) -> str:
    """The figure of a scene (Qt: GUI thread) on a canvas from headless.make_canvas."""
    from app.canvas.canvas import LAYERS
    from app.export.figure import render_figure as render

    from .headless import show_scene
    os.makedirs(figures_dir, exist_ok=True)
    path = os.path.join(figures_dir, scene.stem + ".png")
    layers = {key: on for key, _label, on in LAYERS} | FIGURE_LAYERS
    show_scene(canvas, scene.doc, layers=layers)
    render(canvas, path, "png", 2.0, "white")
    return path


def collect(figures_dir: str | None = None, log=print) -> Report:
    """Every check, and the figure of each verification scene (written to figures_dir; None: none)."""
    t0 = time.perf_counter()
    rep = Report(scenes=scenes())
    for label, job in check_jobs(rep.scenes):
        t1 = time.perf_counter()
        rows = job()
        rep.checks += rows
        log(f"  {label:<34} {len(rows):3d} checks   {time.perf_counter() - t1:5.1f} s")
    if figures_dir:
        from .headless import make_canvas
        t1 = time.perf_counter()
        canvas = make_canvas()
        try:
            for sc in rep.scenes:
                rep.figures[sc.title] = render_figure(canvas, sc, figures_dir)
        finally:
            canvas.shutdown()
            canvas.deleteLater()
        log(f"  {'figures':<34} {len(rep.figures):3d}          {time.perf_counter() - t1:5.1f} s")
    rep.seconds = time.perf_counter() - t0
    return rep


# ---------------------------------------------------------------------- text of the numbers
def num(v: float) -> str:
    if not np.isfinite(v):
        return str(v)
    if v == 0.0:
        return "0"
    return f"{v:.10g}" if 1e-4 <= abs(v) < 1e6 else f"{v:.6e}"


def how_parts(how: str) -> list[tuple[str, str]]:
    """The explanation as (label, text) pairs: "Theory: …" → ("Theory", "…"); a line without a label → ("", …)."""
    out = []
    for line in how.split("\n"):
        line = line.strip()
        if not line:
            continue
        head, sep, rest = line.partition(": ")
        if sep and head in ("Theory", "Program", "Tolerance"):
            out.append((head, rest))
        else:
            out.append(("", line))
    return out


def how_html(c: Check) -> str:
    """The explanation of a check with its numbers, as HTML (the dialog and the HTML report)."""
    parts = [f"<p><b>{html.escape(k)}:</b> {html.escape(t)}</p>" if k else f"<p>{html.escape(t)}</p>"
             for k, t in how_parts(c.how)]
    verdict = "OK" if c.ok else "FAIL"
    parts.append(f"<p><b>Result:</b> analytic {html.escape(num(c.analytic))}, program {html.escape(num(c.numerical))}"
                 f" → error |program − analytic| = {c.error:.3g} {'&lt;' if c.ok else '≥'} tolerance {c.tolerance:g}"
                 f" → <b>{verdict}</b></p>")
    return "\n".join(parts)


def _versions() -> str:
    v = [f"Python {platform.python_version()}", f"NumPy {np.__version__}"]
    try:
        import numba
        v.append(f"Numba {numba.__version__}")
    except ImportError:                               # pragma: no cover - optional
        v.append("without Numba")
    return f"{APP_NAME} {APP_VERSION} · {datetime.datetime.now():%Y-%m-%d %H:%M} · {', '.join(v)} · {platform.system()}"


def summary(rep: Report) -> str:
    n_ok = sum(c.ok for c in rep.checks)
    return f"{n_ok} of {len(rep.checks)} checks OK" + ("" if n_ok == len(rep.checks) else
                                                       f" — {len(rep.checks) - n_ok} FAILED")


# ---------------------------------------------------------------------- CSV
def write_csv(path: str, checks):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:            # (Excel reads the BOM as UTF-8)
        w = csv.writer(f)
        w.writerow(CSV_HEADER)
        for c in checks:
            w.writerow([c.section, c.case, c.quantity, repr(c.analytic), repr(c.numerical), f"{c.error:.3e}",
                        f"{c.tolerance:g}", "OK" if c.ok else "FAIL", " ".join(c.how.split("\n"))])


# ---------------------------------------------------------------------- Markdown
def _md(text: str) -> str:
    return text.replace("|", "\\|")


def _md_table(checks, with_case: bool) -> list[str]:
    head = (["Case"] if with_case else []) + ["Quantity", "Analytic", "Program", "Error", "Tolerance", ""]
    out = ["| " + " | ".join(head) + " |", "|" + "|".join(["---"] * len(head)) + "|"]
    for c in checks:
        cells = ([_md(c.case)] if with_case else []) + [
            _md(c.quantity), num(c.analytic), num(c.numerical), f"{c.error:.1e}", f"{c.tolerance:g}",
            "OK" if c.ok else "**FAIL**"]
        out.append("| " + " | ".join(cells) + " |")
    return out


def markdown(rep: Report, out_dir: str) -> str:
    lines = [f"# {APP_NAME} — verification report", "", _versions(), "",
             f"**Result: {summary(rep)}.**", "",
             "Error = |program − analytic|; a row is OK when the error is below its tolerance. How each check is "
             "computed (theory, program, tolerance) is in verification.html and in the last column of "
             "verification.csv.", ""]
    for k, sec in enumerate(SECTIONS, 1):
        lines += [f"## {k}. {SECTION_TITLES[sec]}", "", SECTION_TEXT[sec], ""]
        if sec == SCENES:
            for j, sc in enumerate(rep.scenes, 1):
                lines += [f"### {k}.{j} {sc.title}", "", f"Scene file: `{sc.name}`", ""]
                if sc.title in rep.figures:
                    rel = os.path.relpath(rep.figures[sc.title], out_dir).replace(os.sep, "/")
                    lines += [f"![{_md(sc.title)}]({rel})", ""]
                lines += _md_table([c for c in rep.section(sec) if c.case == sc.title], False) + [""]
        else:
            lines += _md_table(rep.section(sec), True) + [""]
    return "\n".join(lines)


# ---------------------------------------------------------------------- HTML
_CSS = """
body{font-family:"Segoe UI",system-ui,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px;color:#222;
background:#fbfaf6;line-height:1.45}
h1{font-size:1.6em;margin-bottom:.2em} h2{margin-top:1.8em;border-bottom:2px solid #c9c2ad;padding-bottom:.2em}
h3{margin-top:1.4em} .meta{color:#666;font-size:.9em} .muted{color:#555}
.result{font-size:1.15em;padding:.5em .8em;border-radius:6px;display:inline-block}
.pass{background:#e2f0dc;color:#1f5e1a} .fail{background:#f6dcd8;color:#8a1c12}
table{border-collapse:collapse;width:100%;font-size:.92em;margin:.6em 0}
th,td{border-bottom:1px solid #ddd6c4;padding:5px 8px;text-align:left;vertical-align:top}
th{background:#efeadb} td.n{font-family:Consolas,monospace;white-space:nowrap}
td.ok{color:#1f6e1a;font-weight:600} td.bad{color:#a01c10;font-weight:700}
summary{cursor:pointer} summary::marker{color:#9a8f73}
details .how{background:#fff;border-left:3px solid #c9c2ad;margin:.4em 0 .3em;padding:.2em .8em;font-size:.95em}
details .how p{margin:.35em 0}
img{max-width:min(100%,760px);border:1px solid #ddd6c4}
"""


def _html_table(checks, with_case: bool) -> list[str]:
    head = (["Case"] if with_case else []) + ["Quantity <span class='muted'>(click: how it is computed)</span>",
                                              "Analytic", "Program", "Error", "Tolerance", ""]
    out = ["<table><tr>" + "".join(f"<th>{h}</th>" for h in head) + "</tr>"]
    for c in checks:
        case = f"<td>{html.escape(c.case)}</td>" if with_case else ""
        out.append(f"<tr>{case}<td><details><summary>{html.escape(c.quantity)}</summary><div class='how'>"
                   f"{how_html(c)}</div></details></td><td class='n'>{num(c.analytic)}</td>"
                   f"<td class='n'>{num(c.numerical)}</td><td class='n'>{c.error:.1e}</td>"
                   f"<td class='n'>{c.tolerance:g}</td><td class='{'ok' if c.ok else 'bad'}'>"
                   f"{'OK' if c.ok else 'FAIL'}</td></tr>")
    out.append("</table>")
    return out


def html_report(rep: Report, out_dir: str) -> str:
    lines = ["<!doctype html><html lang='en'><head><meta charset='utf-8'>",
             "<meta name='viewport' content='width=device-width, initial-scale=1'>",
             "<title>Verification report</title>", f"<style>{_CSS}</style></head><body>",
             f"<h1>{APP_NAME} — verification report</h1>",
             f"<p class='meta'>{html.escape(_versions())}</p>",
             f"<p class='result {'pass' if rep.ok else 'fail'}'>{html.escape(summary(rep))}</p>",
             "<p class='muted'>Error = |program − analytic|; a row is OK when the error is below its tolerance. "
             "Click a quantity to see how it is computed: the theory, what the program does, and why the "
             "tolerance is what it is.</p>"]
    for k, sec in enumerate(SECTIONS, 1):
        rows = rep.section(sec)
        n_ok = sum(c.ok for c in rows)
        lines += [f"<h2>{k}. {html.escape(SECTION_TITLES[sec])} <span class='muted'>({n_ok} / {len(rows)} OK)"
                  "</span></h2>", f"<p>{html.escape(SECTION_TEXT[sec])}</p>"]
        if sec == SCENES:
            for j, sc in enumerate(rep.scenes, 1):
                lines += [f"<h3>{k}.{j} {html.escape(sc.title)}</h3>",
                          f"<p class='muted'>Scene file: <code>{html.escape(sc.name)}</code></p>"]
                if sc.title in rep.figures:
                    rel = os.path.relpath(rep.figures[sc.title], out_dir).replace(os.sep, "/")
                    lines.append(f"<p><img src='{html.escape(rel)}' alt='{html.escape(sc.title)}' loading='lazy'></p>")
                lines += _html_table([c for c in rows if c.case == sc.title], False)
        else:
            lines += _html_table(rows, True)
    lines.append("</body></html>")
    return "\n".join(lines)


# ---------------------------------------------------------------------- writing everything
def write(rep: Report, out_dir: str) -> dict:
    """verification.html / .md / .csv into out_dir (the figures are already there). Returns their paths."""
    os.makedirs(out_dir, exist_ok=True)
    paths = {ext: os.path.join(out_dir, f"verification.{ext}") for ext in ("html", "md", "csv")}
    with open(paths["html"], "w", encoding="utf-8") as f:
        f.write(html_report(rep, out_dir))
    with open(paths["md"], "w", encoding="utf-8") as f:
        f.write(markdown(rep, out_dir))
    write_csv(paths["csv"], rep.checks)
    return paths


def run(out_dir: str, figures: bool = True, log=print) -> int:
    """The whole report into out_dir. Returns the exit code: 0 if every check holds, 1 otherwise."""
    log(f"Verification → {os.path.abspath(out_dir)}")
    rep = collect(os.path.join(out_dir, "figures") if figures else None, log)
    paths = write(rep, out_dir)
    for c in rep.checks:
        if not c.ok:
            log(f"  FAIL  {c.case}: {c.quantity}  (error {c.error:.2e} ≥ {c.tolerance:g})")
    log(f"{summary(rep)}  ({rep.seconds:.1f} s)")
    log("\n".join(f"  {p}" for p in paths.values())
        + (f"\n  {len(rep.figures)} figures in {os.path.join(out_dir, 'figures')}" if rep.figures else ""))
    return 0 if rep.ok else 1
