import pygame
from game.entities.base import Entity, AppLike


class TestEye(Entity):
    def __init__(self, pos):
        self.pos = pygame.Vector2(pos)
        self.radius = 22

        # --- Blink state ---
        self.blink_duration = 0.12   # segundos
        self.blink_timer = 0.0
        self.blinking = False

    def handle_event(self, app: AppLike, ev: pygame.event.Event):
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE:
            # dispara parpadeo
            self.blinking = True
            self.blink_timer = self.blink_duration
            return True  # consume el evento

        return False

    def update(self, app, dt: float):
        if self.blinking:
            self.blink_timer -= dt
            if self.blink_timer <= 0:
                self.blinking = False

    def render(self, app, screen):
        x, y = int(self.pos.x), int(self.pos.y)

        if self.blinking:
            # ojo cerrado → línea
            pygame.draw.line(
                screen,
                "black",
                (x - self.radius, y),
                (x + self.radius, y),
                3,
            )
        else:
            # ojo abierto
            pygame.draw.circle(screen, "black", (x, y), self.radius, 2)
            pygame.draw.circle(screen, "black", (x, y), self.radius // 4)
