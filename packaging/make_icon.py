"""
make_icon.py — the exe's icon (Explorer, taskbar) from the program's logo, drawn by the same code as the header
(app/chrome/header.draw_logo, light theme), so it never goes out of step with it. build_exe.spec runs it.

    python packaging/make_icon.py OUT.ico
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
SIZES = (16, 24, 32, 48, 64, 128, 256)


def main(out: str) -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PIL import Image
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtWidgets import QApplication

    from app.chrome.header import logo_pixmap
    from app.theme import LIGHT
    _app = QApplication.instance() or QApplication([])
    images = []
    for s in SIZES:
        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        logo_pixmap(LIGHT, s).save(buf, "PNG")
        images.append(Image.open(io.BytesIO(bytes(buf.data()))).convert("RGBA"))
    images[-1].save(out, format="ICO", sizes=[(s, s) for s in SIZES], append_images=images[:-1])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
