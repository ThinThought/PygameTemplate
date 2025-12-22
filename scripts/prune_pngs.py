#!/usr/bin/env python3
"""Trim away mostly-transparent borders from PNG sprites."""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps


def iter_pngs(targets: Iterable[Path]) -> Iterable[Path]:
    for target in targets:
        if target.is_dir():
            yield from target.rglob("*.png")
        elif target.suffix.lower() == ".png":
            yield target


def prune_image(path: Path, threshold: int, margin: int, dry_run: bool) -> str:
    image = Image.open(path).convert("RGBA")
    alpha = image.split()[-1]

    # Build a binary mask by ignoring almost transparent pixels.
    mask = alpha.point(lambda a: 255 if a > threshold else 0)
    bbox = mask.getbbox()

    if not bbox:
        return "blank"

    cropped = image.crop(bbox)

    if margin:
        cropped = ImageOps.expand(cropped, border=margin, fill=(0, 0, 0, 0))

    if dry_run:
        return "would-change" if cropped.size != image.size else "unchanged"

    if cropped.size == image.size and margin == 0:
        return "unchanged"

    cropped.save(path)
    return "pruned" if cropped.size != image.size else "margin-only"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prune transparent padding around PNG sprites. "
            "Targets default to assets/images/platforms."
        )
    )
    parser.add_argument(
        "targets",
        nargs="*",
        default=["assets/images/platforms"],
        help="Directories or PNG files to process.",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=5,
        help="Minimum alpha value (0-255) treated as visible content.",
    )
    parser.add_argument(
        "--margin",
        type=int,
        default=2,
        help="Transparent pixels to add back after cropping.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    targets = [Path(entry).resolve() for entry in args.targets]
    stats: Counter[str] = Counter()

    for png in iter_pngs(targets):
        stats[prune_image(png, args.threshold, args.margin, args.dry_run)] += 1

    if not stats:
        print("No PNG files found.")
    else:
        for key, count in sorted(stats.items()):
            print(f"{key:>12}: {count}")


if __name__ == "__main__":
    main()
