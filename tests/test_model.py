"""Scene model: every change is a command, everything can be undone and redone exactly."""
import pytest

from model import SceneModel
from physics import Doublet, Source, SymmetryWall, Uniform, Vortex


def scene():
    return [Uniform(V=1.0), Doublet(mu=1.0), Vortex(Gamma=-2.0)]


def snapshot(m):
    return [e.to_dict() for e in m.elements]


def test_add_undo_redo():
    m = SceneModel(scene())
    before = snapshot(m)
    focus = m.add(Source(m=2.0, x0=1.0))
    assert focus == 3 and len(m.elements) == 4 and m.undo_text == "Add source / sink"
    m.undo()
    assert snapshot(m) == before and m.redo_text == "Add source / sink"
    m.redo()
    assert m.elements[3] == Source(m=2.0, x0=1.0)


def test_add_at_index():
    m = SceneModel(scene())
    m.add(Source(), index=1)
    assert m.elements[1].TYPE == "source" and m.elements[2].TYPE == "doublet"


def test_remove_undo_restores_position():
    m = SceneModel(scene())
    removed = m.elements[1]
    m.remove(1)
    assert [e.TYPE for e in m.elements] == ["uniform", "vortex"]
    m.undo()
    assert m.elements[1] is removed


def test_replace_never_modifies_the_old_object():
    m = SceneModel(scene())
    old = m.elements[2]
    m.replace(2, old.copy(Gamma=3.0))
    assert old.Gamma == -2.0 and m.elements[2].Gamma == 3.0
    m.undo()
    assert m.elements[2] is old


def test_replace_with_identical_element_is_not_an_undo_step():
    m = SceneModel(scene())
    assert m.replace(0, m.elements[0].copy()) is None
    assert not m.can_undo


def test_set_enabled_is_undoable():
    m = SceneModel(scene())
    m.set_enabled(1, False)
    assert not m.elements[1].enabled and m.undo_text == "Hide doublet"
    m.undo()
    assert m.elements[1].enabled
    assert m.set_enabled(1, True) is None          # already enabled: nothing to do


def test_duplicate_is_shifted_and_inserted_after():
    m = SceneModel(scene())
    m.duplicate(2)
    assert (m.elements[3].x0, m.elements[3].y0) == (0.5, 0.5) and m.elements[3].Gamma == -2.0
    m.duplicate(0)                                  # uniform flow has no position: identical copy
    assert m.elements[1] == m.elements[0]


def test_wall_duplicate_moves_its_point():
    m = SceneModel([SymmetryWall(xw=0.0, yw=-1.0)])
    m.duplicate(0)
    assert (m.elements[1].xw, m.elements[1].yw) == (0.5, -0.5)


def test_load_and_clear_are_one_step_each():
    m = SceneModel(scene())
    before = snapshot(m)
    m.load([Uniform(), Source(m=1.0)], "Load preset")
    assert len(m.elements) == 2
    m.clear()
    assert m.elements == []
    assert m.clear() is None                        # nothing to clear
    m.undo()
    assert len(m.elements) == 2
    m.undo()
    assert snapshot(m) == before


def test_new_command_clears_redo():
    m = SceneModel(scene())
    m.add(Source())
    m.undo()
    assert m.can_redo
    m.add(Vortex())
    assert not m.can_redo


def test_list_object_is_kept():
    """Canvas, panels and the probe hold a reference to model.elements; it must never be replaced."""
    m = SceneModel(scene())
    ref = m.elements
    m.load([Source()])
    m.undo()
    m.clear()
    m.undo()
    assert m.elements is ref


def test_merge_of_moves():
    m = SceneModel([Source(x0=0.0)])
    for x in (0.1, 0.2, 0.3):
        m.replace(0, m.elements[0].copy(x0=x), "Move source", merge_key="move")
    assert m.elements[0].x0 == 0.3
    m.undo()                                         # one undo returns to the start
    assert m.elements[0].x0 == 0.0 and not m.can_undo


def test_moves_of_different_elements_do_not_merge():
    m = SceneModel([Source(x0=0.0), Vortex(x0=1.0)])
    m.replace(0, m.elements[0].copy(x0=0.5), merge_key="move")
    m.replace(1, m.elements[1].copy(x0=1.5), merge_key="move")
    m.undo()
    assert m.elements[0].x0 == 0.5 and m.elements[1].x0 == 1.0


def test_modified_flag():
    m = SceneModel(scene())
    m.mark_clean()
    assert not m.is_modified
    m.add(Source())
    assert m.is_modified
    m.undo()
    assert not m.is_modified                         # back to the saved state
    m.add(Source())
    m.mark_clean()
    m.replace(3, m.elements[3].copy(x0=0.1), merge_key="move")
    m.mark_clean()
    m.replace(3, m.elements[3].copy(x0=0.2), merge_key="move")    # merged into the saved step
    assert m.is_modified


def test_listeners_get_focus_index():
    m = SceneModel(scene())
    seen = []
    m.subscribe(seen.append)
    m.add(Source())
    m.remove(0)
    m.undo()
    assert seen == [3, 0, 0]


def test_undo_limit():
    m = SceneModel([], undo_limit=5)
    for k in range(8):
        m.add(Source(x0=float(k)))
    n = 0
    while m.can_undo:
        m.undo()
        n += 1
    assert n == 5 and len(m.elements) == 3


def test_bad_index_raises():
    m = SceneModel(scene())
    with pytest.raises(IndexError):
        m.remove(7)
    with pytest.raises(IndexError):
        m.set_enabled(-1, False)


# ---------------------------------------------------------------- preview of a change (dialog validation)
from model import preview_change  # noqa: E402


def messages(issues):
    return [(s.index, s.severity if hasattr(s, "severity") else s.issue.severity, s.message) for s in issues]


def test_preview_valid_addition_has_no_errors():
    _, issues = preview_change(scene(), Source(m=1.0, x0=3.0))
    assert not [s for s in issues if s.is_error]


def test_preview_reports_problem_of_the_new_element():
    els = [SymmetryWall(yw=-1.0), Uniform()]
    _, issues = preview_change(els, Source(m=1.0, y0=-2.0))
    assert any(s.index == 2 and "behind the wall" in s.message for s in issues)


def test_preview_reports_new_problems_of_other_elements():
    """Adding a wall above an existing source puts that source behind the wall."""
    els = [Uniform(), Source(m=1.0, y0=-2.0)]
    _, issues = preview_change(els, SymmetryWall(yw=-1.0))
    assert any(s.index == 1 and "behind the wall" in s.message for s in issues)


def test_preview_of_edit_does_not_repeat_unrelated_old_problems():
    els = [SymmetryWall(yw=-1.0), Uniform(alpha=10.0), Vortex(Gamma=1.0)]     # uniform: not parallel
    _, issues = preview_change(els, Vortex(Gamma=2.0), index=2)                # editing the vortex
    assert not [s for s in issues if "parallel" in s.message]
    _, issues = preview_change(els, Uniform(alpha=0.0), index=1)               # fixing the uniform flow
    assert not [s for s in issues if s.is_error]


def test_preview_does_not_change_the_scene():
    els = scene()
    before = [e.to_dict() for e in els]
    preview_change(els, Source(), index=1)
    assert [e.to_dict() for e in els] == before
