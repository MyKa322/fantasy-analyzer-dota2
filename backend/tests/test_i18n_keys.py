"""Словарь интерфейса покрывает всё, что приходит из данных.

Проверка идёт через границу языков намеренно. Интерфейс переводит по ключу
(`title.lucky.condition`, `stat.camps_stacked`, `title.note.patient`), а ключи
эти рождаются в конфиге и в анализаторе на Python. Опечатка или новый титул без
перевода не сломают ни сборку фронтенда, ни тесты бэкенда по отдельности:
страница просто молча покажет русскую строку читателю, выбравшему китайский.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.fantasy.rules import load_rules
from app.ingest.stat_mapping import PROFILE_FIELDS

MESSAGES = Path(__file__).resolve().parents[2] / "frontend" / "src" / "i18n" / "messages"

# Ключи с числами внутри — их перечисляем явно: в коде они собираются рядом с
# расчётом, и «найти автоматически» тут значит повторить сам разбор.
NOTE_KEYS = {
    "title.note.heroShare",
    "title.note.short",
    "title.note.lucky",
    "title.note.lost",
    "title.note.patient",
    "title.note.decider",
    "title.note.noHeroes",
    "title.note.outside",
    "title.note.notEnough",
}


def dictionary_keys() -> set[str]:
    """Ключи из всех файлов словаря — по левой части записи `"ключ": {`."""
    keys: set[str] = set()
    for path in MESSAGES.glob("*.ts"):
        keys |= set(re.findall(r'^\s*"([\w.\-]+)":\s*\{', path.read_text(encoding="utf-8"), re.M))
    return keys


def test_dictionary_is_not_empty() -> None:
    # Страховка от того, что файлы переехали и регулярка молча нашла ноль
    # ключей — тогда все проверки ниже прошли бы «успешно».
    assert len(dictionary_keys()) > 100


def test_every_title_condition_is_translated() -> None:
    keys = dictionary_keys()
    rules = load_rules()
    missing = [
        f"title.{title['key']}.condition"
        for group in ("prefixes", "suffixes")
        for title in rules.titles.get(group, []) or []
        if f"title.{title['key']}.condition" not in keys
    ]
    assert not missing, f"нет перевода условий титулов: {missing}"


def test_every_unmodelled_reason_is_translated() -> None:
    """У титулов с `note:` в конфиге ключ перевода собирается из их key."""
    keys = dictionary_keys()
    rules = load_rules()
    missing = [
        f"title.note.{title['key']}"
        for group in ("prefixes", "suffixes")
        for title in rules.titles.get(group, []) or []
        if title.get("note") and f"title.note.{title['key']}" not in keys
    ]
    assert not missing, f"нет перевода причин «не оценить»: {missing}"


def test_computed_notes_are_translated() -> None:
    assert not (NOTE_KEYS - dictionary_keys())


def test_every_stat_is_translated() -> None:
    """И Fantasy-статы, и обычная статистика профиля."""
    keys = dictionary_keys()
    rules = load_rules()
    stats = set(rules.stats) | set(PROFILE_FIELDS) | {"duration"}
    missing = sorted(f"stat.{stat}" for stat in stats if f"stat.{stat}" not in keys)
    assert not missing, f"нет перевода названий статов: {missing}"


def test_every_role_is_translated() -> None:
    keys = dictionary_keys()
    missing = [role for role in load_rules().role_slots if f"role.{role}" not in keys]
    assert not missing, f"нет перевода ролей: {missing}"


def test_every_trait_is_translated() -> None:
    keys = dictionary_keys()
    missing = [
        trait for trait in load_rules().traits if f"trait.{trait}.description" not in keys
    ]
    assert not missing, f"нет перевода описаний трейтов: {missing}"
