from __future__ import annotations

from typing import ClassVar

import pygame

from game.entities.collider import Platform
from game.entities.sprite_collider import SpriteColliderMixin


class SpritePlatform(SpriteColliderMixin, Platform):
    """
    Plataforma basada en sprite que reutiliza la lógica de colisión de Platform.

    Define `SPRITE_PATH`, `RENDER_SIZE` y `COLLIDER_SIZE` para configurar la
    imagen asociada y dejar el collider dentro del sprite.
    """

    SPRITE_PATH: ClassVar[str] = ""
    RENDER_SIZE: ClassVar[tuple[int, int] | None] = None
    COLLIDER_SIZE: ClassVar[pygame.Vector2] = pygame.Vector2(200, 32)

    def __init__(
        self,
        pos: pygame.Vector2 | tuple[float, float] | None = None,
        *,
        show_collider: bool = False,
        **platform_kwargs,
    ) -> None:
        super().__init__(pos, show_collider=show_collider, **platform_kwargs)


class GrassSmallPlatform(SpritePlatform):
    """Plataforma corta de pasto."""

    SPRITE_PATH = "images/platforms/grass_platforms/small1.png"
    RENDER_SIZE = (192, 60)
    COLLIDER_SIZE = pygame.Vector2(175, 40)

    def __init__(
        self,
        pos: pygame.Vector2 | tuple[float, float] | None = None,
        *,
        show_collider: bool = False,
        **platform_kwargs,
    ) -> None:
        super().__init__(pos, show_collider=show_collider, **platform_kwargs)
        self.visible = False


class GrassWidePlatform(SpritePlatform):
    """Plataforma mediana con vegetación."""

    SPRITE_PATH = "images/platforms/grass_platforms/medium1.png"
    RENDER_SIZE = (256, 72)
    COLLIDER_SIZE = pygame.Vector2(230, 40)

    def __init__(
        self,
        pos: pygame.Vector2 | tuple[float, float] | None = None,
        *,
        show_collider: bool = False,
        **platform_kwargs,
    ) -> None:
        super().__init__(pos, show_collider=show_collider, **platform_kwargs)
        self.visible = False


class GrassLargePlatform(SpritePlatform):
    """Plataforma larga ideal para secciones horizontales."""

    SPRITE_PATH = "images/platforms/grass_platforms/large2.png"
    RENDER_SIZE = (320, 84)
    COLLIDER_SIZE = pygame.Vector2(300, 75)

    def __init__(
        self,
        pos: pygame.Vector2 | tuple[float, float] | None = None,
        *,
        show_collider: bool = False,
        **platform_kwargs,
    ) -> None:
        super().__init__(pos, show_collider=show_collider, **platform_kwargs)
        self.visible = False


class GrassFloorPlatform(SpritePlatform):
    """Segmento amplio que puede actuar como piso base."""

    SPRITE_PATH = "images/platforms/grass_platforms/floor.png"
    RENDER_SIZE = (720, 480)
    COLLIDER_SIZE = pygame.Vector2(720, 160)

    def __init__(
        self,
        pos: pygame.Vector2 | tuple[float, float] | None = None,
        *,
        show_collider: bool = False,
        **platform_kwargs,
    ) -> None:
        super().__init__(pos, show_collider=show_collider, **platform_kwargs)
        self.visible = False
