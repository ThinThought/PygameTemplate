from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pygame
from rich.console import Console
from rich.panel import Panel

from game.core.clock import GameClock
from game.core.resources import Resources
from game.scenes.base import Scene
from game.scenes.blank import BlankScene
from game.scenes.input_demo import InputTestScene
from game.scenes.assets_demo import AssetsTestScene
from game.core.config import WindowConfig
from game.core.audio import AudioManager


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
        self.scenes = [
            BlankScene(),
            InputTestScene(),
            AssetsTestScene()
        ]
        self.scene: Scene = self.scenes[2]

        console.print(Panel.fit("✅ Pygame initialized", border_style="green"))

    def run(self) -> None:
        self.scene.on_enter(self)

        while self.running:
            dt = self.clock.tick()

            for ev in pygame.event.get():
                self.scene.handle_event(self, ev)

            self.scene.update(self, dt)
            self.scene.render(self, self.screen)
            pygame.display.flip()

        self.scene.on_exit(self)
        self.audio.stop_all_sounds()
        self.audio.stop_music()
        pygame.quit()
