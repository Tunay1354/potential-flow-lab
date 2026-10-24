"""
Potential Flow Lab — UI prototype.
Run:  python main.py
"""
import sys

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow, default_font


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Potential Flow Lab")
    app.setStyle("Fusion")          # same look on Windows and macOS
    app.setFont(default_font())
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
