"""The command line (Paket V): `main.py --verify` (report of every check) and `main.py SCENE --figure /
--data` (export without a window), and the checks of what the program computes (physics/program_checks)."""
import csv
import os
import subprocess
import sys

import numpy as np
import pytest

from app.cli import parse_layers, parse_tables, wants_cli
from app.cli.report import assignment_scenes, roundtrip_checks
from physics.program_checks import accuracy_checks, scene_checks

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIFTING = os.path.join(ROOT, "presets", "1 Verification cases (assignment)", "08_lifting_cylinder.pflow")


def _bad(rows):
    return "\n".join(f"{c.case}: {c.quantity}  {c.numerical} vs {c.analytic} (tol {c.tolerance})"
                     for c in rows if not c.ok)


# ---------------------------------------------------------------------- the checks
def test_every_assignment_scene_has_its_checks_and_they_hold():
    scenes = assignment_scenes()
    assert len(scenes) == 9
    for name, doc in scenes:
        rows = scene_checks(doc.title, doc.elements, doc.view)
        assert len(rows) >= 2, name                      # every verification scene is recognised
        assert not _bad(rows), _bad(rows)


def test_lifting_cylinder_checks_compare_with_kutta_joukowski():
    (_name, doc), = [s for s in assignment_scenes() if s[0].startswith("08")]
    rows = scene_checks(doc.title, doc.elements, doc.view)
    lift = next(c for c in rows if c.quantity.startswith("lift"))
    assert lift.analytic == pytest.approx(1.225 * 2.0)
    assert lift.numerical == pytest.approx(2.45, rel=1e-3)
    assert any(c.quantity.startswith("stagnation points") and c.error < 1e-8 for c in rows)


def test_accuracy_checks_hold():
    rows = accuracy_checks()
    assert len(rows) >= 15
    assert not _bad(rows), _bad(rows)


def test_save_and_reopen_gives_the_same_scene():
    (_name, doc), = [s for s in assignment_scenes() if s[0].startswith("07")]
    rows = roundtrip_checks(doc.title, doc)
    assert len(rows) == 3 and all(c.ok for c in rows)


def test_save_and_reopen_check_sees_a_changed_element(monkeypatch):
    import model.scene_file as sf
    (_name, doc), = [s for s in assignment_scenes() if s[0].startswith("07")]
    real = sf.loads

    def changed(text, name="the file"):
        back = real(text, name)
        back.elements[1].mu *= 1.01
        return back

    monkeypatch.setattr(sf, "loads", changed)
    rows = roundtrip_checks(doc.title, doc)
    assert [c.ok for c in rows] == [False, True, False]


# ---------------------------------------------------------------------- arguments
def test_cli_is_only_used_with_its_options():
    assert not wants_cli([])
    assert not wants_cli(["scene.pflow"])
    assert wants_cli(["--verify"])
    assert wants_cli(["scene.pflow", "--figure=out.png"])
    assert wants_cli(["-h"])


def test_layer_switches():
    on = parse_layers("+bodies,-markers")
    assert on["bodies"] and not on["markers"] and on["streamlines"]
    exact = parse_layers("streamlines,cp")
    assert [k for k, v in exact.items() if v] == ["streamlines", "cp"]
    with pytest.raises(ValueError):
        parse_layers("+nothing")
    with pytest.raises(ValueError):
        parse_layers("streamlines,+bodies")


def test_tables():
    assert "surface" in parse_tables("all")
    assert parse_tables("elements, stagnation") == ["elements", "stagnation"]
    with pytest.raises(ValueError):
        parse_tables("pressure")


# ---------------------------------------------------------------------- running it
def test_verify_writes_the_report(tmp_path):
    from app.cli import main
    out = tmp_path / "report"
    assert main(["--verify", "--no-figures", "--out", str(out)]) == 0
    text = (out / "verification.md").read_text(encoding="utf-8")
    for heading in ("## 1. Analytic formulas", "## 2. The verification scenes", "### 2.8 ", "## 3. Accuracy"):
        assert heading in text
    assert "FAIL" not in text
    with open(out / "verification.csv", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 90 and {r["ok"] for r in rows} == {"OK"}
    assert {r["section"] for r in rows} == {"Analytic formulas", "The program's results for the scene",
                                             "Accuracy of the numerical methods"}
    assert all(float(r["error"]) < float(r["tolerance"]) for r in rows)


def test_export_figure_and_data_without_a_window(qapp, tmp_path):
    from PySide6.QtGui import QImage

    from app.cli import main
    png, data = tmp_path / "lift.png", tmp_path / "lift.csv"
    code = main([LIFTING, "--figure", str(png), "--data", str(data), "--tables", "stagnation,surface",
                 "--view", "-2", "2", "-1", "1", "--layers", "+bodies,+surface", "--width", "400", "--scale", "1"])
    assert code == 0
    img = QImage(str(png))
    assert not img.isNull() and img.width() > img.height()
    with open(tmp_path / "lift_stagnation.csv", encoding="utf-8-sig") as f:
        stag = list(csv.DictReader(f))
    s = -2.0 / (4 * np.pi)                                # sin θ = Γ/(4πV∞a)
    assert len(stag) == 2
    assert all(float(r["y [m]"]) == pytest.approx(s, abs=1e-8) for r in stag)
    assert (tmp_path / "lift_surface.csv").stat().st_size > 1000


def test_export_errors_give_exit_code_2(qapp, tmp_path, capsys):
    from app.cli import main
    assert main([LIFTING, "--figure", str(tmp_path / "x.bmp")]) == 2
    assert main([str(tmp_path / "missing.pflow"), "--figure", str(tmp_path / "x.png")]) == 2
    assert "error" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main(["--figure", str(tmp_path / "x.png")])          # no scene: argparse stops


def test_main_py_help_runs_without_a_window():
    res = subprocess.run([sys.executable, os.path.join(ROOT, "main.py"), "--help"], capture_output=True,
                         text=True, encoding="utf-8", timeout=120, cwd=ROOT)
    assert res.returncode == 0
    assert "--verify" in res.stdout and "--figure" in res.stdout
