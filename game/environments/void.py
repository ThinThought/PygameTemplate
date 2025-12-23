from __future__ import annotations

import pygame

from game.environments.base import Environment, AppLike


class VoidEnvironment(Environment):
    """
    Environment utilitario sin efectos para anclar subárboles EEI.

    Funciona como contraparte del `VoidEntity`: permite colgar otros environments
    de una entidad invisible y, opcionalmente, puede mostrarse en pantalla para
    depurar posiciones o límites lógicos.
    """

    def __init__(
        self,
        pos: pygame.Vector2 | tuple[float, float] | None = None,
        *,
        visible: bool = False,
        radius: float = 24.0,
        color: pygame.Color | str | tuple[int, int, int] = (50, 50, 50),
        crosshair: bool = True,
    ) -> None:
        self.pos = pygame.Vector2(pos) if pos is not None else pygame.Vector2(0, 0)
        self.visible = bool(visible)
        self.radius = max(1.0, float(radius))
        self.color = self._to_color(color)
        self.crosshair = bool(crosshair)

    def handle_event(self, app: AppLike, ev: pygame.event.Event) -> None:
        """No procesa eventos; sirve solo como contenedor lógico."""
        return

    def update(self, app: AppLike, dt: float) -> None:
        """No tiene lógica; solo mantiene posición/estado."""
        return

    def render(self, app: AppLike, screen: pygame.Surface) -> None:
        if not self.visible:
            return

        center = (int(self.pos.x), int(self.pos.y))
        color = self._to_color(getattr(self, "color", self.color))
        radius = int(self.radius)
        pygame.draw.circle(screen, color, center, radius, width=1)

        if self.crosshair:
            arm = max(4, radius // 2)
            pygame.draw.line(
                screen,
                color,
                (center[0] - arm, center[1]),
                (center[0] + arm, center[1]),
                width=1,
            )
            pygame.draw.line(
                screen,
                color,
                (center[0], center[1] - arm),
                (center[0], center[1] + arm),
                width=1,
            )

    @staticmethod
    def _to_color(value: pygame.Color | str | tuple[int, int, int]) -> pygame.Color:
        try:
            if isinstance(value, pygame.Color):
                return pygame.Color(value)
            if isinstance(value, str):
                return pygame.Color(value)
            if isinstance(value, (tuple, list)):
                return pygame.Color(*value)
        except (ValueError, TypeError):
            pass
        return pygame.Color(50, 50, 50)
