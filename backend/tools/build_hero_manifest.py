"""Собрать манифест иконок героев и выбросить лишние файлы.

В матче лежит только `hero_id`, а иконки названы внутренним именем героя
(`npc_dota_hero_axe_png.webp`). Манифест связывает одно с другим:

    {"2": "npc_dota_hero_axe_png.webp", ...}

Заодно удаляются варианты образов (persona, alt, carnival) — их в справочнике
героев нет, а в репозитории они занимали бы место просто так.

    python tools/build_hero_manifest.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.profiles import load_hero_npc_names  # noqa: E402

HERO_ASSETS = (
    Path(__file__).resolve().parents[2] / "frontend" / "public" / "assets" / "heroes"
)


def main() -> int:
    npc_names = load_hero_npc_names()
    if not npc_names:
        print("справочник героев пуст — сначала `cli.py ingest-heroes`")
        return 1
    if not HERO_ASSETS.exists():
        print(f"нет каталога иконок {HERO_ASSETS} — сначала `tools/optimise_assets.py`")
        return 1

    files = {path.name: path for path in HERO_ASSETS.glob("*.webp")}
    manifest: dict[str, str] = {}
    missing: list[str] = []

    for hero_id, npc in sorted(npc_names.items()):
        name = f"{npc}_png.webp"
        if name in files:
            manifest[str(hero_id)] = name
        else:
            missing.append(npc)

    used = set(manifest.values())
    extra = [path for name, path in files.items() if name not in used]
    for path in extra:
        path.unlink()

    (HERO_ASSETS / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8"
    )

    print(f"{HERO_ASSETS / 'manifest.json'}: {len(manifest)} иконок")
    if extra:
        print(f"удалено вариантов образов: {len(extra)}")
    if missing:
        print(f"нет иконки для: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
