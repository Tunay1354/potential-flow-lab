"""
art.py — the beaver's pixel art, drawn by code: every pose is a list of simple shapes (ellipses, rotated
rectangles, polygons) in "art pixels"; a frame is rasterized at one sample per art pixel and then enlarged
with whole device pixels per art pixel, so it stays crisp at any display scale. Because the shapes are
rasterized fresh, a rotated or shrunk frame (tumbling, a vortex) is as crisp as the upright one.

    frame(kind, scale, rot=0, shrink=1, flip=False, **pose) -> QImage   (cached)

kinds: "perch" (peeking over the ruler), "front", "side" (standing / walking, facing right), "swim" (carried
by the flow, facing right). Pose options: mood ("open", "closed", "happy", "worried", "dizzy"), f (bandana
flutter frame 0–2), arm ("down" / "up": held), tap (paw on the glass), step (-1 / 0 / 1: walking),
phase (0 / 1: paddling).

All frames share one canvas (CANVAS × CANVAS art pixels) centred on the pose's pivot, so a sprite does not
jump between frames; FEET[kind] is how far the feet are below the centre (art pixels, upright).
"""
from __future__ import annotations

import functools
import math

import numpy as np
from PySide6.QtGui import QImage

CANVAS = 48
PIVOT = {"front": (16.0, 17.0), "side": (17.0, 18.0), "swim": (18.0, 16.0), "perch": (16.0, 15.0)}
FEET = {"front": 14.6, "side": 14.0, "swim": 7.0, "perch": 10.4}

PAL = {
    "K": (52, 32, 20),      # outline
    "B": (139, 90, 52),     # fur
    "D": (106, 66, 38),     # fur shade
    "L": (236, 205, 158),   # muzzle / belly
    "W": (255, 255, 255),
    "E": (30, 18, 10),      # eye
    "N": (58, 34, 22),      # nose
    "P": (222, 140, 118),   # cheeks / inner ear
    "T": (92, 60, 36),      # tail
    "t": (70, 46, 28),      # tail hatch
    "R": (198, 52, 38),     # bandana
    "r": (232, 98, 70),     # bandana light
    "Q": (142, 34, 26),     # bandana shade
}


class Part:
    """One shape: kind "ell" (centre, half axes a, b), "rect" (centre, half sizes), "poly" (points);
    rot in degrees; hatch = a second colour in a crossing pattern (the tail); edge = a darker rim where the
    shape lies over earlier ones (an arm in front of the body)."""
    __slots__ = ("kind", "color", "cx", "cy", "a", "b", "rot", "hatch", "edge", "pts")

    def __init__(self, kind, color, cx=0.0, cy=0.0, a=1.0, b=None, rot=0.0, hatch=None, edge=None, pts=None):
        self.kind, self.color, self.cx, self.cy = kind, color, cx, cy
        self.a, self.b = a, (a if b is None else b)
        self.rot, self.hatch, self.edge, self.pts = math.radians(rot), hatch, edge, pts

    def inside(self, x, y):
        if self.kind == "poly":
            inside = np.zeros(x.shape, bool)
            pts = self.pts
            for i in range(len(pts)):
                x1, y1 = pts[i]
                x2, y2 = pts[(i + 1) % len(pts)]
                if y1 == y2:
                    continue
                cross = (y1 > y) != (y2 > y)
                xi = (x2 - x1) * (y - y1) / (y2 - y1) + x1
                inside ^= cross & (x < xi)
            return inside
        dx, dy = x - self.cx, y - self.cy
        c, s = math.cos(-self.rot), math.sin(-self.rot)
        u, v = c * dx - s * dy, s * dx + c * dy
        if self.kind == "ell":
            return (u / self.a) ** 2 + (v / self.b) ** 2 <= 1.0
        return (np.abs(u) <= self.a) & (np.abs(v) <= self.b)


# ---------------------------------------------------------------------- details
def _eye(x, y, mood="open"):
    if mood == "happy":                    # ^ (closed, smiling)
        return [Part("rect", "E", x - 1.2, y + 0.3, 0.9, 0.45, rot=35), Part("rect", "E", x + 0.6, y + 0.3, 0.9, 0.45, rot=-35)]
    if mood == "closed":                   # blink / asleep
        return [Part("rect", "E", x, y + 0.6, 1.6, 0.42)]
    if mood == "dizzy":                    # X
        return [Part("rect", "E", x, y, 1.9, 0.45, rot=45), Part("rect", "E", x, y, 1.9, 0.45, rot=-45)]
    if mood == "worried":                  # wide open, eyebrow up
        return [Part("ell", "W", x, y, 2.1, 2.6), Part("ell", "E", x, y + 0.4, 1.0),
                Part("rect", "E", x, y - 3.3, 1.6, 0.4, rot=-20)]
    return [Part("ell", "E", x, y + 0.3, 1.55, 2.05), Part("ell", "W", x - 0.5, y - 0.6, 0.62)]


def _wave(f):
    return [(0.0, 0.0), (1.0, -1.2), (-0.6, 1.0)][f % 3]


def _bandana(f, y):
    """Front: a band round the neck, the knot on his right (viewer's left), two ends waving out."""
    w = _wave(f)
    return [Part("ell", "R", 16, y, 8.4, 1.9), Part("rect", "r", 16, y - 0.7, 6.8, 0.35),
            Part("poly", "R", pts=[(9.5, y - 1.2), (3.0 + w[0], y - 4.4 + w[1]), (2.0 + w[0], y - 2.0 + w[1]), (8.5, y + 1.2)]),
            Part("poly", "Q", pts=[(9.0, y + 0.2), (2.6 - w[0], y + 2.0 - w[1]), (4.0 - w[0], y + 4.0 - w[1]), (9.8, y + 1.6)]),
            Part("ell", "Q", 9.4, y + 0.2, 1.6, 1.5)]


# ---------------------------------------------------------------------- poses
def front(mood="open", arm="down", tap=False, f=0):
    p = [Part("ell", "T", 24.5, 22, 4.3, 6.5, rot=25, hatch="t"),
         Part("ell", "D", 11.5, 29.5, 3.0, 1.6), Part("ell", "D", 20.5, 29.5, 3.0, 1.6),
         Part("ell", "B", 16, 22.5, 8.2, 7.2),
         Part("ell", "L", 16, 23.5, 5.0, 5.0)]
    if arm == "up":
        p += [Part("ell", "B", 4.5, 17.5, 1.9, 4.2, rot=55, edge="D"), Part("ell", "B", 27.5, 17.5, 1.9, 4.2, rot=-55, edge="D")]
    else:
        p += [Part("ell", "B", 8.6, 21, 2.1, 3.6, rot=-18, edge="D")]
        if not tap:
            p += [Part("ell", "B", 23.4, 21, 2.1, 3.6, rot=18, edge="D")]
    p += _bandana(f, 18.4)
    p += [Part("ell", "B", 8.0, 5.0, 2.7), Part("ell", "P", 8.0, 5.0, 1.3),
          Part("ell", "B", 24.0, 5.0, 2.7), Part("ell", "P", 24.0, 5.0, 1.3),
          Part("ell", "B", 16, 11, 9.2, 8.0),
          Part("ell", "L", 16, 14.6, 4.6, 3.4),
          Part("ell", "P", 9.6, 13.6, 1.3, 0.9), Part("ell", "P", 22.4, 13.6, 1.3, 0.9)]
    p += _eye(12.4, 10.0, mood) + _eye(19.6, 10.0, mood)
    p += [Part("ell", "N", 16, 12.9, 1.7, 1.15)]
    if mood == "worried":
        p += [Part("ell", "K", 16, 16.6, 1.0, 1.1)]                     # "o" mouth
    else:
        p += [Part("rect", "W", 16, 16.9, 1.25, 1.25), Part("rect", "K", 16, 16.9, 0.18, 1.25)]
    if tap:                                                             # a paw pressed on the glass
        p += [Part("ell", "B", 24.5, 17.0, 2.6, 3.4, rot=-15, edge="D"), Part("ell", "P", 24.6, 16.2, 1.2, 1.0),
              Part("ell", "P", 23.2, 14.2, 0.45), Part("ell", "P", 24.7, 13.8, 0.45), Part("ell", "P", 26.1, 14.4, 0.45)]
    return p


def side(mood="open", f=0, step=0):
    """Standing, facing right (walking: step −1 / 0 / 1); the bandana knotted at the back, ends blowing back."""
    w = _wave(f)
    return [Part("ell", "T", 5.5, 27.6, 6.8, 2.5, rot=8, hatch="t"),
            Part("ell", "D", 13.0 - 1.6 * step, 30.6, 3.6, 1.5), Part("ell", "D", 21.5 + 1.6 * step, 30.8, 2.6, 1.3),
            Part("ell", "B", 15.5, 23.5 - 0.5 * abs(step), 8.6, 7.6),
            Part("ell", "L", 20.0, 25.0, 3.6, 5.2, rot=-8),
            Part("ell", "B", 17.2, 7.4, 2.4), Part("ell", "P", 17.3, 7.5, 1.1),
            Part("ell", "B", 20.8, 13.4, 7.6, 7.0),
            Part("ell", "B", 26.4, 15.6, 3.8, 3.2),
            Part("ell", "L", 27.2, 16.7, 3.2, 2.3),
            Part("rect", "W", 28.0, 19.0, 0.95, 1.2),
            Part("ell", "P", 22.6, 16.4, 1.2, 0.85),
            Part("rect", "R", 19.5, 19.4, 5.8, 1.6, rot=-12), Part("rect", "r", 20.0, 18.6, 4.6, 0.3, rot=-12),
            Part("poly", "R", pts=[(14.5, 19.6), (8.0 + w[0], 16.5 + w[1]), (7.0 + w[0], 18.8 + w[1]), (13.8, 21.4)]),
            Part("poly", "Q", pts=[(14.2, 20.6), (8.6 - w[0], 22.5 - w[1]), (9.6 - w[0], 24.2 - w[1]), (14.8, 21.8)]),
            Part("ell", "Q", 14.6, 20.4, 1.5, 1.4),
            Part("ell", "B", 22.6, 23.0, 1.8, 3.2, rot=18, edge="D")] + _eye(23.2, 11.6, mood) + \
        [Part("ell", "N", 29.9, 14.6, 1.3, 1.1)]


def swim(mood="happy", phase=0, f=0):
    """Carried by the flow, facing right: stretched out, paddling, bandana ends streaming back."""
    k = 1 if phase else -1
    w = _wave(f)
    return [Part("ell", "T", 2.5, 18.5, 6.0, 2.4, rot=-8 * k, hatch="t"),
            Part("ell", "D", 9.5, 22.5 + 0.6 * k, 2.6, 1.3, rot=-20),
            Part("ell", "B", 14, 17.5, 9.5, 5.6),
            Part("ell", "L", 15.5, 20.0, 6.0, 2.6),
            Part("ell", "B", 22.0, 21.5 - 1.2 * k, 1.6, 2.8, rot=-50 + 25 * k, edge="D"),
            Part("poly", "R", pts=[(19.0, 11.5), (10.0 + w[0], 8.5 + w[1]), (9.5 + w[0], 10.8 + w[1]), (18.5, 13.5)]),
            Part("poly", "Q", pts=[(18.8, 13.2), (11.5 - w[0], 13.6 - w[1]), (12.0 - w[0], 15.4 - w[1]), (19.2, 14.6)]),
            Part("ell", "R", 21.0, 15.2, 1.9, 4.8, rot=10), Part("ell", "Q", 19.2, 12.6, 1.4, 1.3),
            Part("ell", "B", 22.0, 7.5, 2.5), Part("ell", "P", 22.0, 7.5, 1.2),
            Part("ell", "B", 26.5, 13.0, 7.2, 6.6),
            Part("ell", "L", 31.6, 15.4, 3.6, 2.8), Part("ell", "P", 26.0, 15.8, 1.2, 0.85)] + \
        _eye(28.4, 11.4, mood) + [Part("ell", "N", 34.8, 13.9, 1.2, 1.0), Part("rect", "W", 32.6, 18.0, 0.85, 1.0)]


def perch(mood="open", f=0):
    """Peeking over the ruler: head and two paws."""
    return [Part("ell", "B", 8.0, 6.0, 2.7), Part("ell", "P", 8.0, 6.0, 1.3),
            Part("ell", "B", 24.0, 6.0, 2.7), Part("ell", "P", 24.0, 6.0, 1.3),
            Part("ell", "B", 16, 13, 9.4, 8.5)] + _bandana(f, 21.0)[:1] + [Part("rect", "r", 16, 20.3, 6.4, 0.3)] + \
        _bandana(f, 21.0)[2:] + \
        [Part("ell", "L", 16, 16.8, 4.6, 3.4),
         Part("ell", "P", 9.5, 15.8, 1.3, 0.9), Part("ell", "P", 22.5, 15.8, 1.3, 0.9),
         Part("ell", "B", 11.5, 23.6, 2.6, 1.7, edge="D"), Part("ell", "B", 21.0, 23.6, 2.6, 1.7, edge="D")] + \
        _eye(12.4, 12.2, mood) + _eye(19.6, 12.2, mood) + \
        [Part("ell", "N", 16, 15.1, 1.7, 1.15), Part("rect", "W", 16, 19.1, 1.25, 1.25),
         Part("rect", "K", 16, 19.1, 0.18, 1.25)]


POSES = {"front": front, "side": side, "swim": swim, "perch": perch}


# ---------------------------------------------------------------------- rasterizing
def rasterize(parts, pivot, rot=0.0, shrink=1.0, flip=False, size=CANVAS) -> np.ndarray:
    """RGBA array (size × size): the parts (local art coordinates) with `pivot` at the canvas centre,
    rotated by `rot` degrees (counter-clockwise on screen), shrunk, mirrored; one dark outline round all."""
    j, i = np.mgrid[0:size, 0:size]
    X = (i + 0.5 - size / 2.0) / shrink
    Y = (j + 0.5 - size / 2.0) / shrink
    r = math.radians(rot)
    c, s = math.cos(r), math.sin(r)
    u, v = c * X - s * Y, s * X + c * Y
    if flip:
        u = -u
    x, y = u + pivot[0], v + pivot[1]
    img = np.zeros((size, size, 4), np.uint8)
    filled = np.zeros((size, size), bool)
    for part in parts:
        mask = part.inside(x, y)
        if not mask.any():
            continue
        img[mask] = (*PAL[part.color], 255)
        if part.hatch:
            fu, fv = np.floor(x + 50).astype(int), np.floor(y * 0.9 + 50).astype(int)
            h = mask & (((fu + fv) % 3 == 0) | ((fu - fv) % 4 == 0))
            img[h] = (*PAL[part.hatch], 255)
        if part.edge:
            m = mask
            inner = m & np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1)
            rim = m & ~inner & filled
            img[rim] = (*PAL[part.edge], 255)
        filled |= mask
    nb = np.zeros_like(filled)
    nb[1:] |= filled[:-1]
    nb[:-1] |= filled[1:]
    nb[:, 1:] |= filled[:, :-1]
    nb[:, :-1] |= filled[:, 1:]
    img[nb & ~filled] = (*PAL["K"], 255)
    return img


def art_scale(dpr: float) -> int:
    """Device pixels per art pixel: about 2 logical pixels, always a whole number of device pixels."""
    return max(2, int(math.floor(2.0 * dpr + 0.5)))


@functools.lru_cache(maxsize=512)
def _frame(kind, scale, rot, shrink, flip, pose):
    arr = rasterize(POSES[kind](**dict(pose)), PIVOT[kind], rot, shrink, flip)
    big = np.ascontiguousarray(np.repeat(np.repeat(arr, scale, axis=0), scale, axis=1))
    img = QImage(big.data, big.shape[1], big.shape[0], big.shape[1] * 4, QImage.Format_RGBA8888)
    return img.copy()                              # (own the pixels: `big` goes away)


def frame(kind: str, scale: int, rot: float = 0.0, shrink: float = 1.0, flip: bool = False, **pose) -> QImage:
    """The pose as a QImage of CANVAS·scale device pixels (cached; rotation in 5° steps, size in 5 % steps)."""
    rot = round(rot / 5.0) * 5.0 % 360.0
    shrink = max(0.05, round(shrink * 20.0) / 20.0)
    return _frame(kind, int(scale), rot, shrink, bool(flip), tuple(sorted(pose.items())))
