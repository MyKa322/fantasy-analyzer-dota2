"""Вычисление фич по каноническому матчу.

Слой тонкий по замыслу: он только обходит реестр и склеивает результаты. Вся
содержательная часть живёт в `match.py` и `player.py`, где каждая группа фич —
отдельная чистая функция, которую можно вызвать на одном матче и глазами
проверить.
"""

from __future__ import annotations

from app.core import CanonicalMatch, PlayerGame

# Импорт ради побочного эффекта: декораторы наполняют реестр. Без него реестр
# пуст, и фичи молча не считаются — поэтому импорт явный и с пометкой.
from app.features import match as _match_features  # noqa: F401
from app.features import player as _player_features  # noqa: F401
from app.features.registry import MATCH_FEATURES, PLAYER_FEATURES


def match_features(match: CanonicalMatch) -> dict[str, float]:
    """Все фичи уровня матча."""
    out: dict[str, float] = {}
    for group in MATCH_FEATURES:
        out.update(group.fn(match))
    return out


def player_features(match: CanonicalMatch, player: PlayerGame) -> dict[str, float]:
    """Все фичи одного игрока в этой карте."""
    out: dict[str, float] = {}
    for group in PLAYER_FEATURES:
        out.update(group.fn(match, player))
    return out


def all_player_features(match: CanonicalMatch) -> dict[int, dict[str, float]]:
    """Фичи всех опознанных игроков карты, ключ — account_id.

    Анонимные пропускаются: сопоставить их с игроком всё равно нельзя, а строка
    без account_id в таблице фич — мусор, который потом никто не удалит.
    """
    return {
        player.account_id: player_features(match, player)
        for player in match.players
        if player.account_id is not None
    }
