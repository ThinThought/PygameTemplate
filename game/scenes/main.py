from __future__ import annotations

import pygame
from game.scenes.base import Scene, AppLike
from game.entities.eye import Eye
from game.entities.mouth import Mouth


class MainScene(Scene):
    def __init__(self) -> None:
        self.entities: list[object] = []

    def on_enter(self, app: AppLike) -> None:
        cx, cy = app.screen.get_rect().center

        # Ojo izquierdo
        left_eye = Eye(pygame.Vector2(cx - 40, cy - 30))
        # Ojo derecho
        right_eye = Eye(pygame.Vector2(cx + 40, cy - 30))
        # Boca
        mouth = Mouth(pygame.Vector2(cx, cy + 30))

        self.entities = [left_eye, right_eye, mouth]

        # audio de test si quieres
        app.audio.play_music("demo.mp3", volume=1.0, fade_ms=500)

    def on_exit(self, app: AppLike) -> None:
        app.audio.stop_music(fade_ms=200)

    def handle_event(self, app: AppLike, ev: pygame.event.Event) -> None:
        if ev.type == pygame.QUIT:
            app.running = False

        # Pasar eventos a las entidades (parpadeo, animaciones, etc.)
        for ent in self.entities:
            h = getattr(ent, "handle_event", None)
            if callable(h):
                h(app, ev)

    def update(self, app: AppLike, dt: float) -> None:
        for ent in self.entities:
            ent.update(app, dt)

    def render(self, app: AppLike, screen: pygame.Surface) -> None:
        screen.fill("white")

        for ent in self.entities:
            ent.render(app, screen)
