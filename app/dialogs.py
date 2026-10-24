"""
dialogs.py — parameter dialog generated automatically from an ElementSpec.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel,
                               QPushButton, QVBoxLayout)

from .element_specs import ElementSpec
from .icons import make_element_icon


class ElementDialog(QDialog):
    def __init__(self, spec: ElementSpec, theme: dict, editing=False, parent=None):
        super().__init__(parent)
        self.spec = spec
        self.theme = theme
        self.setWindowTitle(("Edit — " if editing else "Add — ") + spec.name)
        self.setMinimumWidth(430)
        self.widgets = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)

        # header: icon + title
        head = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(make_element_icon(spec.key, theme, 96).pixmap(40, 40))
        head.addWidget(icon)
        title = QLabel(("Edit " if editing else "Add ") + spec.name.lower())
        title.setObjectName("DialogTitle")
        head.addWidget(title, 1)
        lay.addLayout(head)

        desc = QLabel(spec.description)
        desc.setObjectName("Muted")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        formula = QLabel(spec.formula)
        formula.setObjectName("Formula")
        formula.setTextFormat(Qt.RichText)
        formula.setAlignment(Qt.AlignCenter)
        lay.addWidget(formula)

        # parameter fields
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(8)
        for p in spec.params:
            if p.choices:
                w = QComboBox()
                w.addItems(p.choices)
                w.setCurrentIndex(int(p.default))
            else:
                w = QDoubleSpinBox()
                w.setRange(p.minimum, p.maximum)
                w.setDecimals(p.decimals)
                w.setSingleStep(p.step)
                w.setValue(p.default)
                w.setMinimumWidth(150)
                if p.unit:
                    w.setSuffix(("" if p.unit == "°" else " ") + p.unit)
                w.valueChanged.connect(self._update_info)
            if p.tooltip:
                w.setToolTip(p.tooltip)
            self.widgets[p.key] = w
            sym = f"<b>{p.symbol}</b>&nbsp;&nbsp;" if p.symbol else ""
            lbl = QLabel(f"{sym}<span>{p.name}</span>")
            lbl.setTextFormat(Qt.RichText)
            form.addRow(lbl, w)
        lay.addLayout(form)

        # live info / validation line
        self.info = QLabel("")
        self.info.setTextFormat(Qt.RichText)
        self.info.setWordWrap(True)
        lay.addWidget(self.info)

        # buttons
        lay.addSpacing(4)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("Cancel")
        apply_ = QPushButton("Apply")
        apply_.setObjectName("Primary")
        apply_.setDefault(True)
        cancel.clicked.connect(self.reject)
        apply_.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(apply_)
        lay.addLayout(row)

        self._update_info()

    def _update_info(self):
        """Small live hints. In the real program: full validation from the physics class."""
        t = self.theme
        ok, bad = t["el_sector"], t["danger"]
        k = self.spec.key
        v = {key: w.value() for key, w in self.widgets.items() if isinstance(w, QDoubleSpinBox)}
        text = ""
        if k == "source":
            m = v["m"]
            text = ("→ <b>source</b> (fluid comes out)" if m > 0 else
                    "→ <b>sink</b> (fluid goes in)" if m < 0 else
                    f"<span style='color:{bad}'>m = 0 has no effect</span>")
        elif k == "vortex":
            g = v["Gamma"]
            text = ("→ rotates <b>counter-clockwise</b>" if g > 0 else
                    "→ rotates <b>clockwise</b>" if g < 0 else
                    f"<span style='color:{bad}'>Γ = 0 has no effect</span>")
        elif k == "sector":
            beta = v["theta2"] - v["theta1"]
            if beta <= 0 or beta > 360:
                text = f"<span style='color:{bad}'>Need 0° &lt; β = θ₂ − θ₁ ≤ 360°</span>"
            else:
                n = 180.0 / beta
                images = 180.0 / beta
                exact = abs(images - round(images)) < 1e-9
                text = (f"β = <b>{beta:.1f}°</b>,&nbsp; n = π/β = <b>{n:.3f}</b>"
                        + (f"<br><span style='color:{ok}'>β = π/{round(images)} → other elements can be "
                           f"added with exact wall images</span>" if exact else
                           "<br>β is not π/k → walls are not exact if other elements are added"))
        elif k == "uniform" and v["V"] == 0:
            text = f"<span style='color:{bad}'>V∞ = 0 has no effect</span>"
        self.info.setText(text)
        self.info.setVisible(bool(text))
