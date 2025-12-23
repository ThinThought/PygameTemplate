from __future__ import annotations

from typing import ClassVar, Iterator

import pygame

from game.entities.base import AppLike
from game.entities.mass import MassEntity
from game.entities.collider import Platform


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
        size: float = 32.0,
        show_velocity: bool = True,
        show_label: bool = True,
    ) -> None:
        super().__init__(pos=pos, mass=mass, velocity=velocity)

        # OJO: aquí normalizamos, pero AUN ASÍ podemos ser pisados luego por runtime/editor.
        self.color = self._to_color(color, fallback=(76, 139, 245))
        self.outline_color = self._to_color(outline_color, fallback=(18, 44, 92))
        self.label_color = self._to_color(label_color, fallback=(255, 255, 255))

        self.size = max(4.0, float(size))
        self.show_velocity = bool(show_velocity)
        self.show_label = bool(show_label)

        self._runtime = None
        self._node_id: str | None = None
        self._environment_id: str | None = None
        self._prev_pos = pygame.Vector2(self.pos)
        self.grounded = False

    # ------------------------------------------------------------------
    def on_spawn(self, app: AppLike) -> None:
        self._bind_runtime(app)

    def on_despawn(self, app: AppLike) -> None:
        self._runtime = None
        self._node_id = None
        self._environment_id = None

    def update(self, app: AppLike, dt: float) -> None:
        self._bind_runtime(app)
        self.grounded = False
        self._apply_platform_collisions()

    def integrate(self, dt: float) -> None:
        self._prev_pos = pygame.Vector2(self.pos)
        super().integrate(dt)

    # ------------------------------------------------------------------
    def render(self, app: AppLike, screen: pygame.Surface) -> None:
        rect = self._cube_rect()
        center = rect.center

        # Blindaje: si alguien pisó self.color con un str, lo re-coercemos aquí.
        fill = self._to_color(
            getattr(self, "color", (76, 139, 245)), fallback=(76, 139, 245)
        )
        outline = self._to_color(
            getattr(self, "outline_color", (18, 44, 92)), fallback=(18, 44, 92)
        )

        pygame.draw.rect(screen, fill, rect, border_radius=4)
        pygame.draw.rect(screen, outline, rect, width=2, border_radius=4)

        if self.show_velocity:
            self._draw_velocity(screen, center, outline)

        if self.show_label:
            self._draw_mass_label(app, screen, center)

    # ------------------------------------------------------------------
    def _apply_platform_collisions(self) -> None:
        runtime = self._runtime
        env_id = self._environment_id

        if runtime is None or env_id is None:
            return

        platforms = list(self._iter_sibling_platforms())
        if not platforms:
            return

        cube = self._cube_rect()
        prev_cube = self._cube_rect(self._prev_pos)

        for platform in platforms:
            surface = pygame.Rect(platform.surface_rect())
            if not cube.colliderect(surface):
                continue

            curr_bottom = cube.bottom
            curr_top = cube.top
            prev_bottom = prev_cube.bottom
            prev_top = prev_cube.top

            if prev_bottom <= surface.top <= curr_bottom:
                self.pos.y = surface.top - self._half_size()
                cube = self._cube_rect()
                if self.velocity.y > 0:
                    self.velocity.y = 0
                    self.grounded = True
                continue

            if prev_top >= surface.bottom >= curr_top:
                self.pos.y = surface.bottom + self._half_size()
                cube = self._cube_rect()
                if self.velocity.y < 0:
                    self.velocity.y = 0
                    self.grounded = True

    def _iter_sibling_platforms(self) -> Iterator[Platform]:
        runtime = self._runtime
        env_id = self._environment_id
        if runtime is None or env_id is None:
            return iter(())

        node = runtime.nodes.get(env_id)
        if node is None:
            return iter(())

        def _gen() -> Iterator[Platform]:
            for child_id in node.children:
                if child_id == self._node_id:
                    continue
                child_node = runtime.nodes.get(child_id)
                if child_node is None:
                    continue
                instance = getattr(child_node, "instance", None)
                if isinstance(instance, Platform):
                    yield instance

        return _gen()

    def _bind_runtime(self, app: AppLike) -> None:
        scene = getattr(app, "scene", None)
        runtime = getattr(scene, "runtime", None)
        if runtime is None:
            self._runtime = None
            self._node_id = None
            self._environment_id = None
            return

        for node in runtime.iter_nodes("entity"):
            if node.instance is self:
                self._runtime = runtime
                self._node_id = node.id
                self._environment_id = node.parent
                return

        self._runtime = None
        self._node_id = None
        self._environment_id = None

    def _cube_rect(self, pos: pygame.Vector2 | None = None) -> pygame.Rect:
        center = pos if pos is not None else self.pos
        half = self._half_size()
        left = center.x - half
        top = center.y - half
        size = int(round(self.size))
        if size <= 0:
            size = 1
        return pygame.Rect(int(round(left)), int(round(top)), size, size)

    def _half_size(self) -> float:
        return max(0.5, self.size * 0.5)

    def _draw_velocity(
        self,
        screen: pygame.Surface,
        center: tuple[int, int],
        outline: pygame.Color,
    ) -> None:
        if self.velocity.length_squared() <= 1e-6:
            return

        direction = pygame.Vector2(self.velocity)
        try:
            direction = direction.normalize()
        except ValueError:
            return

        tip = pygame.Vector2(center) + direction * (self._half_size() + 16)
        pygame.draw.line(screen, outline, center, tip, 2)

    def _draw_mass_label(
        self, app: AppLike, screen: pygame.Surface, center: tuple[int, int]
    ) -> None:
        font = getattr(app, "hud_font", None) or self._get_label_font()

        # Blindaje otra vez por si label_color fue pisado
        label = self._to_color(
            getattr(self, "label_color", (255, 255, 255)), fallback=(255, 255, 255)
        )

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
                return pygame.Color(
                    cls._clamp8(c.r),
                    cls._clamp8(c.g),
                    cls._clamp8(c.b),
                    cls._clamp8(c.a),
                )

            if isinstance(value, str):
                c = pygame.Color(value)  # falla si el nombre no existe
                return pygame.Color(
                    cls._clamp8(c.r),
                    cls._clamp8(c.g),
                    cls._clamp8(c.b),
                    cls._clamp8(c.a),
                )

            if isinstance(value, (tuple, list)):
                if len(value) == 3:
                    r, g, b = value
                    return pygame.Color(cls._clamp8(r), cls._clamp8(g), cls._clamp8(b))
                if len(value) == 4:
                    r, g, b, a = value
                    return pygame.Color(
                        cls._clamp8(r), cls._clamp8(g), cls._clamp8(b), cls._clamp8(a)
                    )

        except (ValueError, TypeError):
            pass

        fr, fg, fb = fallback
        return pygame.Color(cls._clamp8(fr), cls._clamp8(fg), cls._clamp8(fb))
