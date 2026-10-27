"""
dialogs.py — the option dialogs of File → Export figure… and File → Export data (CSV)….
"""
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
                               QPushButton, QRadioButton, QSpinBox, QVBoxLayout, QWidget)

from ..chrome import themed_combo
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
