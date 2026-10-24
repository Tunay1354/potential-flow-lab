"""
element_specs.py — description of every element type.

The parameter dialog, toolbar button and list entries are generated
automatically from these specs. Adding a new element type later means
adding ONE new entry here (and, in the real program, its physics class).

Notation follows the course notes:
  F(z) = phi + i psi,  w = dF/dz = u - i v,  Gamma > 0 counter-clockwise.
"""
from dataclasses import dataclass, field


@dataclass
class Param:
    key: str            # internal name
    symbol: str         # shown in the dialog, e.g. "m"
    name: str           # long name, e.g. "Strength"
    unit: str = ""      # e.g. "m²/s", "°"
    default: float = 0.0
    minimum: float = -1e6
    maximum: float = 1e6
    decimals: int = 3
    step: float = 0.1
    tooltip: str = ""
    choices: list = field(default_factory=list)   # 2 choices -> radio buttons, more -> combo box
    # Signed parameter: the user enters the MAGNITUDE and picks the sign with two radio buttons
    # (positive label, negative label). The dialog returns the signed value.
    sign_labels: tuple = ()
    sign_title: str = ""                          # label of the radio-button row, e.g. "Type"


@dataclass
class ElementSpec:
    key: str
    name: str
    color_key: str      # key in the theme palette
    description: str
    formula: str        # complex potential, shown in the dialog
    params: list


ELEMENT_SPECS = [
    ElementSpec(
        key="uniform", name="Uniform flow", color_key="el_uniform",
        description="Freestream of speed V∞ at angle α measured from the +x axis. "
                    "α = 90° gives a vertical flow.",
        formula="F(z) = V∞ e<sup>−iα</sup> z",
        params=[
            Param("V", "V∞", "Speed", "m/s", 1.0, 0.0, 1e4, tooltip="Freestream speed (≥ 0)"),
            Param("alpha", "α", "Angle", "°", 0.0, -360, 360, decimals=1, step=5,
                  tooltip="Flow direction measured from +x axis, counter-clockwise"),
        ]),
    ElementSpec(
        key="source", name="Source / sink", color_key="el_source",
        description="Strength |m| = volume flow rate per unit depth. A source pushes fluid out "
                    "(m > 0), a sink pulls it in (m < 0).",
        formula="F(z) = (m / 2π) log(z − z<sub>0</sub>)",
        params=[
            Param("m", "|m|", "Strength", "m²/s", 1.0, 0.0, 1e6,
                  tooltip="Magnitude of the strength; choose source or sink below",
                  sign_labels=("Source", "Sink"), sign_title="Type"),
            Param("x0", "x<sub>0</sub>", "Position x", "m", 0.0),
            Param("y0", "y<sub>0</sub>", "Position y", "m", 0.0),
        ]),
    ElementSpec(
        key="vortex", name="Vortex", color_key="el_vortex",
        description="Point vortex with circulation |Γ|. Counter-clockwise rotation is Γ > 0, "
                    "clockwise is Γ < 0 (course convention).",
        formula="F(z) = −i (Γ / 2π) log(z − z<sub>0</sub>)",
        params=[
            Param("Gamma", "|Γ|", "Circulation", "m²/s", 1.0, 0.0, 1e6,
                  tooltip="Magnitude of the circulation; choose the rotation below",
                  sign_labels=("Counter-clockwise", "Clockwise"), sign_title="Rotation"),
            Param("x0", "x<sub>0</sub>", "Position x", "m", 0.0),
            Param("y0", "y<sub>0</sub>", "Position y", "m", 0.0),
        ]),
    ElementSpec(
        key="doublet", name="Doublet", color_key="el_doublet",
        description="Doublet of strength μ (μ = mε/π). δ rotates the doublet axis; "
                    "δ = 0 is the orientation used in the course notes.",
        formula="F(z) = μ e<sup>iδ</sup> / (z − z<sub>0</sub>)",
        params=[
            Param("mu", "μ", "Strength", "m³/s", 1.0),
            Param("x0", "x<sub>0</sub>", "Position x", "m", 0.0),
            Param("y0", "y<sub>0</sub>", "Position y", "m", 0.0),
            Param("delta", "δ", "Orientation", "°", 0.0, -360, 360, decimals=1, step=5),
        ]),
    ElementSpec(
        key="sector", name="Sector (wedge) flow", color_key="el_sector",
        description="Flow inside a wedge with vertex z₀; the walls are at θ₁ and θ₂ and the opening angle "
                    "β = θ₂ − θ₁ is measured counter-clockwise (0° < β ≤ 360°). Only defined inside the wedge.",
        formula="F(z) = V [(z − z<sub>0</sub>) e<sup>−iθ₁</sup>]<sup>n</sup>,  n = π/β",
        params=[
            Param("V", "|V|", "Strength constant", "", 1.0, 0.0, 1e6,
                  tooltip="Magnitude of V; choose the flow direction below",
                  sign_labels=("θ₂ wall → θ₁ wall", "θ₁ wall → θ₂ wall"), sign_title="Direction"),
            Param("x0", "x<sub>0</sub>", "Vertex x", "m", 0.0),
            Param("y0", "y<sub>0</sub>", "Vertex y", "m", 0.0),
            Param("theta1", "θ<sub>1</sub>", "First wall angle", "°", 0.0, -360, 360, decimals=1, step=5),
            Param("theta2", "θ<sub>2</sub>", "Second wall angle", "°", 90.0, -360, 360, decimals=1, step=5),
        ]),
    ElementSpec(
        key="wall", name="Symmetry wall", color_key="el_wall",
        description="Straight impermeable wall (V·n = 0) enforced with the method of images. "
                    "Fluid exists only on the chosen side.",
        formula="F<sub>total</sub>(z) = F(z) + conj F(z*)",
        params=[
            Param("xw", "x<sub>w</sub>", "Point on wall x", "m", 0.0),
            Param("yw", "y<sub>w</sub>", "Point on wall y", "m", -1.5),
            Param("theta_w", "θ<sub>w</sub>", "Wall angle", "°", 0.0, -180, 180, decimals=1, step=5),
            Param("side", "", "Fluid side", "", 0, choices=["Left of wall direction",
                                                             "Right of wall direction"]),
        ]),
]

SPEC_BY_KEY = {s.key: s for s in ELEMENT_SPECS}
