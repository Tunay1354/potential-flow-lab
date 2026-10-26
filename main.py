"""
Potential Flow Lab
Run:  python main.py                 (starts with the lifting-cylinder scene)
      python main.py scene.pflow     (opens a saved scene; also used when a file is double-clicked)
"""
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow, setup_application


def main():
    app = QApplication(sys.argv)
    setup_application(app)
    win = MainWindow()
    win.show()
    files = [a for a in sys.argv[1:] if not a.startswith("-")]
    if files:
        QTimer.singleShot(0, lambda: win.open_scene(files[0]))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
