"""
scene.py — the elements shown when the program starts.
Phase 2 replaces this with New / Open / Presets; for now it is the lifting cylinder
of the course notes:  V∞ = 1, doublet μ = 1 (a = √(μ/V∞) = 1), clockwise circulation 2.
"""
from physics import Doublet, Uniform, Vortex


def starter_scene():
    return [Uniform(V=1.0, alpha=0.0), Doublet(mu=1.0), Vortex(Gamma=-2.0)]
