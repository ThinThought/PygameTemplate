from __future__ import annotations

import pygame

from game.environments.base import Environment, AppLike


class MusicEnvironment(Environment):
    """
    Environment que solo gestiona música de fondo.

    - Al entrar en escena reproduce una pista.
    - Al salir detiene la música.
    - No renderiza nada en pantalla.
    """

    def __init__(
        self,
        pos: pygame.Vector2 | tuple[float, float] | None = None,
        *,
        track: str = "demo.mp3",
        volume: float = 1.0,
        loop: bool = True,
        fade_ms: int = 0,
        stop_fade_ms: int | None = None,
    ) -> None:
        # Environments se instancian con una posición por defecto desde el loader.
        self.pos = pygame.Vector2(pos) if pos is not None else pygame.Vector2(0, 0)
        resolved_track = track if isinstance(track, str) else "demo.mp3"
        self.track = resolved_track
        self._default_track = resolved_track
        self.volume = volume
        self.loop = loop
        self.fade_ms = fade_ms
        self.stop_fade_ms = stop_fade_ms if stop_fade_ms is not None else fade_ms
        self._active = False

    def on_spawn(self, app: AppLike) -> None:
        """Empieza a reproducir la pista configurada."""
        track = (
            self.track
            if isinstance(self.track, str) and self.track
            else self._default_track
        )
        if not isinstance(self.track, str):
            print(
                "[MusicEnvironment] Track inválido en composición. Usando valor por defecto."
            )
        app.audio.play_music(
            track,
            volume=self.volume,
            loop=self.loop,
            fade_ms=self.fade_ms,
        )
        self._active = True

    def on_despawn(self, app: AppLike) -> None:
        """Detiene la música cuando se retira del árbol."""
        if not self._active:
            return
        app.audio.stop_music(fade_ms=self.stop_fade_ms)
        self._active = False

    def handle_event(self, app: AppLike, ev: pygame.event.Event) -> None:
        """No maneja eventos (placeholder para compatibilidad)."""
        return

    def update(self, app: AppLike, dt: float) -> None:
        """No necesita lógica de actualización."""
        return

    def render(self, app: AppLike, screen: pygame.Surface) -> None:
        """No renderiza nada en pantalla."""
        return
