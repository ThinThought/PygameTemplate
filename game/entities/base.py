from __future__ import annotations


from typing import Protocol
import pygame


class AppLike(Protocol):
    """Lo mínimo que una entidad puede necesitar del mundo."""

    pass


class Entity:
    """
    Unidad básica del juego.

    - No conoce escenas
    - No conoce input directamente
    - No gestiona el loop
    """

    def on_spawn(self, app: AppLike) -> None:
        """Se llama cuando la entidad entra en escena."""
        pass

    def on_despawn(self, app: AppLike) -> None:
        """Se llama cuando la entidad sale de escena."""
        pass

    def handle_event(self, app: AppLike, ev: pygame.event.Event):
        """propagar el evento a la entidad"""
        pass

    def update(self, app: AppLike, dt: float) -> None:
        """Lógica por frame."""
        pass

    def render(self, app: AppLike, screen: pygame.Surface) -> None:
        """Dibujo."""
        pass
