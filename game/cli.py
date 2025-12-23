from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path
from typing import Sequence

_COPY_DIRS = ("assets", "configs", "game", "vendor")
_COPY_FILES = (
    "pyproject.toml",
    "README.md",
    "deploy_to_console.sh",
    "uv.lock",
    "PygameVideogameMaker.pygame",
)
_IGNORE_PATTERNS = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", "*.py[co]")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="pygametemplate",
        description="Ejecuta la plantilla actual o genera un nuevo proyecto desde ella.",
    )
    parser.set_defaults(func=_run_game)
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser(
        "run", help="Ejecuta el juego definido en la plantilla."
    )
    run_parser.set_defaults(func=_run_game)

    new_parser = subparsers.add_parser(
        "new",
        help="Genera un nuevo proyecto copiando los archivos de la plantilla.",
    )
    new_parser.add_argument(
        "name",
        help="Nombre del proyecto o ruta destino. Se inferirá una carpeta con ese nombre.",
    )
    new_parser.add_argument(
        "-o",
        "--output-dir",
        default=".",
        help="Directorio donde se creará el proyecto (por defecto el directorio actual).",
    )
    new_parser.set_defaults(func=_generate_project)

    args = parser.parse_args(argv)
    func = args.func
    func(args)


def _run_game(_: argparse.Namespace) -> None:
    from game.main import main as run_game

    run_game()


def _generate_project(args: argparse.Namespace) -> None:
    destination = _resolve_destination(args.name, args.output_dir)
    template_root = Path(__file__).resolve().parents[1]

    if destination.exists():
        raise SystemExit(
            f"La ruta destino '{destination}' ya existe. Elige otra carpeta."
        )

    destination.mkdir(parents=True)

    for folder in _COPY_DIRS:
        src = template_root / folder
        if not src.exists():
            continue
        shutil.copytree(
            src, destination / folder, dirs_exist_ok=True, ignore=_IGNORE_PATTERNS
        )

    for file_name in _COPY_FILES:
        src_file = template_root / file_name
        if not src_file.exists():
            continue
        (destination / file_name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, destination / file_name)

    name_tokens = _tokenize_name(args.name)
    slug = (
        _slugify("-".join(name_tokens)) if name_tokens else _slugify(destination.name)
    )
    readable_name = _to_display_name(name_tokens) if name_tokens else destination.name
    launcher_stub = _to_pascal_case(name_tokens)

    _rewrite_pyproject(destination / "pyproject.toml", slug)
    _rename_launcher(destination, launcher_stub)
    _rewrite_readme(destination / "README.md", readable_name)

    rel_path = (
        destination.relative_to(Path.cwd())
        if destination.is_relative_to(Path.cwd())
        else destination
    )
    print(f"Proyecto generado en: {rel_path}")


def _resolve_destination(name: str, base_dir: str) -> Path:
    path_candidate = Path(name.strip())
    if not path_candidate.is_absolute():
        path_candidate = Path(base_dir).expanduser() / path_candidate
    return path_candidate.resolve()


def _tokenize_name(raw_name: str) -> list[str]:
    tokens = re.split(r"[^A-Za-z0-9]+", raw_name)
    return [token for token in tokens if token]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        raise SystemExit("No se pudo inferir un nombre válido para el proyecto.")
    return slug


def _to_display_name(tokens: list[str]) -> str:
    return " ".join(token.capitalize() for token in tokens) if tokens else "Nuevo Juego"


def _to_pascal_case(tokens: list[str]) -> str:
    return "".join(token.capitalize() for token in tokens) if tokens else "Game"


def _rewrite_pyproject(pyproject_path: Path, project_slug: str) -> None:
    if not pyproject_path.exists():
        return

    content = pyproject_path.read_text(encoding="utf-8")
    content = re.sub(
        r'(?m)^name\s*=\s*".*"$', f'name = "{project_slug}"', content, count=1
    )
    content = re.sub(
        r'(?m)^(\s*)pygametemplate\s*=\s*".*"$',
        r"\1" + f'{project_slug} = "game.cli:main"',
        content,
        count=1,
    )
    pyproject_path.write_text(content, encoding="utf-8")


def _rename_launcher(project_root: Path, launcher_stub: str) -> None:
    original_launcher = project_root / "PygameVideogameMaker.pygame"
    if not original_launcher.exists():
        return
    new_name = project_root / f"{launcher_stub or 'Game'}.pygame"
    original_launcher.rename(new_name)


def _rewrite_readme(readme_path: Path, project_name: str) -> None:
    if not readme_path.exists():
        return
    lines = readme_path.read_text(encoding="utf-8").splitlines()
    if not lines:
        return
    if lines[0].startswith("# "):
        lines[0] = f"# {project_name}"
        readme_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
