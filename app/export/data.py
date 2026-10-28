"""
data.py — CSV tables for spreadsheets / MATLAB / Python: the elements, the stagnation points, the
streamlines in view, u, v, |V|, Cp, φ, ψ on a grid over the view, and Cp along the surfaces (body
surfaces and walls).
"""
import csv
import os

import numpy as np

from physics.field import complex_potential, fluid_mask, reference_speed, singularity_mask, velocity


DATASETS = (("elements", "Elements (parameters)"),
            ("stagnation", "Stagnation points"),
            ("streamlines", "Streamlines in view (x, y of every point)"),
            ("field", "Velocity field on a grid (u, v, |V|, Cp, φ, ψ)"),
            ("surface", "Surface pressure (Cp along body surfaces and walls)"))


def _fmt(v) -> str:
    if isinstance(v, (float, np.floating)):
        return "" if not np.isfinite(v) else repr(round(float(v), 10))
    return str(v)


def element_rows(elements):
    """Wide table: one row per element, one column per parameter name (empty if not used)."""
    keys = []
    for e in elements:
        for p in e.PARAMS:
            if p.key not in keys:
                keys.append(p.key)
    header = ["index", "type", "enabled"] + keys + ["summary"]
    rows = []
    for i, e in enumerate(elements, 1):
        own = {p.key for p in e.PARAMS}
        rows.append([i, e.TYPE, int(e.enabled)] + [_fmt(getattr(e, k)) if k in own else "" for k in keys]
                    + [e.summary()])
    return header, rows


def stagnation_rows(points):
    header = ["index", "x [m]", "y [m]", "kind", "description"]
    return header, [[i, _fmt(p.x), _fmt(p.y), p.kind, p.describe()] for i, p in enumerate(points, 1)]


def streamline_rows(lines, view):
    """Points of the streamlines that are (partly) in view; one row per point."""
    (x0, x1), (y0, y1) = view
    header = ["line", "point", "x [m]", "y [m]"]
    rows, n = [], 0
    for ln in lines:
        ln = np.asarray(ln)
        if not len(ln) or not np.any((ln[:, 0] >= x0) & (ln[:, 0] <= x1) & (ln[:, 1] >= y0) & (ln[:, 1] <= y1)):
            continue
        n += 1
        rows += [[n, k, _fmt(x), _fmt(y)] for k, (x, y) in enumerate(ln, 1) if np.isfinite(x) and np.isfinite(y)]
    return header, rows


def field_rows(elements, view, nx: int, v_ref=None):
    """u, v, |V|, Cp, φ, ψ on an nx × ny grid over the view (same spacing in x and y). Points in the
    solid or on a singularity are left empty. ψ (and φ) of a vortex (source) are multi-valued: they
    jump across a branch cut, as in the textbook formulas."""
    (x0, x1), (y0, y1) = view
    ny = max(2, int(round((nx - 1) * (y1 - y0) / (x1 - x0))) + 1)
    X, Y = np.meshgrid(np.linspace(x0, x1, nx), np.linspace(y0, y1, ny))
    z = (X + 1j * Y).ravel()
    u, v = velocity(elements, z.real, z.imag)
    u, v = np.asarray(u, float).ravel(), np.asarray(v, float).ravel()
    F = np.asarray(complex_potential(elements, z)).ravel()
    bad = ~np.asarray(fluid_mask(elements, z), bool).ravel()
    bad |= np.asarray(singularity_mask(elements, z, 1e-9 * (x1 - x0)), bool).ravel()
    speed = np.hypot(u, v)
    v_ref = v_ref or reference_speed(elements)          # Computation → Cp reference, else V∞
    cp = 1.0 - (speed / v_ref) ** 2 if v_ref else np.full_like(speed, np.nan)
    cols = [z.real, z.imag, u, v, speed, cp, F.real, F.imag]
    for c in cols[2:]:
        c[bad] = np.nan
    header = ["x [m]", "y [m]", "u [m/s]", "v [m/s]", "|V| [m/s]", "Cp", "phi [m2/s]", "psi [m2/s]"]
    rows = [[_fmt(c[i]) for c in cols] for i in range(z.size)]
    return header, rows


def surface_rows(elements, surfaces, v_ref=None):
    """One row per surface point: the surface (Body 1, Wall 1 …), x, y, arc length s, θ round the center
    (closed bodies), distance along the free stream, u, v, |V|, Cp. `surfaces` = physics.surface.Surface
    list (as on the plot); v_ref = Cp reference speed (None = V∞ of the uniform flow)."""
    from physics.surface import free_stream_angle, rotate_to_theta0
    v_ref = v_ref or reference_speed(elements)
    alpha = free_stream_angle(elements)
    header = ["surface", "kind", "closed", "point", "x [m]", "y [m]", "s [m]", "theta [deg]", "x along flow [m]",
              "u [m/s]", "v [m/s]", "|V| [m/s]", "Cp"]
    rows = []
    for srf in surfaces:
        srf = rotate_to_theta0(srf, alpha)
        cp = srf.cp(v_ref)
        th = srf.theta(alpha) if srf.closed else np.full(srf.z.shape, np.nan)
        xf = srf.along_flow(alpha) if srf.kind == "body" else np.full(srf.z.shape, np.nan)
        for k in range(srf.z.size):
            rows.append([srf.name, srf.kind, int(srf.closed), k + 1, _fmt(srf.z[k].real), _fmt(srf.z[k].imag),
                         _fmt(srf.s[k]), _fmt(th[k]), _fmt(xf[k]), _fmt(srf.vel[k].real), _fmt(srf.vel[k].imag),
                         _fmt(abs(srf.vel[k])), _fmt(cp[k])])
    return header, rows


def write_csv(path: str, header, rows, separator: str = ","):
    """UTF-8 with BOM (Excel shows Γ, μ correctly). separator ',' -> numbers with a decimal point
    (Python, MATLAB, English Excel); ';' -> decimal comma, as Excel with Turkish settings expects."""
    def cell(v):
        if separator == ";" and isinstance(v, str) and v and v[0] in "-0123456789" and _is_number(v):
            return v.replace(".", ",")
        return v
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.writer(f, delimiter=separator)
        wr.writerow(header)
        wr.writerows([[cell(v) for v in row] for row in rows])


def _surfaces(elements, view):
    from physics.surface import body_surfaces, wall_surfaces
    return body_surfaces(elements) + wall_surfaces(elements, view)


def _is_number(text: str) -> bool:
    try:
        float(text)
        return True
    except ValueError:
        return False


def export_data(path: str, datasets, elements, view, stagnation=(), streamlines=(), v_ref=None,
                grid_nx: int = 101, separator: str = ",", surfaces=None):
    """Write the chosen tables (keys of DATASETS) for the view ((x0, x1), (y0, y1)): the stagnation
    points and streamline arrays as drawn, v_ref = Cp reference speed (None = V∞ of the uniform flow),
    surfaces = the surfaces as on the plot (None: computed here).
    One table -> `path`; several -> path stem + '_elements.csv' etc. Returns the written paths."""
    (x0, x1), (y0, y1) = view
    view = ((float(x0), float(x1)), (float(y0), float(y1)))
    tables = {
        "elements": lambda: element_rows(elements),
        "stagnation": lambda: stagnation_rows(stagnation),
        "streamlines": lambda: streamline_rows(streamlines, view),
        "field": lambda: field_rows(elements, view, grid_nx, v_ref),
        "surface": lambda: surface_rows(elements, _surfaces(elements, view) if surfaces is None else surfaces,
                                        v_ref),
    }
    chosen = [d for d in datasets if d in tables]
    stem, ext = os.path.splitext(path)
    ext = ext or ".csv"
    written = []
    for d in chosen:
        out = stem + ext if len(chosen) == 1 else f"{stem}_{d}{ext}"
        header, rows = tables[d]()
        write_csv(out, header, rows, separator)
        written.append(out)
    return written
