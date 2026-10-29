"""
gl_animation.py — the Particles and Pulses pictures drawn by the graphics card (while the GPU box is on).

Without the graphics card the animation picture is painted pixel by pixel by the processor
(kernel.draw_segments) and handed to the plot as an image every frame. Here the processor only says
WHERE the short lines are; the graphics card paints them (one rectangle per line piece, the round,
smoothed edge computed per pixel in a shader — the same formula as draw_segments), fades the particle
trails and lays the picture over the plot. Pulses: the line pieces are sent once (when the lines or the
view change); every frame only the animation time changes, the shader decides which pieces are lit.

    target picture (a frame buffer, the plot area in device pixels, row 0 = bottom — the same pixels as the
    processor's picture) → drawn onto the plot inside the plot's own paint (QPainter.beginNativePainting)

A GLAnimation lives in one OpenGL context (the plot's PlotGLViewport) and is made the first time it is
needed. Anything that fails (old OpenGL, a shader the driver refuses) makes it unusable: the layer then
draws with the processor again (AnimatedLayer.use_gpu). Exports never come here.
"""
from __future__ import annotations

import logging

import numpy as np
from PySide6.QtCore import QPointF
from PySide6.QtGui import QOpenGLContext, QVector2D, QVector4D
from PySide6.QtOpenGL import (QOpenGLBuffer, QOpenGLFramebufferObject, QOpenGLFramebufferObjectFormat,
                              QOpenGLShader, QOpenGLShaderProgram, QOpenGLVertexArrayObject)

log = logging.getLogger("pflab")

# OpenGL constants (not in Qt's Python classes)
GL_FLOAT, GL_TRIANGLES, GL_TRIANGLE_STRIP = 0x1406, 0x0004, 0x0005
GL_BLEND, GL_SCISSOR_TEST, GL_DEPTH_TEST, GL_STENCIL_TEST, GL_CULL_FACE = 0x0BE2, 0x0C11, 0x0B71, 0x0B90, 0x0B44
GL_ZERO, GL_ONE, GL_SRC_COLOR, GL_ONE_MINUS_SRC_ALPHA = 0, 1, 0x0300, 0x0303
GL_FUNC_ADD, GL_FUNC_REVERSE_SUBTRACT, GL_MAX = 0x8006, 0x800B, 0x8008
GL_COLOR_BUFFER_BIT, GL_TEXTURE_2D, GL_TEXTURE0, GL_RGBA8 = 0x4000, 0x0DE1, 0x84C0, 0x8058
GL_FRAMEBUFFER = 0x8D40

BINS = 8                    # speed colours (animation_layer.BINS)
SEG_FLOATS = 6              # per line piece: ax, ay, bx, by, band, alpha (or phase)

_SEG_VS = """#version 330
in vec2 a_corner;                 // x: 0 = start end, 1 = finish end; y: -1 / +1 = the two sides
in vec4 a_seg;                    // ax, ay, bx, by in picture pixels (row 0 = bottom)
in vec2 a_attr;                   // speed band (< 0: not drawn), alpha (pulses: phase)
uniform vec2 u_size;
uniform float u_radius;
uniform vec4 u_pal[8];            // r, g, b 0 … 255, alpha 0 … 1
uniform int u_pulse;              // 1: a_attr.y is the phase, lit while s = fract(u_t - phase) < u_len
uniform float u_t;
uniform float u_len;
out vec4 v_color;
flat out vec4 v_seg;
void main() {
    int band = int(floor(a_attr.x + 0.5));
    float alpha = a_attr.y;
    if (u_pulse == 1) {
        float s = fract(u_t - a_attr.y);
        alpha = s < u_len ? 1.0 - s / u_len : 0.0;          // bright head, fading tail
    }
    vec4 c = u_pal[clamp(band, 0, 7)];
    float ca = c.a * alpha;
    v_seg = a_seg;
    if (band < 0 || ca <= 0.0) {                            // not drawn: outside the picture
        v_color = vec4(0.0);
        gl_Position = vec4(3.0, 3.0, 0.0, 1.0);
        return;
    }
    vec2 a = a_seg.xy, b = a_seg.zw;
    vec2 d = b - a;
    float L = length(d);
    vec2 t = L > 1e-6 ? d / L : vec2(1.0, 0.0);
    vec2 n = vec2(-t.y, t.x);
    float e = u_radius + 1.0;
    vec2 p = (a_corner.x < 0.5 ? a - t * e : b + t * e) + n * (a_corner.y * e);
    gl_Position = vec4(p / u_size * 2.0 - 1.0, 0.0, 1.0);
    v_color = vec4(c.rgb / 255.0 * ca, ca);                 // premultiplied
}
"""

_SEG_FS = """#version 330
in vec4 v_color;
flat in vec4 v_seg;
uniform float u_radius;
out vec4 o_color;
void main() {
    vec2 p = gl_FragCoord.xy;                               // pixel centre (i + 0.5, j + 0.5)
    vec2 a = v_seg.xy, d = v_seg.zw - v_seg.xy;
    float L2 = dot(d, d);
    float t = L2 > 0.0 ? clamp(dot(p - a, d) / L2, 0.0, 1.0) : 0.0;
    float cov = u_radius + 0.5 - length(a + t * d - p);     // as kernel.draw_segments
    if (cov <= 0.0) discard;
    o_color = v_color * min(cov, 1.0);
}
"""

_FILL_VS = """#version 330
void main() {                                               // one triangle over the whole target
    vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}
"""

_FILL_FS = """#version 330
uniform vec4 u_color;
out vec4 o_color;
void main() { o_color = u_color; }
"""

_QUAD_VS = """#version 330
in vec2 a_pos;                    // clip coordinates
in vec2 a_uv;
out vec2 v_uv;
void main() { v_uv = a_uv; gl_Position = vec4(a_pos, 0.0, 1.0); }
"""

_QUAD_FS = """#version 330
uniform sampler2D u_tex;
in vec2 v_uv;
out vec4 o_color;
void main() { o_color = texture(u_tex, v_uv); }
"""

# one line piece = two triangles: the corners (end, side)
_CORNERS = np.array([[0, -1], [1, -1], [1, 1], [0, -1], [1, 1], [0, 1]], np.float32)


def _uniform(p: QOpenGLShaderProgram, name: str, value):
    """Set a uniform by name (PySide's name + number overloads are ambiguous: by location)."""
    loc = p.uniformLocation(name)
    if loc < 0:
        return
    if isinstance(value, bool) or isinstance(value, (int, np.integer)):
        p.setUniformValue1i(loc, int(value))
    elif isinstance(value, (float, np.floating)):
        p.setUniformValue1f(loc, float(value))
    else:
        p.setUniformValue(loc, value)


class Target:
    """One layer's picture on the graphics card: a frame buffer of the plot area's size."""

    def __init__(self):
        self.fbo: QOpenGLFramebufferObject | None = None
        self.view = None                  # the view (x-range, y-range) the picture belongs to
        self.count = 0                    # line pieces in the instance buffer (pulses)
        self.buffer: QOpenGLBuffer | None = None


class GLAnimation:
    """The shaders, buffers and pictures of the animations in one OpenGL context."""

    def __init__(self):
        self.ok = None                    # None: not tried yet; False: unusable (the processor draws)
        self.error = ""
        self.targets: dict[str, Target] = {}

    # ------------------------------------------------------------------ set up (context current)
    def ensure(self) -> bool:
        if self.ok is not None:
            return self.ok
        try:
            ctx = QOpenGLContext.currentContext()
            fmt = ctx.format()
            if ctx.isOpenGLES() or (fmt.majorVersion(), fmt.minorVersion()) < (3, 3):
                raise RuntimeError(f"OpenGL {fmt.majorVersion()}.{fmt.minorVersion()} (3.3 is needed)")
            self.f, self.xf = ctx.functions(), ctx.extraFunctions()
            self.seg = self._program(_SEG_VS, _SEG_FS, {"a_corner": 0, "a_seg": 1, "a_attr": 2})
            self.fill = self._program(_FILL_VS, _FILL_FS, {})
            self.quad = self._program(_QUAD_VS, _QUAD_FS, {"a_pos": 0, "a_uv": 1})
            self.vao = QOpenGLVertexArrayObject()
            if not self.vao.create():
                raise RuntimeError("no vertex array object")
            self.corners = self._buffer(_CORNERS)
            self.quad_buf = self._buffer(np.zeros((4, 4), np.float32))
            self.stream = self._buffer(np.zeros((1, SEG_FLOATS), np.float32))      # particles: new every frame
            self.ok = True
            log.info("animations drawn by the graphics card")
        except Exception as exc:                          # noqa: BLE001 - the processor draws instead
            self.ok, self.error = False, f"{type(exc).__name__}: {exc}"
            log.warning("animations on the graphics card not possible: %s", self.error)
        return self.ok

    def _program(self, vs, fs, attrs):
        p = QOpenGLShaderProgram()
        if not p.addShaderFromSourceCode(QOpenGLShader.Vertex, vs) or \
                not p.addShaderFromSourceCode(QOpenGLShader.Fragment, fs):
            raise RuntimeError("shader not compiled: " + p.log())
        for name, loc in attrs.items():
            p.bindAttributeLocation(name, loc)
        if not p.link():
            raise RuntimeError("shader not linked: " + p.log())
        return p

    @staticmethod
    def _buffer(data: np.ndarray, usage=QOpenGLBuffer.StaticDraw) -> QOpenGLBuffer:
        b = QOpenGLBuffer(QOpenGLBuffer.VertexBuffer)
        if not b.create():
            raise RuntimeError("no vertex buffer")
        b.setUsagePattern(usage)
        b.bind()
        data = np.ascontiguousarray(data, np.float32)
        b.allocate(data, data.nbytes)
        b.release()
        return b

    def destroy(self):
        """Free everything (the context is current; it is about to go)."""
        for t in self.targets.values():
            t.fbo = None
            if t.buffer is not None:
                t.buffer.destroy()
        self.targets.clear()
        if self.ok:
            for b in (self.corners, self.quad_buf, self.stream):
                b.destroy()
            self.vao.destroy()
        self.ok = None

    # ------------------------------------------------------------------ pictures
    def target(self, name: str, size: tuple[int, int], view, carry: bool) -> Target:
        """The layer's picture for this size and view: a new one when they changed (carry: the old picture
        is drawn into it where its region now is, as AnimatedLayer._carry_over does)."""
        t = self.targets.setdefault(name, Target())
        if t.fbo is not None and (t.fbo.width(), t.fbo.height()) == size and t.view == view:
            return t
        old, old_view = t.fbo, t.view
        fmt = QOpenGLFramebufferObjectFormat()
        fmt.setInternalTextureFormat(GL_RGBA8)
        t.fbo = QOpenGLFramebufferObject(size[0], size[1], fmt)
        t.view = view
        self._bind(t)
        self.f.glClearColor(0.0, 0.0, 0.0, 0.0)
        self.f.glClear(GL_COLOR_BUFFER_BIT)
        if carry and old is not None and old_view is not None and old.isValid():
            (a0, a1), (b0, b1) = old_view
            (x0, x1), (y0, y1) = view
            ratio = (a1 - a0) / (x1 - x0)
            if 0.5 < ratio < 2.0:
                corners = [((a - x0) / (x1 - x0) * 2 - 1, (b - y0) / (y1 - y0) * 2 - 1) for a, b in
                           ((a0, b0), (a1, b0), (a0, b1), (a1, b1))]
                self._blit(old.texture(), corners, blend=False)
        return t

    def clear(self, name: str):
        t = self.targets.get(name)
        if t is not None and t.fbo is not None:
            self._bind(t)
            self.f.glClearColor(0.0, 0.0, 0.0, 0.0)
            self.f.glClear(GL_COLOR_BUFFER_BIT)

    def _bind(self, t: Target):
        t.fbo.bind()
        self.f.glViewport(0, 0, t.fbo.width(), t.fbo.height())
        for cap in (GL_SCISSOR_TEST, GL_DEPTH_TEST, GL_STENCIL_TEST, GL_CULL_FACE):
            self.f.glDisable(cap)

    # ------------------------------------------------------------------ drawing into a picture
    def fade(self, t: Target, keep: float):
        """Particles' trails: every pixel × keep, then 1/255 less (faint pixels really reach 0)."""
        self._bind(t)
        f = self.f
        f.glEnable(GL_BLEND)
        self.vao.bind()
        self.fill.bind()
        f.glBlendEquation(GL_FUNC_ADD)
        f.glBlendFunc(GL_ZERO, GL_SRC_COLOR)
        _uniform(self.fill, "u_color", QVector4D(keep, keep, keep, keep))
        f.glDrawArrays(GL_TRIANGLES, 0, 3)
        f.glBlendEquation(GL_FUNC_REVERSE_SUBTRACT)
        f.glBlendFunc(GL_ONE, GL_ONE)
        d = 1.0 / 255.0
        _uniform(self.fill, "u_color", QVector4D(d, d, d, d))
        f.glDrawArrays(GL_TRIANGLES, 0, 3)
        f.glBlendEquation(GL_FUNC_ADD)
        self.fill.release()
        self.vao.release()

    def upload(self, t: Target, segs: np.ndarray):
        """The line pieces of a layer (pulses: kept on the card until the lines or the view change)."""
        segs = np.ascontiguousarray(segs, np.float32).reshape(-1, SEG_FLOATS)
        if t.buffer is None:
            t.buffer = QOpenGLBuffer(QOpenGLBuffer.VertexBuffer)
            t.buffer.create()
            t.buffer.setUsagePattern(QOpenGLBuffer.StaticDraw)
        t.buffer.bind()
        t.buffer.allocate(segs if segs.size else np.zeros(SEG_FLOATS, np.float32), max(segs.nbytes, 24))
        t.buffer.release()
        t.count = segs.shape[0]

    def segments(self, t: Target, palette, radius: float, *, segs: np.ndarray | None = None,
                 pulse: tuple[float, float] | None = None, keep_max: bool = False):
        """Draw line pieces into the picture: `segs` (n, 6) now (particles), or the uploaded pieces of t
        (pulses, with pulse = (t / period, lit length))."""
        if segs is not None:
            segs = np.ascontiguousarray(segs, np.float32).reshape(-1, SEG_FLOATS)
            n, buf = segs.shape[0], self.stream
            if n == 0:
                return
            buf.bind()
            if buf.size() < segs.nbytes:
                buf.allocate(segs, segs.nbytes)
            else:
                buf.write(0, segs, segs.nbytes)
            buf.release()
        else:
            n, buf = t.count, t.buffer
            if n == 0 or buf is None:
                return
        self._bind(t)
        f, xf, p = self.f, self.xf, self.seg
        f.glEnable(GL_BLEND)
        if keep_max:                         # overlapping round ends of one line do not darken
            f.glBlendEquation(GL_MAX)
            f.glBlendFunc(GL_ONE, GL_ONE)
        else:
            f.glBlendEquation(GL_FUNC_ADD)
            f.glBlendFunc(GL_ONE, GL_ONE_MINUS_SRC_ALPHA)
        self.vao.bind()
        p.bind()
        _uniform(p, "u_size", QVector2D(t.fbo.width(), t.fbo.height()))
        _uniform(p, "u_radius", float(radius))
        for k in range(BINS):
            c = palette[min(k, len(palette) - 1)]
            _uniform(p, f"u_pal[{k}]", QVector4D(float(c[0]), float(c[1]), float(c[2]), float(c[3])))
        _uniform(p, "u_pulse", 1 if pulse is not None else 0)
        _uniform(p, "u_t", float(pulse[0] % 1.0) if pulse is not None else 0.0)
        _uniform(p, "u_len", float(pulse[1]) if pulse is not None else 0.0)
        self.corners.bind()
        p.enableAttributeArray(0)
        p.setAttributeBuffer(0, GL_FLOAT, 0, 2, 8)
        xf.glVertexAttribDivisor(0, 0)
        buf.bind()
        p.enableAttributeArray(1)
        p.setAttributeBuffer(1, GL_FLOAT, 0, 4, SEG_FLOATS * 4)
        xf.glVertexAttribDivisor(1, 1)
        p.enableAttributeArray(2)
        p.setAttributeBuffer(2, GL_FLOAT, 16, 2, SEG_FLOATS * 4)
        xf.glVertexAttribDivisor(2, 1)
        xf.glDrawArraysInstanced(GL_TRIANGLES, 0, 6, n)
        xf.glVertexAttribDivisor(1, 0)
        xf.glVertexAttribDivisor(2, 0)
        for loc in (0, 1, 2):
            p.disableAttributeArray(loc)
        buf.release()
        p.release()
        self.vao.release()
        f.glBlendEquation(GL_FUNC_ADD)

    # ------------------------------------------------------------------ onto the plot
    def _blit(self, texture: int, corners, blend: bool):
        """A picture onto the bound frame buffer: corners = clip coordinates of its (x0, y0), (x1, y0),
        (x0, y1), (x1, y1) (texture u, v = 0 / 1)."""
        f = self.f
        data = np.array([[cx, cy, u, v] for (cx, cy), (u, v) in zip(corners, ((0, 0), (1, 0), (0, 1), (1, 1)))],
                        np.float32)
        self.quad_buf.bind()
        self.quad_buf.write(0, data, data.nbytes)
        if blend:
            f.glEnable(GL_BLEND)
            f.glBlendEquation(GL_FUNC_ADD)
            f.glBlendFunc(GL_ONE, GL_ONE_MINUS_SRC_ALPHA)            # premultiplied picture
        else:
            f.glDisable(GL_BLEND)
        self.vao.bind()
        q = self.quad
        q.bind()
        _uniform(q, "u_tex", 0)
        f.glActiveTexture(GL_TEXTURE0)
        f.glBindTexture(GL_TEXTURE_2D, texture)
        q.enableAttributeArray(0)
        q.setAttributeBuffer(0, GL_FLOAT, 0, 2, 16)
        q.enableAttributeArray(1)
        q.setAttributeBuffer(1, GL_FLOAT, 8, 2, 16)
        f.glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
        q.disableAttributeArray(0)
        q.disableAttributeArray(1)
        f.glBindTexture(GL_TEXTURE_2D, 0)
        q.release()
        self.vao.release()
        self.quad_buf.release()

    def present(self, t: Target, painter, rect, viewport):
        """The picture onto the plot (inside the plot's paint): rect = its region in data coordinates."""
        if t.fbo is None:
            return
        dpr = viewport.devicePixelRatioF()
        W, H = viewport.width() * dpr, viewport.height() * dpr
        tr = painter.combinedTransform()
        corners = []
        for x, y in ((rect.left(), rect.top()), (rect.right(), rect.top()),
                     (rect.left(), rect.bottom()), (rect.right(), rect.bottom())):
            p = tr.map(QPointF(x, y))                     # (top/bottom: data y grows upwards in the rect)
            corners.append((p.x() * dpr / W * 2.0 - 1.0, 1.0 - p.y() * dpr / H * 2.0))
        f = self.f
        f.glBindFramebuffer(GL_FRAMEBUFFER, viewport.defaultFramebufferObject())
        f.glViewport(0, 0, int(round(W)), int(round(H)))
        for cap in (GL_DEPTH_TEST, GL_STENCIL_TEST, GL_CULL_FACE):
            f.glDisable(cap)
        self._blit(t.fbo.texture(), corners, blend=True)
