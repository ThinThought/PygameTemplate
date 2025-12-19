from __future__ import annotations
import pygame
from game.environments.base import Environment, AppLike

class BlackZone(Environment):
    def __init__(self, pos):
        self.pos = pygame.Vector2(pos)
        self.dims = pygame.Vector2(200, 200)

    def handle_event(self, app: AppLike, ev: pygame.event.Event):
        pass

    def update(self, app, dt: float):
        pass

    def render(self, app, screen):
        x, y = int(self.pos.x), int(self.pos.y)
        w, h = int(self.dims.x), int(self.dims.y)

        pygame.draw.rect(
            screen,
            "black",
            pygame.Rect(x - w // 2, y - h // 2, w, h)
        )
