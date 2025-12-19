from __future__ import annotations

from pathlib import Path
import pygame
from rich.console import Console
from rich.panel import Panel

from game.core.clock import GameClock
from game.core.resources import Resources
from game.core.config import WindowConfig
from game.core.audio import AudioManager

from game.scenes import *  # ojo: recomendado solo si __all__ está bien


console = Console()


class App:
    def __init__(self, config: WindowConfig) -> None:
        self.cfg = config

        pygame.init()
        pygame.display.set_caption(self.cfg.title)
        self.screen = pygame.display.set_mode((self.cfg.width, self.cfg.height))

        self.clock = GameClock(self.cfg.fps)

        root = Path(__file__).resolve().parents[2]
        assets_dir = root / "assets"
        self.resources = Resources(assets_dir)

        self.audio = AudioManager(assets_dir)
        self.audio.init()

        self.running = True

        # Lista: da igual lo que metas aquí, el ciclo recorre TODO
        self.scenes: list[Scene] = [
            InputTesterScene(),
            EntityEditorScene(),
        ]

        self._scene_index = 2
        self.scene: Scene = self.scenes[self._scene_index]

        console.print(Panel.fit("✅ Pygame initialized", border_style="green"))
        console.print(Panel.fit("F1/F2 o TAB/SHIFT+TAB: cambiar escena", border_style="cyan"))

    # --- Scene switching -------------------------------------------------

    def _wrap_index(self, index: int) -> int:
        if not self.scenes:
            return 0
        return index % len(self.scenes)

    def set_scene(self, index: int) -> None:
        """Cambia a la escena por índice (con wrap)."""
        if not self.scenes:
            return

        new_index = self._wrap_index(index)
        if new_index == self._scene_index:
            return

        self.scene.on_exit(self)

        self._scene_index = new_index
        self.scene = self.scenes[self._scene_index]
        self.scene.on_enter(self)

        console.print(
            Panel.fit(
                f"🎬 Scene -> {self.scene.__class__.__name__} ({self._scene_index+1}/{len(self.scenes)})",
                border_style="magenta",
            )
        )

    def cycle_scene(self, step: int = 1) -> None:
        """Recorre la lista completa (wrap infinito). step puede ser +1 o -1 o lo que quieras."""
        self.set_scene(self._scene_index + step)

    def next_scene(self) -> None:
        self.cycle_scene(+1)

    def prev_scene(self) -> None:
        self.cycle_scene(-1)

    # --- Main loop -------------------------------------------------------

    def run(self) -> None:
        self.scene.on_enter(self)

        while self.running:
            dt = self.clock.tick()

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.running = False
                    continue

                if ev.type == pygame.KEYDOWN:
                    # recorrido genérico: no importa cuántas escenas haya
                    if ev.key in (pygame.K_F2, pygame.K_TAB) and not (ev.mod & pygame.KMOD_SHIFT):
                        self.next_scene()
                        continue

                    if ev.key == pygame.K_F1 or (ev.key == pygame.K_TAB and (ev.mod & pygame.KMOD_SHIFT)):
                        self.prev_scene()
                        continue

                    # Opcional: saltar directo con números 1..9
                    if pygame.K_1 <= ev.key <= pygame.K_9:
                        idx = ev.key - pygame.K_1
                        if idx < len(self.scenes):
                            self.set_scene(idx)
                            continue

                self.scene.handle_event(self, ev)

            self.scene.update(self, dt)
            self.scene.render(self, self.screen)
            pygame.display.flip()

        self.scene.on_exit(self)
        self.audio.stop_all_sounds()
        self.audio.stop_music()
        pygame.quit()
