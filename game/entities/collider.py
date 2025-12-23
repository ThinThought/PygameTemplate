from __future__ import annotations

from collections import deque
from typing import Any
import weakref

import pygame

from game.entities.base import Entity, AppLike


class ColliderEntity(Entity):
    """
    Entidad invisible que representa una zona rectangular del escenario.

    - Se registra automáticamente en el entorno que la contiene.
    - No permite que colliders de distinta clase se solapen.
    - Los colliders de la misma clase se agrupan en un único rectángulo de
      cobertura para que puedan comportarse como una sola plataforma.
    """

    _spaces: weakref.WeakKeyDictionary[Any, _ColliderSpace] = (
        weakref.WeakKeyDictionary()
    )

    def __init__(
        self,
        pos: pygame.Vector2 | tuple[float, float] | None = None,
        *,
        size: pygame.Vector2 | tuple[float, float] | None = None,
        collider_offset: pygame.Vector2 | tuple[float, float] | None = None,
        visible: bool = False,
        debug_outline_color: pygame.Color | str | tuple[int, int, int] = (40, 146, 255),
        debug_fill_color: pygame.Color | str | tuple[int, int, int, int] = (
            40,
            146,
            255,
            60,
        ),
    ) -> None:
        self.pos = pygame.Vector2(pos) if pos is not None else pygame.Vector2(0, 0)
        self.size = self._coerce_size(size)
        self._collider_offset = self._coerce_offset(collider_offset)

        self.visible = bool(visible)
        self._debug_outline_color = pygame.Color(0, 0, 0)
        self._debug_fill_color = pygame.Color(0, 0, 0, 0)
        self._debug_outline_fallback: tuple[int, int, int] = (40, 146, 255)
        self._debug_fill_fallback: tuple[int, int, int, int] = (40, 146, 255, 60)
        self.debug_outline_color = debug_outline_color
        self.debug_fill_color = debug_fill_color

        self._space: _ColliderSpace | None = None
        self._runtime = None
        self._node_id: str | None = None
        self._environment: Any | None = None
        self._group_rect: pygame.Rect | None = None

    # ------------------------------------------------------------------
    def on_spawn(self, app: AppLike) -> None:
        self._ensure_space(app)

    def on_despawn(self, app: AppLike) -> None:
        if self._space:
            self._space.unregister(self)
        self._space = None
        self._runtime = None
        self._node_id = None
        self._environment = None
        self._group_rect = None

    def update(self, app: AppLike, dt: float) -> None:
        if self._space is None:
            self._ensure_space(app)

    def render(self, app: AppLike, screen: pygame.Surface) -> None:
        if not self.visible:
            return

        pygame.draw.rect(screen, self.debug_fill_color, self.rect, border_radius=4)
        pygame.draw.rect(
            screen, self.debug_outline_color, self.rect, width=1, border_radius=4
        )

    # ------------------------------------------------------------------
    @property
    def debug_outline_color(self) -> pygame.Color:
        return self._debug_outline_color

    @debug_outline_color.setter
    def debug_outline_color(
        self, value: pygame.Color | str | tuple[int, int, int]
    ) -> None:
        color = self._to_color(value, self._debug_outline_fallback)
        self._debug_outline_color = color
        self._debug_outline_fallback = (color.r, color.g, color.b)

    @property
    def debug_fill_color(self) -> pygame.Color:
        return self._debug_fill_color

    @debug_fill_color.setter
    def debug_fill_color(
        self, value: pygame.Color | str | tuple[int, int, int, int]
    ) -> None:
        color = self._to_color(value, self._debug_fill_fallback)
        self._debug_fill_color = color
        self._debug_fill_fallback = (color.r, color.g, color.b, color.a)

    # ------------------------------------------------------------------
    @property
    def rect(self) -> pygame.Rect:
        """Devuelve el rectángulo base del collider (en píxeles)."""
        half = self.size * 0.5
        center = self.pos + self._collider_offset
        top_left = center - half
        width = max(1, int(round(self.size.x)))
        height = max(1, int(round(self.size.y)))
        return pygame.Rect(
            int(round(top_left.x)), int(round(top_left.y)), width, height
        )

    @property
    def coverage_rect(self) -> pygame.Rect:
        """
        Rectángulo combinado con otros colliders de la misma clase.

        Si no hay vecinos, coincide con rect.
        """
        if self._group_rect is None:
            return self.rect
        return pygame.Rect(self._group_rect)

    def overlaps(self, other: ColliderEntity) -> bool:
        return self.rect.colliderect(other.rect)

    def notify_bounds_changed(self) -> None:
        """
        Recalcula restricciones tras modificar tamaño/posición.
        Debe llamarse cuando se cambian manualmente pos o size.
        """
        if self._space:
            self._space.revalidate(self)

    # ------------------------------------------------------------------
    @property
    def collider_offset(self) -> pygame.Vector2:
        return pygame.Vector2(self._collider_offset)

    @collider_offset.setter
    def collider_offset(self, value: pygame.Vector2 | tuple[float, float]) -> None:
        self._collider_offset = self._coerce_offset(value)
        self.notify_bounds_changed()

    # ------------------------------------------------------------------
    def _ensure_space(self, app: AppLike) -> None:
        if self._space is not None:
            return

        self._bind_runtime(app)
        if self._environment is None:
            return

        space = self._spaces.get(self._environment)
        if space is None:
            space = _ColliderSpace()
            self._spaces[self._environment] = space

        space.register(self)
        self._space = space

    def _bind_runtime(self, app: AppLike) -> None:
        scene = getattr(app, "scene", None)
        runtime = getattr(scene, "runtime", None)
        if runtime is None:
            self._runtime = None
            self._node_id = None
            self._environment = None
            return

        for node in runtime.iter_nodes("entity"):
            if node.instance is self:
                self._runtime = runtime
                self._node_id = node.id
                parent = runtime.nodes.get(node.parent) if node.parent else None
                self._environment = parent.instance if parent is not None else None
                return

        self._runtime = None
        self._node_id = None
        self._environment = None

    def _set_group_rect(self, rect: pygame.Rect | None) -> None:
        self._group_rect = pygame.Rect(rect) if rect is not None else None

    @staticmethod
    def _coerce_size(
        size: pygame.Vector2 | tuple[float, float] | None,
    ) -> pygame.Vector2:
        if isinstance(size, pygame.Vector2):
            dims = pygame.Vector2(size)
        elif isinstance(size, (tuple, list)) and len(size) == 2:
            dims = pygame.Vector2(float(size[0]), float(size[1]))
        else:
            dims = pygame.Vector2(120, 32)
        dims.x = max(1.0, float(dims.x))
        dims.y = max(1.0, float(dims.y))
        return dims

    @staticmethod
    def _coerce_offset(
        offset: pygame.Vector2 | tuple[float, float] | None,
    ) -> pygame.Vector2:
        if isinstance(offset, pygame.Vector2):
            return pygame.Vector2(offset)
        if isinstance(offset, (tuple, list)) and len(offset) == 2:
            return pygame.Vector2(float(offset[0]), float(offset[1]))
        return pygame.Vector2(0.0, 0.0)

    @staticmethod
    def _to_color(
        value, fallback: tuple[int, int, int] | tuple[int, int, int, int]
    ) -> pygame.Color:
        try:
            if isinstance(value, pygame.Color):
                return pygame.Color(value)
            if isinstance(value, str):
                text = value.strip()
                literal = ColliderEntity._parse_color_literal(text)
                if literal is not None:
                    return pygame.Color(*literal)
                return pygame.Color(text)
            if isinstance(value, (tuple, list)):
                return pygame.Color(*value)
        except (ValueError, TypeError):
            pass
        return pygame.Color(*fallback)

    @staticmethod
    def _parse_color_literal(text: str) -> tuple[int, ...] | None:
        if not text.lower().startswith("color(") or not text.endswith(")"):
            return None
        inner = text[text.find("(") + 1 : -1]
        parts = [part.strip() for part in inner.split(",") if part.strip()]
        if len(parts) not in (3, 4):
            return None
        components: list[int] = []
        for part in parts:
            try:
                value = ColliderEntity._clamp_color_component(float(part))
            except ValueError:
                return None
            components.append(value)
        return tuple(components)

    @staticmethod
    def _clamp_color_component(value: float) -> int:
        return max(0, min(255, int(round(value))))


class Platform(ColliderEntity):
    """
    Collider especializado en modelar plataformas.

    Por defecto es invisible pero puede mostrar su zona de contacto si
    `visible=True`. Utiliza coverage_rect como superficie efectiva, por lo
    que varias plataformas iguales pueden fusionarse.
    """

    def __init__(
        self,
        pos: pygame.Vector2 | tuple[float, float] | None = None,
        *,
        size: pygame.Vector2 | tuple[float, float] | None = None,
        collider_offset: pygame.Vector2 | tuple[float, float] | None = None,
        friction: float = 0.85,
        grip: float = 1.0,
        visible: bool = False,
    ) -> None:
        super().__init__(
            pos,
            size=size if size is not None else (200, 24),
            collider_offset=collider_offset,
            visible=visible,
            debug_outline_color=(32, 170, 116),
            debug_fill_color=(32, 170, 116, 70),
        )
        self.friction = max(0.0, float(friction))
        self.grip = max(0.0, float(grip))

    def surface_rect(self) -> pygame.Rect:
        """Devuelve el área útil final de la plataforma."""
        return self.coverage_rect


class _ColliderSpace:
    """
    Gestiona los colliders que cuelgan de un mismo entorno.
    """

    def __init__(self) -> None:
        self._by_class: dict[type[ColliderEntity], set[ColliderEntity]] = {}

    def register(self, collider: ColliderEntity) -> None:
        self._check_cross_class_overlap(collider)
        colliders = self._by_class.setdefault(collider.__class__, set())
        colliders.add(collider)
        self._recompute_groups(collider.__class__)

    def unregister(self, collider: ColliderEntity) -> None:
        colliders = self._by_class.get(collider.__class__)
        if not colliders:
            return
        if collider in colliders:
            colliders.remove(collider)
            collider._set_group_rect(None)
        if colliders:
            self._recompute_groups(collider.__class__)
        else:
            self._by_class.pop(collider.__class__, None)

    def revalidate(self, collider: ColliderEntity) -> None:
        self._check_cross_class_overlap(collider)
        if collider.__class__ in self._by_class:
            self._recompute_groups(collider.__class__)

    def _check_cross_class_overlap(self, collider: ColliderEntity) -> None:
        for other_cls, colliders in self._by_class.items():
            if other_cls is collider.__class__:
                continue
            for other in colliders:
                if collider.overlaps(other):
                    raise ValueError(
                        f"Collider {collider.__class__.__name__} se solapa con {other.__class__.__name__}; "
                        "solo colliders de la misma clase pueden compartir espacio."
                    )

    def _recompute_groups(self, cls: type[ColliderEntity]) -> None:
        colliders = list(self._by_class.get(cls, ()))
        visited: set[ColliderEntity] = set()
        for collider in colliders:
            if collider in visited:
                continue
            group = self._collect_group(collider, colliders)
            visited.update(group)

            iterator = iter(group)
            union_rect = next(iterator).rect.copy()
            for member in iterator:
                union_rect.union_ip(member.rect)

            for member in group:
                member._set_group_rect(union_rect)

    def _collect_group(
        self,
        seed: ColliderEntity,
        colliders: list[ColliderEntity],
    ) -> set[ColliderEntity]:
        group: set[ColliderEntity] = {seed}
        queue = deque([seed])
        while queue:
            current = queue.popleft()
            for candidate in colliders:
                if candidate in group:
                    continue
                if current.overlaps(candidate):
                    group.add(candidate)
                    queue.append(candidate)
        return group
