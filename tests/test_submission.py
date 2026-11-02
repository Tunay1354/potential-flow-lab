"""The zips handed in for the assignment (packaging/make_submission.py, ROADMAP 24.3)."""
import importlib.util
import zipfile
from pathlib import Path

import app_info

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("make_submission", ROOT / "packaging" / "make_submission.py")
ms = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ms)


def _inputs(tmp_path):
    program = tmp_path / "dist" / app_info.APP_NAME
    (program / "_internal").mkdir(parents=True)
    (program / f"{app_info.APP_NAME}.exe").write_bytes(b"exe")
    (program / "_internal" / "lib.dll").write_bytes(b"dll")
    setup = tmp_path / f"{app_info.APP_NAME}-v{app_info.APP_VERSION}-setup.exe"
    setup.write_bytes(b"setup")
    verify = tmp_path / "verify"
    (verify / "figures").mkdir(parents=True)
    (verify / "verification.html").write_text("<html></html>")
    (verify / "verification.md").write_text("![a](figures/a.png)")
    (verify / "verification.csv").write_text("a,b")
    (verify / "figures" / "a.png").write_bytes(b"png")
    return program, setup, verify


def test_both_zips(tmp_path):
    program, setup, verify = _inputs(tmp_path)
    out = tmp_path / "out"
    assert ms.main(["--program", str(program), "--setup", str(setup), "--verify", str(verify),
                    "--name", "X", "--out", str(out)]) == 0
    top = ms.FOLDER
    for kind in ("portable", "setup"):
        names = set(zipfile.ZipFile(out / f"X-{kind}.zip").namelist())
        assert all(n.startswith(top + "/") for n in names)                 # one folder inside
        for d in ms.DOCS:
            assert f"{top}/{d}" in names
        assert f"{top}/5_Verification/verification.html" in names
        assert f"{top}/5_Verification/figures/a.png" in names
        other = f"{top}/5_Verification/{ms.OTHER_FORMATS}"
        assert {f"{other}/verification.md", f"{other}/verification.csv"} <= names
        md = zipfile.ZipFile(out / f"X-{kind}.zip").read(f"{other}/verification.md").decode("utf-8")
        assert "](../figures/a.png)" in md                                 # its pictures one folder up
        src = f"{top}/4_Source_Code/"
        for f in ("main.py", "app_info.py", "requirements.txt", "physics/field.py", "tests/conftest.py"):
            assert src + f in names, f
        tops = {n[len(src):].split("/")[0] for n in names if n.startswith(src)}
        assert tops == {"app", "physics", "model", "presets", "assets", "tests", "main.py", "app_info.py",
                        "requirements.txt", "pyproject.toml"}             # no notes, build files, scripts
        assert src + "tests/test_submission.py" not in names
        assert not any("__pycache__" in n or "/.venv/" in n for n in names)
        readme = zipfile.ZipFile(out / f"X-{kind}.zip").read(f"{top}/README.txt").decode("utf-8")
        assert "{" not in readme and app_info.APP_VERSION in readme
        program_files = {n for n in names if n.startswith(f"{top}/3_Program/")}
        if kind == "portable":
            folder = f"{top}/3_Program/{app_info.APP_NAME} {app_info.APP_VERSION}"
            assert program_files == {f"{folder}/{app_info.APP_NAME}.exe", f"{folder}/_internal/lib.dll"}
        else:
            assert program_files == {f"{top}/3_Program/{setup.name}"}
            assert setup.name in readme


def test_missing_input(tmp_path, capsys):
    program, setup, verify = _inputs(tmp_path)
    (verify / "verification.html").unlink()
    try:
        ms.main(["--program", str(program), "--setup", str(setup), "--verify", str(verify), "--name", "X"])
    except SystemExit as e:
        assert e.code != 0
    else:
        raise AssertionError("a missing verification report must stop it")
    assert "verification.html" in capsys.readouterr().err


def test_placeholder_marker(tmp_path, monkeypatch):
    for d, body in zip(ms.DOCS, (b"%PDF real", b"%PDF " + ms.PLACEHOLDER)):
        (tmp_path / d).write_bytes(body)
    monkeypatch.setattr(ms, "SUBMISSION", tmp_path)
    assert ms.placeholders() == [ms.DOCS[1]]
