"""
validation.py — checks of the whole scene (not just single elements).

check_scene(elements) returns a list of SceneIssue. `index` points to the element the issue is
about (None = the scene as a whole). The GUI shows errors and refuses invalid input; tests use it too.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .base import FlowElement, Issue
from .field import coincident_singularities, complex_velocity, singular_points
from .images import build_image_system, resolve
from .stagnation import ALIGN_TOL_DEG, doublet_alignment, flow_at


@dataclass(frozen=True)
class SceneIssue:
    index: int | None
    issue: Issue

    @property
    def is_error(self) -> bool:
        return self.issue.is_error

    @property
    def severity(self) -> str:
        return self.issue.severity

    @property
    def message(self) -> str:
        return self.issue.message


def check_scene(elements: Sequence[FlowElement]) -> list[SceneIssue]:
    out: list[SceneIssue] = []

    # 1) each element on its own
    for i, e in enumerate(elements):
        out.extend(SceneIssue(i, iss) for iss in e.check())

    act = [(i, e) for i, e in enumerate(elements) if e.enabled]
    walls = [e for _, e in act if e.IS_BOUNDARY]

    # 2) elements must be strictly on the fluid side of every wall
    for i, e in act:
        if e.IS_BOUNDARY:
            continue
        for p in e.singular_points():
            for w in walls:
                dist = float(w.signed_distance(p))
                tol = 1e-9 * (1.0 + abs(p))
                if abs(dist) <= tol:
                    out.append(SceneIssue(i, Issue("error", f"{e.NAME} lies on the wall "
                                                            f"(θ_w = {w.theta_w:.4g}°); move it into the fluid.")))
                elif dist < 0:
                    out.append(SceneIssue(i, Issue("error", f"{e.NAME} is behind the wall "
                                                            f"(θ_w = {w.theta_w:.4g}°), outside the fluid.")))

    # 2b) the same for elements with a fluid region of their own (sector flow: inside the wedge)
    domains = [e for _, e in act if not e.IS_BOUNDARY and e.implied_walls() is not None]
    for i, e in act:
        if e.IS_BOUNDARY or e in domains:
            continue
        for p in e.marker_points():
            for d in domains:
                dist = float(d.signed_distance(p))
                tol = 1e-9 * (1.0 + abs(p))
                if abs(dist) <= tol:
                    out.append(SceneIssue(i, Issue("error", f"{e.NAME} lies on a wall of the {d.NAME.lower()}; "
                                                            f"move it inside the wedge.")))
                elif dist < 0:
                    out.append(SceneIssue(i, Issue("error", f"{e.NAME} is outside the wedge of the "
                                                            f"{d.NAME.lower()} (outside the fluid).")))

    # 3) the walls must leave some fluid
    if len(walls) >= 2 and not _fluid_exists(walls):
        out.append(SceneIssue(None, Issue("error", "The walls leave no fluid region (check their fluid sides).")))

    # 4) image system (uniform flow parallel to walls, exact / truncated images)
    if walls or domains:
        system = build_image_system(elements)
        out.extend(SceneIssue(None, iss) for iss in system.issues)

    # 5) a doublet makes a cylinder only along the free stream (δ = α): a warning, not an error
    out.extend(_doublet_alignment(elements))

    # 6) coincident singular points (allowed, e.g. doublet + vortex at a cylinder center)
    for i, j in coincident_singularities(elements):
        out.append(SceneIssue(j, Issue("info", f"{elements[j].NAME} is at the same point as "
                                                  f"[{i + 1}] {elements[i].NAME}. This is allowed (e.g. doublet + "
                                                  f"vortex of a lifting cylinder); the point itself is not plotted.")))
    return out


def _doublet_alignment(elements) -> list[SceneIssue]:
    """A warning for every doublet whose axis is not along the flow AT the doublet (made by the other
    elements; stagnation.doublet_alignment): uniform flow + doublet is the flow past a cylinder only
    for δ = α. Other elements turn the flow there too (e.g. a vortex beside the doublet, not at its
    center, or a source nearby). The Solid bodies layer uses the same test (stagnation.open_elements)."""
    act = [e for e in elements if e.enabled]
    fs = complex(sum((e.freestream_velocity() or 0j) for e in act))
    if abs(fs) == 0 and not any(e.TYPE == "sector" for e in act):
        return []
    try:
        flows = resolve(act)
    except Exception:                                   # noqa: BLE001 - an invalid scene: other checks say why
        return []
    sing = singular_points(act)
    out = []
    for i, e in enumerate(elements):
        if not e.enabled or e.TYPE != "doublet" or e.mu == 0:
            continue
        al = doublet_alignment(act, e, flows, sing)
        if al is None or abs(al[1]) <= ALIGN_TOL_DEG:
            continue
        angle = al[0]
        want = (angle - (180.0 if e.mu < 0 else 0.0) + 180.0) % 360.0 - 180.0
        local = flow_at(flows, sing, e.z0)
        if abs(fs) > 0 and abs(local - fs) <= 1e-6 * abs(fs):           # only the uniform flow there
            text = (f"The doublet axis (δ = {e.delta:.4g}°) is not along the uniform flow (α = {angle:.4g}°): "
                    f"this is not the flow past a cylinder — part of the free stream goes through the doublet. "
                    f"For a cylinder set δ = {want:.4g}°.")
        else:
            text = (f"The flow at the doublet (made by the other elements) goes at {angle:.4g}°, but the doublet "
                    f"axis is δ = {e.delta:.4g}°: part of the free stream goes through the doublet, so it makes "
                    f"no closed body (Solid bodies leaves it empty). For a (nearly) closed body set δ = {want:.4g}°.")
            if any(x.TYPE == "vortex" and min(abs(q - e.z0) for q in x.singular_points()) > 1e-9 * (1.0 + abs(e.z0))
                   for x in act):
                text += " For a lifting cylinder put the vortex at the doublet's center."
        out.append(SceneIssue(i, Issue("warning", text)))
    return out


def scene_is_valid(elements) -> bool:
    return not any(s.is_error for s in check_scene(elements))


def _fluid_exists(walls) -> bool:
    """Is the intersection of the fluid half-planes non-empty? (candidate points test)"""
    pts = [w.point for w in walls]
    span = 1.0 + max(abs(p - q) for p in pts for q in pts)
    cand = []
    for w in walls:
        for t in (-1e3, -1.0, 0.0, 1.0, 1e3):
            cand.append(w.point + t * span * w.direction + 1e-3 * span * w.normal)
    for a in range(len(walls)):                     # near pairwise intersections
        for b in range(a + 1, len(walls)):
            wa, wb = walls[a], walls[b]
            den = (np.conj(wa.direction) * wb.direction).imag
            if abs(den) < 1e-12:
                continue
            t = ((np.conj(wb.direction) * (wb.point - wa.point)).imag) / (-den)
            x = wa.point + t * wa.direction
            for k in range(16):
                cand.append(x + 1e-3 * span * np.exp(2j * np.pi * k / 16))
    cand = np.array(cand)
    ok = np.ones(cand.shape, dtype=bool)
    for w in walls:
        ok &= w.signed_distance(cand) > 0
    return bool(ok.any())
