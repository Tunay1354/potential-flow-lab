"""
preview.py — what a change WOULD do to the scene, before it is applied (used by the dialog).

preview_change(elements, new, index) checks the scene in which element `index` is replaced by
`new` (index=None: `new` is added at the end) and returns the problems the user should see:
  * every problem about the changed element itself, and
  * every other problem that does not exist in the current scene yet
    (e.g. adding a wall puts an existing source "behind the wall").
Problems that already existed and are unrelated to the change are not repeated.
"""
from __future__ import annotations

from physics import check_scene


def candidate_scene(elements, new, index: int | None):
    cand = list(elements)
    if index is None:
        cand.append(new)
        return cand, len(cand) - 1
    cand[index] = new
    return cand, index


def preview_change(elements, new, index: int | None = None):
    """Returns (candidate_elements, [SceneIssue, ...])."""
    cand, idx = candidate_scene(elements, new, index)
    before = {(s.index, s.message) for s in check_scene(elements)}
    out = []
    for s in check_scene(cand):
        if s.index == idx or (s.index, s.message) not in before:
            out.append(s)
    return cand, out
