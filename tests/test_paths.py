"""paths.py: the program's data folder, and paths as the browser / Explorer see them (Microsoft Store Python
keeps what it writes under %LOCALAPPDATA% in its own package folder: "Open log folder" / "Open full report"
opened a folder that only the program itself could see)."""
import os

from app import paths

STORE = r"C:\Program Files\WindowsApps\PythonSoftwareFoundation.Python.3.13_3.13.2032.0_x64__qbz5n2kfra8p0"


def _windows(monkeypatch, tmp_path, base_prefix):
    local = tmp_path / "Local"
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setattr(paths.sys, "base_prefix", base_prefix)
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    return local


def test_store_python_paths_are_mapped_to_its_package_folder(monkeypatch, tmp_path):
    local = _windows(monkeypatch, tmp_path, STORE)
    real = local / "Packages" / "PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0" / "LocalCache" / "Local" \
        / "IZTECH" / "Flowy" / "logs"
    real.mkdir(parents=True)
    seen = str(local / "IZTECH" / "Flowy" / "logs")
    assert paths.outside_path(seen) == str(real)


def test_other_pythons_and_other_folders_keep_their_path(monkeypatch, tmp_path):
    local = _windows(monkeypatch, tmp_path, r"C:\Users\me\AppData\Local\Programs\Python\Python313")
    (local / "Packages" / "PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0" / "LocalCache" / "Local" / "x") \
        .mkdir(parents=True)
    assert paths.outside_path(str(local / "x")) == str(local / "x")              # python.org Python
    monkeypatch.setattr(paths.sys, "base_prefix", STORE)
    assert paths.outside_path(str(local / "missing")) == str(local / "missing")  # nothing there: unchanged
    assert paths.outside_path(str(tmp_path / "elsewhere")) == str(tmp_path / "elsewhere")


def test_not_windows_is_unchanged(monkeypatch, tmp_path):
    monkeypatch.setattr(paths.sys, "platform", "linux")
    assert paths.outside_path(str(tmp_path)) == str(tmp_path)


def test_data_folder_is_the_program_folder():
    assert os.path.basename(paths.data_folder("logs")) == "logs"
    assert paths.data_folder("a", "b").endswith(os.path.join("a", "b"))
