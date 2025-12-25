from __future__ import annotations

from pathlib import Path
from typing import Sequence

import pygame

from game.environments.base import Environment, AppLike


DEFAULT_LAYER_PATHS: tuple[str, ...] = ("images/backgrounds/bg1/bg_sky.png",)


class BackgroundEnvironment(Environment):
    """
    Environment que compone una imagen de fondo a partir de varias capas.

    Cada capa es una ruta relativa dentro de `assets/` y se mezcla en orden.
    La superficie resultante se inicializa con las dimensiones iniciales de la
    escena y se reescala automáticamente si el viewport cambia.
    """

    def __init__(
        self,
        pos: pygame.Vector2 | tuple[float, float] | None = None,
        *,
        layers: Sequence[str] | None = None,
        fill_color: str | tuple[int, int, int] | tuple[int, int, int, int] = "#0b0b0f",
    ) -> None:
        self.pos = pygame.Vector2(pos) if pos is not None else pygame.Vector2(0, 0)
        self.layers = list(layers) if layers is not None else list(DEFAULT_LAYER_PATHS)
        self.fill_color = fill_color

        self._surface: pygame.Surface | None = None
        self._surface_size: tuple[int, int] | None = None

    def on_spawn(self, app: AppLike) -> None:
        size = self._initial_scene_size(app)
        self._compose_background(app, size)

    def on_despawn(self, app: AppLike) -> None:
        self._surface = None
        self._surface_size = None

    def render(self, app: AppLike, screen: pygame.Surface) -> None:
        if self._surface is None or self._surface_size != screen.get_size():
            self._compose_background(app, screen.get_size())

        if self._surface is None:
            return

        screen.blit(self._surface, (0, 0))

    def _initial_scene_size(self, app: AppLike) -> tuple[int, int]:
        viewport_fn = getattr(app, "scene_viewport", None)
        if callable(viewport_fn):
            rect = viewport_fn()
            if rect is not None:
                return (max(0, int(rect.width)), max(0, int(rect.height)))

        screen = getattr(app, "screen", None)
        if screen is not None:
            return screen.get_size()

        cfg = getattr(app, "cfg", None)
        width = getattr(cfg, "width", 0) or 0
        height = getattr(cfg, "height", 0) or 0
        return (int(width), int(height))

    def _compose_background(self, app: AppLike, size: tuple[int, int]) -> None:
        width, height = size
        if width <= 0 or height <= 0:
            self._surface = None
            self._surface_size = None
            return

        composed = pygame.Surface(size, pygame.SRCALPHA)
        color = self._coerce_color(self.fill_color)
        if color is not None:
            composed.fill(color)

        for layer_path in self.layers:
            layer_surface = self._load_layer(layer_path, app, size)
            if layer_surface is None:
                continue
            composed.blit(layer_surface, (0, 0))

        self._surface = composed.convert_alpha()
        self._surface_size = size

    def _load_layer(
        self, layer_path: str, app: AppLike, size: tuple[int, int]
    ) -> pygame.Surface | None:
        resolved_path = self._resolve_layer_path(app, layer_path)
        if resolved_path is None:
            print(f"[BackgroundEnvironment] Ruta inválida para capa: {layer_path!r}")
            return None

        if not resolved_path.exists():
            print(f"[BackgroundEnvironment] Archivo no encontrado: {resolved_path}")
            return None

        try:
            image = pygame.image.load(resolved_path.as_posix()).convert_alpha()
        except pygame.error as exc:
            print(f"[BackgroundEnvironment] No se pudo cargar {resolved_path}: {exc}")
            return None

        if image.get_size() != size:
            image = pygame.transform.smoothscale(image, size)

        return image

    def _resolve_layer_path(self, app: AppLike, layer_path: str) -> Path | None:
        if not isinstance(layer_path, str) or not layer_path.strip():
            return None

        candidate = Path(layer_path)
        if candidate.is_absolute():
            return candidate

        resources = getattr(app, "resources", None)
        if resources is not None and hasattr(resources, "path"):
            try:
                return Path(resources.path(*candidate.parts))
            except TypeError:
                pass

        root = Path(__file__).resolve().parents[1] / "assets"
        return root / candidate

    @staticmethod
    def _coerce_color(
        value: str | tuple[int, int, int] | tuple[int, int, int, int] | None,
    ) -> tuple[int, int, int, int] | None:
        if value is None:
            return None
        try:
            color = pygame.Color(value)
            return (color.r, color.g, color.b, color.a)
        except (ValueError, TypeError):
            print(f"[BackgroundEnvironment] Color inválido: {value!r}")
            return None
