from __future__ import annotations

import pygame

from game.entities.base import Entity


class MassEntity(Entity):
    """Entidad física: inputs en metros, render en píxeles."""

    _MIN_MASS = 1e-4
    PIXELS_PER_METER = 100.0  # escala global: 1m = 100px

    def __init__(
        self,
        pos: pygame.Vector2 | tuple[float, float] | None = None,
        *,
        mass: float = 1.0,  # kg
        velocity: pygame.Vector2 | tuple[float, float] | None = None,  # m/s
    ) -> None:
        self.pos = pygame.Vector2(pos) if pos is not None else pygame.Vector2(0, 0)
        self.mass = max(self._MIN_MASS, float(mass))

        # velocity interna en px/s
        self.velocity = (
            self._v2(velocity) * self.PIXELS_PER_METER if velocity else pygame.Vector2()
        )
        self._force_accumulator = pygame.Vector2()  # en "px-N": fuerza * PPM

    # -----------------------------
    # API FÍSICA (unidades reales)
    # -----------------------------
    def clear_forces(self) -> None:
        self._force_accumulator.update(0, 0)

    def apply_force(self, force: pygame.Vector2 | tuple[float, float]) -> None:
        """Force en Newtons (kg·m/s²)."""
        f = self._v2(force)
        self._force_accumulator += f * self.PIXELS_PER_METER

    def apply_acceleration(self, accel: pygame.Vector2 | tuple[float, float]) -> None:
        """Aceleración en m/s². (gravedad real, etc.)"""
        a = self._v2(accel)
        self._force_accumulator += a * self.mass * self.PIXELS_PER_METER

    def integrate(self, dt: float) -> None:
        if dt <= 0:
            self.clear_forces()
            return

        acceleration_px = self._force_accumulator / self.mass  # (m/s²)*PPM -> px/s²
        self.velocity += acceleration_px * dt
        self.pos += self.velocity * dt

        self.clear_forces()

    # -----------------------------
    # HELPERS DE CONTROL (baratos)
    # -----------------------------
    def clamp_velocity_x(self, max_speed_mps: float) -> None:
        """Limita vx usando unidades reales (m/s)."""
        vmax = float(max_speed_mps) * self.PIXELS_PER_METER
        if self.velocity.x > vmax:
            self.velocity.x = vmax
        elif self.velocity.x < -vmax:
            self.velocity.x = -vmax

    def apply_damping_x(self, damping_per_s: float) -> None:
        """
        Fricción lineal: F = -m * damping * v  (estable y barata).
        damping_per_s en 1/s.
        """
        d = float(damping_per_s)
        if d <= 0.0:
            return
        # v está en px/s; convertimos a m/s para calcular fuerza en N coherente
        vx_mps = self.velocity.x / self.PIXELS_PER_METER
        fx = -self.mass * d * vx_mps
        self.apply_force((fx, 0.0))

    @staticmethod
    def _v2(v) -> pygame.Vector2:
        if isinstance(v, pygame.Vector2):
            return pygame.Vector2(v)
        if isinstance(v, (tuple, list)) and len(v) == 2:
            return pygame.Vector2(float(v[0]), float(v[1]))
        return pygame.Vector2()
