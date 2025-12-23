from pathlib import Path
from game.core.app import App
from game.core.config import load_window_config


def main() -> None:
    cfg = load_window_config(Path("configs/settings.toml"))
    App(cfg).run()


if __name__ == "__main__":
    main()
