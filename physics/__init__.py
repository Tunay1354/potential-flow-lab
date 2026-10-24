"""
physics — the flow engine. Pure Python + NumPy, no GUI code here.

    from physics import Uniform, Source, Vortex, Doublet, SymmetryWall, compute_field
"""
from .base import FlowElement, Issue, ParamSpec
from .elements import Doublet, SectorFlow, Source, SymmetryWall, Uniform, Vortex
from .field import (FieldResult, coincident_singularities, complex_potential, complex_velocity,
                    compute_field, make_grid, pressure_coefficient, reference_speed, velocity)
from .images import ImageSystem, build_image_system, resolve
from .registry import ELEMENT_TYPES, element_from_dict, register
from .validation import SceneIssue, check_scene, scene_is_valid

__all__ = [
    "FlowElement", "Issue", "ParamSpec",
    "Uniform", "Source", "Vortex", "Doublet", "SectorFlow", "SymmetryWall",
    "ImageSystem", "build_image_system", "resolve", "SceneIssue", "check_scene", "scene_is_valid",
    "FieldResult", "compute_field", "make_grid", "complex_velocity", "complex_potential",
    "velocity", "reference_speed", "pressure_coefficient", "coincident_singularities",
    "ELEMENT_TYPES", "element_from_dict", "register",
]
