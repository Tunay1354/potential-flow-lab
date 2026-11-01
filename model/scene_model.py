"""
scene_model.py — the list of elements of the current scene, changed ONLY through commands.

Every change (add, edit, delete, hide, load a preset, ...) is a Command with do() and undo().
SceneModel keeps an undo and a redo stack, so every change can be undone. Elements are never
modified in place: a command replaces an element object by a new one, which makes undo exact.

Listeners (e.g. the main window) are called after every change with the index of the element
that should be selected afterwards (or None).

Merging: consecutive commands that say so (e.g. the many small moves while an element is dragged
on the plot) are merged into ONE undo step.
"""
from __future__ import annotations

import itertools
from typing import Callable

_ids = itertools.count(1)


class Command:
    """Base class. Subclasses implement do() / undo(); both return the index to select,
    −1 = select nothing, None = keep the current selection."""
    text = ""

    def __init__(self):
        self.id = next(_ids)

    def do(self, elements: list) -> int | None:
        raise NotImplementedError

    def undo(self, elements: list) -> int | None:
        raise NotImplementedError

    def merge(self, other: "Command") -> bool:
        """Absorb `other` (already executed) into this command. Return True if merged."""
        return False


class AddElement(Command):
    def __init__(self, element, index: int | None = None, text: str | None = None):
        super().__init__()
        self.element, self.index = element, index
        self.text = text or f"Add {element.NAME.lower()}"

    def do(self, elements):
        if self.index is None or self.index > len(elements):
            self.index = len(elements)
        elements.insert(self.index, self.element)
        return self.index

    def undo(self, elements):
        elements.pop(self.index)
        return min(self.index, len(elements) - 1) if elements else None


class RemoveElement(Command):
    def __init__(self, index: int, text: str | None = None):
        super().__init__()
        self.index, self.element = index, None
        self._text = text

    def do(self, elements):
        self.element = elements.pop(self.index)
        self.text = self._text or f"Delete {self.element.NAME.lower()}"
        return min(self.index, len(elements) - 1) if elements else None

    def undo(self, elements):
        elements.insert(self.index, self.element)
        return self.index


class ReplaceElement(Command):
    """Replace the element at `index` by `new` (edit, hide / show, move)."""

    def __init__(self, index: int, new, text: str | None = None, merge_key: str | None = None):
        super().__init__()
        self.index, self.new, self.old = index, new, None
        self.text = text or f"Edit {new.NAME.lower()}"
        self.merge_key = merge_key        # commands with the same key and index merge (e.g. "move")

    def do(self, elements):
        self.old = elements[self.index]
        elements[self.index] = self.new
        return self.index

    def undo(self, elements):
        elements[self.index] = self.old
        return self.index

    def merge(self, other):
        if (self.merge_key is not None and isinstance(other, ReplaceElement)
                and other.merge_key == self.merge_key and other.index == self.index):
            self.new = other.new          # keep our `old`, take their `new`
            return True
        return False


class ReplaceAll(Command):
    """Replace the whole scene (load a preset, clear all, open a file)."""

    def __init__(self, new_elements: list, text: str = "Replace scene"):
        super().__init__()
        self.new, self.old = list(new_elements), None
        self.text = text

    def do(self, elements):
        self.old = list(elements)
        elements[:] = self.new
        return -1                   # a whole new scene: nothing selected (None would keep the selection)

    def undo(self, elements):
        elements[:] = self.old
        return -1


class SceneModel:
    def __init__(self, elements=None, undo_limit: int = 200):
        self.elements: list = list(elements or [])     # the SAME list object for the whole session
        self._undo: list[Command] = []
        self._redo: list[Command] = []
        self._limit = undo_limit
        self._listeners: list[Callable] = []
        self._clean_id: int | None = None             # id of the top command when last saved

    # ------------------------------------------------------------------ listeners
    def subscribe(self, fn: Callable[[int | None], None]):
        self._listeners.append(fn)

    def _notify(self, focus):
        for fn in list(self._listeners):
            fn(focus)

    # ------------------------------------------------------------------ undo / redo
    def push(self, cmd: Command) -> int | None:
        focus = cmd.do(self.elements)
        if self._undo and self._undo[-1].merge(cmd):
            self._undo[-1].id = next(_ids)              # merged step differs from any saved state
        else:
            self._undo.append(cmd)
            if len(self._undo) > self._limit:
                self._undo.pop(0)
        self._redo.clear()
        self._notify(focus)
        return focus

    def undo(self):
        if not self._undo:
            return
        cmd = self._undo.pop()
        focus = cmd.undo(self.elements)
        self._redo.append(cmd)
        self._notify(focus)

    def redo(self):
        if not self._redo:
            return
        cmd = self._redo.pop()
        focus = cmd.do(self.elements)
        self._undo.append(cmd)
        self._notify(focus)

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def undo_text(self) -> str:
        return self._undo[-1].text if self._undo else ""

    @property
    def redo_text(self) -> str:
        return self._redo[-1].text if self._redo else ""

    # ------------------------------------------------------------------ saved / modified (File menu)
    def mark_modified(self):
        """Unsaved, whatever the history says (a scene carried over a restart that was not saved)."""
        self._clean_id = -1

    def mark_clean(self):
        self._clean_id = self._undo[-1].id if self._undo else None

    @property
    def is_modified(self) -> bool:
        return (self._undo[-1].id if self._undo else None) != self._clean_id

    # ------------------------------------------------------------------ convenience
    def add(self, element, index: int | None = None, text: str | None = None):
        return self.push(AddElement(element, index, text))

    def remove(self, index: int):
        self._check(index)
        return self.push(RemoveElement(index))

    def replace(self, index: int, new, text: str | None = None, merge_key: str | None = None):
        self._check(index)
        if new == self.elements[index]:
            return None                                 # nothing changed: no undo step
        return self.push(ReplaceElement(index, new, text, merge_key))

    def set_enabled(self, index: int, enabled: bool):
        self._check(index)
        el = self.elements[index]
        if el.enabled == enabled:
            return None
        verb = "Show" if enabled else "Hide"
        return self.push(ReplaceElement(index, el.copy(enabled=enabled), f"{verb} {el.NAME.lower()}"))

    def duplicate(self, index: int, offset: tuple[float, float] = (0.5, 0.5)):
        self._check(index)
        el = self.elements[index]
        return self.push(AddElement(el.translated(*offset), index + 1, f"Duplicate {el.NAME.lower()}"))

    def reset(self, elements):
        """Start a new document (File → New / Open): new elements, empty undo history, not modified."""
        self.elements[:] = list(elements)               # same list object (the GUI holds a reference)
        self._undo.clear()
        self._redo.clear()
        self.mark_clean()
        self._notify(-1)                                # nothing selected in a new document

    def load(self, elements, text: str = "Load scene"):
        return self.push(ReplaceAll(elements, text))

    def clear(self):
        if self.elements:
            return self.push(ReplaceAll([], "Clear all elements"))
        return None

    def _check(self, index):
        if not 0 <= index < len(self.elements):
            raise IndexError(f"No element at index {index}")
