"""
dialogs.py — parameter dialog generated automatically from an ElementSpec.

Field types (chosen from the Param description, nothing is hard-coded per element):
  * number                    -> spin box
  * signed number             -> spin box for the MAGNITUDE + two radio buttons for the sign
                                 (e.g. Source / Sink, Counter-clockwise / Clockwise)
  * 2 choices                 -> two radio buttons
  * 3+ choices                -> combo box

values() returns the signed values ready for the physics element; set_values() fills the
dialog from an existing element (used when editing). Both are used when the dialog is
connected to the model in Phase 2.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout,
                               QLabel, QPushButton, QRadioButton, QVBoxLayout, QWidget)

from .element_specs import ElementSpec
from .icons import make_element_icon


class _RadioPair(QWidget):
    """Two mutually exclusive radio buttons; one of them is always selected."""

    def __init__(self, labels, selected=0, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(18)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)              # never two selected at the same time
        for i, text in enumerate(labels):
            b = QRadioButton(text)
            b.setCursor(Qt.PointingHandCursor)
            self.group.addButton(b, i)
            lay.addWidget(b)
        lay.addStretch(1)
        self.group.button(selected).setChecked(True)   # never empty: something is selected at start

    def index(self) -> int:
        return self.group.checkedId()

    def set_index(self, i: int):
        self.group.button(int(i)).setChecked(True)


class ElementDialog(QDialog):
    def __init__(self, spec: ElementSpec, theme: dict, editing=False, parent=None, values: dict | None = None):
        super().__init__(parent)
        self.spec = spec
        self.theme = theme
        self.setWindowTitle(("Edit — " if editing else "Add — ") + spec.name)
        self.setMinimumWidth(440)
        self.widgets = {}        # key -> spin box / combo box / _RadioPair
        self.signs = {}          # key -> _RadioPair choosing the sign of a signed parameter

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)

        # header: icon + title
        head = QHBoxLayout()
        self.icon = QLabel()
        head.addWidget(self.icon)
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
            if p.choices and len(p.choices) == 2:
                w = _RadioPair(p.choices, int(p.default))
                w.group.idToggled.connect(lambda *_: self._update_info())
            elif p.choices:
                w = QComboBox()
                w.addItems(p.choices)
                w.setCurrentIndex(int(p.default))
            else:
                w = QDoubleSpinBox()
                w.setRange(p.minimum, p.maximum)
                w.setDecimals(p.decimals)
                w.setSingleStep(p.step)
                w.setValue(abs(p.default) if p.sign_labels else p.default)
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
            if p.sign_labels:
                pair = _RadioPair(p.sign_labels, 0 if p.default >= 0 else 1)
                pair.group.idToggled.connect(lambda *_: self._update_info())
                self.signs[p.key] = pair
                form.addRow(QLabel(p.sign_title), pair)
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

        if values:
            self.set_values(values)
        self._update_info()

    # ------------------------------------------------------------------ values
    def values(self) -> dict:
        """Parameter values as the physics element expects them (signed numbers, choice indices)."""
        out = {}
        for p in self.spec.params:
            w = self.widgets[p.key]
            if isinstance(w, _RadioPair):
                out[p.key] = w.index()
            elif isinstance(w, QComboBox):
                out[p.key] = w.currentIndex()
            else:
                val = w.value()
                if p.key in self.signs and self.signs[p.key].index() == 1:
                    val = -val
                out[p.key] = val
        return out

    def set_values(self, values: dict):
        """Fill the dialog from existing values (e.g. a sink with m = −3 -> |m| = 3 and 'Sink')."""
        for p in self.spec.params:
            if p.key not in values:
                continue
            val = values[p.key]
            w = self.widgets[p.key]
            if isinstance(w, _RadioPair):
                w.set_index(int(val))
            elif isinstance(w, QComboBox):
                w.setCurrentIndex(int(val))
            else:
                if p.key in self.signs:
                    self.signs[p.key].set_index(0 if val >= 0 else 1)
                    val = abs(val)
                w.setValue(val)
        self._update_info()

    # ------------------------------------------------------------------ live hints
    def _update_info(self):
        """Header icon follows the chosen sign; small live hints. Full validation comes from physics."""
        t = self.theme
        ok, bad = t["el_sector"], t["danger"]
        k = self.spec.key
        v = self.values()
        sign = -1 if any(pair.index() == 1 for pair in self.signs.values()) else 1
        self.icon.setPixmap(make_element_icon(k, t, 96, sign=sign).pixmap(40, 40))

        text = ""
        if k == "source":
            m = v["m"]
            text = (f"<span style='color:{bad}'>|m| = 0 has no effect</span>" if m == 0 else
                    f"→ <b>source</b>: fluid comes out, m = {m:+.3f}" if m > 0 else
                    f"→ <b>sink</b>: fluid goes in, m = {m:+.3f}")
        elif k == "vortex":
            g = v["Gamma"]
            text = (f"<span style='color:{bad}'>|Γ| = 0 has no effect</span>" if g == 0 else
                    f"→ rotates <b>counter-clockwise</b>, Γ = {g:+.3f}" if g > 0 else
                    f"→ rotates <b>clockwise</b>, Γ = {g:+.3f}")
        elif k == "sector":
            beta = (v["theta2"] - v["theta1"]) % 360.0          # same rule as physics: β in (0°, 360°]
            if beta <= 1e-9:
                beta = 360.0
            n = 180.0 / beta
            k_int = round(n)
            flow = ("fluid comes in along the θ₂ wall and leaves along the θ₁ wall" if v["V"] > 0 else
                    "fluid comes in along the θ₁ wall and leaves along the θ₂ wall" if v["V"] < 0 else
                    f"<span style='color:{bad}'>|V| = 0 has no effect</span>")
            text = f"β = <b>{beta:.4g}°</b>,&nbsp; n = π/β = <b>{n:.4g}</b>&nbsp; → {flow}"
            if beta >= 360.0 - 1e-9:
                text += "<br>β = 360°: flow around the tip of a semi-infinite plate (velocity → ∞ at the tip)"
            elif beta > 180.0:
                text += ("<br>β &gt; 180°: flow around a corner (velocity → ∞ at the vertex); "
                         "other elements cannot be added to it")
            elif abs(n - k_int) < 1e-9:
                text += (f"<br><span style='color:{ok}'>β = 180°/{k_int} → sources, vortices and doublets "
                         f"can be added inside the wedge (exact wall images)</span>")
            else:
                text += "<br>β is not 180°/k → other elements cannot be added inside the wedge"
        elif k == "uniform" and v["V"] == 0:
            text = f"<span style='color:{bad}'>V∞ = 0 has no effect</span>"
        self.info.setText(text)
        self.info.setVisible(bool(text))
