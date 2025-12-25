from __future__ import annotations

from typing import Any

from game.entities.playable import PlayableMassEntity
from dataclasses import dataclass
import random
from pathlib import Path
import pygame

@dataclass
class AnimClip:
    frames: list[pygame.Surface]
    fps: float = 10.0
    loop: bool = True

    t: float = 0.0
    idx: int = 0

    def reset(self) -> None:
        self.t = 0.0
        self.idx = 0

    def update(self, dt: float) -> None:
        if len(self.frames) <= 1 or self.fps <= 0:
            return

        self.t += dt
        frame_time = 1.0 / self.fps

        # avanzar de forma robusta aunque dt venga grande
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
    def __init__(self, base_dir: Path, *, size: tuple[int, int] | None = None) -> None:
        self.base_dir = Path(base_dir)
        self.size = size
        self.clips: dict[str, AnimClip] = {}
        self.state: str = "idle"
        self.facing: int = 1  # 1 derecha, -1 izquierda

    def load_clip(self, state: str, *, fps: float, loop: bool = True) -> None:
        folder = self.base_dir / state
        paths = sorted(
            folder.glob("*.png"),
            key=lambda p: int(p.stem) if p.stem.isdigit() else p.stem,
        )

        frames: list[pygame.Surface] = []
        for p in paths:
            surf = pygame.image.load(p.as_posix()).convert_alpha()
            if self.size is not None:
                surf = pygame.transform.smoothscale(
                    surf, (int(self.size[0]), int(self.size[1]))
                )
            frames.append(surf)

        if not frames:
            raise FileNotFoundError(f"No hay frames para estado {state!r} en {folder}")

        self.clips[state] = AnimClip(frames=frames, fps=fps, loop=loop)

    def set_state(self, state: str) -> None:
        if state == self.state:
            return
        self.state = state
        self.clips[state].reset()

    def update(self, dt: float) -> None:
        self.clips[self.state].update(dt)

    def frame(self) -> pygame.Surface:
        surf = self.clips[self.state].current()
        if self.facing < 0:
            surf = pygame.transform.flip(surf, True, False)
        return surf

class SpykePlayer(PlayableMassEntity):
    SPRITE_BASE = "images/pc/spyke"  # relativo a assets/
    SPRITE_SIZE = (64, 64)  # ajústalo a tu arte
    WALK_FPS = 12.0
    IDLE_FPS = 6.0
    JUMP_FPS = 10.0

    # cache preview por clase (barato y suficiente para editor)
    _preview_surface: pygame.Surface | None = None
    _preview_loaded: bool = False
    def __init__(self, pos=None, *, mass: float = 1.0, **kwargs: Any) -> None:
        super().__init__(pos=pos, mass=mass, **kwargs)

        self._left = False
        self._right = False
        self._jump_pressed = False
        self._jump_time_left = 0.0
        self._is_jumping = False

        self.anim: SpriteAnimator | None = None

    def on_spawn(self, app: Any) -> None:
        super().on_spawn(app)

        # Resuelve assets root como ya haces en tu mixin
        assets_root = getattr(app, "resources", None)
        if assets_root is not None and hasattr(assets_root, "path"):
            base_dir = Path(assets_root.path(self.SPRITE_BASE))
        else:
            base_dir = Path(__file__).resolve().parents[1] / "assets" / self.SPRITE_BASE

        self.anim = SpriteAnimator(base_dir, size=self.SPRITE_SIZE)
        self.anim.load_clip("idle", fps=self.IDLE_FPS, loop=True)
        self.anim.load_clip("walk", fps=self.WALK_FPS, loop=True)
        self.anim.load_clip("jump", fps=self.JUMP_FPS, loop=True)

    def update(self, app: Any, dt: float) -> None:
        # --- tu lógica existente ---
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

        if getattr(self, "grounded", False):
            self._jump_time_left = 0.0
            self._is_jumping = False
            if self.velocity.y > 0.0:
                self.velocity.y = 0.0

        # --- anim state box ---
        self._update_anim_state(dt)
        self._update_anim_state(dt)

    def _update_anim_state(self, dt: float) -> None:
        if self.anim is None:
            return

        grounded = bool(getattr(self, "grounded", False))
        vx = self.velocity.x
        dead = 5.0  # px/s, umbral para considerar “quieto”

        # facing por input (mejor que por vx si hay damping)
        if self._left and not self._right:
            self.anim.facing = -1
        elif self._right and not self._left:
            self.anim.facing = 1
        elif abs(vx) > dead:
            self.anim.facing = 1 if vx > 0 else -1

        if not grounded:
            self.anim.set_state("jump")
        else:
            if abs(vx) > dead:
                self.anim.set_state("walk")
            else:
                self.anim.set_state("idle")

        self.anim.update(dt)

    def render(self, app, screen: pygame.Surface) -> None:
        # 1) Si tenemos animación, usamos el frame actual
        if self.anim is not None:
            frame = self.anim.frame()
        else:
            # 2) Editor/preview: frame por defecto
            frame = self._get_editor_preview_frame(app, prefer_idle=True, random_fallback=True)
            if frame is None:
                return  # o dibuja un placeholder

        anchor = (int(self.pos.x), int(self.pos.y) + 16)  # mejor: anclar a tu collider
        rect = frame.get_rect(midbottom=anchor)
        screen.blit(frame, rect)

    @classmethod
    def _get_editor_preview_frame(
        cls,
        app,
        *,
        prefer_idle: bool = True,
        random_fallback: bool = True,
    ) -> pygame.Surface | None:
        # Si ya lo cargamos (ok o fail), no repetimos
        if cls._preview_loaded:
            return cls._preview_surface
        cls._preview_loaded = True

        base_dir = cls._resolve_sprite_base_dir(app)
        if base_dir is None:
            return None

        # 1) Intentar primer frame de idle
        candidates: list[Path] = []
        if prefer_idle:
            idle_dir = base_dir / "idle"
            if idle_dir.exists():
                idle_pngs = sorted(
                    idle_dir.glob("*.png"),
                    key=lambda p: int(p.stem) if p.stem.isdigit() else p.stem,
                )
                if idle_pngs:
                    candidates = [idle_pngs[0]]

        # 2) Fallback: cualquier png (y aleatorio si quieres)
        if not candidates and random_fallback:
            all_pngs = list(base_dir.rglob("*.png"))
            if all_pngs:
                candidates = [random.choice(all_pngs)]

        if not candidates:
            return None

        # Cargar y escalar
        try:
            surf = pygame.image.load(candidates[0].as_posix()).convert_alpha()
        except pygame.error:
            return None

        if cls.SPRITE_SIZE is not None:
            w, h = cls.SPRITE_SIZE
            surf = pygame.transform.smoothscale(surf, (int(w), int(h)))

        cls._preview_surface = surf
        return surf

    @classmethod
    def _resolve_sprite_base_dir(cls, app) -> Path | None:
        # igual que tu patrón actual
        assets_root = getattr(app, "resources", None)
        if assets_root is not None and hasattr(assets_root, "path"):
            return Path(assets_root.path(cls.SPRITE_BASE))

        return Path(__file__).resolve().parents[1] / "assets" / cls.SPRITE_BASE