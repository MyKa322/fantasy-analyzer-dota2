"""Витрина фич: одно место, где метрика определена, и одна версия этой метрики.

До этого слоя одни и те же величины считались в трёх местах по-разному —
`fantasy/`, `analytics/` и `services/profiles.py`. Здесь метрика объявляется
один раз чистой функцией от канонического матча, материализуется в таблицу и
дальше читается всеми потребителями в одинаковом виде.
"""

from app.features.compute import all_player_features, match_features, player_features
from app.features.registry import (
    FEATURES_VERSION,
    MATCH_FEATURES,
    PLAYER_FEATURES,
    FeatureGroup,
    declared_keys,
    safe_ratio,
)
from app.features.store import MaterializeResult, materialize

__all__ = [
    "FEATURES_VERSION",
    "FeatureGroup",
    "MATCH_FEATURES",
    "MaterializeResult",
    "PLAYER_FEATURES",
    "all_player_features",
    "declared_keys",
    "match_features",
    "materialize",
    "player_features",
    "safe_ratio",
]
