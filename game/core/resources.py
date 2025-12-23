from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Resources:
    root: Path

    def path(self, *parts: str) -> Path:
        return self.root.joinpath(*parts)
