"""
app/cli — the program from the command line, without a window (Paket V):

  python main.py --verify [--out DIR] [--no-figures]
        every check (analytic formulas, the assignment's verification scenes, accuracy of the numerical
        methods) → DIR/verification.md, verification.csv, figures/*.png; exit code 0 = all OK
  python main.py SCENE.pflow --figure out.png [--data out.csv] [options]
        a saved scene as a figure (PNG / SVG / PDF) and / or CSV tables, as File → Export would write them

Without these options main.py starts the program (main.py SCENE.pflow opens the scene in the window).
"""
from __future__ import annotations

import argparse
import os
import sys

CLI_OPTIONS = ("--verify", "--figure", "--data", "--help", "-h")
DEFAULT_OUT = "verification"


def wants_cli(argv) -> bool:
    """True if the arguments ask for the command line instead of the window."""
    return any(a == opt or a.startswith(opt + "=") for a in argv for opt in CLI_OPTIONS)


def _layer_keys():
    from app.canvas.canvas import LAYERS
    return [key for key, _label, _on in LAYERS]


def parser() -> argparse.ArgumentParser:
    from app.canvas.canvas import LAYERS
    from app.export.data import DATASETS
    from app.export.figure import BACKGROUNDS
    p = argparse.ArgumentParser(
        prog="main.py",
        description="Flowy (Potential Flow Lab) without the window: verification report, figure and data export.",
        epilog="Layers (default on: " + ", ".join(k for k, _l, on in LAYERS if on) + "): "
               + ", ".join(k for k, _l, _on in LAYERS) + ".   Tables: " + ", ".join(k for k, _l in DATASETS) + ".",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("scene", nargs="?", help="a saved scene (.pflow) for --figure / --data")
    v = p.add_argument_group("verification")
    v.add_argument("--verify", action="store_true",
                   help="run every check and write the report (Markdown + CSV + figures); exit code 0 = all OK")
    v.add_argument("--out", default=DEFAULT_OUT, metavar="DIR",
                   help=f"folder of the report (default: ./{DEFAULT_OUT})")
    v.add_argument("--no-figures", action="store_true", help="the report without the figures (faster)")
    f = p.add_argument_group("figure / data of SCENE")
    f.add_argument("--figure", metavar="FILE", help="write the plot to FILE (.png, .svg or .pdf)")
    f.add_argument("--data", metavar="FILE", help="write CSV tables (several tables: FILE_<table>.csv)")
    f.add_argument("--tables", default="all", metavar="LIST",
                   help="tables for --data, comma separated (default: all)")
    f.add_argument("--view", nargs=4, type=float, metavar=("X0", "X1", "Y0", "Y1"),
                   help="the region shown (default: the view saved in the scene)")
    f.add_argument("--layers", default="", metavar="LIST",
                   help="layer switches, e.g. +bodies,+surface,-markers (+/− change the defaults; "
                        "names without a sign: exactly these layers)")
    f.add_argument("--width", type=int, metavar="PX", help="plot area width in pixels (default 900)")
    f.add_argument("--height", type=int, metavar="PX", help="plot area height in pixels (default: from the view; with --width too, the view is widened "
                        "to that shape)")
    f.add_argument("--scale", type=float, default=2.0, help="PNG resolution: 1–4 × the screen (default 2)")
    f.add_argument("--background", choices=list(BACKGROUNDS), default="white", help="figure background")
    f.add_argument("--dark", action="store_true", help="dark theme colors (default: light)")
    f.add_argument("--vref", type=float, metavar="V", help="Cp reference speed (default: the scene's, or V∞)")
    f.add_argument("--grid", type=int, default=101, metavar="N", help="grid points along x of the field table")
    f.add_argument("--separator", choices=[",", ";", "tab"], default=",", help="CSV separator")
    return p


def parse_layers(text: str) -> dict:
    """'+bodies,-markers' → the defaults changed; 'streamlines,bodies' → exactly these. Raises ValueError."""
    from app.canvas.canvas import LAYERS
    items = [t.strip() for t in text.split(",") if t.strip()]
    keys = _layer_keys()
    for t in items:
        if t.lstrip("+-") not in keys:
            raise ValueError(f"unknown layer '{t.lstrip('+-')}' (layers: {', '.join(keys)})")
    signed = [t for t in items if t[0] in "+-"]
    if signed and len(signed) != len(items):
        raise ValueError("use either +/− changes or a plain list of layers, not both")
    if items and not signed:
        return {k: k in items for k in keys}
    out = {key: on for key, _label, on in LAYERS}
    for t in signed:
        out[t[1:]] = t[0] == "+"
    return out


def parse_tables(text: str) -> list[str]:
    from app.export.data import DATASETS
    keys = [k for k, _l in DATASETS]
    if text.strip().lower() == "all":
        return keys
    items = [t.strip() for t in text.split(",") if t.strip()]
    for t in items:
        if t not in keys:
            raise ValueError(f"unknown table '{t}' (tables: {', '.join(keys)})")
    return items


def export(args, log=print) -> int:
    """SCENE → figure and / or CSV tables (as File → Export figure / Export data)."""
    from app.export.data import export_data
    from app.export.figure import FORMATS, render_figure
    from model.scene_file import SceneFileError, load_scene

    from .headless import make_canvas, show_scene
    fmt = None
    if args.figure:
        fmt = os.path.splitext(args.figure)[1].lower().lstrip(".")
        if fmt not in FORMATS:
            raise ValueError(f"--figure: the file must end in {', '.join('.' + f for f in FORMATS)}")
        if not 1.0 <= args.scale <= 4.0:
            raise ValueError("--scale must be between 1 and 4")
    tables = parse_tables(args.tables) if args.data else []
    layers = parse_layers(args.layers)
    if args.view and (args.view[1] <= args.view[0] or args.view[3] <= args.view[2]):
        raise ValueError("--view: X0 < X1 and Y0 < Y1")
    try:
        doc = load_scene(args.scene)
    except SceneFileError as exc:
        raise ValueError(str(exc)) from None
    for w in doc.warnings:
        log(f"  note: {w}")
    if args.vref is not None:
        doc.settings = dict(doc.settings, cp_reference=args.vref)
    view = ((args.view[0], args.view[1]), (args.view[2], args.view[3])) if args.view else None
    cv = make_canvas(dark=args.dark)
    try:
        show_scene(cv, doc, view, layers, (args.width, args.height))
        (x0, x1), (y0, y1) = cv.view()
        log(f"{os.path.basename(args.scene)}: {len([e for e in doc.elements if e.enabled])} elements, view "
            f"x[{x0:.3g}, {x1:.3g}] y[{y0:.3g}, {y1:.3g}], {len(cv.stagnation_points)} stagnation points")
        if args.figure:
            render_figure(cv, args.figure, fmt, args.scale, args.background)
            log(f"  figure  {args.figure}")
        if args.data:
            surfaces = cv.surfaces.surfaces() if cv.surfaces.wanted else None
            written = export_data(args.data, tables, doc.elements, cv.view(), cv.stagnation_points,
                                  cv.last_result.lines if cv.last_result else [], cv.settings.cp_reference,
                                  args.grid, "\t" if args.separator == "tab" else args.separator, surfaces)
            for path in written:
                log(f"  data    {path}")
    finally:
        cv.shutdown()
    return 0


def main(argv=None) -> int:
    """The command line (see the module docstring). Returns the exit code: 0 OK, 1 a check failed,
    2 wrong arguments / the scene or a file cannot be read or written."""
    if hasattr(sys.stdout, "reconfigure"):              # Γ, θ, → on any Windows console / redirect
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except (OSError, ValueError):                    # pragma: no cover
            pass
    argv = sys.argv[1:] if argv is None else list(argv)
    p = parser()
    args = p.parse_args(argv)
    if args.verify:
        if args.figure or args.data:
            p.error("--verify cannot be combined with --figure / --data")
        from .headless import application
        if not args.no_figures:
            application()
        from .report import run
        return run(args.out, figures=not args.no_figures)
    if not (args.figure or args.data):
        p.error("nothing to do: give --verify, or a scene with --figure and / or --data")
    if not args.scene:
        p.error("--figure / --data need a scene file (.pflow)")
    try:
        return export(args)
    except (ValueError, OSError) as exc:
        print(f"main.py: error: {exc}", file=sys.stderr)
        return 2
