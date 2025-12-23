from __future__ import annotations

from pathlib import Path
from time import perf_counter
from collections import deque
from typing import NamedTuple
import pygame
from rich.console import Console
from rich.panel import Panel

from game.core.clock import GameClock
from game.core.resources import Resources
from game.core.config import WindowConfig
from game.core.audio import AudioManager

import game.scenes as scenes_mod
from game.scenes.base import Scene


class HudLine(NamedTuple):
    text: str
    color: tuple[int, int, int]
    align: str = "left"


console = Console()


def _build_scenes() -> list[type[Scene]]:
    scene_classes = []
    for name in getattr(scenes_mod, "__all__", []):
        obj = getattr(scenes_mod, name, None)
        if isinstance(obj, type) and issubclass(obj, Scene):
            scene_classes.append(obj)

    return scene_classes


class App:
    def __init__(self, config: WindowConfig) -> None:
        self.cfg = config

        pygame.init()
        pygame.joystick.init()

        self.joysticks: list[pygame.joystick.Joystick] = []
        for i in range(pygame.joystick.get_count()):
            js = pygame.joystick.Joystick(i)
            self.joysticks.append(js)

        self.joy_buttons_down: set[int] = set()

        pygame.display.set_caption(self.cfg.title)
        self.screen = pygame.display.set_mode((self.cfg.width, self.cfg.height))

        self.clock = GameClock(self.cfg.fps)

        root = Path(__file__).resolve().parents[2]
        assets_dir = root / "assets"
        self.resources = Resources(assets_dir)

        self.audio = AudioManager(assets_dir)
        self.audio.init()

        self.running = True

        self.scenes = _build_scenes()
        self._scene_index = 1
        self.scene: Scene | None = None

        console.print(Panel.fit("✅ Pygame initialized", border_style="green"))
        console.print(
            Panel.fit("F1/F2 o TAB/SHIFT+TAB: cambiar escena", border_style="cyan")
        )

        # HUD
        self.hud_font = pygame.font.Font(None, 33)
        self.hud_visible = True
        self.hud_height = 20  # alto por fila del HUD
        self.hud_alpha = 75  # 0..255 (transparencia del fondo del HUD)
        self._hud_last_input = "-"
        self._hud_recent_inputs: deque[str] = deque(maxlen=5)
        self._avg_timings: dict[str, float] = {
            "events": 0.0,
            "update": 0.0,
            "render": 0.0,
        }
        self._avg_fps = 0.0
        self._avg_dt_ms = 0.0
        self._hud_stats_alpha = 0.12

        self._toast_text: str | None = None
        self._toast_t = 0.0

        # Render target cache (evita alloc cada frame)
        self._scene_surf: pygame.Surface | None = None
        self._scene_surf_size: tuple[int, int] | None = None
        self._timings: dict[str, float] = {"events": 0.0, "update": 0.0, "render": 0.0}
        self._hud_show_timings = False
        self._hud_text_cache: dict[str, tuple[str, pygame.Surface]] = {}
        self._hud_bar_surface: pygame.Surface | None = None
        self._hud_bar_size: tuple[int, int] | None = None
        self._hud_bar_alpha: int | None = None
        self._profiling_mode = False
        self._profiling_frame_window = 60
        self._profiling_frames = 0
        self._profiling_accumulator: dict[str, float] = {
            "events": 0.0,
            "update": 0.0,
            "render": 0.0,
        }

    # --- Scene switching -------------------------------------------------
    def _wrap_index(self, index: int) -> int:
        return 0 if not self.scenes else index % len(self.scenes)

    def set_scene(self, index: int) -> None:
        if not self.scenes:
            return

        new_index = self._wrap_index(index)
        if new_index == self._scene_index and self.scene is not None:
            return

        if self.scene is not None:
            self.scene.on_exit(self)

        self._scene_index = new_index
        scene_cls = self.scenes[self._scene_index]
        self.scene = scene_cls()
        self.scene.on_enter(self)

        self._toast_text = f"{self.scene.__class__.__name__}  ({self._scene_index + 1}/{len(self.scenes)})"
        self._toast_t = 1.2

        console.print(
            Panel.fit(
                f"🎬 Scene -> {self.scene.__class__.__name__} ({self._scene_index + 1}/{len(self.scenes)})",
                border_style="magenta",
            )
        )

    def cycle_scene(self, step: int = 1) -> None:
        self.set_scene(self._scene_index + step)

    def next_scene(self) -> None:
        self.cycle_scene(+1)

    def prev_scene(self) -> None:
        self.cycle_scene(-1)

    # --- HUD -------------------------------------------------------------

    def _apply_hud_visibility(self, visible: bool) -> None:
        if self.hud_visible == visible:
            return
        self.hud_visible = visible
        # fuerza recreación del render target (viewport cambia)
        self._scene_surf_size = None

    def toggle_hud(self) -> None:
        self._apply_hud_visibility(not self.hud_visible)
        self._toast_text = f"HUD {'ON' if self.hud_visible else 'OFF'}"
        self._toast_t = 1.0

    def cycle_hud_mode(self) -> None:
        if not self.hud_visible:
            self._apply_hud_visibility(True)
            self._hud_show_timings = False
            label = "HUD normal"
        elif not self._hud_show_timings:
            self._hud_show_timings = True
            label = "HUD complejo"
        else:
            self._hud_show_timings = False
            self._apply_hud_visibility(False)
            label = "HUD oculto"
        self._toast_text = label
        self._toast_t = 1.0

    def scene_viewport(self) -> pygame.Rect:
        w, h = self.screen.get_size()
        return pygame.Rect(0, 0, w, h)

    def hud_rect(self, rows: int | None = None) -> pygame.Rect:
        w, h = self.screen.get_size()
        rows = rows or (2 if self._hud_show_timings else 1)
        rows = max(1, rows)
        height = self.hud_height * rows
        return pygame.Rect(0, h - height, w, height)

    def _ensure_scene_surface(self, vp: pygame.Rect) -> pygame.Surface:
        size = (vp.w, vp.h)
        if self._scene_surf is None or self._scene_surf_size != size:
            self._scene_surf = pygame.Surface(size).convert()
            self._scene_surf_size = size
        return self._scene_surf

    # --- Main loop -------------------------------------------------------

    def run(self) -> None:
        if self.scene is None:
            self.set_scene(self._scene_index)

        if self.scene is None:
            return

        while self.running:
            dt = self.clock.tick()

            if self._toast_t > 0:
                self._toast_t -= dt
                if self._toast_t <= 0:
                    self._toast_text = None

            events_start = perf_counter()
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.running = False
                    continue

                self._track_last_input(ev)

                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_p:
                        self._profiling_mode = not self._profiling_mode
                        self._toast_text = (
                            f"Profiling {'ON' if self._profiling_mode else 'OFF'}"
                        )
                        self._toast_t = 1.0
                        self._profiling_frames = 0
                        self._reset_profiling_accumulators()
                        continue

                    # HUD toggle
                    if ev.key == pygame.K_h:
                        self.toggle_hud()
                        continue

                    # Scene switching: F1/F2 o TAB/SHIFT+TAB
                    if ev.key in (pygame.K_F2, pygame.K_TAB) and not (
                        ev.mod & pygame.KMOD_SHIFT
                    ):
                        self.next_scene()
                        continue

                    if ev.key == pygame.K_F1 or (
                        ev.key == pygame.K_TAB and (ev.mod & pygame.KMOD_SHIFT)
                    ):
                        self.prev_scene()
                        continue

                if ev.type == pygame.JOYBUTTONDOWN:
                    self.joy_buttons_down.add(ev.button)

                    # combo: 12 + 14
                    if 12 in self.joy_buttons_down and 14 in self.joy_buttons_down:
                        self.cycle_hud_mode()
                        self.joy_buttons_down.clear()
                        continue

                    if ev.button == 15:  # botón 11 solo
                        self.prev_scene()
                        self.joy_buttons_down.clear()
                        continue

                    if ev.button == 16:  # botón 9 solo
                        self.next_scene()
                        self.joy_buttons_down.clear()
                        continue

                if ev.type == pygame.JOYBUTTONUP:
                    self.joy_buttons_down.discard(ev.button)

                if self.scene is not None:
                    self.scene.handle_event(self, ev)
            self._timings["events"] = (perf_counter() - events_start) * 1000.0

            update_start = perf_counter()
            if self.scene is not None:
                self.scene.update(self, dt)
            self._timings["update"] = (perf_counter() - update_start) * 1000.0

            render_start = perf_counter()
            vp = self.scene_viewport()
            scene_surf = self._ensure_scene_surface(vp)
            if self.scene is not None:
                self.scene.render(self, scene_surf)
            self.screen.blit(scene_surf, vp.topleft)
            self._timings["render"] = (perf_counter() - render_start) * 1000.0
            self._update_hud_stats(dt)

            # HUD overlay
            if self.hud_visible:
                self._render_hud(dt)

            pygame.display.flip()

            if self._profiling_mode:
                self._profiling_frames += 1
                for key in self._timings:
                    self._profiling_accumulator[key] += self._timings[key]
                if self._profiling_frames >= self._profiling_frame_window:
                    self._emit_profiling_summary()
                    self._profiling_frames = 0
                    self._reset_profiling_accumulators()

        if self.scene is not None:
            self.scene.on_exit(self)
        self.audio.stop_all_sounds()
        self.audio.stop_music()
        pygame.quit()

    def _reset_profiling_accumulators(self) -> None:
        for key in self._profiling_accumulator:
            self._profiling_accumulator[key] = 0.0

    def _emit_profiling_summary(self) -> None:
        frames = self._profiling_frame_window
        if frames <= 0:
            return

        avg_events = self._profiling_accumulator["events"] / frames
        avg_update = self._profiling_accumulator["update"] / frames
        avg_render = self._profiling_accumulator["render"] / frames
        lines = [
            f"avg events {avg_events:0.2f}ms   update {avg_update:0.2f}ms   render {avg_render:0.2f}ms"
        ]

        update_top: list[tuple[str, float]] = []
        render_top: list[tuple[str, float]] = []
        if self.scene is not None:
            reporter = getattr(self.scene, "node_timing_report", None)
            if callable(reporter):
                update_top, render_top = reporter()

        if update_top:
            lines.append(
                "Update top: "
                + ", ".join(f"{name} {time:0.2f}ms" for name, time in update_top)
            )
        if render_top:
            lines.append(
                "Render top: "
                + ", ".join(f"{name} {time:0.2f}ms" for name, time in render_top)
            )

        console.print(
            Panel.fit("\n".join(lines), title="Profiling (avg)", border_style="yellow")
        )

    def _render_hud(self, dt: float) -> None:
        extra_lines = self._build_hud_lines()
        rows = 1 + len(extra_lines)
        r = self.hud_rect(rows)
        w, bar_h, bar_y = r.w, r.h, r.y
        row_height = self.hud_height

        bar = self._ensure_hud_bar_surface(w, bar_h, int(self.hud_alpha))
        self.screen.blit(bar, (0, bar_y))

        fps = 0.0 if dt <= 0 else (1.0 / dt)
        left_text = f"{self.scene.__class__.__name__}  [{self._scene_index + 1}/{len(self.scenes)}]"

        center_parts = [
            f"FPS {fps:0.1f}",
            f"dt {dt * 1000:0.1f} ms",
        ]
        center_text = "   ".join(center_parts)
        right_text = self._toast_text or "F1/F2  TAB / SHIFT+TAB"

        pad_x = 12
        line_h = self.hud_font.get_height()
        y = bar_y + (row_height - line_h) // 2

        t_left = self._hud_text_surface("left", left_text, (255, 255, 255))
        self.screen.blit(t_left, (pad_x, y))

        t_center = self._hud_text_surface("center", center_text, (200, 200, 200))
        cx = (w - t_center.get_width()) // 2
        self.screen.blit(t_center, (cx, y))

        t_right = self._hud_text_surface("right", right_text, (180, 220, 180))
        rx = w - t_right.get_width() - pad_x
        self.screen.blit(t_right, (rx, y))

        for idx, line in enumerate(extra_lines, start=1):
            ty = bar_y + idx * row_height + (row_height - line_h) // 2
            surface = self._hud_text_surface(f"extra_{idx}", line.text, line.color)
            if line.align == "center":
                tx = (w - surface.get_width()) // 2
            elif line.align == "right":
                tx = w - surface.get_width() - pad_x
            else:
                tx = pad_x
            self.screen.blit(surface, (tx, ty))

        pygame.draw.line(self.screen, (70, 70, 70), (0, bar_y), (w, bar_y), 1)

    def _hud_text_surface(
        self, key: str, text: str, color: tuple[int, int, int]
    ) -> pygame.Surface:
        cached = self._hud_text_cache.get(key)
        if cached and cached[0] == text:
            return cached[1]
        surface = self.hud_font.render(text, True, color)
        self._hud_text_cache[key] = (text, surface)
        return surface

    def _ensure_hud_bar_surface(
        self, width: int, height: int, alpha: int
    ) -> pygame.Surface:
        size = (width, height)
        if (
            self._hud_bar_surface is None
            or self._hud_bar_size != size
            or self._hud_bar_alpha != alpha
        ):
            bar = pygame.Surface(size, pygame.SRCALPHA)
            bar.fill((20, 20, 20, alpha))
            self._hud_bar_surface = bar
            self._hud_bar_size = size
            self._hud_bar_alpha = alpha
        return self._hud_bar_surface

    def _track_last_input(self, ev: pygame.event.Event) -> None:
        label = None
        if ev.type == pygame.KEYDOWN:
            label = f"Key {pygame.key.name(ev.key)}"
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            label = f"Mouse {ev.button}"
        elif ev.type == pygame.MOUSEWHEEL:
            label = "Mouse wheel"
        elif ev.type == pygame.JOYBUTTONDOWN:
            label = f"Joy{ev.joy} Btn{ev.button}"
        elif ev.type == pygame.JOYAXISMOTION:
            label = f"Joy{ev.joy} Axis{ev.axis}:{ev.value:0.2f}"
        elif ev.type == pygame.JOYHATMOTION:
            label = f"Joy{ev.joy} Hat{ev.hat} {ev.value}"

        if label:
            self._hud_last_input = label
            self._hud_recent_inputs.appendleft(label)

    def _build_hud_lines(self) -> list[HudLine]:
        lines: list[HudLine] = []
        lines.append(HudLine(self._input_status_text(), (200, 200, 200), "left"))

        audio_line = self._audio_status_text()
        if audio_line:
            lines.append(HudLine(audio_line, (200, 220, 220), "left"))

        avg_line = self._avg_timings_text()
        if avg_line:
            lines.append(HudLine(avg_line, (160, 200, 255), "left"))

        if self._hud_show_timings:
            timings_text = (
                f"Frame events {self._timings['events']:0.1f}ms   "
                f"update {self._timings['update']:0.1f}ms   "
                f"render {self._timings['render']:0.1f}ms"
            )
            lines.append(HudLine(timings_text, (160, 200, 255), "center"))
            lines.extend(
                HudLine(text, (180, 210, 255), "left")
                for text in self._node_timing_lines()
            )

        for row in self._scene_debug_rows():
            lines.append(HudLine(row, (220, 210, 150), "left"))

        return [line for line in lines if line.text]

    def _scene_debug_rows(self) -> list[str]:
        if self.scene is None:
            return []
        provider = getattr(self.scene, "debug_hud_rows", None)
        if not callable(provider):
            return []
        try:
            rows = provider(self) or []
        except Exception:
            return []
        return [str(row) for row in rows if row]

    def _node_timing_lines(self) -> list[str]:
        if self.scene is None:
            return []
        reporter = getattr(self.scene, "node_timing_report", None)
        if not callable(reporter):
            return []
        update_top, render_top = reporter()
        lines: list[str] = []
        if update_top:
            update_txt = ", ".join(
                f"{name} {elapsed:0.2f}ms" for name, elapsed in update_top
            )
            lines.append(f"Update top: {update_txt}")
        if render_top:
            render_txt = ", ".join(
                f"{name} {elapsed:0.2f}ms" for name, elapsed in render_top
            )
            lines.append(f"Render top: {render_txt}")
        return lines

    def _input_status_text(self) -> str:
        pads = len(self.joysticks)
        pressed = len(self.joy_buttons_down)
        recent = ", ".join(self._hud_recent_inputs)
        if recent:
            recent = f"  recent [{recent}]"
        return f"Input: pads {pads}  btn {pressed}  last {self._hud_last_input}{recent}"

    def _audio_status_text(self) -> str:
        if not pygame.mixer.get_init():
            return "Audio: mixer OFF"

        parts = []
        if pygame.mixer.music.get_busy():
            name = getattr(self.audio, "current_music", None)
            pos_ms = max(0, pygame.mixer.music.get_pos())
            pos_s = pos_ms / 1000.0
            if name:
                parts.append(f"music {name} {pos_s:0.1f}s")
            else:
                parts.append(f"music {pos_s:0.1f}s")
        else:
            parts.append("music idle")

        busy_channels = self._busy_channels()
        total_channels = pygame.mixer.get_num_channels()
        parts.append(f"sfx {busy_channels}/{total_channels} busy")
        return "Audio: " + "  •  ".join(parts)

    def _busy_channels(self) -> int:
        total = pygame.mixer.get_num_channels()
        busy = 0
        for idx in range(total):
            ch = pygame.mixer.Channel(idx)
            if ch.get_busy():
                busy += 1
        return busy

    def _avg_timings_text(self) -> str:
        if not self._avg_timings:
            return ""
        return (
            f"Avg FPS {self._avg_fps:0.1f}  dt {self._avg_dt_ms:0.1f}ms  "
            f"events {self._avg_timings['events']:0.2f}ms  "
            f"update {self._avg_timings['update']:0.2f}ms  "
            f"render {self._avg_timings['render']:0.2f}ms"
        )

    def _update_hud_stats(self, dt: float) -> None:
        fps = 0.0 if dt <= 0 else 1.0 / dt
        alpha = self._hud_stats_alpha
        self._avg_fps = (1 - alpha) * self._avg_fps + alpha * fps
        self._avg_dt_ms = (1 - alpha) * self._avg_dt_ms + alpha * (dt * 1000.0)
        for key, value in self._timings.items():
            prev = self._avg_timings.get(key, 0.0)
            self._avg_timings[key] = (1 - alpha) * prev + alpha * value
