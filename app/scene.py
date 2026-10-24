"""
scene.py — the scene shown at start-up and the Presets menu.

Each preset returns (elements, view) with view = ((xmin, xmax), (ymin, ymax)).
Phase 2b will store presets as JSON files in the same format as File → Save;
until then they are defined here.
"""
from physics import Doublet, Source, SymmetryWall, Uniform, Vortex


def starter_scene():
    """Lifting cylinder of the course notes: V∞ = 1, μ = 1 (a = 1), clockwise circulation 2."""
    return [Uniform(V=1.0, alpha=0.0), Doublet(mu=1.0), Vortex(Gamma=-2.0)]


WIDE = ((-4.0, 4.0), (-3.0, 3.0))

PRESETS = {
    "Non-lifting cylinder": lambda: ([Uniform(V=1.0), Doublet(mu=1.0)], WIDE),
    "Lifting (rotating) cylinder": lambda: (starter_scene(), WIDE),
    "Rankine half-body": lambda: ([Uniform(V=1.0), Source(m=2.0)], ((-3.0, 5.0), (-3.0, 3.0))),
    "Rankine oval": lambda: ([Uniform(V=1.0), Source(m=3.0, x0=-1.0), Source(m=-3.0, x0=1.0)], WIDE),
    "Corner flow (90° sector)": None,                                  # Phase 1d
    "—": None,
    "Source near a wall": lambda: ([SymmetryWall(yw=0.0), Source(m=2.0, y0=1.0)], ((-4.0, 4.0), (-1.0, 5.0))),
    "Vortex near a wall": lambda: ([SymmetryWall(yw=0.0), Vortex(Gamma=2.0, y0=1.0)], ((-4.0, 4.0), (-1.0, 5.0))),
    "Cylinder above the ground": lambda: ([SymmetryWall(yw=-1.6), Uniform(V=1.0), Doublet(mu=1.0)],
                                          ((-4.0, 4.0), (-2.2, 3.8))),
    "Source in a 90° corner (two walls)": lambda: (
        [SymmetryWall(xw=0.0, yw=0.0, side=0), SymmetryWall(xw=0.0, yw=0.0, theta_w=90.0, side=1),
         Source(m=2.0, x0=1.0, y0=1.0)],
        ((-0.5, 4.5), (-0.5, 4.0))),
    "Channel: uniform flow + source + vortex": lambda: (
        [SymmetryWall(yw=-1.0, side=0), SymmetryWall(yw=1.0, side=1), Uniform(V=1.0),
         Source(m=1.0, x0=-1.5, y0=0.3), Vortex(Gamma=1.0, x0=1.5, y0=-0.3)],
        ((-5.0, 5.0), (-1.6, 1.6))),
}
