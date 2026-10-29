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
- `presets/` scenes (folder = menu group), `assets/` (fonts, icons; Pixelify Sans is no
  longer used since the bubble restyle of 29 Oct),
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
every rotation / size is crisp), speech bubble typed letter by letter (`bubble.py`: "drafting card" look since 29 Oct —
thick ink frame, stepped corners, shadow, header name + tag, IBM Plex Mono text, buttons with the main one in the
plank colour; dialogs with choices / buttons), English lines (`lines.py`, 40+ situations, ~180 lines, random without quick repeats; PRIORITY
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
- **29 Oct, tour lock (ROADMAP 19c)**, from his step-by-step Windows test of the tour: while the tour runs the
  window is locked — `Step.allow` + `Tour.allows` decide what a press / double-click / wheel / right-click may
  reach (checked in `Beaver._tour_blocks`, app-wide event filter; never block releases or moves); keys: Enter /
  Space next or skip, Esc end, all others swallowed except `Step.keys` (M in the Move step), also when a text field
  has the focus. Bubble buttons End tour / Next / Skip (`bubble.buttons`, `button_clicked`). Sub-steps `Tour.sub`:
  "drag" (palette drag: plot highlighted), "dialog" (the window sends dialog_open / dialog_closed around every
  element dialog; the beaver stands where his bubble fits beside it). The window also sends edited / setting /
  mouse_mode / palette_drag(_end). The bubble never covers `Tour.avoid_rect()`. 18 steps.
  Offscreen note: after a modal dialog the window is not active again by itself → shortcuts (M) need
  `activateWindow()` in scripts; a real double-click is press, release, double-click, release (QTest.mouseDClick
  alone is ignored by item views).
- **29 Oct, bubble restyle + 2 tour bugs (ROADMAP 19d)**: his mock-up (Turkish text, ours stays English): the
  bubble got a header (name `lines.NAME`, a placeholder, + tag), mono text, buttons (`say(..., title, tag, buttons,
  primary)`); no hint lines any more (Enter / Space are found anyway). The tour-offer bubble has buttons (Enter /
  1 yes, Esc / 2 no), menu / questions a Close button, an answer Close + More questions. Bugs: (1) `bubble.clear()`
  kept the old lines, so a remark still "typing" stopped the tour's first step (i stayed −1) — `clear()` resets
  them and `Tour.start()` clears the bubble; (2) a slider scrolled out of the Plot settings (he had scrolled the
  panel) could not be shown nor scrolled to (lock) — `Tour._prepare` opens the panel, scrolls the slider into
  view, skips the step if its section is hidden.
- **29 Oct, item 20 started — baseline measured (no OpenGL)**: `scripts/benchmark.py` (new, program unchanged;
  sections startup / compute / paint / interact / anim / export / verify; `--out x.json`, `--quick`, `--only`)
  → `benchmarks/2026-10-29_baseline_cloud-2cpu_run{1,2}.json` (this 2-CPU offscreen server; numbers in ROADMAP 20).
  Everything fine; only stutters: pan / zoom with every layer on (p95 25–40 ms, rare 90–130 ms) and the background
  compute of busy scenes (8 elements: 1.4 s). He asked to add OpenGL next and compare with the SAME script, also on
  his Windows PC (ask him to run `python scripts/benchmark.py --out before.json` there before the change).
- **29 Oct, 20.1 loading screen + hardware (ROADMAP 20.1)**: main.py → `app/splash.LoadingScreen` (shown
  after the light `app/startup.setup_application`, before heavy imports) → `app/hardware.detect()` (profile in
  QSettings "hardware/profile", re-detected when `fingerprint()` changes; OpenGL asked ONLY in a child process
  `main.py --probe-gpu FILE` — a GL call on a non-current context segfaults, seen here) → `physics/warmup.steps()`
  (everything compiled before the window; checked with numba compile events: nothing compiles later) →
  MainWindow (`win.hardware`). Help → Your computer… (`hardware_dialog.py`). This server now has Xvfb + Mesa
  (llvmpipe, GL 4.5): `Xvfb :99 &`, then DISPLAY=:99 QT_QPA_PLATFORM=xcb for OpenGL tests (software only).
  His PC: Windows 11 laptop, 16 threads, RTX 3050 Ti (+ probably Intel), Hz unknown; his baseline numbers in
  ROADMAP 20. Next packages: 20.2 multi-core (always on), 20.3 GPU box in the header + OpenGL plot + Graphics card
  panel (FPS, fps cap Match screen / 60 / 120 / 144) + Intel → NVIDIA (write HKCU\Software\Microsoft\DirectX\
  UserGpuPreferences "GpuPreference=2;" for the exe / python.exe after asking, restart, check the renderer;
  fallback: open ms-settings:display-advancedgraphics), 20.4 GPU particles / pulses + calibrated maxima.
- **29 Oct, 20.2 multi-core (always on)**: `physics/parallel.py` (pool of cpu_threads − 1, `PFL_THREADS`, nested
  calls run serially, results in order). Used by `level._integrate` / `_integrate_both` (seed pieces of the nogil
  tracer; both directions at once on several cores) and `field.complex_velocity / complex_potential` (≥ 20 000
  points). Bit-identical to one core (3457 line arrays, 84 grids; tests/test_parallel.py). This server has 2
  hyper-threads → workers() = 1 by default: run tests with PFL_THREADS=4 to exercise the parallel code.
- **29 Oct, 20.3 GPU box + OpenGL plot (ROADMAP 20.3)**: header box `Plank.gpu` + View action `act_gpu` →
  `GraphicsMixin.set_gpu` (`app/window/graphics.py`) → `PlotCanvas.set_gpu` swaps the plot viewport to
  `PlotGLViewport` (`app/canvas/gl_viewport.py`, 4× MSAA) at run time; FullViewportUpdate with GL (Minimal would
  leave the rest of the frame empty); `PlotInteraction.viewport_changed` rebinds drops / cursor / filter. Rules,
  fps cap, crash guard (`SessionGuard` lock file) and the Windows GpuPreference registry write live in `app/gpu.py`;
  panel `app/gpu_panel.py` (dock "Graphics card", only while on). Fallback: no context / no frameSwapped in 6 s →
  raster + message. Laptop: `hardware.runs_on_weak_card` → offer → registry + `hardware/reprobe` → restart
  (`restart_program`) → `_gpu_check_switch`. Tests replace `_ask_strong_card`, `_show_switch_help`. Offscreen
  has no OpenGL (switching on fails cleanly there — tested); real GL test runs in a subprocess on Xvfb
  (`test_opengl_draws_the_plot`, skipped when no X server answers). Software GL is refused by the box
  (`PFL_GPU_ALLOW_SOFTWARE=1` for server tests; `benchmark.py --gpu` forces it). He has not tried it on Windows yet.
- **29 Oct, 20.3b**: on his laptop the registry entry for `.venv\Scripts\python.exe` did not help (still Intel): his
  base Python is the **Microsoft Store** one (WindowsApps; the venv exe only starts it). Now the real process file
  (`hardware.process_image_path`) is registered too, and after "Use NVIDIA" `SHIM_MCCOMPAT=0x800000001` is set at
  every start (`gpu.apply_startup_env`). `scripts/gpu_check.py` shows which way works — waiting for his output.
- **29 Oct, 20.3c**: his Windows numbers came (benchmarks/windows_after_*.json, if he pushed them): the GPU helps
  painting with many layers (channel every layer 32.5 → 8.3 ms), animation was capped at 23 fps by the
  pixmap cache (fixed, see §7). Benchmark anim now reports the frames the plot really showed + paint ms.
- **29 Oct, 20.3d**: stale-picture fix, frame pacing, `kernel.draw_segments_parallel` (row bands, bit-identical),
  `parallel.run` does queued tasks itself. Friend's C++ project (laurance18/potential-flow-lab) studied: everything
  is drawn by the GPU (points / polylines + shaders, trail fade in an FBO); see ROADMAP 20.3d.
- **29 Oct, 20.4 (done)**: with the GPU box on, Particles / Pulses are drawn by the card
  (`app/canvas/gl_animation.py`, instanced capsules with the draw_segments coverage formula, FBO per layer,
  composited in `TrailItem.paint` via beginNativePainting; layers record `GLFrame` ops; `gpu_broken` → CPU).
  Pulses upload pieces once, the shader decides lit pieces from the time. Particles max with GPU calibrated
  (`step_ms`, stored `gpu/particles_max` + fingerprint, ≤ 100 000); advect split on cores for ≥ 10 000.
  Uniforms must be set by location (`gl_animation._uniform`): PySide's name overloads are ambiguous.
- **29 Oct, 20.5**: `scripts/benchmark.py --full --out benchmarks/<name>.json` = the one command for him (all
  sections incl. the new `limits` with `stress_scene()`, then paint / interact / anim / limits again with the GPU,
  keys suffixed " [GPU]"). He runs it and pushes the JSON from GitHub Desktop.
- **29 Oct, 20.5b**: his `windows_full.json` [GPU] part ran on **Intel** (the in-process SHIM_MCCOMPAT of 20.3b does
  NOT work; only at process start). `gpu.relaunch_on_strong_card()` (main.py when "Use NVIDIA" was chosen;
  benchmark --gpu/--full always unless --integrated) restarts the process once with the switch and waits.
  Not verified on Windows yet — ask him to run `--full` again and check the "graphics card:" line.
- **Next**: his Windows check of 20.3d / 20.4 (fps in Pulses / Particles at 144, many particles); then item 20's
  remaining measurements (Solid bodies, Surface pressure, export) from his benchmark files, then 21 …
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
