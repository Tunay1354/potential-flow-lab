"""
Potential Flow Lab
Run:  python main.py                 (starts with the lifting-cylinder scene)
      python main.py scene.pflow     (opens a saved scene; also used when a file is double-clicked)

Without a window (app/cli):
      python main.py --verify [--out DIR]                    verification report (Markdown + CSV + figures)
      python main.py scene.pflow --figure out.png --data out.csv     figure / CSV tables of a scene
      python main.py --help                                  all options
"""
import sys


def main():
    from app.cli import main as cli_main, wants_cli
    if wants_cli(sys.argv[1:]):
        sys.exit(cli_main(sys.argv[1:]))
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from app.main_window import MainWindow, setup_application
    from app.theme import LAYOUT
    app = QApplication(sys.argv)
    setup_application(app)
    win = MainWindow()
    if LAYOUT["start_maximized"]:
        win.showMaximized()          # fills the screen (the title bar's restore button gives window_size)
    else:
        win.show()
    files = [a for a in sys.argv[1:] if not a.startswith("-")]
    if files:
        QTimer.singleShot(0, lambda: win.open_scene(files[0]))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
