from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import json
from pathlib import Path
import time
import pygame

from game.scenes.base import Scene
from game.compositions import load_composition
from game.input import ControllerProfile, gather_input_actions
from game.scenes.editor import EditorScene


@dataclass
class JoyInfo:
    idx: int
    name: str
    axes: int
    buttons: int
    hats: int


class InputTesterScene(Scene):
    def __init__(self) -> None:
        self.font: pygame.font.Font | None = None
        self.small: pygame.font.Font | None = None

        self.events: deque[str] = deque(maxlen=200)
        self.keys_down: set[int] = set()

        self.joysticks: list[pygame.joystick.Joystick] = []
        self.joy_infos: list[JoyInfo] = []
        self.active_joy = 0

        self.deadzone = 0.20

        root = Path(__file__).resolve().parents[2]
        self._controller_cfg_path = root / "configs" / "controllers" / "generic.toml"
        self._composition_path = self._default_composition_path(root)
        self._joystick_cfg_path = root / "configs" / "input_tester_joystick.json"
        self._snapshot_dirty = False
        self._snapshot_cooldown = 0.25  # segs entre escrituras en disco
        self._last_snapshot = time.monotonic()
        self.controller_profile: ControllerProfile | None = None
        self._action_dictionary: dict[str, list] = {"entities": [], "editor": []}
        self._action_dictionary_error: str | None = None

        self._action_scroll_y = 0
        self._log_scroll_y = 0
        self._action_surface: pygame.Surface | None = None
        self._log_surface: pygame.Surface | None = None
        self._action_rect: pygame.Rect | None = None
        self._log_rect: pygame.Rect | None = None
        self._action_content_height = 0
        self._log_content_height = 0

    def on_enter(self, app) -> None:
        self._load_controller_profile()
        self._refresh_action_dictionary()

        pygame.joystick.init()
        self._discover_joysticks()

        self.events.clear()
        self._push(f"Joysticks detected: {len(self.joysticks)}")
        if self.joysticks:
            self._push(
                f"Active joy: {self.active_joy} ({self.joy_infos[self.active_joy].name})"
            )
        else:
            self._push("No joystick found (ok on some devices).")

        # fuentes se crean en render porque dependen de tamaño de pantalla (relativo)
        self.font = None
        self.small = None
        self._render_action_surface()
        self._render_log_surface()

    def _discover_joysticks(self) -> None:
        self.joysticks = []
        self.joy_infos = []

        for i in range(pygame.joystick.get_count()):
            js = pygame.joystick.Joystick(i)
            self.joysticks.append(js)
            self.joy_infos.append(
                JoyInfo(
                    idx=i,
                    name=js.get_name(),
                    axes=js.get_numaxes(),
                    buttons=js.get_numbuttons(),
                    hats=js.get_numhats(),
                )
            )
        self.active_joy = 0 if self.joysticks else 0
        self._mark_snapshot_dirty()

    def _push(self, msg: str) -> None:
        self.events.appendleft(msg)
        self._render_log_surface()

    def _mark_snapshot_dirty(self) -> None:
        self._snapshot_dirty = True

    def _joystick_snapshot(self) -> dict[str, object]:
        data = {
            "joysticks": [
                {
                    "index": info.idx,
                    "name": info.name,
                    "axes": info.axes,
                    "buttons": info.buttons,
                    "hats": info.hats,
                }
                for info in self.joy_infos
            ],
            "active_index": self.active_joy if self.joysticks else None,
        }

        if self.joysticks:
            info = self.joy_infos[self.active_joy]
            js = self.joysticks[self.active_joy]
            data["active_joystick"] = {
                "index": info.idx,
                "name": info.name,
                "axes": info.axes,
                "axis_values": [float(js.get_axis(i)) for i in range(info.axes)],
                "buttons": info.buttons,
                "buttons_pressed": [i for i in range(info.buttons) if js.get_button(i)],
                "hats": info.hats,
                "hat_values": [list(js.get_hat(i)) for i in range(info.hats)],
                "deadzone": self.deadzone,
            }
        else:
            data["active_joystick"] = None

        return data

    def _flush_snapshot(self) -> None:
        snapshot = self._joystick_snapshot()
        self._joystick_cfg_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._joystick_cfg_path.write_text(json.dumps(snapshot, indent=2))
        except OSError as exc:
            self._push(f"No se pudo guardar joystick en configs: {exc}")
        else:
            self._snapshot_dirty = False
            self._last_snapshot = time.monotonic()

    def _maybe_write_snapshot(self) -> None:
        if not self._snapshot_dirty:
            return

        now = time.monotonic()
        if now - self._last_snapshot < self._snapshot_cooldown:
            return

        self._flush_snapshot()

    def handle_event(self, app, ev: pygame.event.Event) -> None:
        if ev.type == pygame.QUIT:
            app.running = False
            return

        if ev.type == pygame.MOUSEWHEEL:
            mouse_pos = pygame.mouse.get_pos()
            scroll_speed = 30  # pixels per wheel turn

            if self._action_rect and self._action_rect.collidepoint(mouse_pos):
                self._action_scroll_y += ev.y * scroll_speed
                self._action_scroll_y = max(
                    0,
                    min(
                        self._action_scroll_y,
                        self._action_content_height - self._action_rect.height,
                    ),
                )
            elif self._log_rect and self._log_rect.collidepoint(mouse_pos):
                self._log_scroll_y += ev.y * scroll_speed
                self._log_scroll_y = max(
                    0,
                    min(
                        self._log_scroll_y,
                        self._log_content_height - self._log_rect.height,
                    ),
                )

        if ev.type == pygame.KEYDOWN:
            self.keys_down.add(ev.key)

            if ev.key == pygame.K_ESCAPE:
                app.running = False
                return

            if ev.key == pygame.K_r:
                self._discover_joysticks()
                self._push(f"Re-scan -> joysticks: {len(self.joysticks)}")
                return

            if ev.key == pygame.K_TAB and self.joysticks:
                self.active_joy = (self.active_joy + 1) % len(self.joysticks)
                self._push(
                    f"Active joy -> {self.active_joy} ({self.joy_infos[self.active_joy].name})"
                )
                self._mark_snapshot_dirty()
                return

            self._push(f"KEYDOWN key={ev.key}")

        elif ev.type == pygame.KEYUP:
            self.keys_down.discard(ev.key)
            self._push(f"KEYUP key={ev.key}")

        elif ev.type == pygame.JOYBUTTONDOWN:
            self._push(f"JOY{ev.joy} BUTTONDOWN b={ev.button}")
            self._mark_snapshot_dirty()

        elif ev.type == pygame.JOYBUTTONUP:
            self._push(f"JOY{ev.joy} BUTTONUP b={ev.button}")
            self._mark_snapshot_dirty()

        elif ev.type == pygame.JOYHATMOTION:
            self._push(f"JOY{ev.joy} HAT v={ev.value}")
            self._mark_snapshot_dirty()

        elif ev.type == pygame.JOYAXISMOTION:
            self._push(f"JOY{ev.joy} AXIS a={ev.axis} v={ev.value:+.3f}")
            self._mark_snapshot_dirty()

    def update(self, app, dt: float) -> None:
        self._maybe_write_snapshot()

    def render(self, app, screen: pygame.Surface) -> None:
        w, h = screen.get_size()
        m = min(w, h)

        # Helpers relativos
        def px(rx: float) -> int:
            return int(w * rx)

        def py(ry: float) -> int:
            return int(h * ry)

        def ps(rs: float) -> int:
            return max(1, int(m * rs))

        # Fonts relativas (solo si cambia tamaño)
        big_size = ps(0.06)
        small_size = ps(0.05)
        if (
            not self.font
            or self.font.get_height() < big_size - 2
            or self.font.get_height() > big_size + 2
        ):
            self.font = pygame.font.Font(None, big_size)
        if (
            not self.small
            or self.small.get_height() < small_size - 2
            or self.small.get_height() > small_size + 2
        ):
            self.small = pygame.font.Font(None, small_size)

        screen.fill((10, 10, 10))

        # Layout relativo
        pad_x = px(0.03)
        pad_y = py(0.03)
        gutter = px(0.03)

        left_w = px(0.45)  # panel principal
        right_x = pad_x + left_w + gutter
        right_w = w - right_x - pad_x

        y = pad_y

        def draw_line(text: str, big: bool = False, col_x: int | None = None) -> int:
            nonlocal y
            f = self.font if big else self.small
            surf = f.render(text, True, (220, 220, 220))
            x0 = col_x if col_x is not None else pad_x
            screen.blit(surf, (x0, y))
            y += int(f.get_height() * 1.25)
            return y

        def draw_header(text: str) -> None:
            nonlocal y
            f = self.font
            surf = f.render(text, True, (180, 180, 255))
            screen.blit(surf, (pad_x, y))
            y += int(f.get_height() * 1.3)

        def bar(label: str, value: float, bx: int, by: int, bw: int, bh: int) -> None:
            # clamp
            v = max(-1.0, min(1.0, value))
            # fondo
            pygame.draw.rect(
                screen, (55, 55, 55), (bx, by, bw, bh), border_radius=ps(0.010)
            )
            # centro
            mid = bx + bw // 2
            pygame.draw.line(screen, (110, 110, 110), (mid, by), (mid, by + bh), 1)
            # relleno
            fill = int((v + 1.0) * 0.5 * bw)
            pygame.draw.rect(
                screen, (200, 200, 80), (bx, by, fill, bh), border_radius=ps(0.010)
            )

        # Panel izquierdo (estado)
        draw_header("Input Test (relative layout)")

        if not self.joysticks:
            draw_line("No joystick detected.", big=False)
            draw_line("TAB: (none) | R: rescan | ESC: quit", big=False)
        else:
            info = self.joy_infos[self.active_joy]
            js = self.joysticks[self.active_joy]

            draw_line(f"Active joy: {info.idx} | {info.name}", big=False)
            draw_line(
                f"Buttons: {info.buttons} | Axes: {info.axes} | Hats: {info.hats}",
                big=False,
            )
            draw_line("TAB: switch joy | R: rescan | ESC: quit", big=False)

            y += py(0.01)

            pressed_idx = [i for i in range(info.buttons) if js.get_button(i)]
            if pressed_idx:
                pressed_label = ", ".join(
                    self._controller_button_label(i) for i in pressed_idx
                )
            else:
                pressed_label = "None"
            draw_line(f"Pressed buttons: {pressed_label}", big=False)

            if info.hats:
                hat_parts = []
                for i in range(info.hats):
                    value = js.get_hat(i)
                    hat_parts.append(f"{self._controller_hat_label(i)}={value}")
                draw_line(f"Hats: {' | '.join(hat_parts)}", big=False)

            y += py(0.01)

            # Axes con barritas relativas
            if info.axes:
                max_axes_to_show = 8
                axes_to_show = min(info.axes, max_axes_to_show)

                label_gap = py(0.006)
                bar_h = ps(0.018)
                bar_w = int(left_w * 0.65)

                for a in range(axes_to_show):
                    v = float(js.get_axis(a))
                    if abs(v) < self.deadzone:
                        v = 0.0

                    # label
                    label = f"{self._controller_axis_label(a)}: {v:+.3f}"
                    surf = self.small.render(label, True, (220, 220, 220))
                    screen.blit(surf, (pad_x, y))
                    y += surf.get_height() + label_gap

                    # bar
                    bx = pad_x
                    by = y
                    bar(label, v, bx, by, bar_w, bar_h)
                    y += bar_h + py(0.014)

                if info.axes > axes_to_show:
                    draw_line(
                        f"... ({info.axes - axes_to_show} more axes hidden)", big=False
                    )

        dict_gap = py(0.02)
        dict_h = int(h * 0.45)
        self._action_rect = pygame.Rect(right_x, pad_y, right_w, dict_h)

        log_h = max(0, h - self._action_rect.bottom - dict_gap - pad_y)
        self._log_rect = pygame.Rect(
            right_x,
            self._action_rect.bottom + dict_gap,
            right_w,
            log_h,
        )

        self._draw_action_dictionary(screen, self._action_rect)
        self._draw_event_log(screen, self._log_rect)

    def _draw_action_dictionary(
        self, screen: pygame.Surface, rect: pygame.Rect
    ) -> None:
        if rect.width <= 0 or rect.height <= 0:
            return

        pygame.draw.rect(screen, (18, 18, 24), rect, border_radius=12)
        pygame.draw.rect(screen, (40, 40, 60), rect, width=1, border_radius=12)

        if self._action_surface:
            screen.blit(
                self._action_surface,
                (rect.x, rect.y),
                (0, self._action_scroll_y, rect.width, rect.height),
            )

    def _render_action_surface(self) -> None:
        if not self.small or not self._action_rect:
            return

        width = self._action_rect.width
        y = 12 + self.small.get_height() + 10

        # Calculate content height
        content_h = y
        for __, actions in [
            ("Entities in scene", self._action_dictionary.get("entities", [])),
            ("Editor tooling", self._action_dictionary.get("editor", [])),
        ]:
            if not actions:
                continue
            content_h += len(actions) * (self.small.get_height() + 8)
        if self._action_dictionary_error:
            content_h += self.small.get_height() + 6
        self._action_content_height = content_h

        # Create surface
        self._action_surface = pygame.Surface((width, content_h), pygame.SRCALPHA)
        self._action_surface.fill((0, 0, 0, 0))

        # Render content
        title = self.small.render("Action Dictionary", True, (180, 180, 255))
        self._action_surface.blit(title, (14, 12))

        # Header for the table
        header_font = self.small
        h_target = header_font.render("Target", True, (140, 190, 255))
        h_action = header_font.render("Action", True, (140, 190, 255))
        h_bindings = header_font.render("Bindings", True, (140, 190, 255))

        col_target_x = 20
        col_action_x = 150
        col_bindings_x = 300

        self._action_surface.blit(h_target, (col_target_x, y))
        self._action_surface.blit(h_action, (col_action_x, y))
        self._action_surface.blit(h_bindings, (col_bindings_x, y))
        y += h_target.get_height() + 6

        contexts = [
            ("Entities in scene", self._action_dictionary.get("entities", [])),
            ("Editor tooling", self._action_dictionary.get("editor", [])),
        ]

        for ctx_label, actions in contexts:
            if not actions:
                continue

            for action in actions:
                target_surf = self.small.render(
                    str(action.target), True, (220, 220, 220)
                )
                action_surf = self.small.render(
                    str(action.action), True, (220, 220, 220)
                )

                bindings_text = ", ".join(
                    self._format_binding(b) for b in action.bindings
                )
                bindings_surf = self.small.render(bindings_text, True, (180, 180, 180))

                self._action_surface.blit(target_surf, (col_target_x, y))
                self._action_surface.blit(action_surf, (col_action_x, y))
                self._action_surface.blit(bindings_surf, (col_bindings_x, y))

                y += target_surf.get_height() + 8

        if self._action_dictionary_error:
            err = self.small.render(
                self._action_dictionary_error, True, (220, 130, 130)
            )
            self._action_surface.blit(err, (14, content_h - err.get_height() - 6))

    def _draw_event_log(self, screen: pygame.Surface, rect: pygame.Rect) -> None:
        if rect.width <= 0 or rect.height <= 0:
            return

        pygame.draw.rect(screen, (18, 18, 24), rect, border_radius=12)
        pygame.draw.rect(screen, (40, 40, 60), rect, width=1, border_radius=12)

        if self._log_surface:
            screen.blit(
                self._log_surface,
                (rect.x, rect.y),
                (0, self._log_scroll_y, rect.width, rect.height),
            )

    def _render_log_surface(self) -> None:
        if not self.small or not self._log_rect:
            return

        width = self._log_rect.width
        line_gap = 4
        content_h = 12 + self.small.get_height() + 6
        content_h += len(self.events) * (self.small.get_height() + line_gap)
        self._log_content_height = content_h

        self._log_surface = pygame.Surface((width, content_h), pygame.SRCALPHA)
        self._log_surface.fill((0, 0, 0, 0))

        title = self.small.render("Last events", True, (180, 180, 255))
        self._log_surface.blit(title, (14, 12))

        ty = 12 + title.get_height() + 6
        for msg in self.events:
            surf = self.small.render(msg, True, (200, 200, 200))
            self._log_surface.blit(surf, (18, ty))
            ty += surf.get_height() + line_gap

    def _load_controller_profile(self) -> None:
        if not self._controller_cfg_path.exists():
            self.controller_profile = ControllerProfile.default()
            self.deadzone = self.controller_profile.deadzone
            return

        try:
            self.controller_profile = ControllerProfile.from_toml(
                self._controller_cfg_path
            )
        except (OSError, ValueError) as exc:
            self._push(f"No se pudo leer controller profile: {exc}")
            self.controller_profile = ControllerProfile.default()
        self.deadzone = self.controller_profile.deadzone

    def _refresh_action_dictionary(self) -> None:
        contexts: dict[str, list] = {"entities": [], "editor": []}
        try:
            contexts["editor"] = gather_input_actions(
                EditorScene, context="editor", default_target="Editor"
            )
        except Exception as exc:
            self._action_dictionary_error = f"Editor bindings invalid: {exc}"
            self._action_dictionary = contexts
            self._render_action_surface()
            return

        if self._composition_path is None:
            self._action_dictionary_error = "No composition detected for entity lookup."
            self._action_dictionary = contexts
            self._render_action_surface()
            return

        try:
            runtime = load_composition(self._composition_path)
        except Exception as exc:
            self._action_dictionary_error = f"Composition load failed: {exc}"
            self._action_dictionary = contexts
            self._render_action_surface()
            return

        for node in runtime.iter_nodes("entity"):
            try:
                actions = gather_input_actions(
                    node.instance,
                    context="entity",
                    default_target=getattr(
                        node.instance, "__class__", type(node.instance)
                    ).__name__,
                )
            except Exception as exc:
                self._push(f"Input metadata error in {node.id}: {exc}")
                continue
            contexts["entities"].extend(actions)

        self._action_dictionary = contexts
        self._action_dictionary_error = None
        self._render_action_surface()

    def _controller_button_label(self, control: str | int) -> str:
        if self.controller_profile:
            return self.controller_profile.button_label(control)
        if isinstance(control, int):
            return f"Button {control}"
        return control

    def _controller_axis_label(self, control: str | int) -> str:
        if self.controller_profile:
            return self.controller_profile.axis_label(control)
        if isinstance(control, int):
            return f"Axis {control}"
        return control

    def _controller_hat_label(self, control: str | int) -> str:
        if self.controller_profile:
            return self.controller_profile.hat_label(control)
        if isinstance(control, int):
            return f"Hat {control}"
        return control

    def _format_binding(self, binding) -> str:
        if binding.label:
            base = binding.label
        elif binding.device == "keyboard":
            base = self._key_label(binding.control)
        elif binding.device == "mouse":
            base = self._mouse_label(binding.control)
        elif binding.device == "joystick_button":
            base = self._controller_button_label(binding.control)
        elif binding.device == "joystick_axis":
            base = self._controller_axis_label(binding.control)
        elif binding.device == "joystick_hat":
            base = self._controller_hat_label(binding.control)
        else:
            base = binding.control

        if binding.modifiers:
            mods = "+".join(binding.modifiers)
            return f"{mods}+{base}"
        return base

    def _key_label(self, control: str) -> str:
        attr_name = control.upper()
        keycode = getattr(pygame, attr_name, None)
        if isinstance(keycode, int):
            return pygame.key.name(keycode).replace("_", " ").title()
        return control

    def _mouse_label(self, control: str) -> str:
        mapping = {
            "button1": "Left Click",
            "button2": "Middle Click",
            "button3": "Right Click",
        }
        return mapping.get(control.lower(), control.title())

    def _default_composition_path(self, root: Path) -> Path | None:
        comps = root / "configs" / "compositions"
        for candidate in ("editor_export.eei.json", "demo_face.eei.json"):
            cand_path = comps / candidate
            if cand_path.exists():
                return cand_path
        return None
