# CLAUDE.md — handover for an AI assistant continuing this project

You are taking over a project that another assistant has been building **with** the owner since 24 Oct 2026.
Read this whole file first. Then `ROADMAP.md` (Turkish; every package that was done, with measured numbers,
and the remaining work in order) and `README.md` (Turkish; how to run, every feature, folder table).
Claude Code loads this file automatically; in claude.ai, the owner will point you to it.

---------------------------------------------------------------------------------------------------------------
## 1. The project in one paragraph

**Potential Flow Lab** — an interactive 2D potential-flow simulator in Python (PySide6 + pyqtgraph, NumPy,
Numba, contourpy). It is Semester Project 1 of the **Aerodynamics** course (İzmir Institute of Technology, ME,
Fall 2026). Due **≈ 26 Nov 2026**: the program + a 4–6 page report + a user guide + a live demo. The assignment
asks for superposition of elementary flows with a GUI, streamlines, and verification cases; the owner wants
far more: a polished, downloadable Windows tool (exe in a zip), animation, presets, undo / redo, export,
built-in verification, a mascot. Repo: `github.com/Tunay1354/potential-flow-lab` (private), branch `main`,
~75 commits. The assignment's verification cases are the scenes in `presets/1 Verification cases
(assignment)/` (case 5 = save → reopen → same list and same plot). The assignment PDF is **not** in the repo —
ask him for it when exact wording matters (e.g. for the report or the final check).

---------------------------------------------------------------------------------------------------------------
## 2. The owner and how to work with him

- **Mahmut Tunay Bacaksız**, 4th-year ME student. **Not an experienced programmer**: you write all code; he
  pulls with **GitHub Desktop** and runs it in **VS Code** on **Windows** (venv in `.venv`, `python main.py`).
- **Language**: reply in **Turkish**, but keep **every technical term in English** (his department teaches in
  English; he doesn't know the Turkish terms). Code, comments, UI text, commit messages, the beaver's lines:
  **English**. He writes quickly, informally, with typos — read for intent.
- **"feedback ver" / "kodu elleme" / "programı elleme"** = analyse, explain, propose — **do not change code**.
  Throw-away analysis / mock-up scripts in a scratch folder are fine (he liked seeing mock-ups and GIFs first).
- **One package of work = one commit, pushed to `main`**, so each package can be reverted alone (GitHub
  Desktop → History → right click → Revert). In the same commit update `ROADMAP.md` (what was done, numbers),
  `README.md` (usage, folder table) and the **Current status** section of this file.
- Tell him explicitly: what changed, **how to see it** ("Pull, open the program, click …"), and whether a
  **new pip package** is needed (then: `pip install -r requirements-dev.txt`). Short bullet lists, then a
  natural next step. He likes screenshots / short videos of the GUI (rendered offscreen, see §6).
- **Big or ambiguous work: propose options first and let him choose** (he often answers "do all of it").
  Small, clear fixes: just do them. When he asks "what's left?", give the ordered list from ROADMAP.
- He tests on his own PC and sends screenshots of problems. Things only verified offscreen should be named as
  such ("I couldn't test this on Windows").
- His screen: 1920×1080 at **125 %** → **1536 × 864 logical px**. The window must fit; side panels ~320 px.
  Light "drafting paper" theme by default, dark theme too.
- Git hiccup seen once: GitHub Desktop "Can't find potential-flow-lab" (folder moved) → Locate… or Clone Again;
  after a fresh clone the venv must be rebuilt (`python -m venv .venv`, activate, `pip install -r
  requirements-dev.txt`).
- Decisions he made: the exe is built **last** (fallback: source zip + install notes, or demo from his laptop);
  dye rake and Joukowski airfoil are "maybe"; the beaver speaks **English**; the beaver's name "Psi" is a
  placeholder.

---------------------------------------------------------------------------------------------------------------
## 3. Running, testing, checking

```
python main.py                     # GUI (python main.py scene.pflow opens a scene)
python main.py --first-run         # start as a first-time user (the beaver offers the tour)
python -m pytest -q                # all tests, ~10 min; GUI tests run offscreen (tests/conftest.py)
python main.py --verify            # verification report → verification/ (102 checks, must stay 102 / 102)
python main.py scene.pflow --figure out.png --data out.csv     # export without a window
python scripts/streamline_quality.py   /   python scripts/smoothness.py    # measurements
```
- **Before every commit: full test suite green and verification 102 / 102.**
- Tests write to Qt's test folders (`QStandardPaths.setTestModeEnabled(True)`) and set
  `beaver/tour_offered = True` (no first-start question during tests) — keep that in `tests/conftest.py`.
- Requirements: `requirements.txt` (PySide6, pyqtgraph, numpy, contourpy, numba, pillow, imageio-ffmpeg),
  `requirements-dev.txt` (+ pytest, pyinstaller). Python 3.13 here; he has a recent 3.x on Windows.

---------------------------------------------------------------------------------------------------------------
## 4. Where things are (details: README folder table)

- `physics/` — **no Qt**. Elements (`elements/`: uniform, source/sink, vortex, doublet, sector flow, symmetry
  wall), superposition (`field.py`), method of images incl. corners π/k and channels in closed form
  (`images.py`), scene validation → errors / warnings / notes (`validation.py`), Numba kernels with NumPy
  fallback (`kernel.py`, `warmup.py`), evenly spaced streamlines (`streamlines/`: Jobard–Lefer + RK4, pan
  cache), stagnation points (Newton) + dividing streamlines + where fluid comes from (`stagnation.py`), solid
  bodies map (`bodies.py`), body surfaces / Cp / pressure force / Kutta–Joukowski (`surface.py`), particles and
  pulse travel times (`particles.py`), verification (`verification.py` analytic, `program_checks.py` the
  program's own numerical results; every check has a `how` text).
- `model/` — scene model with undo / redo (`scene_model.py`), `.pflow` JSON format (`scene_file.py`), plot
  settings saved with a scene (`plot_settings.py`).
- `app/` — GUI. `main_window.py` + mixins in `app/window/` (layout/docks, menus + shortcuts, files, exporting,
  status bar + scene check popup `issues_popup.py`). The plot: `app/canvas/canvas.py` (`PlotCanvas`) with
  independent **layers** (`PlotLayer` hooks: theme, scene, view, drag …): streamlines, stagnation, field maps
  (φ, |V|, Cp), elements, particles / pulses animation, solid bodies, surface pressure.
  Also: `surface_panel.py`, `export/` (figure PNG/SVG/PDF, data CSV, animation GIF/MP4), `cli/` (command line
  + verification report HTML/MD/CSV), `verification_dialog.py` (Help → Run verification, with "how it is
  computed" per check), `errors.py` (log file, error window, crash file), `recovery.py` (autosave + restore after
  a crash), `beaver/` (the mascot, §5), `chrome/` (header, cards, palette, fonts), `theme.py` (all colours and
  sizes).
- `presets/` scenes (folder = menu group), `assets/` (fonts incl. Pixelify Sans for the beaver, icons),
  `packaging/` PyInstaller spec (exe: later), `scripts/` measurements, `tests/` (~32 files).

---------------------------------------------------------------------------------------------------------------
## 5. What has been built (short history; details in ROADMAP)

- **24–26 Oct** — physics core (4 elementary flows, walls with images, sector flow), evenly spaced
  streamlines, scene model with undo / redo, File menu + presets, Numba speed-up (≈ 60 fps pan),
  stagnation points + dividing streamlines, the drafting-paper theme, dockable panels, plot mouse modes
  (Select / Move / Pan) + changeable shortcuts, export (figure + CSV), field layers (φ, |V|, Cp).
- **27 Oct** — code restructured into `app/canvas` layers (pixel-identical before / after), more speed,
  animation (Particles, Pulses), Solid bodies layer, GIF / MP4 export, many user fixes.
- **28 Oct** — Solid bodies made zoom-independent (4 root causes, see §7), Surface pressure (Cp on bodies and
  walls, panel with lift / drag vs Kutta–Joukowski), command line + `--verify` report, Help → Run
  verification, clickable scene check in the status bar, error log + error window, autosave / recovery,
  CLAUDE.md, the beaver stage 1 (pixel art, behaviour on the plot).
- **29 Oct** — the beaver stage 2: click = menu / drag = carry, **P = questions & answers**, first-start
  **tour** that makes the user add a uniform flow and a doublet, edit, move, animate; ends on an empty plot.

**The beaver (`app/beaver/`)** — a pixel-art beaver with a red bandana, drawn by code from shapes (`art.py`, so
every rotation / size is crisp), speech bubble with a pixel font typed letter by letter (`bubble.py`, dialogs
with choices), English lines (`lines.py`, 40+ situations, ~180 lines, random without quick repeats; PRIORITY
decides what may wait vs be skipped so no line is cut off), Q&A (`faq.py`), tour (`tour.py`, 16 steps,
`spotlight.py` highlight). Behaviour (`beaver.py`): sits on the ruler right of Help; Static mode = glass in
front of the plot (screen-fixed); Particles = a tracer in the real flow (data-fixed; dizzy in a free vortex,
swallowed by a sink, stuck at a stagnation point, bored if very slow); Pulses = knocked along his streamline
by each pulse (runs off if pulses are very slow); goes home by hopping to the ruler and walking. Never in
exports; only his own pixels take clicks; wheel passes to the plot; View → Beaver turns him off.

---------------------------------------------------------------------------------------------------------------
## 6. How to look at the GUI yourself (offscreen)

```python
import os; os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QStandardPaths; QStandardPaths.setTestModeEnabled(True)
from PySide6.QtWidgets import QApplication
app = QApplication([])
from app.main_window import MainWindow, setup_application
setup_application(app)
w = MainWindow(); w.setFixedSize(1536, 830); w.show()      # his logical screen size
# … processEvents for ~1.5 s, drive the beaver with w.beaver.advance(dt), the animation with
# w.canvas.animation.advance(dt) …
w.grab().save("shot.png")
```
Frames grabbed this way can be turned into an MP4 with `imageio_ffmpeg.get_ffmpeg_exe()` to show him motion.

---------------------------------------------------------------------------------------------------------------
## 7. Problems we hit and how they were solved (do not relearn these)

Physics / numerics
- **Solid bodies depended on zoom** (ROADMAP 14d–14e, "Kök neden 1–4"): (1) a weak source's stagnation point
  is very close (m/2πU) → Newton seeds also at each element's own scale; (2) the doublet open / closed decision
  and the scene warning must be the **same test** (`doublet_alignment`, ALIGN_TOL_DEG = 0.5°); (3) leak tails of
  nearly closed doublets → a body whose fluid goes far is not a body, inner branches act as barriers, slivers
  absorbed; (4) small half-body surface branches lost inside the tracer's singular radius → finer tracer near
  singular points. Rule (`open_elements`): a source / doublet the free stream passes THROUGH makes no body.
  **Any change there: run the random multi-view comparison against a reference map (ROADMAP 14e) first.**
- **Two very close half-bodies merged** in Surface pressure → traced side test only where the grid shows two
  body regions (`surface._surface_parts`), regions never joined directly.
- **φ lines across a vortex branch cut** had a gap → Δφ chosen so 2Γ is a multiple, lines drawn as zeros of
  sin(πφ/Δφ), each point Newton-snapped (`vortex_step`, `fields`).
- **ZeroDivisionError at a corner of two walls** (velocity exactly 0) → `kernel._direction` returns NaN.
- **Stagnation point in a 90° walled corner** is a *triple* zero of w (w ∝ z³) → position only defined to
  (1e-16)^(1/3) ≈ 5e-6; verification tolerance 1e-5 for that reason. ψ constancy along drawn lines: 0.2–0.3 % of
  the line spacing, tolerance 1 %.

GUI / Qt
- View jumping ~40×/s at some window sizes (axis label width ↔ aspect lock) → axis text space only grows.
- 125 % display scale: a doubled dark line at the plot's right edge → plot background cache off (`CacheNone`).
- Plot settings panel overflowing when a note made a label long → notes on their own line.
- Surface panel: graph jumped on hover, ring jumped between curves → fixed ranges, nearest point on screen.
- Particle trails stayed on an empty page (last steps redrawn every frame) → no step without flow + clear.
- **Exceptions in Qt slots / paint events** go to `sys.excepthook` → `app/errors.py` logs them and shows one
  window per distinct error (no floods). Background threads (QThreadPool) never touch widgets; results and
  errors come back through signals.
- **The exe has no console**: `sys.stderr` is None there → never rely on `print`; use the `pflab` logger.
- Recovery after a crash: each session holds a `QLockFile`; a copy whose owner is gone = a crashed session.
- **Space / Esc are window shortcuts** → in the beaver's tour / dialogs they are taken via `ShortcutOverride`
  (not while a text field or a modal dialog has the keys).
- Beaver: a press is a click until the mouse moves > 6 px; the sprite has a mask (clicks through transparent
  pixels); rotated pixel art is re-rasterized from shapes (never rotate the bitmap).
- Windows-specific checks still pending (he hasn't confirmed): the 125 % double line is gone, Help → Run
  verification, the beaver's feel (speed, drag), the tour from start to end.

---------------------------------------------------------------------------------------------------------------
## 8. Current status and what comes next (keep this section up to date)

- **Done**: ROADMAP items 1–19 (everything above), 29 Oct 2026. Tests green, verification 102 / 102.
- **29 Oct, handover check (19b)** by the assistant in the owner's second account: clean install, all tests,
  `--verify` and an independent physics comparison passed; `test_kernel.py` made pytest-9 compatible (pytest ≥ 9
  refuses nested lists in `approx()`; compare arrays instead). This machine has 2 cores: the full suite takes
  ~50 min here (run it in the background). Also: the Elements list no longer cuts names / parameters off
  (`app/panels.py`, `ElementRowDelegate`: parameters in the old 150 px column, wrapped between parameters;
  under the name when the name is too long). Column 1 still holds `e.summary()` (hidden), tests read it.
- **Next: item 20 — optimization (+ E2)**: measure first, then improve: start-up and first Numba compile,
  dragging, zoom / pan, animation (maybe an "Use graphics card (OpenGL)" option with a fallback), Solid bodies,
  Surface pressure, export times; scripts in `scripts/`, before / after numbers in ROADMAP.
- Then, in this order (all planned, "as if time were unlimited"):
  21 code cleanup without behaviour change (dead / duplicate code, names, docstrings, pyflakes, long files) →
  22 text and visual review **with him** (every UI string in one list + screenshot gallery; he marks what to
  change; open decisions: dividing-streamline colour, element colours, icons, the beaver's name and his side /
  swimming poses, which he finds a bit odd) →
  23 exhaustive random test with the final code (hundreds–thousands of random scenes in several views:
  no exceptions, V = 0 at stagnation points, ψ constant along lines, no crossing lines, zoom-independent bodies,
  forces vs Kutta–Joukowski / d'Alembert, save → reopen, exports, particles stay in the fluid; plus random GUI
  actions incl. undo / redo and recovery; every bug found becomes a permanent test) →
  24 packaging (Windows exe in a zip, version 1.0, GitHub Releases, Inno Setup, Numba cache, .pflow file
  association, test on a PC without Python; note for the zip: Windows SmartScreen "More info → Run anyway") →
  25 report (4–6 pages; figures and tables from `--verify`) + user guide (Help → User guide, F1 is a placeholder
  today) → 26 final check against the assignment text, item by item → 27 demo rehearsal.
- **Maybe** (not dropped): dye rake (streaklines), Joukowski airfoil (conformal mapping, Kutta condition).
- Suggestions he did not take yet: GitHub Actions (Windows tests + automatic exe), test on another PC, macOS.
