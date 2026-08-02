"""Ужать портреты и логотипы до веб-размеров.

Исходники — PNG по мегабайту: 80 портретов дают 79 МБ, и в репозиторий такое
класть нельзя, а страница на них грузилась бы секундами. Портрет показывается
кружком 28-44 пикселя, логотип — иконкой, так что исходное разрешение не нужно
никому.

Скрипт читает исходные папки в корне проекта и перезаписывает
frontend/public/assets. Запускается вручную после обновления ассетов:

    python tools/optimise_assets.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ASSETS = ROOT / "frontend" / "public" / "assets"

# Портрет рендерится максимум 44px, но с запасом на retina и крупные карточки.
PORTRAIT_SIZE = 256
CREST_SIZE = 192
EMBLEM_SIZE = 128
WEBP_QUALITY = 82


def convert(source: Path, target: Path, max_size: int) -> tuple[int, int]:
    """Ужать изображение и сохранить в WebP. Возвращает (было, стало) в байтах."""
    before = source.stat().st_size
    target.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(source) as image:
        image = image.convert("RGBA")
        image.thumbnail((max_size, max_size), Image.LANCZOS)
        image.save(target, "WEBP", quality=WEBP_QUALITY, method=6)

    return before, target.stat().st_size


def process(source_dir: Path, target_dir: Path, max_size: int, *, flat: bool) -> tuple[int, int]:
    total_before = total_after = 0
    if not source_dir.exists():
        print(f"  пропуск: нет каталога {source_dir}")
        return 0, 0

    if target_dir.exists():
        shutil.rmtree(target_dir)

    pattern = "*.png" if flat else "*/*.png"
    for source in sorted(source_dir.glob(pattern)):
        relative = source.name if flat else f"{source.parent.name}/{source.name}"
        target = target_dir / Path(relative).with_suffix(".webp")
        before, after = convert(source, target, max_size)
        total_before += before
        total_after += after

    return total_before, total_after


def main() -> int:
    jobs = [
        ("портреты", ROOT / "players", FRONTEND_ASSETS / "players", PORTRAIT_SIZE, False),
        ("логотипы", ROOT / "teams", FRONTEND_ASSETS / "teams", CREST_SIZE, True),
        ("эмблемы", ROOT / "fantasy_craft", FRONTEND_ASSETS / "emblems", EMBLEM_SIZE, True),
    ]

    grand_before = grand_after = 0
    for label, source, target, size, flat in jobs:
        print(f"{label}:")
        before, after = process(source, target, size, flat=flat)
        grand_before += before
        grand_after += after
        if before:
            print(f"  {before / 1024 / 1024:.1f} МБ -> {after / 1024 / 1024:.1f} МБ")

    if grand_before:
        print(
            f"\nитого: {grand_before / 1024 / 1024:.1f} МБ -> "
            f"{grand_after / 1024 / 1024:.1f} МБ "
            f"({grand_after / grand_before:.1%})"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
