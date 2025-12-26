from .base import Scene
from .main import MainScene
from .editor import EditorScene
from .input_tester import InputTesterScene

SCENES = {
    "main": MainScene,
    "editor": EditorScene,
    "input_tester": InputTesterScene,
}

__all__ = ["MainScene", "EditorScene", "InputTesterScene"]
