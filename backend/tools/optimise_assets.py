"""Ужать портреты и логотипы до веб-размеров.

Исходники — PNG по мегабайту: 80 портретов дают 79 МБ, и в репозиторий такое
класть нельзя, а страница на них грузилась бы секундами. Портрет показывается
кружком 28-44 пикселя, логотип — иконкой, так что исходное разрешение не нужно
никому.

Скрипт читает исходные папки в корне проекта и перезаписывает
frontend/public/assets. Запускается вручную после обновления ассетов:

    python tools/optimise_assets.py

Каталоги перезаписываются целиком, поэтому манифесты портретов и героев после
него надо собрать заново — они лежат там же, но делаются другими скриптами:

    python tools/build_portrait_manifest.py
    python tools/build_hero_manifest.py
"""

from __future__ import annotations

import json
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
# Иконка героя стоит в строке таблицы и в списке пула — крупнее 96 не нужна.
HERO_SIZE = 96
# Предмет в слоте инвентаря — 28px, с запасом на retina.
ITEM_SIZE = 64
WEBP_QUALITY = 82

# Выгрузка интерфейса из игры. Оттуда нужны четыре файла и каталог предметов —
# остальные 4600 картинок к аналитике отношения не имеют.
PANORAMA = ROOT / "panorama" / "images"
MATERIALS = ROOT / "materials" / "vgui" / "hud"

# Карта и маркеры для страницы матча. Маркеры — чёрные глифы с альфой, на
# странице они красятся через CSS-маску, поэтому цвет исходника не важен.
MAP_ASSETS = {
    "minimap.webp": (PANORAMA / "textures" / "minimap_game_png.png", 512),
    "ward.webp": (MATERIALS / "minimap_ward_obs_psd_adc970aa.png", 64),
    "death.webp": (MATERIALS / "minimap_death_psd_6987e15d.png", 64),
    "roshan.webp": (MATERIALS / "minimap_roshancamp_psd_a910ba97.png", 64),
    "tower.webp": (MATERIALS / "minimap_tower45_psd_da58cb65.png", 64),
    "racks.webp": (MATERIALS / "minimap_racks45_psd_2d62119d.png", 64),
    "ancient.webp": (MATERIALS / "minimap_ancient_psd_1bfdd08d.png", 64),
}


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


def build_map(target_dir: Path) -> tuple[int, int]:
    """Миникарта и маркеры: файлы перечислены поимённо, а не собраны маской."""
    before = after = 0
    for name, (source, size) in MAP_ASSETS.items():
        if not source.exists():
            print(f"  пропуск: нет {source.name}")
            continue
        was, now = convert(source, target_dir / name, size)
        before += was
        after += now
    return before, after


def build_items(source_dir: Path, target_dir: Path) -> tuple[int, int]:
    """Иконки предметов плюс манифест имён.

    В логе покупок OpenDota лежит внутреннее имя (`power_treads`), а файлы
    выгружены как `power_treads_png.png`. Манифест нужен, чтобы страница знала,
    для каких предметов иконка вообще есть: набор в игре меняется каждый патч.
    """
    if not source_dir.exists():
        print(f"  пропуск: нет каталога {source_dir}")
        return 0, 0
    if target_dir.exists():
        shutil.rmtree(target_dir)

    before = after = 0
    names: list[str] = []
    for source in sorted(source_dir.glob("*.png")):
        name = source.stem.removesuffix("_png")
        was, now = convert(source, target_dir / f"{name}.webp", ITEM_SIZE)
        before += was
        after += now
        names.append(name)

    (target_dir / "manifest.json").write_text(
        json.dumps(sorted(names), ensure_ascii=False, indent=0), encoding="utf-8"
    )
    print(f"  предметов: {len(names)}")
    return before, after


def main() -> int:
    jobs = [
        ("портреты", ROOT / "players", FRONTEND_ASSETS / "players", PORTRAIT_SIZE, False),
        ("логотипы", ROOT / "teams", FRONTEND_ASSETS / "teams", CREST_SIZE, True),
        ("эмблемы", ROOT / "fantasy_craft", FRONTEND_ASSETS / "emblems", EMBLEM_SIZE, True),
        ("герои", ROOT / "heroes" / "icons", FRONTEND_ASSETS / "heroes", HERO_SIZE, True),
    ]

    grand_before = grand_after = 0
    for label, source, target, size, flat in jobs:
        print(f"{label}:")
        before, after = process(source, target, size, flat=flat)
        grand_before += before
        grand_after += after
        if before:
            print(f"  {before / 1024 / 1024:.1f} МБ -> {after / 1024 / 1024:.1f} МБ")

    for label, builder, target in (
        ("карта", build_map, FRONTEND_ASSETS / "map"),
        ("предметы", lambda t: build_items(PANORAMA / "items", t), FRONTEND_ASSETS / "items"),
    ):
        print(f"{label}:")
        before, after = builder(target)
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
