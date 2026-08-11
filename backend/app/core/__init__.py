"""Канонический слой: одна форма матча для всех анализаторов.

`core` не знает ни про OpenDota, ни про реплеи — источники складываются в его
структуры адаптерами. Всё, что считает метрики, читает отсюда.
"""

from app.core.model import (
    FANTASY_STATS,
    PROFILE_FIELDS,
    STATS_VERSION,
    CanonicalMatch,
    DraftPick,
    PlayerGame,
    TeamGame,
)
from app.core.opendota_adapter import from_opendota
from app.core.provenance import (
    Availability,
    Provenance,
    Source,
    best_source,
    describe,
    merge_stats,
    unusable_stats,
)

__all__ = [
    "Availability",
    "CanonicalMatch",
    "DraftPick",
    "FANTASY_STATS",
    "PROFILE_FIELDS",
    "PlayerGame",
    "Provenance",
    "STATS_VERSION",
    "Source",
    "TeamGame",
    "best_source",
    "describe",
    "from_opendota",
    "merge_stats",
    "unusable_stats",
]
