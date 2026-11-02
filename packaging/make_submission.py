"""
make_submission.py — the two zips handed in for the assignment (ROADMAP 24.3). GitHub's Windows build
(.github/workflows/windows-build.yml) calls it after the exe and the installer are built and checked:

    python packaging/make_submission.py --program dist/Flowy --setup Flowy-v1.0.0-setup.exe \
        --verify exe-check/verify --name Flowy-v1.0.0 --out submission-out

and puts <name>-portable.zip and <name>-setup.zip on the Releases page. Both hold one folder (FOLDER):

    1_Report.pdf, 2_User_Guide.pdf     from submission/ (placeholders until the real ones replace them)
    3_Program/                         portable: the exe folder as "<APP_NAME> <APP_VERSION>/" · setup: the installer
    4_Source_Code/                     the program's files from the repository (SOURCE: what it needs to run and its
                                       tests, one requirements.txt) — not the development notes, build files, scripts
    5_Verification/                    the report of `--verify` made by the built exe: verification.html (figures
                                       inside), figures/, and other_formats_optional/ (the .md and the .csv)
    README.txt                         submission/README.txt with the names and the program part filled in
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import app_info  # noqa: E402

SUBMISSION = ROOT / "submission"
FOLDER = "ME470_Project1_300203046_Bacaksiz"           # the one folder inside each zip
DOCS = ("1_Report.pdf", "2_User_Guide.pdf")
PLACEHOLDER = b"PLACEHOLDER"                             # in the placeholder PDFs' title (see ROADMAP 24.3)
SOURCE = ("app/", "physics/", "model/", "presets/", "assets/", "tests/", "main.py", "app_info.py",
          "requirements.txt", "pyproject.toml")          # pyproject.toml: pytest's settings
SOURCE_SKIP = ("tests/test_submission.py",)              # tests this script (not in the zip)
OTHER_FORMATS = "other_formats_optional"                 # the .md and .csv of the verification report

PROGRAM = {
    "portable": (
        "{folder}\\  the program, ready to run (no installation)",
        "  1. Extract this zip first (right-click -> Extract All...): the program does not run from inside a zip.\n"
        "  2. Open 3_Program\\{folder} and double-click {app}.exe.\n"
        "     If Windows says \"Windows protected your PC\": More info -> Run anyway (the program is not signed)."),
    "setup": (
        "{setup}  the installer",
        "  1. Extract this zip first (right-click -> Extract All...).\n"
        "  2. Double-click 3_Program\\{setup}.\n"
        "     If Windows says \"Windows protected your PC\": More info -> Run anyway (the program is not signed).\n"
        "  3. Choose the language, for whom, the folder and the options, then Install and Finish.\n"
        "     Start it from the Start menu or the desktop. Uninstall: Settings -> Apps -> Installed apps -> {app}."),
}


def source_files() -> list[str]:
    """The program's files that git tracks (never caches, builds or files kept out of the repository)."""
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True).stdout
    names = [n for n in out.decode("utf-8").split("\0") if n]
    return [n for n in names if (n in SOURCE or n.startswith(tuple(s for s in SOURCE if s.endswith("/"))))
            and n not in SOURCE_SKIP]


def program_folder() -> str:
    return f"{app_info.APP_NAME} {app_info.APP_VERSION}"


def readme(kind: str, setup_name: str) -> str:
    line, steps = (s.format(app=app_info.APP_NAME, setup=setup_name, folder=program_folder()) for s in PROGRAM[kind])
    text = (SUBMISSION / "README.txt").read_text(encoding="utf-8")
    text = text.format(app=app_info.APP_NAME, version=app_info.APP_VERSION, program_line=line,
                       program_steps=steps)
    return text.replace("\n", "\r\n")                    # Notepad-friendly


def placeholders() -> list[str]:
    return [d for d in DOCS if PLACEHOLDER in (SUBMISSION / d).read_bytes()]


def _add_tree(z: zipfile.ZipFile, src: Path, dest: str) -> None:
    for p in sorted(src.rglob("*")):
        if p.is_file():
            z.write(p, f"{dest}/{p.relative_to(src).as_posix()}")


def _add_verification(z: zipfile.ZipFile, src: Path, dest: str) -> None:
    """verification.html and figures/ on top; the same tables as .md / .csv one folder down (optional)."""
    z.write(src / "verification.html", f"{dest}/verification.html")
    _add_tree(z, src / "figures", f"{dest}/figures")
    md = (src / "verification.md").read_text(encoding="utf-8").replace("](figures/", "](../figures/")
    z.writestr(f"{dest}/{OTHER_FORMATS}/verification.md", md)
    z.write(src / "verification.csv", f"{dest}/{OTHER_FORMATS}/verification.csv")


def build(kind: str, program: Path, setup: Path, verify: Path, path: Path) -> Path:
    top = FOLDER
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for d in DOCS:
            z.write(SUBMISSION / d, f"{top}/{d}")
        if kind == "portable":
            _add_tree(z, program, f"{top}/3_Program/{program_folder()}")
        else:
            z.write(setup, f"{top}/3_Program/{setup.name}")
        for name in source_files():
            z.write(ROOT / name, f"{top}/4_Source_Code/{name}")
        _add_verification(z, verify, f"{top}/5_Verification")
        z.writestr(f"{top}/README.txt", readme(kind, setup.name))
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--program", type=Path, required=True, help="the exe folder (dist/<APP_NAME>)")
    ap.add_argument("--setup", type=Path, required=True, help="the installer (…-setup.exe)")
    ap.add_argument("--verify", type=Path, required=True, help="the output folder of --verify")
    ap.add_argument("--name", required=True, help="the zips' name before -portable.zip / -setup.zip")
    ap.add_argument("--out", type=Path, default=Path("."))
    a = ap.parse_args(argv)
    for p in (a.program / f"{app_info.APP_NAME}.exe", a.setup,
              *(a.verify / f"verification.{ext}" for ext in ("html", "md", "csv")),
              *(SUBMISSION / d for d in DOCS)):
        if not p.is_file():
            ap.error(f"missing: {p}")
    a.out.mkdir(parents=True, exist_ok=True)
    for kind in PROGRAM:
        path = build(kind, a.program, a.setup, a.verify, a.out / f"{a.name}-{kind}.zip")
        print(f"{path.name}: {path.stat().st_size / 1e6:.1f} MB")
    for d in placeholders():
        print(f"::warning::{d} is still the placeholder (submission/{d})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
