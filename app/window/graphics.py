"""
graphics.py — part of MainWindow: drawing the plot with the graphics card (the GPU box in the header, View →
Draw with the graphics card) and the Graphics card panel (the arrow beside the box), safely.

    off on a first start; remembered (app/gpu.py)
    ticking / unticking the box restarts the program at once (app/restart.py): the graphics card — on a laptop the
        NVIDIA card, gpu.relaunch_on_strong_card — can only be chosen when a program starts, and a window that
        once had OpenGL in it keeps it. The scene, its file name, unsaved changes, the view, the layers and
        the view mode come back exactly; nothing has to be saved first
    can be ticked only where OpenGL 2.0+ comes from a real graphics card (gpu.support; the box explains)
    a start with the box ticked: the plot gets an OpenGL viewport (set_gpu, also used live by tests and the
        benchmark)
    no picture within START_TIMEOUT_MS (the window visible) or no OpenGL context -> back to the normal
        drawing at once, with a message
    a program that ended abnormally while the graphics card drew (gpu.SessionGuard) -> the next start
        begins with the normal drawing and says why
    a laptop still on its power-saving card: NVIDIA was asked at the start already -> how to do it by hand
        in Windows (once); another faster card (AMD) -> offered (Windows setting + restart)
    with the card the Plot settings sliders reach further (gpu.GPU_LIMITS, Particles measured per computer;
        a mark on each bar shows the processor's limit); without it they come back, values above the limit
        come down to it
"""
from __future__ import annotations

import html
import logging
import os

from PySide6.QtCore import QPoint, QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QMessageBox

from .. import gpu, hardware
from ..chrome import tint_title_bar
from ..gpu_panel import short_name

log = logging.getLogger("pflab")

PARTICLE_BUDGET_MS = 4.0             # GPU mode: the most particles = what this computer moves in ~4 ms a frame
PARTICLES_GPU_MAX = 100_000          # ... at most (the slider's upper end)
PARTICLE_PROBE = 20_000              # particles timed once per computer for that
START_TIMEOUT_MS = 6000              # no frame shown this long after switching on (window visible): failed
CHECK_MS = 1500                      # looked at this often while starting; no OpenGL context by then: failed
LIMIT_NAMES = {"density": "Density", "particles": "Particles", "anim_speed": "Particle speed",
               "trail": "Trail length", "pulse_speed": "Pulse speed", "pulse_length": "Pulse length",
               "pulse_spacing": "Pulse spacing"}


class GraphicsMixin:

    # ------------------------------------------------------------------ build
    def _build_graphics(self):
        """The header box and its arrow, the View menu action, the panel; then the remembered state (called
        once the menus and the layout exist)."""
        self._gpu_guard = gpu.SessionGuard()
        self._gpu_frames = 0
        self._gpu_weak = None                    # the faster card, while the program runs on the other one
        self._gpu_timer = QTimer(self)
        self._gpu_timer.setSingleShot(True)
        self._gpu_timer.setInterval(CHECK_MS)
        self._gpu_waited = 0                     # ms the window was visible since switching on
        self._gpu_timer.timeout.connect(self._gpu_check_started)
        panel = self.gpu_panel
        panel.meter = self.canvas.plot.meter
        panel.cap_changed.connect(self.set_fps_cap)
        panel.switch_requested.connect(self.offer_strong_card)
        panel.higher_changed.connect(self.set_higher_limits)
        panel.set_higher(gpu.higher_limits())
        plank = self.header.plank
        plank.gpu.toggled.connect(self.gpu_box_changed)
        self.act_gpu.toggled.connect(self.gpu_box_changed)
        plank.gpu_more.toggled.connect(self.show_gpu_panel)
        self.act_gpu_panel.toggled.connect(self.show_gpu_panel)
        self._update_gpu_controls()

        crashed = self._gpu_guard.crashed_before()
        if crashed and gpu.enabled():
            gpu.set_enabled(False)
            log.warning("the last program drawing with the graphics card ended abnormally: GPU mode off")
            self._when_shown(lambda: self._notify_user(
                "warning", "Graphics card drawing is off",
                "The program did not close normally last time while the graphics card was drawing the plot. "
                "To be safe it now draws with the processor.\n\nTick GPU in the header to try the graphics "
                "card again."), 1500)
        ok, _why = gpu.support(self.hardware)
        if gpu.enabled() and ok:
            self.set_gpu(True)
        else:
            self._apply_fps_cap()
            self._apply_limits()
        self._when_shown(self._gpu_check_switch, 2500)

    def _when_shown(self, fn, delay_ms: int, tries: int = 120):
        """fn() delay_ms after the window is on the screen (not at all if it closes before)."""
        def later():
            if self.isVisible():
                fn()
            elif tries > 0 and not getattr(self, "_gpu_closed", False):
                self._when_shown(fn, 500, tries - 1)
        QTimer.singleShot(delay_ms, self, later)

    def _update_gpu_controls(self):
        """Box and menu action: ticked = drawing with the graphics card; usable only where it can work."""
        ok, why = gpu.support(self.hardware)
        on = self.canvas.gpu
        box = self.header.plank.gpu
        for w in (box, self.act_gpu):
            w.blockSignals(True)
            w.setChecked(on)
            w.setEnabled(ok or on)
            w.blockSignals(False)
        if on:
            box.setToolTip("The graphics card draws the plot (OpenGL). Untick to draw with the processor "
                           "(the program restarts in a few seconds; your scene stays as it is).")
        elif ok:
            box.setToolTip(f"Draw the plot with the graphics card: {why}\n"
                           "The program restarts in a few seconds; your scene stays as it is.")
        else:
            box.setToolTip(f"Graphics card drawing is not possible on this computer.\n{why}")
        self.act_gpu.setToolTip(box.toolTip())
        self.gpu_panel.set_mode(on, ok, why)
        self._place_gpu_panel()

    # ------------------------------------------------------------------ the box: switch = restart
    def gpu_box_changed(self, on: bool):
        """The user ticked / unticked GPU: remember it and start the program again at once (no question: nothing
        is lost, the restart takes a few seconds)."""
        on = bool(on)
        if on == self.canvas.gpu:
            self._update_gpu_controls()
            return
        if on:
            ok, why = gpu.support(self.hardware)
            if not ok:
                self._update_gpu_controls()
                self._notify_user("information", "Graphics card drawing", why)
                return
        before = gpu.enabled()
        gpu.set_enabled(on)
        if on:
            QSettings().remove(gpu.KEY_WEAK_TOLD)    # (a new try: the laptop help may come once more)
        log.info("graphics card drawing %s: restarting", "on" if on else "off")
        if not self.restart_program():
            gpu.set_enabled(before)                  # could not start again: everything stays as it was
            self._update_gpu_controls()

    # ------------------------------------------------------------------ the viewport (live)
    def set_gpu(self, on: bool, user: bool = False) -> bool:
        """Draw the plot with the graphics card (True) or the processor, in this running program (at the
        start; the tests and the benchmark). The box restarts instead (gpu_box_changed). user: a message if
        it cannot work. Returns whether it is on now."""
        on = bool(on)
        if on == self.canvas.gpu:
            self._update_gpu_controls()
            return on
        if on:
            ok, why = gpu.support(self.hardware)
            if not ok:
                self._update_gpu_controls()
                if user:
                    self._notify_user("information", "Graphics card drawing", why)
                return False
            self._gpu_guard.hold()                    # (before the first OpenGL call: a crash is noticed)
            self._gpu_frames = 0
            self._gpu_waited = 0
            self._gpu_fail_told = False
            try:
                vp = self.canvas.set_gpu(True, gpu.MSAA_SAMPLES)
                vp.ready.connect(self._gpu_ready)
                vp.failed.connect(self._gpu_failed, Qt.QueuedConnection)    # (not inside its own initializeGL)
                vp.frameSwapped.connect(self._gpu_frame)
                if vp.error:                              # (Qt may start it while it is put in place)
                    raise RuntimeError(vp.error)
            except Exception as exc:                      # noqa: BLE001 - never leaves the program broken
                log.exception("OpenGL viewport not made")
                self._gpu_failed(f"{type(exc).__name__}: {exc}")
                return False
            self.gpu_panel.set_card(None)
            if vp.info:
                self._gpu_ready(vp.info)
            self._gpu_timer.start()
            gpu.set_enabled(True)
            log.info("graphics card drawing on")
        else:
            self._gpu_timer.stop()
            self.canvas.set_gpu(False)
            self._gpu_guard.release()
            if user:
                gpu.set_enabled(False)
            log.info("graphics card drawing off")
        self._update_gpu_controls()
        self._apply_fps_cap()
        self._apply_limits()
        QTimer.singleShot(0, self, self._after_viewport_switch)
        return self.canvas.gpu

    def _after_viewport_switch(self):
        """Windows may give the window a new native handle when OpenGL joins: its title bar colour again."""
        tint_title_bar(self, self.theme)

    def _gpu_ready(self, info: dict):
        self.canvas.gpu_info = info
        self._gpu_weak = self._weak_card(info)
        self.gpu_panel.set_card(info, self._gpu_weak)
        self._place_gpu_panel()

    def _gpu_frame(self):
        self._gpu_frames += 1
        if self._gpu_frames == 2:                    # pictures arrive: started
            self._gpu_timer.stop()
            if self._gpu_weak is not None and not QSettings().value(gpu.KEY_WEAK_TOLD, False, bool):
                QSettings().setValue(gpu.KEY_WEAK_TOLD, True)
                QTimer.singleShot(600, self, self._still_on_weak_card)

    def _still_on_weak_card(self):
        """The card that draws is a laptop's power-saving one: NVIDIA was asked for at the start already (it
        did not work: the manual way), another faster card is offered."""
        strong = self._gpu_weak
        if strong is None or not self.isVisible():
            return
        nvidia_tried = hardware.vendor_of(strong["name"]) == "nvidia" and bool(
            os.environ.get(gpu.SHIM_ENV) or os.environ.get(gpu.RELAUNCH_ENV))
        if nvidia_tried:
            drawn = (self.canvas.gpu_info or {}).get("renderer", "the power-saving card")
            self._manual_switch_help(f"Windows still gives the program {drawn}, the power-saving card.")
        else:
            self.offer_strong_card()

    def _gpu_check_started(self):
        """Every CHECK_MS after switching on, until pictures come: no OpenGL context once the window could
        show one, or no picture after START_TIMEOUT_MS -> failed."""
        if not self.canvas.gpu or self._gpu_frames > 0:
            return
        if not self.isVisible() or self.isMinimized():
            self._gpu_timer.start()                  # nothing could be shown yet: wait
            return
        self._gpu_waited += CHECK_MS
        vp = self.canvas.plot.viewport()
        if not vp.isValid():
            vp.repaint()                             # (a busy start may not have painted yet: try it now)
        if not vp.isValid():
            self._gpu_failed(getattr(vp, "error", None) or "no OpenGL context could be made")
        elif self._gpu_waited >= START_TIMEOUT_MS:
            self._gpu_failed("no picture came from the graphics card")
        else:
            self._gpu_timer.start()

    def _gpu_failed(self, reason: str):
        """The OpenGL viewport did not work: back to the normal drawing (and say so)."""
        log.warning("graphics card drawing failed: %s", reason)
        if self.canvas.gpu:
            self._gpu_timer.stop()
            self.canvas.set_gpu(False)
        self._gpu_guard.release()
        gpu.set_enabled(False)
        self._update_gpu_controls()
        self._apply_fps_cap()
        self._apply_limits()
        if getattr(self, "_gpu_fail_told", False):
            return                                   # (one message per switch-on)
        self._gpu_fail_told = True
        QTimer.singleShot(0, self, lambda: self._notify_user(
            "warning", "Graphics card drawing did not start",
            f"The graphics card could not draw the plot ({reason}).\n\nThe program draws with the processor "
            "again; nothing was lost. Updating the graphics driver may help."))

    def gpu_redraw(self):
        """With the card: draw the whole plot anew (after the scene changed; a cheap safety net against a
        stale picture on some drivers)."""
        if getattr(self.canvas, "gpu", False):
            self.canvas.plot.viewport().update()

    # ------------------------------------------------------------------ the Graphics card panel
    def show_gpu_panel(self, on: bool):
        """The arrow beside the box (or View → Panels → Graphics card): the panel over the right part of the
        window, wherever the side panels are."""
        on = bool(on)
        for w in (self.header.plank.gpu_more, self.act_gpu_panel):
            if w.isChecked() != on:
                w.blockSignals(True)
                w.setChecked(on)
                w.blockSignals(False)
        plank = self.header.plank.gpu_more
        plank.setText("▴" if on else "▾")
        p = self.gpu_panel
        if on:
            self._apply_fps_cap()
            p.show()
            p.raise_()
            self._place_gpu_panel()
        else:
            p.hide()

    def _place_gpu_panel(self):
        """Hanging from the arrow beside the GPU box: its notch under the arrow, right edge near the window's,
        as tall as its contents (never below the status bar)."""
        p = getattr(self, "gpu_panel", None)
        if p is None or not p.isVisible():
            return
        arrow, plank = self.header.plank.gpu_more, self.header.plank
        a = arrow.mapTo(self, QPoint(arrow.width() // 2, arrow.height()))
        top = plank.mapTo(self, QPoint(0, plank.height())).y() - 3          # the notch reaches into the plank's edge
        right = min(self.width() - 6, a.x() + 36)
        bottom = self.height() - (self.statusBar().height() if self.statusBar().isVisible() else 0) - 8
        lay = p.layout()
        need = lay.totalHeightForWidth(p.width()) if lay.hasHeightForWidth() else lay.sizeHint().height()
        h = min(max(need, lay.minimumSize().height()) + 14, max(160, bottom - top))   # (+ rich text slack)
        p.setGeometry(right - p.width(), top, p.width(), h)
        p.notch_x = a.x() - (right - p.width())
        p.raise_()
        p.update()
        if getattr(self, "beaver", None) is not None:
            for w in (self.beaver.sprite, self.beaver.bubble):   # (the beaver stays in front)
                if w.isVisible():
                    w.raise_()

    # ------------------------------------------------------------------ frame rate limit
    def screen_hz(self) -> float:
        s = self.screen() if self.isVisible() else QApplication.primaryScreen()
        try:
            hz = float(s.refreshRate()) if s is not None else 60.0
        except Exception:                                 # noqa: BLE001
            hz = 60.0
        return hz if hz > 1 else 60.0

    def set_fps_cap(self, cap: str):
        """The animations' frame rate limit of the mode the program is in (each mode remembers its own)."""
        gpu.set_fps_cap(cap, self.canvas.gpu)
        self._apply_fps_cap()

    def _apply_fps_cap(self):
        hz = self.screen_hz()
        cap = gpu.fps_cap(self.canvas.gpu)
        self.gpu_panel.set_screen_hz(hz)
        self.gpu_panel.set_cap(cap)
        self.canvas.set_frame_interval(gpu.frame_ms(cap, hz))

    # ------------------------------------------------------------------ higher slider limits with the card
    def particles_max(self) -> int:
        """Particles → Count with the graphics card: as many as this computer moves in PARTICLE_BUDGET_MS per
        frame (measured once per computer), at least the processor's limit."""
        from ..canvas.settings import slider
        cpu = slider("particles").hi
        s = QSettings()
        fp = str((self.hardware or {}).get("fingerprint", ""))
        known = int(s.value("gpu/particles_max", 0) or 0)
        if known > 0 and s.value("gpu/particles_fp", "") == fp:
            return known
        try:
            from physics.particles import step_ms
            ms = step_ms(PARTICLE_PROBE)
            m = PARTICLE_PROBE * PARTICLE_BUDGET_MS / max(ms, 1e-3)
            log.info("particles: %d moved in %.2f ms -> up to %d with the graphics card", PARTICLE_PROBE, ms, m)
        except Exception:                                 # noqa: BLE001
            log.exception("particle timing failed")
            m = PARTICLE_PROBE
        m = int(min(max(int(m) // 5000 * 5000, cpu), PARTICLES_GPU_MAX))
        s.setValue("gpu/particles_max", m)
        s.setValue("gpu/particles_fp", fp)
        return m

    def gpu_limits(self) -> dict:
        """{slider key: upper end with the card} (gpu.GPU_LIMITS + the measured particles)."""
        return dict(gpu.GPU_LIMITS, particles=self.particles_max())

    def set_higher_limits(self, on: bool):
        gpu.set_higher_limits(on)
        self._apply_limits()

    def _apply_limits(self):
        """The sliders' upper ends for the mode: with the card (and Higher limits) further, with a mark at the
        processor's limit; without, the processor's. Values above come down (setting_changed / _limit_sliders)."""
        from ..canvas.settings import slider
        high = self.canvas.gpu and gpu.higher_limits()
        limits = self.gpu_limits()
        rows = []
        for key in self.settings_panel.sliders:
            spec = slider(key)
            hi = limits.get(key, spec.hi)
            self.settings_panel.set_slider_max(key, hi if high else spec.hi, spec.hi if high else None)
            if key in limits:
                rows.append((LIMIT_NAMES.get(key, key), self._limit_text(key, spec.hi),
                             self._limit_text(key, hi)))
        self.gpu_panel.set_limits(rows)
        self.gpu_panel.set_particles_max(limits.get("particles", slider("particles").hi))
        self._limit_sliders()
        self._place_gpu_panel()

    @staticmethod
    def _limit_text(key: str, position: int) -> str:
        from ..canvas.settings import slider
        v = slider(key).value(position)
        if key == "particles":
            return f"{int(v):,}".replace(",", " ")
        return f"{v:g}"

    def _limit_sliders(self):
        """No setting beyond its slider's end (also a scene saved with more, with the card or elsewhere)."""
        from ..canvas.settings import slider
        sp, cv = self.settings_panel, self.canvas
        for key, w in sp.sliders.items():
            spec = slider(key)
            if int(round((getattr(cv.settings, key) - spec.offset) / spec.step)) > w.maximum():
                getattr(cv, f"set_{key}")(spec.value(w.maximum()))

    # ------------------------------------------------------------------ the faster card (laptops)
    def _weak_card(self, info: dict) -> dict | None:
        """The fast card, when the plot is drawn by another one (a laptop's power-saving card)."""
        if not info:
            return None
        return hardware.runs_on_weak_card(info.get("renderer", ""), info.get("vendor", ""),
                                          (self.hardware or {}).get("adapters"))

    def offer_strong_card(self):
        """Ask: tell Windows to give the program the faster card, then restart."""
        strong = self._gpu_weak
        if strong is None:
            return
        answer = self._ask_strong_card(strong)
        if answer == "windows":
            self.open_graphics_settings()
        elif answer == "yes":
            self.switch_to_strong_card(strong)

    def _ask_strong_card(self, strong: dict) -> str:
        """"yes" (switch and restart), "windows" (open the Windows settings) or "no". (Tests replace it.)"""
        drawn = (self.canvas.gpu_info or {}).get("renderer", "the power-saving graphics card")
        box = QMessageBox(self)
        box.setWindowTitle("Use the faster graphics card?")
        box.setIcon(QMessageBox.Question)
        box.setTextFormat(Qt.RichText)
        box.setText(f"Windows lets this program draw with <b>{html.escape(drawn)}</b>, the power-saving card. "
                    f"This computer also has <b>{html.escape(strong['name'])}</b>, which is much faster.")
        box.setInformativeText("The program can ask Windows to always give it the faster card (the same setting "
                               "as Settings → Display → Graphics). The program then starts again; your scene "
                               "stays as it is.")
        b_yes = box.addButton(f"Use {short_name(strong['name'])} and restart", QMessageBox.AcceptRole)
        b_win = box.addButton("Windows settings…", QMessageBox.HelpRole)
        box.addButton("Not now", QMessageBox.RejectRole)
        box.setDefaultButton(b_yes)
        box.exec()
        clicked = box.clickedButton()
        box.deleteLater()
        return "yes" if clicked is b_yes else "windows" if clicked is b_win else "no"

    def switch_to_strong_card(self, strong: dict):
        done, message = gpu.ask_for_strong_card()
        if not done:
            self._manual_switch_help(message)
            return
        s = QSettings()
        s.setValue(gpu.KEY_SWITCHING, strong["name"])
        s.setValue(gpu.KEY_REPROBE, True)             # main.py: ask OpenGL again at the next start
        s.sync()
        if not self.restart_program():
            s.remove(gpu.KEY_SWITCHING)               # (not restarted: the setting stays for the next start)
            self.flash(f"Windows will use {short_name(strong['name'])} from the next start of the program.")

    def _gpu_check_switch(self):
        """After a restart for the faster card: did Windows do it?"""
        s = QSettings()
        wanted = s.value(gpu.KEY_SWITCHING, "")
        if not wanted:
            return
        s.remove(gpu.KEY_SWITCHING)
        gl = (self.hardware or {}).get("opengl") or {}
        if hardware.vendor_of(gl.get("renderer", "")) == hardware.vendor_of(str(wanted)):
            self.flash(f"The graphics card is now {gl.get('renderer')}.")
            log.info("faster graphics card in use: %s", gl.get("renderer"))
        else:
            self._manual_switch_help(f"Windows still gives the program {gl.get('renderer', 'the other card')}.")

    def _manual_switch_help(self, reason: str):
        if self._show_switch_help(reason):
            self.open_graphics_settings()

    def _show_switch_help(self, reason: str) -> bool:
        """How to choose the card in Windows by hand; True = open the Windows settings. (Tests replace it.)"""
        paths = "<br>".join(f"<code>{html.escape(p)}</code>" for p in gpu.program_paths())
        box = QMessageBox(self)
        box.setWindowTitle("Choose the graphics card in Windows")
        box.setIcon(QMessageBox.Information)
        box.setTextFormat(Qt.RichText)
        box.setText(f"{html.escape(reason)}<br><br>You can choose it in Windows yourself:<ol>"
                    "<li>Settings → System → Display → <b>Graphics</b></li>"
                    "<li><b>Add desktop app</b> (Browse) and choose:<br>" + paths + "</li>"
                    "<li>Click it → <b>Options</b> → <b>High performance</b> → Save</li>"
                    "<li>Start the program again.</li></ol>"
                    "Some computers set this in the NVIDIA Control Panel instead (Manage 3D settings → "
                    "Program Settings → High-performance NVIDIA processor).<br><br>Until then the program "
                    "draws with the power-saving card, which works too, only slower."
                    + ("<br><br><b>Note:</b> this Python comes from the Microsoft Store; Windows often cannot set "
                       "the graphics card for it. Python from python.org (or the program's own exe, later) "
                       "does not have this problem." if gpu.store_python() else ""))
        b_open = box.addButton("Open Windows settings", QMessageBox.AcceptRole)
        box.addButton("Close", QMessageBox.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        box.deleteLater()
        return clicked is b_open

    def open_graphics_settings(self):
        if not QDesktopServices.openUrl(QUrl(gpu.SETTINGS_URL)):
            self.flash("Open Settings → System → Display → Graphics.")

    # ------------------------------------------------------------------ restart
    def restart_program(self) -> bool:
        """Start the program again with everything as it is now (app/restart.py) and close this one, without
        the "unsaved changes" question (they come back unsaved). False if the new program could not start
        (then nothing happens)."""
        from .. import restart
        try:
            path = restart.write_state(self._document(), self.restart_state())
        except Exception as exc:                          # noqa: BLE001
            log.exception("restart state not written")
            self._notify_user("warning", "Cannot restart", f"The program could not prepare the restart ({exc}).")
            return False
        if not self._start_again(path):
            restart.discard(path)
            self._notify_user("warning", "Cannot restart",
                              "The program could not start itself again. Nothing has changed; you can close "
                              "it and start it yourself.")
            return False
        self._restarting = True
        self.close()
        return True

    def _start_again(self, path: str) -> bool:
        """(Tests replace it.)"""
        from .. import restart
        return restart.start_again(path)

    def restart_state(self) -> dict:
        """What a restart keeps besides the scene file (app/restart.py)."""
        sp = self.settings_panel
        return {"file": self.current_path, "title": self.scene_title, "modified": self.model.is_modified,
                "layers": {k: b.isChecked() for k, b in sp.layer_boxes.items()},
                "view_mode": self.canvas.view_mode, "selected": self.elements_panel.current_row(),
                "gpu_panel": self.gpu_panel.isVisible()}

    # ------------------------------------------------------------------ closing
    def _gpu_closing(self):
        self._gpu_closed = True
        self._gpu_timer.stop()
        self._gpu_guard.release()                  # closed normally: no crash to report next time
