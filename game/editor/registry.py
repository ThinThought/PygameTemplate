from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Literal, Sequence, Any

import pygame

PaletteKind = Literal["entity", "environment"]
Factory = Callable[[pygame.Vector2], Any]


@dataclass(frozen=True)
class PaletteItem:
    """Metadata de un elemento de la paleta del editor."""

    name: str
    factory: Factory
    kind: PaletteKind


class PaletteRegistry:
    """Agrupa tipos disponibles de entidades y entornos."""

    def __init__(
        self,
        entities: Sequence[PaletteItem],
        environments: Sequence[PaletteItem],
    ) -> None:
        self.entities = list(entities)
        self.environments = list(environments)

    def get_collection(self, kind: PaletteKind) -> list[PaletteItem]:
        return self.entities if kind == "entity" else self.environments

    def get_item(self, kind: PaletteKind, idx: int) -> PaletteItem | None:
        collection = self.get_collection(kind)
        if 0 <= idx < len(collection):
            return collection[idx]
        return None

    @classmethod
    def from_modules(
        cls, entities_mod: Any, environments_mod: Any
    ) -> "PaletteRegistry":
        return cls(
            list(_iter_items(entities_mod, "entity")),
            list(_iter_items(environments_mod, "environment")),
        )


def _iter_items(module: Any, kind: PaletteKind) -> Iterable[PaletteItem]:
    names = getattr(module, "__all__", [])
    for name in names:
        attr = getattr(module, name, None)
        if attr is None:
            continue
        yield PaletteItem(name=name, factory=attr, kind=kind)
