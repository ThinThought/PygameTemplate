from __future__ import annotations

import pygame

from game.entities.base import Entity


class MassEntity(Entity):
    """Entidad física: inputs en metros, render en píxeles."""

    _MIN_MASS = 1e-4
    PIXELS_PER_METER = 100.0  # <-- escala global

    def __init__(
        self,
        pos: pygame.Vector2 | tuple[float, float] | None = None,
        *,
        mass: float = 1.0,                  # kg
        velocity: pygame.Vector2 | tuple[float, float] | None = None,  # m/s
    ) -> None:
        self.pos = pygame.Vector2(pos) if pos is not None else pygame.Vector2(0, 0)
        self.mass = max(self._MIN_MASS, float(mass))

        # velocity en px/s internamente
        self.velocity = self._v2(velocity) * self.PIXELS_PER_METER if velocity else pygame.Vector2()

        self._force_accumulator = pygame.Vector2()

    # -----------------------------
    # API FÍSICA (unidades reales)
    # -----------------------------
    def apply_force(self, force: pygame.Vector2 | tuple[float, float]) -> None:
        """Force en Newtons (kg·m/s²)."""
        f = self._v2(force)
        self._force_accumulator += f * self.PIXELS_PER_METER

    def apply_acceleration(self, accel: pygame.Vector2 | tuple[float, float]) -> None:
        """Aceleración en m/s² (gravedad real)."""
        a = self._v2(accel)
        self._force_accumulator += a * self.mass * self.PIXELS_PER_METER

    def integrate(self, dt: float) -> None:
        if dt <= 0:
            self._force_accumulator.update(0, 0)
            return

        acceleration_px = self._force_accumulator / self.mass
        self.velocity += acceleration_px * dt
        self.pos += self.velocity * dt

        self._force_accumulator.update(0, 0)

    # -----------------------------
    @staticmethod
    def _v2(v) -> pygame.Vector2:
        if isinstance(v, pygame.Vector2):
            return pygame.Vector2(v)
        if isinstance(v, (tuple, list)) and len(v) == 2:
            return pygame.Vector2(float(v[0]), float(v[1]))
        return pygame.Vector2()
