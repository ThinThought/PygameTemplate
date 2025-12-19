from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import pygame

from game.scenes.base import Scene


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

        self.events: deque[str] = deque(maxlen=12)
        self.keys_down: set[int] = set()

        self.joysticks: list[pygame.joystick.Joystick] = []
        self.joy_infos: list[JoyInfo] = []
        self.active_joy = 0

        self.deadzone = 0.20

    def on_enter(self, app) -> None:
        pygame.joystick.init()
        self._discover_joysticks()

        self.events.clear()
        self._push(f"Joysticks detected: {len(self.joysticks)}")
        if self.joysticks:
            self._push(f"Active joy: {self.active_joy} ({self.joy_infos[self.active_joy].name})")
        else:
            self._push("No joystick found (ok on some devices).")

        # fuentes se crean en render porque dependen de tamaño de pantalla (relativo)
        self.font = None
        self.small = None

    def _discover_joysticks(self) -> None:
        self.joysticks = []
        self.joy_infos = []

        for i in range(pygame.joystick.get_count()):
            js = pygame.joystick.Joystick(i)
            js.init()
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

    def _push(self, msg: str) -> None:
        self.events.appendleft(msg)

    def handle_event(self, app, ev: pygame.event.Event) -> None:
        if ev.type == pygame.QUIT:
            app.running = False
            return

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
                self._push(f"Active joy -> {self.active_joy} ({self.joy_infos[self.active_joy].name})")
                return

            self._push(f"KEYDOWN key={ev.key}")

        elif ev.type == pygame.KEYUP:
            self.keys_down.discard(ev.key)
            self._push(f"KEYUP key={ev.key}")

        elif ev.type == pygame.JOYBUTTONDOWN:
            self._push(f"JOY{ev.joy} BUTTONDOWN b={ev.button}")

        elif ev.type == pygame.JOYBUTTONUP:
            self._push(f"JOY{ev.joy} BUTTONUP b={ev.button}")

        elif ev.type == pygame.JOYHATMOTION:
            self._push(f"JOY{ev.joy} HAT v={ev.value}")

        elif ev.type == pygame.JOYAXISMOTION:
            self._push(f"JOY{ev.joy} AXIS a={ev.axis} v={ev.value:+.3f}")

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
        if not self.font or self.font.get_height() < big_size - 2 or self.font.get_height() > big_size + 2:
            self.font = pygame.font.Font(None, big_size)
        if not self.small or self.small.get_height() < small_size - 2 or self.small.get_height() > small_size + 2:
            self.small = pygame.font.Font(None, small_size)

        screen.fill((10, 10, 10))

        # Layout relativo
        pad_x = px(0.03)
        pad_y = py(0.03)
        gutter = px(0.03)

        left_w = px(0.45)   # panel principal
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
            pygame.draw.rect(screen, (55, 55, 55), (bx, by, bw, bh), border_radius=ps(0.010))
            # centro
            mid = bx + bw // 2
            pygame.draw.line(screen, (110, 110, 110), (mid, by), (mid, by + bh), 1)
            # relleno
            fill = int((v + 1.0) * 0.5 * bw)
            pygame.draw.rect(screen, (200, 200, 80), (bx, by, fill, bh), border_radius=ps(0.010))

        # Panel izquierdo (estado)
        draw_header("Input Test (relative layout)")

        if not self.joysticks:
            draw_line("No joystick detected.", big=False)
            draw_line("TAB: (none) | R: rescan | ESC: quit", big=False)
        else:
            info = self.joy_infos[self.active_joy]
            js = self.joysticks[self.active_joy]

            draw_line(f"Active joy: {info.idx} | {info.name}", big=False)
            draw_line(f"Buttons: {info.buttons} | Axes: {info.axes} | Hats: {info.hats}", big=False)
            draw_line("TAB: switch joy | R: rescan | ESC: quit", big=False)

            y += py(0.01)

            pressed = [i for i in range(info.buttons) if js.get_button(i)]
            draw_line(f"Pressed buttons: {pressed if pressed else '[]'}", big=False)

            if info.hats:
                hats = [js.get_hat(i) for i in range(info.hats)]
                draw_line(f"Hats: {hats}", big=False)

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
                    label = f"Axis {a}: {v:+.3f}"
                    surf = self.small.render(label, True, (220, 220, 220))
                    screen.blit(surf, (pad_x, y))
                    y += surf.get_height() + label_gap

                    # bar
                    bx = pad_x
                    by = y
                    bar(label, v, bx, by, bar_w, bar_h)
                    y += bar_h + py(0.014)

                if info.axes > axes_to_show:
                    draw_line(f"... ({info.axes - axes_to_show} more axes hidden)", big=False)

        # Panel derecho (event log)
        # Caja relativa para el log
        log_title = self.small.render("Last events", True, (180, 180, 255))
        screen.blit(log_title, (right_x, pad_y))

        ly = pad_y + int(log_title.get_height() * 1.4)
        max_log_h = h - ly - pad_y

        # fondo del panel de log
        panel_rect = pygame.Rect(right_x, ly - py(0.01), right_w, max_log_h + py(0.01))
        pygame.draw.rect(screen, (18, 18, 24), panel_rect, border_radius=ps(0.015))
        pygame.draw.rect(screen, (40, 40, 60), panel_rect, width=1, border_radius=ps(0.015))

        # texto log
        ty = ly
        line_gap = py(0.004)
        for msg in self.events:
            surf = self.small.render(msg, True, (200, 200, 200))
            screen.blit(surf, (right_x + px(0.01), ty))
            ty += surf.get_height() + line_gap
            if ty > panel_rect.bottom - py(0.02):
                break
