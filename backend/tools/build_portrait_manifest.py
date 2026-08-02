"""Собрать манифест портретов игроков для фронтенда.

Имена файлов не совпадают с никами из OpenDota: в никах встречаются иероглифы,
масти и прочие украшения (`医者watson``, `Ace ♠`, `Mirage`雨`), а в файлах —
их «чистая» форма. Плюс попадаются опечатки (`Np[o]ne-` вместо `No[o]ne-`).

Скрипт нормализует и то, и другое до [a-z0-9] и пишет
frontend/public/assets/players/manifest.json вида:

    {"TeamYandex": {"watson": "watson.png", "dm": "DM.png"}, ...}

Фронтенд нормализует ник тем же способом и берёт файл по ключу.

    python tools/build_portrait_manifest.py
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

FRONTEND_PLAYERS = (
    Path(__file__).resolve().parents[2] / "frontend" / "public" / "assets" / "players"
)

# Ручные алиасы для случаев, где нормализация не спасает: опечатка в имени файла.
ALIASES: dict[str, dict[str, str]] = {
    "TeamVision": {"noone": "Np[o]ne-.webp"},
}


def normalise(value: str) -> str:
    """Ник или имя файла -> сравнимая форма: только латиница и цифры."""
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", ascii_only.lower())


def build() -> dict[str, dict[str, str]]:
    manifest: dict[str, dict[str, str]] = {}
    for team_dir in sorted(p for p in FRONTEND_PLAYERS.iterdir() if p.is_dir()):
        entries: dict[str, str] = {}
        for image in sorted(team_dir.glob("*.webp")):
            key = normalise(image.stem)
            if key:
                entries.setdefault(key, image.name)
        entries |= ALIASES.get(team_dir.name, {})
        manifest[team_dir.name] = entries
    return manifest


def main() -> int:
    if not FRONTEND_PLAYERS.exists():
        print(f"нет каталога с портретами: {FRONTEND_PLAYERS}")
        return 1

    manifest = build()
    path = FRONTEND_PLAYERS / "manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    total = sum(len(v) for v in manifest.values())
    print(f"{path}: {len(manifest)} команд, {total} портретов")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
