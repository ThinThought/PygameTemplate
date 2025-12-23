from __future__ import annotations

import pygame
from typing import Any

from game.entities.visible_mass import VisibleMassEntity


class PlayableMassEntity(VisibleMassEntity):
    MAX_SPEED_X: float = 1.5  # m/s  (~140 px/s if PPM=100)
    GROUND_ACCEL: float = 9.0  # m/s^2
    AIR_ACCEL: float = 5.0  # m/s^2

    GROUND_DAMPING: float = 10.0  # 1/s  (linear damping)
    AIR_DAMPING: float = 2.0  # 1/s

    # Jump (2 seconds sustained thrust while holding)
    JUMP_IMPULSE = 5.0  # m/s   ← ESTE es el que manda
    JUMP_HOLD_ACCEL = 15.0  # m/s²
    JUMP_HOLD_TIME = 0.05  # s
    JOY_DEADZONE = 0.3

    def __init__(
        self,
        pos: pygame.Vector2 | tuple[float, float] | None = None,
        *,
        mass: float = 1.0,
        size: float = 48.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(pos=pos, mass=mass, size=size, **kwargs)

        self._left = False
        self._right = False
        self._jump_pressed = False

        self._jump_time_left = 0.0
        self._is_jumping = False

        self.color = getattr(self, "color", (76, 139, 245))

    # ----- jump -----------------------------------------------------------
    def _start_jump(self) -> None:
        ppm = float(getattr(self, "PIXELS_PER_METER", 100.0))

        # set initial upward velocity (convert m/s -> px/s)
        self.velocity.y = -self.JUMP_IMPULSE * ppm

        # enable sustained upward thrust
        self._jump_time_left = float(self.JUMP_HOLD_TIME)
        self._is_jumping = True
        self.grounded = False

    def _stop_jump_early(self) -> None:
        self._jump_time_left = 0.0
        self._is_jumping = False

        # optional: cut upward velocity for short hops
        if self.velocity.y < 0.0:
            self.velocity.y *= 0.35

    # ----- per-frame ------------------------------------------------------
    def update(self, app: Any, dt: float) -> None:
        self._bind_runtime(app)

        grounded = bool(getattr(self, "grounded", False))
        ppm = float(getattr(self, "PIXELS_PER_METER", 100.0))

        # ----------------------------
        # HORIZONTAL movement by forces (cheap + stable)
        # ----------------------------
        move_dir = 0
        if self._left and not self._right:
            move_dir = -1
        elif self._right and not self._left:
            move_dir = 1

        # current vx in m/s
        vx_mps = self.velocity.x / ppm

        accel = self.GROUND_ACCEL if grounded else self.AIR_ACCEL
        damping = self.GROUND_DAMPING if grounded else self.AIR_DAMPING

        if move_dir != 0:
            # accelerate left/right: F = m*a
            ax = move_dir * accel
            self.apply_force((self.mass * ax, 0.0))
        else:
            # linear damping: F = -m * damping * v
            self.apply_force((-self.mass * damping * vx_mps, 0.0))

        # clamp vx to max speed (in px/s)
        vmax_px = self.MAX_SPEED_X * ppm
        if self.velocity.x > vmax_px:
            self.velocity.x = vmax_px
        elif self.velocity.x < -vmax_px:
            self.velocity.x = -vmax_px

        # ----------------------------
        # JUMP HOLD: sustained upward thrust while holding
        # ----------------------------
        if self._jump_pressed:
            # if we're grounded and not already jumping, start
            if grounded and not self._is_jumping:
                self._start_jump()

        if self._jump_time_left > 0.0 and self._is_jumping and self._jump_pressed:
            # upward thrust: a = -JUMP_HOLD_ACCEL (m/s^2)
            self.apply_force((0.0, -self.mass * self.JUMP_HOLD_ACCEL))
            self._jump_time_left -= dt
            if self._jump_time_left <= 0.0:
                self._jump_time_left = 0.0
                self._is_jumping = False

        # Collisions / grounding (post-step correction)
        self._apply_platform_collisions()

        # Base update once (rect sync, etc.)
        super().update(app, dt)

        # landing reset
        if getattr(self, "grounded", False):
            self._jump_time_left = 0.0
            self._is_jumping = False
            if self.velocity.y > 0.0:
                self.velocity.y = 0.0

    def handle_event(self, app: Any, ev: pygame.event.Event) -> None:
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_a, pygame.K_LEFT):
                self._left = True
            elif ev.key in (pygame.K_d, pygame.K_RIGHT):
                self._right = True
            elif ev.key == pygame.K_w:
                self._jump_pressed = True
                if not self.grounded and not self._is_jumping:
                    self._start_jump()

        elif ev.type == pygame.KEYUP:
            if ev.key in (pygame.K_a, pygame.K_LEFT):
                self._left = False
            elif ev.key in (pygame.K_d, pygame.K_RIGHT):
                self._right = False
            elif ev.key == pygame.K_w:
                self._jump_pressed = False
                self._stop_jump_early()

        # 🎮 Botón salto
        elif ev.type == pygame.JOYBUTTONDOWN:
            if ev.button == 4:
                self._jump_pressed = True
                if not self.grounded and not self._is_jumping:
                    self._start_jump()

        elif ev.type == pygame.JOYBUTTONUP:
            if ev.button == 4:
                self._jump_pressed = False
                self._stop_jump_early()

        # 🎮 Joystick izquierdo (eje X)
        elif ev.type == pygame.JOYAXISMOTION:
            if ev.axis == 0:  # eje horizontal stick izquierdo
                value = ev.value

                if value < -self.JOY_DEADZONE:
                    self._left = True
                    self._right = False
                elif value > self.JOY_DEADZONE:
                    self._right = True
                    self._left = False
                else:
                    self._left = False
                    self._right = False
