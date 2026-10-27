"""Scene files (File → Save / Open): exact round trip, readable errors, old-format conversion.
Verification case 5 of the assignment: save → reopen → same element list and same streamlines."""
import json

import numpy as np
import pytest

from model import scene_file as sf
from model.scene_file import SceneDocument, SceneFileError, load_scene, loads, save_scene
from physics import ELEMENT_TYPES, Doublet, SectorFlow, Source, SymmetryWall, Uniform, Vortex
from physics.streamlines import trace_streamlines

SCENE = [
    Uniform(V=2.5, alpha=-135.0),
    Source(m=-3.25, x0=1.5, y0=-0.75),
    Vortex(Gamma=-2.0, x0=-1.0, y0=0.5, enabled=False),
    Doublet(mu=0.6, x0=0.25, y0=1.0, delta=30.0),
    SectorFlow(V=-1.5, x0=0.5, y0=-0.5, theta1=300.0, theta2=30.0),
    SymmetryWall(xw=1.0, yw=-2.0, theta_w=270.0, side=1),
    Source(m=1.23456789012345, x0=-0.0001234, y0=9.87654321e-12),     # many digits
]
VIEW = ((-4.25, 3.5), (-2.0, 2.75))
SETTINGS = {"density": 1.4, "line_width": 1.8, "show_arrows": False, "arrow_density": 2.0}


def doc(**kw):
    base = dict(elements=list(SCENE), title="Kanat önü — ağaç α = 5°", view=VIEW, settings=dict(SETTINGS))
    base.update(kw)
    return SceneDocument(**base)


def test_save_and_open_gives_exactly_the_same_scene(tmp_path):
    path = tmp_path / "scene.pflow"
    save_scene(str(path), doc())
    back = load_scene(str(path))
    assert back.elements == SCENE                    # dataclass equality: every value bit-for-bit
    assert back.title == "Kanat önü — ağaç α = 5°"
    assert back.view == VIEW
    assert back.settings == SETTINGS
    assert back.warnings == []
    # types are preserved (choices stay int, numbers float, enabled bool)
    wall = back.elements[5]
    assert type(wall.side) is int and type(wall.xw) is float
    assert back.elements[2].enabled is False


@pytest.mark.parametrize("key", sorted(ELEMENT_TYPES))
def test_every_element_type_round_trips(key):
    """New element types are saved / opened without touching scene_file.py."""
    cls = ELEMENT_TYPES[key]
    rng = np.random.default_rng(len(key))
    vals = {}
    for p in cls.PARAMS:
        vals[p.key] = len(p.choices) - 1 if p.choices else float(rng.uniform(0.1, 9.9))
    el = cls(**vals)
    back = loads(sf.dumps(SceneDocument([el])))
    assert back.elements == [el]


def test_reopened_scene_gives_the_same_streamlines(tmp_path):
    """Assignment, verification case 5: the plot is reproduced, not only the list."""
    els = [Uniform(V=1.0), Doublet(mu=1.0), Vortex(Gamma=-2.0), Source(m=0.5, x0=-2.0, y0=1.0)]
    path = tmp_path / "case5.pflow"
    save_scene(str(path), SceneDocument(els, "case 5", VIEW, {"density": 1.2}))
    back = load_scene(str(path))
    a = trace_streamlines(els, *VIEW, density=1.2)
    b = trace_streamlines(back.elements, *back.view, density=back.settings["density"])
    assert len(a.lines) == len(b.lines) > 10
    assert all(np.array_equal(p, q) for p, q in zip(a.lines, b.lines))
    assert a.arrows == b.arrows


def test_file_is_readable_json_with_format_and_version(tmp_path):
    path = tmp_path / "s.pflow"
    save_scene(str(path), doc())
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    assert data["format"] == "potential-flow-lab-scene" and data["version"] == sf.VERSION
    assert data["saved_with"].startswith("Potential Flow Lab")
    assert data["elements"][1] == {"type": "source", "enabled": True, "m": -3.25, "x0": 1.5, "y0": -0.75}
    assert "Kanat önü" in text                       # UTF-8, not \\u escapes


def test_scene_without_view_or_settings(tmp_path):
    back = loads(sf.dumps(SceneDocument([Uniform()], "u")))
    assert back.view is None and back.settings == {} and back.elements == [Uniform()]
    empty = loads(sf.dumps(SceneDocument([], "")))
    assert empty.elements == []


# ---------------------------------------------------------------- problems in a file
def _data(**changes):
    data = sf.to_data(doc())
    data.update(changes)
    return data


@pytest.mark.parametrize("text, words", [
    ("not json at all", "damaged"),
    ("[1, 2, 3]", "not a Potential Flow Lab scene"),
    ('{"format": "something-else", "version": 1, "elements": []}', "not a Potential Flow Lab scene"),
    ('{"format": "potential-flow-lab-scene", "version": 99, "elements": []}', "newer version"),
    ('{"format": "potential-flow-lab-scene", "version": "1", "elements": []}', "invalid format version"),
    ('{"format": "potential-flow-lab-scene", "version": 1}', "no element list"),
    ('{"format": "potential-flow-lab-scene", "version": 1, "elements": [{"type": "airfoil"}]}', "unknown type"),
    ('{"format": "potential-flow-lab-scene", "version": 1, "elements": [{"type": ["x"]}]}', "unknown type"),
    ('{"format": "potential-flow-lab-scene", "version": 1, "elements": [5]}', "not a valid element"),
    ('{"format": "potential-flow-lab-scene", "version": 1, "elements": [{"type": "source", "m": "two"}]}',
     "must be a number"),
    ('{"format": "potential-flow-lab-scene", "version": 1, "elements": [{"type": "source", "m": true}]}',
     "must be a number"),
    ('{"format": "potential-flow-lab-scene", "version": 1, "elements": [{"type": "source", "m": NaN}]}',
     "not allowed"),
    ('{"format": "potential-flow-lab-scene", "version": 1, "elements": [{"type": "source", "m": 1e999}]}',
     "finite"),
    ('{"format": "potential-flow-lab-scene", "version": 1, "elements": [{"type": "wall", "side": 2}]}',
     "one of 0"),
])
def test_bad_files_give_a_clear_message(text, words):
    with pytest.raises(SceneFileError) as err:
        loads(text, "bad.pflow")
    assert words in str(err.value)


def test_small_problems_are_warnings_and_the_file_still_opens():
    data = _data(view={"x": [3, 1], "y": [0, 1]},
                 settings={"density": -1, "line_width": 2.0, "colour": "red"})
    data["elements"][1].pop("y0")                                   # missing -> default 0
    data["elements"][1]["comment"] = "my source"                    # unknown -> ignored
    back = sf.from_data(data)
    assert back.elements[1] == Source(m=-3.25, x0=1.5, y0=0.0)
    assert back.view is None
    assert back.settings == {"line_width": 2.0}
    text = "\n".join(back.warnings)
    for words in ("view range", "“density”", "“colour”", "default 0", "“comment”"):
        assert words in text


def test_byte_order_mark_from_windows_editors_is_accepted(tmp_path):
    path = tmp_path / "bom.pflow"
    path.write_text("﻿" + sf.dumps(doc()), encoding="utf-8")
    assert load_scene(str(path)).elements == SCENE


def test_missing_and_binary_files(tmp_path):
    with pytest.raises(SceneFileError, match="Could not open"):
        load_scene(str(tmp_path / "nope.pflow"))
    p = tmp_path / "image.pflow"
    p.write_bytes(bytes(range(256)))
    with pytest.raises(SceneFileError):
        load_scene(str(p))


def test_old_format_versions_are_converted(monkeypatch):
    """When the format changes: VERSION + 1 and a conversion function for the old layout."""
    old = sf.to_data(doc())
    old["objects"] = old.pop("elements")                            # pretend v1 called it "objects"

    def v1_to_v2(data):
        data["elements"] = data.pop("objects")
        return data

    monkeypatch.setattr(sf, "VERSION", 2)
    monkeypatch.setitem(sf.MIGRATIONS, 1, v1_to_v2)
    back = sf.from_data(old)
    assert back.elements == SCENE


# ---------------------------------------------------------------- saving safely
def test_failed_save_keeps_the_old_file(tmp_path):
    path = tmp_path / "keep.pflow"
    save_scene(str(path), doc())
    before = path.read_bytes()
    with pytest.raises(SceneFileError, match="finite"):
        save_scene(str(path), SceneDocument([Source(m=float("inf"))]))
    assert path.read_bytes() == before
    assert not (tmp_path / "keep.pflow.tmp").exists()


def test_save_into_missing_folder_gives_a_message(tmp_path):
    with pytest.raises(SceneFileError, match="Could not save"):
        save_scene(str(tmp_path / "no" / "such" / "dir.pflow"), doc())


def test_overwrite_replaces_the_whole_file(tmp_path):
    path = tmp_path / "s.pflow"
    save_scene(str(path), doc())
    save_scene(str(path), SceneDocument([Uniform()], "short"))
    back = load_scene(str(path))
    assert back.elements == [Uniform()] and back.title == "short"


def test_plot_settings_come_from_one_table():
    """Every slider of Plot settings is a PlotSettings field with a canvas setter, its default fits
    the slider, and the scene file accepts exactly the PlotSettings fields."""
    from dataclasses import fields
    from app.canvas import PlotCanvas
    from app.canvas.settings import SLIDERS
    from model.plot_settings import PlotSettings
    from model.scene_file import SETTINGS, ZERO_ALLOWED
    names = {f.name for f in fields(PlotSettings)}
    assert set(SETTINGS) == names and ZERO_ALLOWED == {"trail", "pulse_length"}
    for spec in SLIDERS:
        assert spec.key in names and callable(getattr(PlotCanvas, f"set_{spec.key}", None))
        default = getattr(PlotSettings(), spec.key)
        assert spec.lo <= spec.position(default) <= spec.hi
        assert spec.value(spec.position(default)) == pytest.approx(default)
        for pos in range(spec.lo, spec.hi + 1, max(1, (spec.hi - spec.lo) // 7)):
            assert spec.position(spec.value(pos)) == pos
