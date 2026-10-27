"""
dialogs.py — the option dialogs of File → Export figure…, Export animation… and Export data (CSV)….
"""
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
                               QPushButton, QRadioButton, QSpinBox, QVBoxLayout, QWidget)

from ..chrome import themed_combo
from .animation import (ANIMATION_FORMATS, DURATIONS, FRAME_RATES, SCALES, VIDEO_BACKGROUNDS, frame_count,
                        missing_package)
from .data import DATASETS
from .figure import BACKGROUNDS, FORMATS, figure_size


class ExportFigureDialog(QDialog):
    """Format, resolution (PNG), background and colors of the exported figure."""

    def __init__(self, canvas, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export figure")
        self.canvas = canvas
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)
        title = QLabel("Export figure")
        title.setObjectName("DialogTitle")
        lay.addWidget(title)
        note = QLabel("The plot as shown (view, layers, selection), with its axes.")
        note.setObjectName("Muted")
        lay.addWidget(note)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(18)
        self.fmt_buttons = {}
        group = QButtonGroup(self)
        for key, text in FORMATS.items():
            b = QRadioButton(text)
            group.addButton(b)
            fmt_row.addWidget(b)
            self.fmt_buttons[key] = b
            b.toggled.connect(self._update)
        fmt_row.addStretch(1)
        form.addRow("Format", fmt_row)

        self.scale = themed_combo(QComboBox())
        for k in (1, 2, 3, 4):
            self.scale.addItem(f"{k}×", k)
        self.scale.currentIndexChanged.connect(self._update)
        self.size_label = QLabel("")
        self.size_label.setObjectName("Muted")
        res = QHBoxLayout()
        res.addWidget(self.scale)
        res.addWidget(self.size_label, 1)
        self.res_row = QWidget()
        self.res_row.setLayout(res)
        res.setContentsMargins(0, 0, 0, 0)
        form.addRow("Resolution", self.res_row)

        self.background = themed_combo(QComboBox())
        for key, text in BACKGROUNDS.items():
            self.background.addItem(text, key)
        form.addRow("Background", self.background)

        self.mirror = QCheckBox("Axes on all four sides (plot area centered)")
        self.mirror.setToolTip("The figure gets the same axis bar on the top and the right as on the bottom "
                               "and the left (only in the file; the screen does not change)")
        self.mirror_numbers = QCheckBox("with numbers and axis titles")
        self.mirror.toggled.connect(self._update)
        form.addRow("Frame", self.mirror)
        form.addRow("", self.mirror_numbers)

        self.light = QCheckBox("Light colors (for printing)")
        self.light.setToolTip("The dark theme is exported with the colors of the light theme")
        self.light.setVisible(canvas.theme["name"] != "light")
        form.addRow("", self.light)
        lay.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Export…")
        ok.setObjectName("Primary")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(ok)
        lay.addLayout(buttons)

        self.fmt_buttons.get(settings.get("format", "png"), self.fmt_buttons["png"]).setChecked(True)
        self.scale.setCurrentIndex(max(0, self.scale.findData(int(settings.get("scale", 2)))))
        self.background.setCurrentIndex(max(0, self.background.findData(settings.get("background", "paper"))))
        self.light.setChecked(bool(settings.get("light", True)))
        self.mirror.setChecked(bool(settings.get("mirror", True)))
        self.mirror_numbers.setChecked(bool(settings.get("mirror_numbers", True)))
        self._update()

    def fmt(self) -> str:
        return next(k for k, b in self.fmt_buttons.items() if b.isChecked())

    def options(self) -> dict:
        return {"format": self.fmt(), "scale": int(self.scale.currentData()),
                "background": self.background.currentData(),
                "light": self.light.isChecked() and self.light.isVisible(),
                "mirror": self.mirror.isChecked(), "mirror_numbers": self.mirror_numbers.isChecked()}

    def _update(self, *_):
        png = self.fmt() == "png" if any(b.isChecked() for b in self.fmt_buttons.values()) else True
        self.res_row.setEnabled(png)
        if hasattr(self, "mirror"):
            self.mirror_numbers.setEnabled(self.mirror.isChecked())
        s = figure_size(self.canvas)
        k = int(self.scale.currentData() or 1)
        self.size_label.setText(f"→ {s.width() * k} × {s.height() * k} px" if png
                                else "vector: sharp at any size")


class ExportDataDialog(QDialog):
    """Which tables to write, grid size of the field, CSV separator."""

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export data")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)
        title = QLabel("Export data (CSV)")
        title.setObjectName("DialogTitle")
        lay.addWidget(title)
        note = QLabel("Several tables are written as separate files: name_elements.csv, name_field.csv …")
        note.setObjectName("Muted")
        note.setWordWrap(True)
        lay.addWidget(note)
        chosen = settings.get("datasets", ["elements", "stagnation"])
        self.boxes = {}
        for key, text in DATASETS:
            c = QCheckBox(text)
            c.setChecked(key in chosen)
            c.toggled.connect(self._update)
            lay.addWidget(c)
            self.boxes[key] = c
        form = QFormLayout()
        self.grid = QSpinBox()
        self.grid.setRange(11, 1001)
        self.grid.setSingleStep(10)
        self.grid.setValue(int(settings.get("grid", 101)))
        self.grid.setSuffix("  points across")
        form.addRow("Field grid", self.grid)
        self.separator = themed_combo(QComboBox())
        self.separator.addItem("Comma  ,", ",")
        self.separator.addItem("Semicolon ;  decimal comma  (Excel with Turkish settings)", ";")
        self.separator.setCurrentIndex(max(0, self.separator.findData(settings.get("separator", ","))))
        form.addRow("Separator", self.separator)
        lay.addLayout(form)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        self.ok = QPushButton("Export…")
        self.ok.setObjectName("Primary")
        self.ok.setDefault(True)
        self.ok.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(self.ok)
        lay.addLayout(buttons)
        self._update()

    def options(self) -> dict:
        return {"datasets": [k for k, c in self.boxes.items() if c.isChecked()],
                "grid": self.grid.value(), "separator": self.separator.currentData()}

    def _update(self, *_):
        self.ok.setEnabled(any(c.isChecked() for c in self.boxes.values()))
        self.grid.setEnabled(self.boxes["field"].isChecked())


class ExportAnimationDialog(QDialog):
    """GIF or MP4, which animation, length, frame rate, resolution, background and colors."""
    VIEWS = {"particles": "Particles", "pulses": "Pulses along streamlines"}

    def __init__(self, canvas, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export animation")
        self.canvas = canvas
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)
        title = QLabel("Export animation")
        title.setObjectName("DialogTitle")
        lay.addWidget(title)
        note = QLabel("The animation as shown (view, layers), with its axes, recorded frame by frame:\n"
                      "it plays smoothly however fast this computer is.")
        note.setObjectName("Muted")
        lay.addWidget(note)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(18)
        self.fmt_buttons = {}
        group = QButtonGroup(self)
        for key, text in ANIMATION_FORMATS.items():
            b = QRadioButton(text)
            group.addButton(b)
            fmt_row.addWidget(b)
            self.fmt_buttons[key] = b
        fmt_row.addStretch(1)
        form.addRow("Format", fmt_row)

        self.view = themed_combo(QComboBox())
        for key, text in self.VIEWS.items():
            self.view.addItem(text, key)
        self.view.setToolTip("Which animation is recorded (the plot switches to it)")
        form.addRow("Animation", self.view)

        self.duration = themed_combo(QComboBox())
        for sec in DURATIONS:
            self.duration.addItem(f"{sec} s", sec)
        form.addRow("Length", self.duration)

        self.fps = themed_combo(QComboBox())
        form.addRow("Frame rate", self.fps)

        self.scale = themed_combo(QComboBox())
        self.size_label = QLabel("")
        self.size_label.setObjectName("Muted")
        res = QHBoxLayout()
        res.setContentsMargins(0, 0, 0, 0)
        res.addWidget(self.scale)
        res.addWidget(self.size_label, 1)
        form.addRow("Resolution", res)

        self.background = themed_combo(QComboBox())
        for key, text in VIDEO_BACKGROUNDS.items():
            self.background.addItem(text, key)
        form.addRow("Background", self.background)

        self.mirror = QCheckBox("Axes on all four sides (plot area centered)")
        self.mirror_numbers = QCheckBox("with numbers and axis titles")
        self.mirror.toggled.connect(self._update)
        form.addRow("Frame", self.mirror)
        form.addRow("", self.mirror_numbers)
        self.light = QCheckBox("Light colors")
        self.light.setToolTip("The dark theme is exported with the colors of the light theme")
        self.light.setVisible(canvas.theme["name"] != "light")
        form.addRow("", self.light)
        lay.addLayout(form)

        self.info = QLabel("")
        self.info.setObjectName("Muted")
        self.info.setWordWrap(True)
        lay.addWidget(self.info)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        self.ok = QPushButton("Export…")
        self.ok.setObjectName("Primary")
        self.ok.setDefault(True)
        self.ok.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(self.ok)
        lay.addLayout(buttons)

        self._settings = settings
        self.fmt_buttons.get(settings.get("format", "mp4"), self.fmt_buttons["mp4"]).setChecked(True)
        view = canvas.view_mode if canvas.animated else settings.get("view", "particles")
        self.view.setCurrentIndex(max(0, self.view.findData(view)))
        self.duration.setCurrentIndex(max(0, self.duration.findData(int(settings.get("seconds", 3)))))
        self.background.setCurrentIndex(max(0, self.background.findData(settings.get("background", "paper"))))
        self.light.setChecked(bool(settings.get("light", True)))
        self.mirror.setChecked(bool(settings.get("mirror", True)))
        self.mirror_numbers.setChecked(bool(settings.get("mirror_numbers", True)))
        self._fill_format_choices()
        for b in self.fmt_buttons.values():
            b.toggled.connect(self._format_changed)
        for c in (self.duration, self.fps, self.scale):
            c.currentIndexChanged.connect(self._update)
        self._update()

    def fmt(self) -> str:
        return next(k for k, b in self.fmt_buttons.items() if b.isChecked())

    def options(self) -> dict:
        return {"format": self.fmt(), "view": self.view.currentData(), "seconds": int(self.duration.currentData()),
                "fps": int(self.fps.currentData()), "scale": float(self.scale.currentData()),
                "background": self.background.currentData(),
                "light": self.light.isChecked() and self.light.isVisible(),
                "mirror": self.mirror.isChecked(), "mirror_numbers": self.mirror_numbers.isChecked()}

    def _format_changed(self, checked):
        if checked:
            self._fill_format_choices()
            self._update()

    def _fill_format_choices(self):
        """Frame rates and resolutions of the chosen format (the last choice of that format)."""
        fmt = self.fmt()
        saved = self._settings.get(fmt, {})
        for combo, values, unit, key, default in ((self.fps, FRAME_RATES[fmt], " fps", "fps", 25 if fmt == "gif" else 30),
                                                  (self.scale, SCALES[fmt], "×", "scale", 1 if fmt == "gif" else 2)):
            combo.blockSignals(True)
            combo.clear()
            for v in values:
                combo.addItem(f"{v:g}{unit}", v)
            combo.setCurrentIndex(max(0, combo.findData(saved.get(key, default))))
            combo.blockSignals(False)

    def _update(self, *_):
        if not self.fmt_buttons or self.scale.currentData() is None:
            return
        self.mirror_numbers.setEnabled(self.mirror.isChecked())
        s = figure_size(self.canvas)
        k = float(self.scale.currentData())
        w, h = int(round(s.width() * k)), int(round(s.height() * k))
        self.size_label.setText(f"→ {w - w % 2} × {h - h % 2} px")
        fmt = self.fmt()
        n = frame_count(self.duration.currentData(), self.fps.currentData())
        package = missing_package(fmt)
        if package:
            self.info.setText(f"⚠  {fmt.upper()} needs the Python package “{package}”:  pip install {package}")
        elif fmt == "gif":
            self.info.setText(f"{n} frames. GIF files are large (a few MB per second); "
                              "MP4 is about 10× smaller and sharper.")
        else:
            self.info.setText(f"{n} frames, H.264: plays in every browser, PowerPoint and phone.")
        self.ok.setEnabled(not package)
