from __future__ import annotations

from pathlib import Path
import pygame


class AudioManager:
    def __init__(self, assets_dir: Path) -> None:
        self.assets_dir = assets_dir
        self.sfx_dir = assets_dir / "sounds"
        self.music_dir = assets_dir / "music"

        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self.current_music: str | None = None

    # ---------- INIT ----------

    def init(
        self, *, frequency: int = 44100, channels: int = 2, buffer: int = 512
    ) -> None:
        if not pygame.mixer.get_init():
            pygame.mixer.init(
                frequency=frequency,
                channels=channels,
                buffer=buffer,
            )

    # ---------- SFX ----------

    def load_sound(self, name: str) -> pygame.mixer.Sound:
        if name in self._sounds:
            return self._sounds[name]

        path = self.sfx_dir / name
        sound = pygame.mixer.Sound(path)
        self._sounds[name] = sound
        return sound

    def play_sound(self, name: str, *, volume: float = 1.0) -> None:
        sound = self.load_sound(name)
        sound.set_volume(volume)
        sound.play()

    def stop_all_sounds(self) -> None:
        pygame.mixer.stop()

    # ---------- MUSIC ----------

    def play_music(
        self,
        name: str,
        *,
        volume: float = 1.0,
        loop: bool = True,
        fade_ms: int = 0,
    ) -> None:
        path = self.music_dir / name
        pygame.mixer.music.load(path)
        pygame.mixer.music.set_volume(volume)
        pygame.mixer.music.play(-1 if loop else 0, fade_ms=fade_ms)
        self.current_music = name

    def stop_music(self, *, fade_ms: int = 0) -> None:
        if fade_ms > 0:
            pygame.mixer.music.fadeout(fade_ms)
        else:
            pygame.mixer.music.stop()
        self.current_music = None

    def pause_music(self) -> None:
        pygame.mixer.music.pause()

    def resume_music(self) -> None:
        pygame.mixer.music.unpause()
