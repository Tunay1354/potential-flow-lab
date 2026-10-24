"""
physics — the flow engine. Pure Python + NumPy, no GUI code here.

    from physics import Uniform, Source, Vortex, Doublet, compute_field
"""
from .base import FlowElement, Issue, ParamSpec
from .elements import Doublet, Source, Uniform, Vortex
from .field import (FieldResult, coincident_singularities, complex_potential, complex_velocity,
                    compute_field, make_grid, pressure_coefficient, reference_speed, velocity)
from .registry import ELEMENT_TYPES, element_from_dict, register

__all__ = [
    "FlowElement", "Issue", "ParamSpec",
    "Uniform", "Source", "Vortex", "Doublet",
    "FieldResult", "compute_field", "make_grid", "complex_velocity", "complex_potential",
    "velocity", "reference_speed", "pressure_coefficient", "coincident_singularities",
    "ELEMENT_TYPES", "element_from_dict", "register",
]
