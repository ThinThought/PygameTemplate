from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pygame

from game.core.resources import get_asset_path
from game.entities.playable import PlayableMassEntity


@dataclass
class JumpPhases:
    takeoff_frame: int = 1
    up_frame: int = 2
    down_frame: int = 3
    land_frame: int = 1
    vy_threshold_px: float = 20.0
    land_hold_s: float = 0.08


@dataclass
class AnimTuning:
    idle_fps: float = 2.0
    walk_fps: float = 7.0
    deadzone_px: float = 2.0
    jump: JumpPhases = field(default_factory=JumpPhases)


@dataclass
class AnimClip:
    frames: list[pygame.Surface]
    fps: float = 10.0
    loop: bool = True

    # runtime
    t: float = 0.0
    idx: int = 0
    frozen: bool = False

    def reset(self) -> None:
        self.t = 0.0
        self.idx = 0
        self.frozen = False

    def set_frame(self, one_based_index: int) -> None:
        self.idx = max(0, min(one_based_index - 1, len(self.frames) - 1))
        self.t = 0.0
        self.frozen = True

    def unfreeze(self) -> None:
        self.frozen = False

    def update(self, dt: float) -> None:
        if self.frozen or len(self.frames) <= 1 or self.fps <= 0:
            return

        self.t += dt
        frame_time = 1.0 / self.fps

        while self.t >= frame_time:
            self.t -= frame_time
            self.idx += 1
            if self.loop:
                self.idx %= len(self.frames)
            else:
                self.idx = min(self.idx, len(self.frames) - 1)

    def current(self) -> pygame.Surface:
        if not self.frames:
            raise RuntimeError("AnimClip sin frames")
        return self.frames[self.idx]


class SpriteAnimator:
    def __init__(
        self,
        base_asset_path_str: str,
        *,
        scale_factor: float | None = None,
        min_size: tuple[int, int] | None = None,
    ) -> None:
        self.base_asset_path_str = base_asset_path_str
        self.scale_factor = scale_factor
        self.min_size = min_size
        self.clips: dict[str, AnimClip] = {}
        self.state: str | None = None
        self.facing: int = 1  # 1 derecha, -1 izquierda

    def load_clip(self, state: str, *, fps: float, loop: bool = True) -> None:
        relative_folder_path = Path(self.base_asset_path_str) / state

        frames: list[pygame.Surface] = []
        i = 1
        while True:
            try:
                relative_frame_path = relative_folder_path / f"{i}.png"
                full_path = get_asset_path(relative_frame_path.as_posix())
                surf = pygame.image.load(full_path).convert_alpha()
                frames.append(surf)
                i += 1
            except FileNotFoundError:
                break

        if not frames:
            raise FileNotFoundError(
                f"No hay frames para estado {state!r} en {relative_folder_path}"
            )

        if self.scale_factor is not None and self.scale_factor != 1.0:
            for i in range(len(frames)):
                surf = frames[i]
                original_size = surf.get_size()
                new_size = (
                    int(original_size[0] * self.scale_factor),
                    int(original_size[1] * self.scale_factor),
                )

                if self.min_size is not None:
                    new_size = (
                        max(new_size[0], self.min_size[0]),
                        max(new_size[1], self.min_size[1]),
                    )

                if new_size != original_size:
                    frames[i] = pygame.transform.smoothscale(surf, new_size)

        self.clips[state] = AnimClip(frames=frames, fps=fps, loop=loop)

    @property
    def current_clip(self) -> AnimClip | None:
        if self.state is None:
            return None
        return self.clips.get(self.state)

    def set_state(self, state: str) -> None:
        if state == self.state:
            return

        self.state = state

        clip = self.current_clip
        if clip:
            clip.reset()  # arranca limpio
            clip.unfreeze()  # por si venía congelado

    def update(self, dt: float) -> None:
        if self.current_clip:
            self.current_clip.update(dt)

    def frame(self) -> pygame.Surface:
        clip = self.current_clip
        if clip is None:
            raise RuntimeError(f"Animator state {self.state!r} no es válido")

        surf = clip.current()
        if self.facing < 0:
            surf = pygame.transform.flip(surf, True, False)
        return surf


class SpykePlayer(PlayableMassEntity):
    SPRITE_BASE = "images/pc/spyke"
    SPRITE_SCALE_FACTOR = 0.10
    COLLIDER_SIZE = (32, 60)

    # cache preview por clase (barato y suficiente para editor)
    _preview_surface: pygame.Surface | None = None
    _preview_loaded: bool = False

    def __init__(
        self,
        pos=None,
        *,
        mass: float = 1.0,
        anim_tuning: AnimTuning | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(pos=pos, mass=mass, visible=True, show_collider=True, **kwargs)
        self.anim_tuning = anim_tuning or AnimTuning()

        self._left = False
        self._right = False
        self._jump_pressed = False
        self._jump_time_left = 0.0
        self._is_jumping = False
        self.anim: SpriteAnimator | None = None

        # Animation state
        self._anim_state: str | None = None
        self._airborne_prev: bool = False
        self._land_hold_timer: float = 0.0

        # NEW: “fuerza del jugador” (intención) para idle/walk
        self._driving_x: bool = False

    def on_spawn(self, app: Any) -> None:
        super().on_spawn(app)

        self.anim = SpriteAnimator(
            self.SPRITE_BASE,
            scale_factor=self.SPRITE_SCALE_FACTOR,
            min_size=self.COLLIDER_SIZE,
        )
        self.anim.load_clip("idle", fps=self.anim_tuning.idle_fps, loop=True)
        self.anim.load_clip("walk", fps=self.anim_tuning.walk_fps, loop=True)
        self.anim.load_clip("jump", fps=0.0, loop=False) # Pose-based clip
        self.anim.set_state("idle")

    def _start_jump(self) -> None:
        super()._start_jump()
        if self.anim:
            self.anim.set_state("jump")
            self.anim.current_clip.set_frame(self.anim_tuning.jump.takeoff_frame)

    def update(self, app: Any, dt: float) -> None:
        self._bind_runtime(app)

        grounded = bool(getattr(self, "grounded", False))
        ppm = float(getattr(self, "PIXELS_PER_METER", 100.0))

        move_dir = 0
        if self._left and not self._right:
            move_dir = -1
        elif self._right and not self._left:
            move_dir = 1

        vx_mps = self.velocity.x / ppm

        accel = self.GROUND_ACCEL if grounded else self.AIR_ACCEL
        damping = self.GROUND_DAMPING if grounded else self.AIR_DAMPING

        if move_dir != 0:
            ax = move_dir * accel
            self.apply_force((self.mass * ax, 0.0))
        else:
            self.apply_force((-self.mass * damping * vx_mps, 0.0))

        vmax_px = self.MAX_SPEED_X * ppm
        self.velocity.x = max(-vmax_px, min(vmax_px, self.velocity.x))

        if self._jump_pressed and grounded and not self._is_jumping:
            self._start_jump()

        if self._jump_time_left > 0.0 and self._is_jumping and self._jump_pressed:
            self.apply_force((0.0, -self.mass * self.JUMP_HOLD_ACCEL))
            self._jump_time_left -= dt
            if self._jump_time_left <= 0.0:
                self._jump_time_left = 0.0
                self._is_jumping = False

        self._apply_platform_collisions()
        super().update(app, dt)

        grounded_now = bool(getattr(self, "grounded", False))

        if grounded_now:
            self._jump_time_left = 0.0
            self.anim.set_state("idle")
            self._is_jumping = False
            if self.velocity.y > 0.0:
                self.velocity.y = 0.0
        self._update_anim_state(dt)

    def _update_anim_state(self, dt: float) -> None:
            if self.anim is None:
                return

            grounded = bool(getattr(self, "grounded", False))
            landed_this_frame = grounded and self._airborne_prev

            # Timers (landing hold)
            if landed_this_frame:
                self._land_hold_timer = self.anim_tuning.jump.land_hold_s

            if self._land_hold_timer > 0.0:
                self._land_hold_timer = max(0.0, self._land_hold_timer - dt)

            ppm = float(getattr(self, "PIXELS_PER_METER", 100.0))
            vx_px = float(self.velocity.x)
            vy_px = float(self.velocity.y)
            vx_mps = vx_px / ppm
            vy_mps = vy_px / ppm
            # print("ppm:", ppm, "vx_mps:", vx_mps, "vy_mps:", vy_mps)

            # Facing (input first, otherwise by velocity)
            if self._left and not self._right:
                self.anim.facing = -1
            elif self._right and not self._left:
                self.anim.facing = 1
            elif abs(vx_mps) >= 0.1:
                self.anim.facing = 1 if vx_mps > 0 else -1

            # ---- Rules ----
            # Jump whenever moving upward (negative Y velocity)
            # Walk when vx > 1.0 m/s OR vx < -0.1 m/s (as you stated)
            WALK_POS_MPS = 1.0
            WALK_NEG_MPS = -0.1

            # Decide state (priority)
            if grounded and self._land_hold_timer > 0.0:
                desired_state = "jump"  # keep "landing pose" inside jump state (below)
            elif grounded:
                desired_state = "idle"
            elif vy_mps < -0.01:
                desired_state = "jump"
            elif (vx_mps > WALK_POS_MPS) or (vx_mps < WALK_NEG_MPS):
                desired_state = "walk"
            else:
                desired_state = "idle"

            self.anim.set_state(desired_state)

            # Pose-based jump frames
            if desired_state == "jump":
                jump_cfg = self.anim_tuning.jump

                if grounded and self._land_hold_timer > 0.0:
                    self.anim.current_clip.set_frame(jump_cfg.land_frame)
                else:
                    # If you truly want: "jump always when vy negative"
                    # then pose frames should also follow vy sign.
                    if vy_px < 0.0:
                        self.anim.current_clip.set_frame(jump_cfg.up_frame)
                    elif vy_px > 0.0:
                        self.anim.current_clip.set_frame(jump_cfg.down_frame)
                    else:
                        self.anim.current_clip.set_frame(jump_cfg.up_frame)

        # walk/idle advance with fps; jump is frozen by set_frame()
            self.anim.update(dt)

    def render(self, app, screen: pygame.Surface) -> None:
        if self.anim is not None:
            # Set a default state if none is set, to prevent crashes
            if self.anim.state is None:
                self.anim.set_state("idle")
            frame = self.anim.frame()
        else:
            frame = self._get_editor_preview_frame(
                app, prefer_idle=True, random_fallback=True
            )
            if frame is None:
                if hasattr(self, "_collider_rect"):
                    pygame.draw.rect(screen, self.color, self._collider_rect(), 2)
                return

        collider_rect = self._collider_rect()
        sprite_rect = frame.get_rect(midbottom=collider_rect.midbottom)

        screen.blit(frame, sprite_rect)

        if self.show_collider or getattr(app, "DEBUG_COLLIDERS", False):
            pygame.draw.rect(screen, (255, 0, 0), collider_rect, 1)

    @classmethod
    def _get_editor_preview_frame(
        cls,
        app,
        *,
        prefer_idle: bool = True,
        random_fallback: bool = True,
    ) -> pygame.Surface | None:
        if cls._preview_loaded:
            return cls._preview_surface
        cls._preview_loaded = True

        base_asset_path_str = cls._resolve_sprite_base_dir()
        if base_asset_path_str is None:
            return None

        candidate_relative_paths: list[str] = []
        if prefer_idle:
            try:
                # Check existence
                get_asset_path(f"{base_asset_path_str}/idle/1.png")
                candidate_relative_paths.append(f"{base_asset_path_str}/idle/1.png")
            except FileNotFoundError:
                pass

        if not candidate_relative_paths:
            return None

        try:
            full_path = get_asset_path(candidate_relative_paths[0])
            surf = pygame.image.load(full_path).convert_alpha()
        except (FileNotFoundError, pygame.error):
            return None

        if hasattr(cls, "SPRITE_SCALE_FACTOR") and cls.SPRITE_SCALE_FACTOR != 1.0:
            scale_factor = cls.SPRITE_SCALE_FACTOR
            original_size = surf.get_size()
            new_size = (
                int(original_size[0] * scale_factor),
                int(original_size[1] * scale_factor),
            )

            if hasattr(cls, "COLLIDER_SIZE"):
                min_size = cls.COLLIDER_SIZE
                new_size = (
                    max(new_size[0], min_size[0]),
                    max(new_size[1], min_size[1]),
                )

            if new_size != original_size:
                surf = pygame.transform.smoothscale(surf, new_size)

        cls._preview_surface = surf
        return surf

    @classmethod
    def _resolve_sprite_base_dir(cls) -> str | None:
        if not cls.SPRITE_BASE:
            return None
        return cls.SPRITE_BASE