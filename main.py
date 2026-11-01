"""
Start the program.

    python main.py                  the window (empty plot; ready-made scenes in Presets)
    python main.py scene.pflow      the window with a saved scene (also what a double-click on a file does)
    python main.py --first-run      as for a first-time user (the beaver offers the tour)
    python main.py --verify         no window: verification report        (python main.py --help: all options)

Internal: --resume FILE (a restart keeps the scene and state, app/restart.py) and --probe-gpu FILE (asks
OpenGL which graphics card draws, in its own process, app/hardware.py).
"""
import logging
import sys

log = logging.getLogger("pflab")


def main():
    from app.restart import split_resume
    args, resume = split_resume(sys.argv[1:])
    if "--probe-gpu" in args:
        from app.hardware import run_probe
        i = args.index("--probe-gpu")
        sys.exit(run_probe(args[i + 1] if i + 1 < len(args) else "gpu-probe.json"))
    from app.cli import main as cli_main, wants_cli
    if wants_cli(args):
        sys.exit(cli_main(args))
    from app.gpu import relaunch_on_strong_card
    code = relaunch_on_strong_card()                 # laptop with the GPU box on: once more, on the NVIDIA card
    if code is not None:
        sys.exit(code)
    sys.exit(run_window(args, resume))


def run_window(args, resume):
    """The program with its window; returns the exit code."""
    from PySide6.QtCore import QTimer, qInstallMessageHandler
    from PySide6.QtWidgets import QApplication

    from app.errors import ErrorReporter, qt_message_handler, setup_logging, shutdown_logging
    from app.gpu import apply_startup_env
    from app.startup import is_first_start, setup_application
    from app.theme import LAYOUT

    app = QApplication(sys.argv)
    setup_application(app)
    apply_startup_env()                              # (before any graphics: the chosen laptop card)
    if "--first-run" in args:
        app.setProperty("first_run", True)
    setup_logging()                                  # log + crash file, before anything can go wrong
    qInstallMessageHandler(qt_message_handler)
    reporter = ErrorReporter(app).install()          # an uncaught error: logged + one window, the program goes on

    splash = loading_screen(first=is_first_start())
    win = open_window(splash)
    reporter.window_parent = win
    if LAYOUT["start_maximized"]:
        win.showMaximized()
    else:
        win.show()
    if splash is not None:
        app.processEvents()
        splash.close()
    if resume:
        win.resume_from(resume)                      # a restart: scene, view, layers … as before
    QTimer.singleShot(0, win.offer_recovery)         # a scene left unsaved by a crash: "Restore it?"
    files = [a for a in args if not a.startswith("-")]
    if files:
        QTimer.singleShot(0, lambda: win.open_scene(files[0]))
    code = app.exec()
    shutdown_logging()
    return code


def loading_screen(first: bool = False):
    """The loading screen (app/splash.py), or None if it cannot be shown. first: the first start on this
    computer or after an update (the screen says it takes a while)."""
    try:
        from app.splash import LoadingScreen
        s = LoadingScreen(first_start=first)
        s.show()
        s.pump()
        return s
    except Exception:                                # noqa: BLE001
        log.exception("loading screen not shown")
        return None


def open_window(splash):
    """Load the program, look at this computer (remembered after the first start), compile the fast kernels
    (first start / after an update only), then make the main window. Nothing here stops the program."""
    def step(text, fraction):
        if splash is not None:
            splash.set_step(text, fraction)

    step("Loading the program…", 0.04)
    from app import hardware
    from app.main_window import MainWindow
    from app.startup import mark_prepared
    from physics import warmup

    step("Looking at this computer…", 0.14)
    profile, fresh = detect_hardware(splash)

    steps = warmup.steps()
    lo, hi = 0.24, 0.9
    for k, (label, fn) in enumerate(steps):
        try:
            if splash is not None:
                splash.run(fn, label, lo + (hi - lo) * k / len(steps), lo + (hi - lo) * (k + 1) / len(steps))
            else:
                fn()
        except Exception:                            # noqa: BLE001 (the window compiles it later then)
            log.exception("warm-up step failed: %s", label)
    warmup.mark_done()
    try:
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


def detect_hardware(splash):
    """(profile, found now) of this computer, written to the log and the loading screen; (None, False) if
    it cannot be found."""
    from PySide6.QtCore import QSettings

    from app import hardware
    try:
        settings = QSettings()
        again = settings.value("hardware/reprobe", False, bool)     # e.g. Windows was told to use another card
        settings.remove("hardware/reprobe")
        profile, fresh = hardware.detect(force=again, wait=splash.pump if splash is not None else None)
    except Exception:                                # noqa: BLE001
        log.exception("hardware detection failed")
        return None, False
    if profile is not None:
        lines = hardware.summary_lines(profile)
        log.info("this computer (%s): %s", "found now" if fresh else "remembered", " | ".join(lines))
        if splash is not None:
            for line in lines:
                splash.add_line(line)
    return profile, fresh


if __name__ == "__main__":
    main()
