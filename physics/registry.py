"""
registry.py — list of all available element types.

Each element class registers itself with the @register decorator. The GUI
(toolbar, dialogs) and save/load read this registry, so adding a new
element type never requires editing them.
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


def element_from_dict(data: dict) -> FlowElement:
    try:
        cls = ELEMENT_TYPES[data["type"]]
    except KeyError:
        raise ValueError(f"Unknown element type: {data.get('type')!r}") from None
    return cls.from_dict(data)
