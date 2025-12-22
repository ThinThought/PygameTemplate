from __future__ import annotations

import math
from typing import ClassVar

import pygame

from game.entities.base import AppLike
from game.entities.mass import MassEntity


class VisibleMassEntity(MassEntity):
    """Entidad con masa que también se dibuja para poder verla en pantalla."""

    _label_font: ClassVar[pygame.font.Font | None] = None

    def __init__(
        self,
        pos: pygame.Vector2 | tuple[float, float] | None = None,
        *,
        mass: float = 1.0,
        velocity: pygame.Vector2 | tuple[float, float] | None = None,
        color: pygame.Color | str | tuple[int, int, int] = (76, 139, 245),
        outline_color: pygame.Color | str | tuple[int, int, int] = (18, 44, 92),
        label_color: pygame.Color | str | tuple[int, int, int] = (255, 255, 255),
        min_radius: float = 8.0,
        radius_scale: float = 12.0,
        show_velocity: bool = True,
        show_label: bool = True,
    ) -> None:
        super().__init__(pos=pos, mass=mass, velocity=velocity)

        # OJO: aquí normalizamos, pero AUN ASÍ podemos ser pisados luego por runtime/editor.
        self.color = self._to_color(color, fallback=(76, 139, 245))
        self.outline_color = self._to_color(outline_color, fallback=(18, 44, 92))
        self.label_color = self._to_color(label_color, fallback=(255, 255, 255))

        self.min_radius = max(1.0, float(min_radius))
        self.radius_scale = max(0.0, float(radius_scale))
        self.show_velocity = bool(show_velocity)
        self.show_label = bool(show_label)

    # ------------------------------------------------------------------
    def render(self, app: AppLike, screen: pygame.Surface) -> None:
        center = (int(self.pos.x), int(self.pos.y))
        radius = self._compute_radius()

        # Blindaje: si alguien pisó self.color con un str, lo re-coercemos aquí.
        fill = self._to_color(getattr(self, "color", (76, 139, 245)), fallback=(76, 139, 245))
        outline = self._to_color(getattr(self, "outline_color", (18, 44, 92)), fallback=(18, 44, 92))

        pygame.draw.circle(screen, fill, center, radius)
        pygame.draw.circle(screen, outline, center, radius, 2)

        if self.show_velocity:
            self._draw_velocity(screen, center, radius, outline)

        if self.show_label:
            self._draw_mass_label(app, screen, center)

    # ------------------------------------------------------------------
    def _compute_radius(self) -> int:
        scaled = math.sqrt(max(float(self.mass), self._MIN_MASS))
        radius = self.min_radius + scaled * self.radius_scale
        return max(1, int(radius))

    def _draw_velocity(
        self,
        screen: pygame.Surface,
        center: tuple[int, int],
        radius: int,
        outline: pygame.Color,
    ) -> None:
        if self.velocity.length_squared() <= 1e-6:
            return

        direction = pygame.Vector2(self.velocity)
        try:
            direction = direction.normalize()
        except ValueError:
            return

        tip = pygame.Vector2(center) + direction * (radius + 16)
        pygame.draw.line(screen, outline, center, tip, 2)

    def _draw_mass_label(self, app: AppLike, screen: pygame.Surface, center: tuple[int, int]) -> None:
        font = getattr(app, "hud_font", None) or self._get_label_font()

        # Blindaje otra vez por si label_color fue pisado
        label = self._to_color(getattr(self, "label_color", (255, 255, 255)), fallback=(255, 255, 255))

        text = font.render(f"{self.mass:.2f}", True, label)
        rect = text.get_rect(center=center)
        screen.blit(text, rect)

    @classmethod
    def _get_label_font(cls) -> pygame.font.Font:
        if cls._label_font is None:
            cls._label_font = pygame.font.Font(None, 18)
        return cls._label_font

    # ------------------------------------------------------------------
    @staticmethod
    def _clamp8(x: float | int) -> int:
        return max(0, min(255, int(x)))

    @classmethod
    def _to_color(
        cls,
        value,
        *,
        fallback: tuple[int, int, int] = (255, 0, 255),
    ) -> pygame.Color:
        """
        Convierte value a pygame.Color de forma robusta.
        Acepta pygame.Color, str, tuplas, listas, etc.
        Si llega basura, usa fallback.
        """
        try:
            if isinstance(value, pygame.Color):
                c = pygame.Color(value)
                return pygame.Color(cls._clamp8(c.r), cls._clamp8(c.g), cls._clamp8(c.b), cls._clamp8(c.a))

            if isinstance(value, str):
                c = pygame.Color(value)  # falla si el nombre no existe
                return pygame.Color(cls._clamp8(c.r), cls._clamp8(c.g), cls._clamp8(c.b), cls._clamp8(c.a))

            if isinstance(value, (tuple, list)):
                if len(value) == 3:
                    r, g, b = value
                    return pygame.Color(cls._clamp8(r), cls._clamp8(g), cls._clamp8(b))
                if len(value) == 4:
                    r, g, b, a = value
                    return pygame.Color(cls._clamp8(r), cls._clamp8(g), cls._clamp8(b), cls._clamp8(a))

        except (ValueError, TypeError):
            pass

        fr, fg, fb = fallback
        return pygame.Color(cls._clamp8(fr), cls._clamp8(fg), cls._clamp8(fb))
