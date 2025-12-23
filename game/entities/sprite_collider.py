from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pygame
from game.entities.base import AppLike


class SpriteColliderMixin:
    """
    Mezcla utilitaria para entidades con sprite + collider rectangular.

    Calcula automáticamente el `collider_offset` para que el rectángulo quede
    dentro del sprite y gestiona la carga/cacheo del recurso visual.
    """

    SPRITE_PATH: ClassVar[str] = ""
    RENDER_SIZE: ClassVar[tuple[int, int] | None] = None
    COLLIDER_SIZE: ClassVar[pygame.Vector2] = pygame.Vector2(200, 32)
    # (0,0) => esquina superior izquierda, (1,1) => esquina inferior derecha.
    COLLIDER_ANCHOR: ClassVar[tuple[float, float]] = (0.5, 1.0)
    COLLIDER_OFFSET: ClassVar[pygame.Vector2 | tuple[float, float] | None] = None
    _surface_cache: ClassVar[dict[str, pygame.Surface]] = {}

    def __init__(
        self,
        pos: pygame.Vector2 | tuple[float, float] | None = None,
        *,
        show_collider: bool = False,
        **collider_kwargs,
    ) -> None:
        collider_kwargs = dict(collider_kwargs)
        collider_kwargs.setdefault("size", pygame.Vector2(self.COLLIDER_SIZE))
        collider_kwargs.setdefault("collider_offset", self._resolve_collider_offset())
        collider_kwargs.setdefault("visible", show_collider)
        super().__init__(pos, **collider_kwargs)
        self._sprite: pygame.Surface | None = None

    # ------------------------------------------------------------------
    def on_spawn(self, app: AppLike) -> None:
        super().on_spawn(app)
        self._sprite = self._ensure_sprite(app)

    def on_despawn(self, app: AppLike) -> None:
        super().on_despawn(app)
        self._sprite = None

    def render(self, app: AppLike, screen: pygame.Surface) -> None:
        sprite = self._sprite or self._ensure_sprite(app)
        if sprite is not None:
            rect = sprite.get_rect(center=(int(self.pos.x), int(self.pos.y)))
            screen.blit(sprite, rect)

        super().render(app, screen)

    # ------------------------------------------------------------------
    def _ensure_sprite(self, app: AppLike) -> pygame.Surface | None:
        key = self._cache_key()
        cached = self._surface_cache.get(key)
        if cached is not None:
            return cached

        sprite = self._load_sprite(app)
        if sprite is not None:
            self._surface_cache[key] = sprite
        return sprite

    def _cache_key(self) -> str:
        size = self.RENDER_SIZE or (-1, -1)
        return f"{self.__class__.__name__}:{self.SPRITE_PATH}:{int(size[0])}x{int(size[1])}"

    def _load_sprite(self, app: AppLike) -> pygame.Surface | None:
        path = self._resolve_asset_path(app)
        if path is None:
            print(
                f"[{self.__class__.__name__}] Ruta de asset inválida: {self.SPRITE_PATH!r}"
            )
            return None

        if not path.exists():
            print(f"[{self.__class__.__name__}] Sprite no encontrado: {path}")
            return None

        try:
            sprite = pygame.image.load(path.as_posix()).convert_alpha()
        except pygame.error as exc:
            print(f"[{self.__class__.__name__}] No se pudo cargar {path}: {exc}")
            return None

        if self.RENDER_SIZE is not None:
            width, height = self.RENDER_SIZE
            if width > 0 and height > 0:
                sprite = pygame.transform.smoothscale(sprite, (int(width), int(height)))

        return sprite

    @classmethod
    def _resolve_asset_path(cls, app: AppLike) -> Path | None:
        if not cls.SPRITE_PATH:
            return None

        candidate = Path(cls.SPRITE_PATH)
        if candidate.is_absolute():
            return candidate

        resources = getattr(app, "resources", None)
        if resources is not None and hasattr(resources, "path"):
            try:
                resolved = Path(resources.path(*candidate.parts))
                return resolved
            except TypeError:
                pass

        root = Path(__file__).resolve().parents[2] / "assets"
        return root / candidate

    # ------------------------------------------------------------------
    def _resolve_collider_offset(self) -> pygame.Vector2:
        if self.COLLIDER_OFFSET is not None:
            return pygame.Vector2(self.COLLIDER_OFFSET)
        return self._offset_from_anchor()

    def _offset_from_anchor(self) -> pygame.Vector2:
        if self.RENDER_SIZE is None:
            return pygame.Vector2(0, 0)

        anchor = self._clamped_anchor()
        sprite_size = pygame.Vector2(self.RENDER_SIZE)
        collider_size = pygame.Vector2(self.COLLIDER_SIZE)
        span = pygame.Vector2(
            max(0.0, sprite_size.x - collider_size.x),
            max(0.0, sprite_size.y - collider_size.y),
        )
        offset = pygame.Vector2(
            (anchor.x - 0.5) * span.x,
            (anchor.y - 0.5) * span.y,
        )
        return offset

    def _clamped_anchor(self) -> pygame.Vector2:
        raw = self.COLLIDER_ANCHOR
        if isinstance(raw, pygame.Vector2):
            anchor = pygame.Vector2(raw)
        elif isinstance(raw, (tuple, list)) and len(raw) == 2:
            anchor = pygame.Vector2(float(raw[0]), float(raw[1]))
        else:
            anchor = pygame.Vector2(0.5, 0.5)

        anchor.x = max(0.0, min(1.0, anchor.x))
        anchor.y = max(0.0, min(1.0, anchor.y))
        return anchor
