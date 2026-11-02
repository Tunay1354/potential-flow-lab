# CLAUDE.md — handover for an AI assistant continuing this project

You are taking over a project that another assistant has been building **with** the owner since 24 Oct 2026.
Read this whole file first. Then `ROADMAP.md` (Turkish; every package that was done, with measured numbers,
and the remaining work in order) and `README.md` (Turkish; how to run, every feature, folder table).
Claude Code loads this file automatically; in claude.ai, the owner will point you to it.

---------------------------------------------------------------------------------------------------------------
## 1. The project in one paragraph

**Flowy** (formerly Potential Flow Lab) — an interactive 2D potential-flow simulator in Python (PySide6 + pyqtgraph, NumPy,
Numba, contourpy). It is Semester Project 1 of the **Aerodynamics** course (İzmir Institute of Technology, ME,
Fall 2026). Due **≈ 26 Nov 2026**: the program + a 4–6 page report + a user guide + a live demo. The assignment
asks for superposition of elementary flows with a GUI, streamlines, and verification cases; the owner wants
far more: a polished, downloadable Windows tool (exe in a zip), animation, presets, undo / redo, export,
built-in verification, a mascot. Repo: `github.com/Tunay1354/potential-flow-lab` (private), branch `main`,
~110 commits. The assignment's verification cases are the scenes in `presets/1 Verification cases
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
  placeholder (`app_info.MASCOT_NAME`: change it there only).

---------------------------------------------------------------------------------------------------------------
## 3. Running, testing, checking

```
python main.py                     # GUI (python main.py scene.pflow opens a scene)
python main.py --first-run         # start as a first-time user (the beaver offers the tour)
python -m pytest -q                # all tests (~50 min on this 2-core server: run in the background); offscreen GUI
python main.py --verify            # verification report → verification/ (102 checks, must stay 102 / 102)
python main.py scene.pflow --figure out.png --data out.csv     # export without a window
python scripts/benchmark.py --full --out benchmarks/NAME.json             # speed of everything (he runs it on Windows)
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
  cache), stagnation points (Newton) + dividing streamlines (`stagnation.py`), where fluid comes from = what a body is (`origin.py`), solid
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
- `app_info.py` (root) — the program's name / subtitle / version, the beaver's name (`MASCOT_NAME`) and the logger
  name (`LOGGER`): the ONLY place to rename them (window, files, reports, exe, settings folder …/IZTECH/<APP_NAME>).
  Never write a name as text elsewhere.
- `presets/` scenes (folder = menu group), `assets/` (fonts, icons), `packaging/build_exe.spec` (exe),
  `scripts/` measurements, `benchmarks/` (his last full measurement), `tests/`.

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
every rotation / size is crisp), speech bubble typed letter by letter (`bubble.py`: "drafting card" look since 29 Oct —
thick ink frame, stepped corners, shadow, header name + tag, IBM Plex Mono text, buttons with the main one in the
plank colour; dialogs with choices / buttons), English lines (`lines.py`, 80 situations, ~570 lines, {name} = his name, random without quick repeats; PRIORITY
decides what may wait vs be skipped so no line is cut off), Q&A (`faq.py`), tour (`tour.py`, 19 steps,
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
from app.main_window import MainWindow
from app.startup import setup_application
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
- **ZeroDivisionError in Newton** when a seed lands exactly on a singular point (free vortex centre, view symmetric about it) → `kernel._at_singularity` makes that seed NaN.
- **ZeroDivisionError at a corner of two walls** (velocity exactly 0) → `kernel._direction` returns NaN.
- **Minutes per picture with 3 walls at random angles** (found by `scripts/random_test.py`): walls that do not tile
  the plane multiply the images at every level (185 364 after 16) → `images.MAX_IMAGES` (600, now 200); the rest of the time
  was ψ summed element by element in Python → `batch_complex_potential` per type, like the velocity (`field._group_sum`).
- **A lifting cylinder boxed in by 4 walls: ~1–4 fps, zoom froze** (he found it): a rectangle went through the
  generic image BFS (1088 images, capped). Now `images._channel` = channel + 0 / 1 / 2 walls across: rows in closed
  form, mirrored in a wall across, repeated every 2L with `PeriodicRow.shift / count` (a few copies; kernel
  `_cot_sums`, one exp for all copies); Σm = 0 required in a closed box. Large arrays (field grids, φ lines) are
  summed by the kernel (`field._summer`, `kernel.potential_many`). Generic MAX_IMAGES = 200.
- **Closed channel zoomed out: no stagnation points at 10×, 8 false ones at 100×** (his first random-test run):
  the flow dies out like e^(−πx/H), the view's median speed → 0. Speed scale = max(median, 1e-6 × `_scene_speed`)
  and `_above_noise` (NOISE_FLOOR = 1e-12) in `stagnation.py`. Random-test checks use the same scene floor.
- **Stagnation point in a 90° walled corner** is a *triple* zero of w (w ∝ z³) → position only defined to
  (1e-16)^(1/3) ≈ 5e-6; verification tolerance 1e-5 for that reason. ψ constancy along drawn lines: 0.2–0.3 % of
  the line spacing, tolerance 1 %.

GUI / Qt
- View jumping ~40×/s at some window sizes (axis label width ↔ aspect lock) → axis text space only grows.
- 125 % display scale: a doubled dark line at the plot's right edge → plot background cache off (`CacheNone`).
  With the GPU the same line came back (an OpenGL frame keeps nothing) → `PlotView.drawBackground` fills it all.
- Plot settings panel overflowing when a note made a label long → notes on their own line.
- Surface panel: graph jumped on hover, ring jumped between curves → fixed ranges, nearest point on screen.
- **Animation slow with several layers (23 fps, 26–29 ms per frame)**: the items cached as pictures while
  animating (DeviceCoordinateCache) live in QPixmapCache, default limit 10 MB — plot-sized pictures did not fit,
  so every frame redrew everything. `canvas.ensure_pixmap_cache()` raises the limit when animating (frame 4–5 ms).
- **Stale streamlines after a drag in Pulses** (pieces of the old position stayed): a cached item picture was not
  refreshed by Qt on new data → `layer.drop_picture` on sigPlotChanged / sigImageChanged (cache off and on).
- **Pulses 27 fps at a 144 fps cap (61 at 60)**: the timer drew frames faster than the window could show them →
  `AnimatedLayer.frame` skips a tick while `TrailItem.shown` is False (≤ 6 ticks).
- **GPU animation picture 1.25× too large / shifted at 125 %**: QPainter.combinedTransform() on the GL viewport
  already contains the screen scale → map the corners with `plot.viewportTransform()` (logical px) instead.
  Test GL things also with QT_SCALE_FACTOR=1.25 on Xvfb.
- **Thick lines far zoomed in with the GPU**: Qt's GL paint engine limits the inverse scale of cosmetic pens (> ~1e4 px per item unit) → items keep view-sized local coordinates (`ScaledCurve`, `PaperGridItem`). Any new line item on the plot: use ScaledCurve, not pg.PlotCurveItem.
- **Lines cut off far zoomed out**: one stagnation-speed threshold for all cache levels → per level.
- **Fans at full speed / no lines at far zoom (1 Nov)**: probes round stagnation points traced with a tiny step across
  3× a huge view (18–66 s) → `_probe_region`; far in, Solid bodies traced across the whole body box with the view's
  step and sampled 11 M barrier points in the GUI thread → `_trace_staged`, `_clip_segments`. Wheel at a zoom limit slid
  the view (pyqtgraph cuts round the asked range's middle) → own clamp in `PlotViewBox.scaleBy`. Old-level jobs
  were never cancelled → level-based cancel in `StreamlineLayer`.
- Particle trails stayed on an empty page (last steps redrawn every frame) → no step without flow + clear.
- **Pulses + zoom far + Fit crashed** (1 Nov, also without GPU): the drawn lines still belonged to the old view and
  were cut into pieces of the new view's 2 px → hundreds of millions → `pulse_layer`: only lines near the view, at
  most MAX_PIECES. Anything cut / sampled "per pixel" must be bounded by the view, never by the scene / old lines.
- **Exceptions in Qt slots / paint events** go to `sys.excepthook` → `app/errors.py` logs them and shows one
  window per distinct error (no floods). Background threads (QThreadPool) never touch widgets; results and
  errors come back through signals.
- **The exe has no console**: `sys.stderr` is None there → never rely on `print`; use the program's logger (`logging.getLogger(app_info.LOGGER)`).
- **Microsoft Store Python** redirects files under %LOCALAPPDATA% into its package folder: anything opened in
  the browser / Explorer goes through `paths.outside_path`.
- Recovery after a crash: each session holds a `QLockFile`; a copy whose owner is gone = a crashed session.
  The same for the crash file (`errors`, crash-<pid>.txt) and the GPU guard (`gpu.SessionGuard`).
- **Space / Esc are window shortcuts** → in the beaver's tour / dialogs they are taken via `ShortcutOverride`
  (not while a text field or a modal dialog has the keys).
- Beaver: a press is a click until the mouse moves > 6 px; the sprite has a mask (clicks through transparent
  pixels); rotated pixel art is re-rasterized from shapes (never rotate the bitmap).

---------------------------------------------------------------------------------------------------------------
## 8. Current status and what comes next (keep this section up to date)

- **Done: ROADMAP 1–21** (2 Nov 2026). Tests green, verification 102 / 102. The full history with measured numbers is
  in ROADMAP (Turkish); this section keeps only what the next session needs.
- **Item 21 = cleanup in 13 packages** (one commit each, ROADMAP 21.1–21.13; he tested between them). Behaviour
  unchanged — checked by snapshots (bit / pixel identical before / after) — except the bugs found on the way:
  Pulses + zoom far + Fit crashed (`pulse_layer`: only lines near the view, MAX_PIECES) · GPU on → dark line at the
  plot's right edge (`PlotView.drawBackground`) · Store Python: Open log folder / full report opened nothing
  (`paths.outside_path`) · no note in the log after a killed session, two programs shared crash.txt (crash-<pid>.txt +
  lock) · a scene restored after a crash skipped the slider limits · `program_checks` raised on a doublet turned
  against the flow. **None of these is confirmed on Windows yet — ask him.**
- **Snapshot method for any change that must not change results** (scripts lived in the session scratchpad
  `check/`; recreate them when needed): keep the old source with `git archive HEAD physics model app app_info.py
  presets assets | tar -x -C OLD` (never git stash), run the same script with `SRC=OLD` and without, compare
  exactly. Used: streamline engine (186 pictures), analysis (1155 items: stagnation, bodies, surfaces, Cp, forces,
  particles), verification numbers (75), plot pixels (presets × 3 layer sets × 2 themes = 126), pulse pieces,
  the whole window (light / dark; only the status bar's ms differ).
- **Subsystems in brief** (details in ROADMAP 20.x): GPU box = restart (`app/restart.py`, `--resume`; scene and
  state come back); on a laptop with NVIDIA the program relaunches itself once with SHIM_MCCOMPAT
  (`gpu.relaunch_on_strong_card`; an in-process switch does not work); OpenGL is only asked in a child process
  (`main.py --probe-gpu`); GPU slider limits `gpu.GPU_LIMITS` + measured particles; the program starts EMPTY
  (`MainWindow.START_SCENE = None`; tests/conftest sets the lifting cylinder); zoom limits 1e4 × Fit
  (`canvas.ZOOM_RANGE`); multi-core `physics/parallel.py` (`PFL_THREADS`; this server has 2 threads → run tests
  with PFL_THREADS=4 to exercise it); loading screen + first-start signature (`app/startup.py`, `app/splash.py`);
  the tour locks the window (`Step.allow`, `Tour.allows`, keys via ShortcutOverride) and can go back
  (`Tour.back` undoes to the step's mark); beaver remarks via `Beaver.remark` (`REMARK_CHANCE`, `REMARK_GAP_S`).
  Offscreen notes: after a modal dialog call `activateWindow()` before shortcuts; a real double-click is press,
  release, double-click, release. OpenGL tests: `Xvfb :99 &`, DISPLAY=:99 QT_QPA_PLATFORM=xcb
  PFL_GPU_ALLOW_SOFTWARE=1 (add QT_SCALE_FACTOR=1.25 for his 125 %).
- **His reference files** (assignment docx, his notebook photos, Anderson chapters) were in the session
  scratchpad `reference/` only — never in the repo (the book must not go in); ask him again when needed. His
  notes' rotating cylinder uses clockwise Γ (as Anderson); the program keeps Γ > 0 ccw and writes the course's
  value as Γ_cw (Sign conventions dialog, verification table).
- **Waiting for his Windows check**: the bug fixes above; 20.7H zoom (fast wheel to both limits with GPU, wheel
  at the limit, Fit); 144 fps in Pulses / Particles; the tour from start to end; the beaver's feel.
- **Next, in this order**:
  22 text and visual review **with him** (every UI string in one list + screenshot gallery; he marks what to
  change; open decisions: dividing-streamline colour, element colours, icons, the beaver's name and his side /
  swimming poses) →
  23 exhaustive random test with the final code — `scripts/random_test.py` (23.1, 2 Nov): physics checks on random
  and extreme scenes in 4 views (no exceptions, V = 0 at stagnation points, lines along V, ψ constant, no crossings,
  zoom-independent bodies, forces vs Kutta–Joukowski / d'Alembert, save → reopen, particles stay in the fluid) +
  random window actions (undo-all / redo-all exact, exports, error log and excepthook watched; 23.3: "chaos" scenes =
  walls / streams / sectors at any angle, scenes with errors computed too (crash + slow only), real wheel bursts,
  mouse pan / drag, wall storms, actions that do not wait for the computation, a live one-line status). He runs it on Windows
  and sends `random_test_results/<run>/`; `--replay file.pflow` repeats one failing scene. Still missing: recovery
  from autosave. Every bug found → fix + permanent test (23.2: the 3-wall image explosion); final run after 22 →
  24 packaging — **he chose both A (zip: Flowy\Flowy.exe + _internal\) and C (Inno Setup installer: Start menu,
  .pflow association, uninstaller)**, version 1.0, GitHub Releases, test on a PC without Python, SmartScreen note
  ("More info → Run anyway"). To do there: bundle imageio-ffmpeg's ffmpeg binary in the spec; Numba's cache goes to
  %LOCALAPPDATA%\numba by itself; settings (registry …\IZTECH\Flowy) and data (%LOCALAPPDATA%\IZTECH\Flowy) are per
  user, the same for A and C, kept across updates; the exe has no console (the CLI prints nothing, exit codes work);
  `startup.prepared_signature` sees no physics/*.py in the exe → only the version decides "first start" there →
  25 report (4–6 pages; figures and tables from `--verify`; read his report preferences in memory first) + user
  guide as a document → 26 final check against the assignment text, item by item → 27 demo rehearsal.
- **Maybe** (not dropped): dye rake (streaklines), Joukowski airfoil (conformal mapping, Kutta condition).
- Suggestions he did not take yet: GitHub Actions (Windows tests + automatic exe), test on another PC, macOS.
