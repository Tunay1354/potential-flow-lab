"""
model — the scene being edited (list of elements) with undo / redo.

Pure Python (no Qt), so it can be tested on its own and reused by other front ends.
"""
from .preview import candidate_scene, preview_change
from .scene_file import EXTENSION, SceneDocument, SceneFileError, load_scene, save_scene
from .scene_model import (AddElement, Command, RemoveElement, ReplaceAll, ReplaceElement, SceneModel)

__all__ = ["SceneModel", "Command", "AddElement", "RemoveElement", "ReplaceElement", "ReplaceAll",
           "preview_change", "candidate_scene",
           "SceneDocument", "SceneFileError", "load_scene", "save_scene", "EXTENSION"]
