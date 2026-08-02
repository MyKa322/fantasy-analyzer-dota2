"""Забор данных из внешних API и их приведение к схеме проекта."""

from .opendota import OpenDotaClient, fetch_parsed_matches
from .stat_mapping import (
    APPROXIMATE_STATS,
    STAT_SOURCES,
    UNAVAILABLE_STATS,
    Availability,
    extract_match_stats,
    extract_player_stats,
    is_parsed,
    missing_stats,
    series_key,
)

__all__ = [
    "APPROXIMATE_STATS",
    "Availability",
    "OpenDotaClient",
    "STAT_SOURCES",
    "UNAVAILABLE_STATS",
    "extract_match_stats",
    "extract_player_stats",
    "fetch_parsed_matches",
    "is_parsed",
    "missing_stats",
    "series_key",
]
