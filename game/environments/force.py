from __future__ import annotations

from typing import Iterator

import pygame

from game.entities.mass import MassEntity
from game.environments.base import Environment, AppLike


class ForceEnvironment(Environment):
    """
    Propaga una fuerza constante (p.ej. gravedad) a sus entidades hijas con masa.
    """

    def __init__(
        self,
        pos: pygame.Vector2 | tuple[float, float] | None = None,
        *,
        direction: pygame.Vector2 | tuple[float, float] = (0, 1),
        magnitude: float = 9.81,
        auto_integrate: bool = True,
    ) -> None:
        self.pos = pygame.Vector2(pos) if pos is not None else pygame.Vector2(0, 0)
        self._direction = self._normalize(direction)
        self.magnitude = float(magnitude)
        self.auto_integrate = auto_integrate

        self._runtime = None
        self._node_id: str | None = None
        self._force_vec = self._direction * self.magnitude

    def on_spawn(self, app: AppLike) -> None:
        self._bind_runtime(app)

    def on_despawn(self, app: AppLike) -> None:
        self._runtime = None
        self._node_id = None

    def update(self, app: AppLike, dt: float) -> None:
        if self._runtime is None or self._node_id is None:
            self._bind_runtime(app)
            if self._runtime is None or self._node_id is None:
                return

        if self.magnitude != 0:
            self._force_vec = self._direction * self.magnitude
        else:
            self._force_vec = pygame.Vector2(0, 0)

        for entity in self._iter_child_mass_entities():
            # magnitude = m/s² (9.81) y direction normalizada
            entity.apply_acceleration(self._direction * self.magnitude)
            if self.auto_integrate:
                entity.integrate(dt)

    # --- Helpers ---------------------------------------------------------

    def set_direction(self, direction: pygame.Vector2 | tuple[float, float]) -> None:
        self._direction = self._normalize(direction)

    def set_magnitude(self, magnitude: float) -> None:
        self.magnitude = float(magnitude)

    def _bind_runtime(self, app: AppLike) -> None:
        scene = getattr(app, "scene", None)
        runtime = getattr(scene, "runtime", None)

        if runtime is None:
            self._runtime = None
            self._node_id = None
            return

        for node in runtime.iter_nodes():
            if node.instance is self:
                self._runtime = runtime
                self._node_id = node.id
                return

        self._runtime = None
        self._node_id = None

    def _iter_child_mass_entities(self) -> Iterator[MassEntity]:
        if self._runtime is None or self._node_id is None:
            return iter(())

        node = self._runtime.nodes.get(self._node_id)
        if node is None:
            return iter(())

        def _gen() -> Iterator[MassEntity]:
            for child_id in node.children:
                child_node = self._runtime.nodes.get(child_id)
                if child_node is None:
                    continue
                instance = child_node.instance
                if isinstance(instance, MassEntity):
                    yield instance

        return _gen()

    @staticmethod
    def _normalize(direction: pygame.Vector2 | tuple[float, float]) -> pygame.Vector2:
        vec = ForceEnvironment._coerce(direction)
        if vec.length_squared() == 0:
            return pygame.Vector2(0, 1)
        return vec.normalize()

    @staticmethod
    def _coerce(value: pygame.Vector2 | tuple[float, float]) -> pygame.Vector2:
        if isinstance(value, pygame.Vector2):
            return pygame.Vector2(value)
        if isinstance(value, (tuple, list)) and len(value) == 2:
            x, y = value
            if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                return pygame.Vector2(float(x), float(y))
        return pygame.Vector2(0, 1)
