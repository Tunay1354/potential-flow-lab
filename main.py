"""
Potential Flow Lab
Run:  python main.py
"""
import sys

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow, setup_application


def main():
    app = QApplication(sys.argv)
    setup_application(app)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
