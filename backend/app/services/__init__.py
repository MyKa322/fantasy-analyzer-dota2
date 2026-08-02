"""Сервисный слой: связывает хранилище с аналитическими модулями."""

from .analysis import (
    ROLE_SIZES,
    build_role_history,
    infer_team_roles,
    latest_ratings,
    load_match_records,
    recompute_ratings,
)

__all__ = [
    "ROLE_SIZES",
    "build_role_history",
    "infer_team_roles",
    "latest_ratings",
    "load_match_records",
    "recompute_ratings",
]
