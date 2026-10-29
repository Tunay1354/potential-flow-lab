"""
graphics.py — part of MainWindow: drawing the plot with the graphics card (the GPU box in the header, View →
Draw with the graphics card, the Graphics card panel), safely.

    off on a first start; remembered (app/gpu.py)
    can be ticked only where OpenGL 2.0+ comes from a real graphics card (gpu.support; the box explains)
    on: the plot gets an OpenGL viewport (PlotCanvas.set_gpu) and the Graphics card panel opens
    no picture within START_TIMEOUT_MS (the window visible) or no OpenGL context -> back to the normal
        drawing, with a message; the box stays usable
    a program that ended abnormally while the graphics card drew (gpu.SessionGuard) -> the next start
        begins with the normal drawing and says why
    a laptop running the program on its power-saving card: offer the faster one (Windows setting +
        restart); after the restart the program checks whether Windows did it, else shows how by hand
"""
from __future__ import annotations

import html
import logging

from PySide6.QtCore import QProcess, QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QMessageBox

from .. import gpu, hardware
from ..chrome import tint_title_bar
from ..gpu_panel import short_name

log = logging.getLogger("pflab")

START_TIMEOUT_MS = 6000              # no frame shown this long after switching on (window visible): failed
CHECK_MS = 1500                      # looked at this often while starting; no OpenGL context by then: failed


class GraphicsMixin:

    # ------------------------------------------------------------------ build
    def _build_graphics(self):
        """The Graphics card panel (a side panel), the header box, the View menu action; then the
        remembered state (called once the menus and the layout exist)."""
        self._gpu_guard = gpu.SessionGuard()
        self._gpu_frames = 0
        self._gpu_weak = None                    # the faster card, while the program runs on the other one
        self._gpu_offer = False                  # offer the faster card when this switch-on succeeded
        self._gpu_timer = QTimer(self)
        self._gpu_timer.setSingleShot(True)
        self._gpu_timer.setInterval(CHECK_MS)
        self._gpu_waited = 0                     # ms the window was visible since switching on
        self._gpu_timer.timeout.connect(self._gpu_check_started)
        panel = self.gpu_panel
        panel.meter = self.canvas.plot.meter
        panel.set_cap(gpu.fps_cap())
        panel.cap_changed.connect(self.set_fps_cap)
        panel.switch_requested.connect(self.offer_strong_card)
        box = self.header.plank.gpu
        box.toggled.connect(lambda on: self.set_gpu(on))
        self.act_gpu.toggled.connect(lambda on: self.set_gpu(on))
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
            self.set_gpu(True, user=False)
        else:
            self.dock_gpu.hide()
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
            box.setToolTip("The graphics card draws the plot (OpenGL). Untick to draw with the processor.")
        elif ok:
            box.setToolTip(f"Draw the plot with the graphics card: {why}")
        else:
            box.setToolTip(f"Graphics card drawing is not possible on this computer.\n{why}")
        self.act_gpu.setToolTip(box.toolTip())
        self.dock_gpu.toggleViewAction().setEnabled(on)

    # ------------------------------------------------------------------ on / off
    def set_gpu(self, on: bool, user: bool = True) -> bool:
        """Draw the plot with the graphics card (True) or the processor. user: the box was ticked (a
        message if it cannot work, the faster card offered). Returns whether it is on now."""
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
            self._gpu_offer = user
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
            self._show_gpu_panel()
            gpu.set_enabled(True)
            log.info("graphics card drawing on")
        else:
            self._gpu_timer.stop()
            self.canvas.set_gpu(False)
            self._gpu_guard.release()
            self.dock_gpu.hide()
            if user:
                gpu.set_enabled(False)
            log.info("graphics card drawing off")
        self._apply_fps_cap()
        self._update_gpu_controls()
        QTimer.singleShot(0, self, self._after_viewport_switch)
        return self.canvas.gpu

    def _show_gpu_panel(self):
        """The Graphics card panel, only as tall as its contents (the panel above keeps the rest)."""
        d = self.dock_gpu
        d.show()
        QTimer.singleShot(0, self, self._fit_gpu_panel)

    def _fit_gpu_panel(self):
        d = self.dock_gpu
        if not d.isVisible():
            return
        need = d.titleBarWidget().sizeHint().height() + d.widget().sizeHint().height()
        # the room it does not need goes to the panel above it in the same column (usually Plot settings)
        same = [o for o in self._docks() if o is not d and o.isVisible() and not o.isFloating()
                and self.dockWidgetArea(o) == self.dockWidgetArea(d)
                and abs(o.geometry().center().x() - d.geometry().center().x()) < 40
                and o.geometry().bottom() <= d.geometry().top() + 2]
        if same:
            above = max(same, key=lambda o: o.geometry().bottom())
            self.resizeDocks([above, d], [above.height() + d.height() - need, need], Qt.Vertical)
        else:
            self.resizeDocks([d], [need], Qt.Vertical)

    def _after_viewport_switch(self):
        """Windows may give the window a new native handle when OpenGL joins: its title bar colour again."""
        tint_title_bar(self, self.theme)

    def _gpu_ready(self, info: dict):
        self.canvas.gpu_info = info
        self._gpu_weak = self._weak_card(info)
        self.gpu_panel.set_card(info, self._gpu_weak)

    def _gpu_frame(self):
        self._gpu_frames += 1
        if self._gpu_frames == 2:                    # pictures arrive: started
            self._gpu_timer.stop()
            if self._gpu_offer and self._gpu_weak is not None:
                self._gpu_offer = False
                QTimer.singleShot(300, self, self.offer_strong_card)

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
        self.dock_gpu.hide()
        gpu.set_enabled(False)
        self._update_gpu_controls()
        self._apply_fps_cap()
        if getattr(self, "_gpu_fail_told", False):
            return                                   # (one message per switch-on)
        self._gpu_fail_told = True
        QTimer.singleShot(0, self, lambda: self._notify_user(
            "warning", "Graphics card drawing did not start",
            f"The graphics card could not draw the plot ({reason}).\n\nThe program draws with the processor "
            "again; nothing was lost. Updating the graphics driver may help."))

    # ------------------------------------------------------------------ frame rate limit
    def screen_hz(self) -> float:
        s = self.screen() if self.isVisible() else QApplication.primaryScreen()
        try:
            hz = float(s.refreshRate()) if s is not None else 60.0
        except Exception:                                 # noqa: BLE001
            hz = 60.0
        return hz if hz > 1 else 60.0

    def set_fps_cap(self, cap: str):
        gpu.set_fps_cap(cap)
        self.gpu_panel.set_cap(gpu.fps_cap())
        self._apply_fps_cap()

    def _apply_fps_cap(self):
        hz = self.screen_hz()
        self.gpu_panel.set_screen_hz(hz)
        ms = gpu.frame_ms(gpu.fps_cap(), hz) if self.canvas.gpu else gpu.RASTER_FRAME_MS
        self.canvas.set_frame_interval(ms)

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
                               "as Settings → Display → Graphics). The program then starts again; if the scene "
                               "has unsaved changes you are asked to save them first.")
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
            s.remove(gpu.KEY_SWITCHING)               # (cancelled: the setting stays for the next start)
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
                    "Program Settings → High-performance NVIDIA processor).")
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
        """Close (unsaved changes: the usual question) and start the program again with the same scene
        file. False if the user cancelled closing."""
        if not self.close():
            return False
        program, args = gpu.restart_command(self.current_path)
        if not QProcess.startDetached(program, args):
            log.error("restart failed: %s %s", program, args)
            QMessageBox.warning(None, "Start the program again",
                                "The program could not start itself again. Please start it yourself.")
        return True

    # ------------------------------------------------------------------ closing
    def _gpu_closing(self):
        self._gpu_closed = True
        self._gpu_timer.stop()
        self._gpu_guard.release()                  # closed normally: no crash to report next time
