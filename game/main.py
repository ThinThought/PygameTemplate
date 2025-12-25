from __future__ import annotations

import importlib.resources
from pathlib import Path

from game.core.app import App
from game.core.config import load_window_config


def _share_path(*parts: str) -> Path:
    """
    Devuelve la ruta a un recurso empaquetado dentro del directorio 'game'.

    Usa importlib.resources para resolver la ruta de forma robusta,
    tanto en desarrollo como en una instalación.
    """
    return importlib.resources.files("game").joinpath(*parts)


def main() -> None:
    # Ahora que 'configs' está dentro del paquete 'game', lo cargamos así:
    cfg = load_window_config(_share_path("configs", "settings.toml"))
    App(cfg).run()


if __name__ == "__main__":
    main()
