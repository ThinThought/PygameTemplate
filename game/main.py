from __future__ import annotations

from pathlib import Path
import sysconfig

from game.core.app import App
from game.core.config import load_window_config


def _share_path(*parts: str) -> Path:
    scheme = sysconfig.get_default_scheme()
    data = Path(sysconfig.get_path("data", scheme=scheme))
    return (data / "share" / "pygame-videogame-maker").joinpath(*parts)


def main() -> None:
    # En tu wheel actual, settings.toml quedó aplanado en:
    #   <prefix>/share/pygame-videogame-maker/settings.toml
    cfg = load_window_config(_share_path("settings.toml"))
    App(cfg).run()


if __name__ == "__main__":
    main()
