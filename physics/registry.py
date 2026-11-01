"""
registry.py — all element types, by their TYPE key. Each element class registers itself with @register; the
palette, the dialogs and the scene files read ELEMENT_TYPES, so a new element type needs no change there.
"""
from __future__ import annotations

from .base import FlowElement

ELEMENT_TYPES: dict[str, type[FlowElement]] = {}


def register(cls: type[FlowElement]) -> type[FlowElement]:
    if not cls.TYPE:
        raise ValueError(f"{cls.__name__} has no TYPE")
    if cls.TYPE in ELEMENT_TYPES:
        raise ValueError(f"Element type '{cls.TYPE}' registered twice")
    ELEMENT_TYPES[cls.TYPE] = cls
    return cls
