from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class WindowConfig:
    width: int
    height: int
    title: str
    fps: int


def load_window_config(path: Path) -> WindowConfig:
    data = tomllib.loads(path.read_text())
    w = data["window"]
    return WindowConfig(
        width=w["width"],
        height=w["height"],
        title=w["title"],
        fps=w["fps"],
    )
