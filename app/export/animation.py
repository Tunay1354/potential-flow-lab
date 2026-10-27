"""
animation.py — the running animation (Particles or Pulses) as an animated GIF or an MP4 video.

The frames are not screenshots of the window: the animation is stepped by exactly 1 / fps seconds per
frame and every frame is drawn like an exported PNG (same region, axes, background, colors, k×
resolution), so the file plays smoothly however fast the computer is. Before the first frame the
animation runs ~1.5 s unseen (trails and pulses are already there in frame 1).

GIF: Pillow (one shared color palette, so colors do not flicker); MP4: H.264 via imageio-ffmpeg (its own
ffmpeg). Both are optional packages: missing_package() names the one to install.
"""
import os
from contextlib import nullcontext

import numpy as np
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter

from ..theme import LIGHT
from .figure import _pinned_items, _scale_pens, mirrored_axes, restore_pinned

ANIMATION_FORMATS = {"gif": "GIF (animated image)", "mp4": "MP4 video (H.264)"}
DURATIONS = (1, 2, 3, 5, 10)                      # seconds
FRAME_RATES = {"gif": (20, 25), "mp4": (24, 30, 60)}
SCALES = {"gif": (1, 1.5, 2), "mp4": (1, 2, 3, 4)}
VIDEO_BACKGROUNDS = {"paper": "Plot color", "white": "White"}
WARMUP_S = 1.5
PACKAGES = {"gif": ("PIL", "pillow"), "mp4": ("imageio_ffmpeg", "imageio-ffmpeg")}


class Cancelled(Exception):
    pass


def missing_package(fmt: str) -> str | None:
    """The pip package needed for `fmt` if it is not installed, else None."""
    module, package = PACKAGES[fmt]
    try:
        __import__(module)
    except ImportError:
        return package
    return None


def frame_count(seconds: float, fps: int) -> int:
    return max(1, int(round(seconds * fps)))


def render_animation(canvas, path: str, fmt: str, seconds: float = 3, fps: int = 25, scale: float = 1.0,
                     background: str = "paper", light: bool = False, mirror: bool = True,
                     mirror_numbers: bool = True, progress=None):
    """Write `seconds` of the running animation to `path` (gif / mp4). progress(done, total) is called
    after every frame and may return False to cancel (raises Cancelled; the file is removed).
    Raises OSError if the file cannot be written, RuntimeError if the package is missing."""
    fmt = fmt.lower()
    if fmt not in ANIMATION_FORMATS:
        raise ValueError(f"Unknown format: {fmt}")
    package = missing_package(fmt)
    if package:
        raise RuntimeError(f"Saving {fmt.upper()} needs the Python package “{package}”:\n"
                           f"pip install {package}")
    if not canvas.animated:
        raise ValueError("Choose Particles or Pulses first (buttons above the plot).")
    layer = canvas.animation
    theme_before = canvas.theme
    cached = canvas.static_cache
    n = frame_count(seconds, fps)
    writer = None
    try:
        if cached:
            canvas.set_static_cache(False)
        if light and canvas.theme["name"] != "light":
            canvas.apply_theme(LIGHT)
        with mirrored_axes(canvas, mirror_numbers) if mirror else nullcontext():
            layer.set_export_scale(float(scale))
            for _ in range(int(WARMUP_S * fps)):
                layer.advance(1.0 / fps)
            writer = (_GifWriter if fmt == "gif" else _Mp4Writer)(path, fps)
            with _ExportMode(canvas, scale, background) as shot:
                for k in range(n):
                    layer.advance(1.0 / fps)
                    writer.add(shot())
                    if progress is not None and progress(k + 1, n) is False:
                        raise Cancelled()
            writer.close()
            writer = None
    except BaseException:
        if writer is not None:
            writer.abort()
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
        raise
    finally:
        layer.set_export_scale(None)
        if canvas.theme is not theme_before:
            canvas.apply_theme(theme_before)
        if cached:
            canvas.set_static_cache(True)
    if not os.path.exists(path):
        raise OSError(f"Could not write {path}")


class _ExportMode:
    """Plot items in export mode (as for a PNG) while the frames are drawn; shot() = one frame as an
    RGB array (rows, cols, 3)."""

    def __init__(self, canvas, scale, background):
        self.canvas, self.k = canvas, float(scale)
        self.bg = QColor("#FFFFFF" if background == "white" else canvas.theme["plot_bg"])

    def __enter__(self):
        scene = self.canvas.plot.scene()
        self.source = self.canvas.plot.getPlotItem().sceneBoundingRect()
        w, h = int(round(self.source.width() * self.k)), int(round(self.source.height() * self.k))
        self.size = (w - w % 2, h - h % 2)                  # even sizes (H.264 needs them)
        self.items = [it for it in scene.items() if hasattr(it, "setExportMode")]
        self.saved = _scale_pens(scene, self.k)
        self.pinned = _pinned_items(scene)
        for it in self.items:
            it.setExportMode(True, {"antialias": True, "resolutionScale": self.k, "background": self.bg})
        return self.shot

    def shot(self) -> np.ndarray:
        w, h = self.size
        img = QImage(w, h, QImage.Format_RGB32)
        img.fill(self.bg)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        src = QRectF(self.source.x(), self.source.y(), w / self.k, h / self.k)
        self.canvas.plot.scene().render(p, QRectF(0, 0, w, h), src, Qt.IgnoreAspectRatio)
        p.end()
        a = np.frombuffer(img.constBits(), np.uint8).reshape(h, img.bytesPerLine() // 4, 4)[:, :w]
        return np.ascontiguousarray(a[..., 2::-1])            # BGRA -> RGB

    def __exit__(self, *exc):
        for it in self.items:
            it.setExportMode(False)
        for it, pen in self.saved:
            it.setPen(pen)
        restore_pinned(self.pinned)
        return False


class _GifWriter:
    """Frames on one shared palette of 255 colors (made from the first frame: no flicker). After the
    first frame, pixels that did not change are transparent (index 255): the previous frame shows
    through and the file gets smaller. Saved at the end."""
    CLEAR = 255

    def __init__(self, path, fps):
        self.path, self.fps = path, fps
        self.frames, self.palette, self.prev = [], None, None

    def add(self, rgb):
        from PIL import Image
        im = Image.fromarray(rgb, "RGB")
        if self.palette is None:
            self.palette = im.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
        q = im.quantize(palette=self.palette, dither=Image.Dither.NONE)
        a = np.asarray(q)
        if self.prev is not None:
            d = a.copy()
            d[a == self.prev] = self.CLEAR
            q = Image.fromarray(d, "P")
            q.putpalette(self.palette.getpalette())
        self.prev = a
        self.frames.append(q)

    def close(self):
        first, rest = self.frames[0], self.frames[1:]
        first.save(self.path, save_all=True, append_images=rest, duration=round(1000 / self.fps), loop=0,
                   transparency=self.CLEAR, disposal=1, optimize=False)
        self.frames = []

    def abort(self):
        self.frames = []


class _Mp4Writer:
    """H.264 (yuv420p: plays everywhere), quality CRF 18, frames sent to ffmpeg as they are made."""

    def __init__(self, path, fps):
        import imageio_ffmpeg
        self.path, self.fps, self.gen = path, fps, None
        self._ffmpeg = imageio_ffmpeg

    def add(self, rgb):
        if self.gen is None:
            h, w = rgb.shape[:2]
            self.gen = self._ffmpeg.write_frames(self.path, (w, h), fps=self.fps, codec="libx264", quality=None,
                                                 macro_block_size=2, pix_fmt_out="yuv420p",
                                                 output_params=["-crf", "18", "-preset", "veryfast",
                                                                "-movflags", "+faststart"])
            self.gen.send(None)
        self.gen.send(rgb.tobytes())

    def close(self):
        if self.gen is not None:
            self.gen.close()
            self.gen = None

    def abort(self):
        try:
            self.close()
        except Exception:                                    # noqa: BLE001 - the file is removed anyway
            pass
