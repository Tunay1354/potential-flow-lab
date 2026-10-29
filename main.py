"""
Potential Flow Lab
Run:  python main.py                 (starts with an empty plot; Presets has ready-made scenes)
      python main.py scene.pflow     (opens a saved scene; also used when a file is double-clicked)
      python main.py --first-run     (starts as for a first-time user: the beaver offers the tour)
      (internal) --resume FILE       a restart (GPU box): the state the previous program left (app/restart.py)

Without a window (app/cli):
      python main.py --verify [--out DIR]                    verification report (Markdown + CSV + figures)
      python main.py scene.pflow --figure out.png --data out.csv     figure / CSV tables of a scene
      python main.py --help                                  all options

Internal: python main.py --probe-gpu FILE   the separate process that asks OpenGL which graphics card draws
(app/hardware.py: a broken graphics driver may crash that process, never the program).
"""
import logging
import sys


def main():
    from app.restart import split_resume
    args, resume = split_resume(sys.argv[1:])        # (a restart: everything as the previous program left it)
    if "--probe-gpu" in args:                        # the OpenGL check, in its own process
        i = args.index("--probe-gpu")
        from app.hardware import run_probe
        sys.exit(run_probe(args[i + 1] if i + 1 < len(args) else "gpu-probe.json"))
    from app.cli import main as cli_main, wants_cli
    if wants_cli(args):
        sys.exit(cli_main(args))
    from app.gpu import relaunch_on_strong_card
    code = relaunch_on_strong_card()                 # laptop + "Use NVIDIA": once more, on the NVIDIA card
    if code is not None:
        sys.exit(code)
    from PySide6.QtCore import QTimer, qInstallMessageHandler
    from PySide6.QtWidgets import QApplication

    from app.errors import ErrorReporter, qt_message_handler, setup_logging, shutdown_logging
    from app.startup import setup_application
    from app.theme import LAYOUT
    app = QApplication(sys.argv)
    setup_application(app)
    from app.gpu import apply_startup_env
    apply_startup_env()                              # (before any graphics: the chosen laptop card)
    if "--first-run" in args:                        # try the first start again (the beaver offers the tour)
        app.setProperty("first_run", True)
    setup_logging()                      # log file (+ crash file); before anything can go wrong
    qInstallMessageHandler(qt_message_handler)
    reporter = ErrorReporter(app).install()        # an uncaught error: logged + a window, the program goes on
    from app.startup import is_first_start
    splash = loading_screen(first=is_first_start())
    win = open_window(splash)
    reporter.window_parent = win
    if LAYOUT["start_maximized"]:
        win.showMaximized()          # fills the screen (the title bar's restore button gives window_size)
    else:
        win.show()
    if splash is not None:
        app.processEvents()
        splash.close()
    if resume:
        win.resume_from(resume)                    # the restart's scene, view, layers … (before anything else)
    QTimer.singleShot(0, win.offer_recovery)       # a scene left unsaved by a crash: "Restore it?"
    files = [a for a in args if not a.startswith("-")]
    if files:
        QTimer.singleShot(0, lambda: win.open_scene(files[0]))
    code = app.exec()
    shutdown_logging()
    sys.exit(code)


def loading_screen(first: bool = False):
    """The loading screen (app/splash.py), or None if it cannot be shown (the program starts without it).
    first: the first start on this computer (or after an update) — the screen says it takes a while."""
    try:
        from app.splash import LoadingScreen
        s = LoadingScreen(first_start=first)
        s.show()
        s.pump()
        return s
    except Exception:                                # noqa: BLE001
        logging.getLogger("pflab").exception("loading screen not shown")
        return None


def open_window(splash):
    """Load the program, find out about this computer (remembered after the first start), compile the fast
    kernels (only the first time on this computer / after an update), then make the main window."""
    log = logging.getLogger("pflab")

    def step(text, fraction):
        if splash is not None:
            splash.set_step(text, fraction)

    step("Loading the program…", 0.04)
    from app import hardware
    from app.main_window import MainWindow
    from physics import warmup

    step("Looking at this computer…", 0.14)
    try:
        from PySide6.QtCore import QSettings
        settings = QSettings()
        again = settings.value("hardware/reprobe", False, bool)     # e.g. Windows was told to use another card
        settings.remove("hardware/reprobe")
        profile, fresh = hardware.detect(force=again, wait=splash.pump if splash is not None else None)
    except Exception:                                # noqa: BLE001 - never stops the program
        log.exception("hardware detection failed")
        profile, fresh = None, False
    if profile is not None:
        lines = hardware.summary_lines(profile)
        log.info("this computer (%s): %s", "found now" if fresh else "remembered", " | ".join(lines))
        if splash is not None:
            for line in lines:
                splash.add_line(line)

    steps = warmup.steps()
    lo, hi = 0.24, 0.9
    for k, (label, fn) in enumerate(steps):
        a, b = lo + (hi - lo) * k / len(steps), lo + (hi - lo) * (k + 1) / len(steps)
        try:
            if splash is not None:
                splash.run(fn, label, a, b)
            else:
                fn()
        except Exception:                            # noqa: BLE001 - the window compiles it later then
            log.exception("warm-up step failed: %s", label)
    warmup.mark_done()
    try:
        from app.startup import mark_prepared
        mark_prepared()                              # the next start is a fast one
    except Exception:                                # noqa: BLE001
        log.exception("start-up signature not saved")
    if profile is not None and fresh and steps:
        try:                                         # the processor's speed, compiled: for later defaults
            profile["cpu_ms"] = round(warmup.streamline_engine(), 1)
            hardware.save_profile(profile)
        except Exception:                            # noqa: BLE001
            log.exception("processor measurement failed")

    step("Opening the window…", 0.95)
    win = MainWindow()
    win.hardware = profile
    step("Ready!", 1.0)
    return win


if __name__ == "__main__":
    main()
