# CLAUDE.md — handover for an AI assistant continuing this project

Read this first, then `ROADMAP.md` (history of every package + the remaining work, in order) and `README.md`
(how to run, folder table). Claude Code loads this file automatically; in claude.ai, point the assistant to it.

## The project
- **Potential Flow Lab**: an interactive 2D potential-flow simulator (Python, PySide6 + pyqtgraph, NumPy, Numba).
  Semester Project 1 of the Aerodynamics course (İYTE, Mechanical Engineering, Fall 2026). Due ≈ **26 Nov 2026**:
  program + 4–6 page report + user guide + live demo.
- The owner (Mahmut Tunay Bacaksız, 4th-year ME student) wants a tool well beyond the assignment: downloadable
  Windows exe (zip), animation, presets, undo / redo, export, verification. He is **not an experienced
  programmer**: the assistant writes the code; he pulls it with GitHub Desktop and runs it in VS Code on Windows.
- Repo: `github.com/Tunay1354/potential-flow-lab` (private), branch `main`.
- The assignment's verification cases are the scenes in `presets/1 Verification cases (assignment)/`
  (case 5 = save → reopen → same list and same plot). The assignment PDF is not in the repo — ask him for it if
  the exact wording matters.

## How to work with him (his standing preferences)
- **Reply in Turkish, but keep every technical term in English** (his department teaches in English; he does
  not know the Turkish terms). Code, comments, UI text, commit messages: English.
- "feedback ver", "kodu elleme", "programı elleme" = analyse and answer only, **do not change code**
  (throw-away analysis scripts are fine).
- One package of work = **one commit, pushed to `main`**, so any package can be reverted alone
  (GitHub Desktop → History → right click → Revert). Update `ROADMAP.md` (what was done, measured numbers) and
  `README.md` (usage, folder table) in the same commit.
- Tell him explicitly when a new pip requirement is added (`requirements.txt`), and what to do to see a change
  ("Pull, open the program, go to …").
- His screen: Windows, 1920×1080 at 125 % → **1536×864 logical pixels**: the window must fit (side panels
  are ~320 px; check widths). Theme: light "drafting paper" look, dark theme too (View → Theme).
- He likes to be shown results (screenshots of the GUI rendered offscreen, numbers) and a short list of what
  changed; long explanations of the machinery only if he asks.
- Before larger or ambiguous work, propose and let him choose; small clear fixes: just do them.

## Where things are (details: README folder table)
- `physics/` — no Qt. Elements (`elements/`), superposition (`field.py`), method of images (`images.py`),
  scene validation (`validation.py`), Numba kernels (`kernel.py`, falls back to NumPy), evenly spaced
  streamlines (`streamlines/`, Jobard–Lefer + RK4), stagnation points + dividing streamlines + where fluid
  comes from (`stagnation.py`), solid bodies map (`bodies.py`), body surfaces / Cp / pressure force
  (`surface.py`), particles (`particles.py`), checks (`verification.py`, `program_checks.py`).
- `model/` — scene model with undo / redo, `.pflow` file format (`scene_file.py`), plot settings.
- `app/` — GUI. `main_window.py` + mixins in `app/window/` (layout, menus, files, exporting, status).
  The plot is `app/canvas/canvas.py` with independent **layers** (`PlotLayer` hooks: theme, scene, view, drag…).
  `app/cli/` command line + verification report, `app/verification_dialog.py` (Help → Run verification),
  `app/errors.py` (log file, error window, crash file), `app/recovery.py` (autosave + restore after a crash).
- `presets/` scenes (folder = menu group), `assets/` fonts / icons, `packaging/` PyInstaller spec (exe: later).

## Running and testing
```
python main.py                    # GUI
python -m pytest -q               # everything (~10 min; GUI tests run offscreen, see tests/conftest.py)
python main.py --verify           # verification report → verification/ (102 checks, ~15 s)
python main.py scene.pflow --figure out.png --data out.csv   # export without a window
```
- GUI checks / screenshots without a display: `QT_QPA_PLATFORM=offscreen`, `QStandardPaths.setTestModeEnabled(True)`,
  then `widget.grab().save(...)`.
- Every change: run the full suite before committing. The verification report must stay 102 / 102 OK.

## Hard-won lessons (do not relearn them)
- Solid-body detection is subtle (ROADMAP item 14 "Kök neden 1–4"): bodies must not depend on zoom; the doublet
  open / closed decision and the scene warning share one test (`doublet_alignment`, ALIGN_TOL_DEG); thin
  channels between close bodies need the traced side test (`surface._surface_parts`). Any change there: run
  the random multi-view comparison described in ROADMAP before committing.
- φ lines across a vortex branch cut: `vortex_step` + sin contour + Newton snap (`fields`), not a plain contour.
- 125 % display scale: plot background cache caused a doubled right edge → `CacheNone` (Windows check pending).
- Background threads (QThreadPool) must never touch widgets; results come back through signals and errors are
  re-raised in the GUI thread (then `app/errors.py` reports them).
- The GUI exe will have **no console** (`console=False`): never rely on print; use the `pflab` logger.
- At a triple zero of w (source in a 90° walled corner) the stagnation point is only defined to ~5e-6.

## Current status (keep this section up to date)
- Done up to ROADMAP item 19 (the beaver `app/beaver/`: pixel art, speech bubble, behaviour in Static /
  Particles / Pulses, click menu, P = questions & answers, first-start tour with actions), 29 Oct 2026.
  First start: `python main.py --first-run` or Help → Beaver → Next start as a first-time user.
- Beaver leftovers: the name "Psi" is a placeholder (he will rename it); he finds the side / swimming poses
  still a bit odd (shapes in `app/beaver/art.py`). All beaver text is English (`lines.py`, `faq.py`, `tour.py`).
- **Next: item 20 — optimization.**
- Then: 20 optimization (+ E2), 21 code cleanup, 22 text / visual review with him, 23 exhaustive random-scene and
  GUI test, 24 exe (deliberately last; fallback: source zip + install notes, or demo from his laptop),
  25 report + user guide, 26 final check against the assignment, 27 demo rehearsal.
  On hold ("maybe"): dye rake, Joukowski airfoil.
- Open questions for him: dividing-streamline color, element colors (in item 22); confirm on Windows that the
  doubled line at 125 % is gone and that Help → Run verification works.
