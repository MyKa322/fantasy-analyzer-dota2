"""Материализация фич в базу.

Пересчёт идёт по версии, а не по времени: строка, посчитанная кодом с
`FEATURES_VERSION` ниже текущей, считается устаревшей и переписывается. Это
единственный способ не остаться навсегда с половиной базы в старом формате —
ровно та же логика, что у `STATS_VERSION` в ingest, и заведена она по той же
причине.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db_adapter import from_db
from app.db.models import Match, MatchFeature, PlayerMatchFeature, PlayerMatchStat
from app.features.compute import all_player_features, match_features
from app.features.registry import FEATURES_VERSION

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MaterializeResult:
    matches: int
    players: int
    skipped_up_to_date: int

    def __str__(self) -> str:
        return (
            f"матчей пересчитано: {self.matches}, строк игроков: {self.players}, "
            f"актуальных пропущено: {self.skipped_up_to_date}"
        )


def _stale_match_ids(session: Session, *, since: datetime | None) -> list[int]:
    """Матчи, у которых фич нет вовсе или они посчитаны старой версией."""
    fresh = select(MatchFeature.match_id).where(
        MatchFeature.features_version == FEATURES_VERSION
    )
    query = select(Match.match_id).where(Match.match_id.not_in(fresh))
    if since is not None:
        query = query.where(Match.start_time >= since)
    return list(session.scalars(query))


def _load(
    session: Session, match_ids: Sequence[int]
) -> Iterator[tuple[Match, list[PlayerMatchStat]]]:
    """Матчи вместе со статами, пачкой.

    Отдельным запросом на статы вместо ленивой связи: полторы тысячи матчей по
    одному запросу на каждый — это минуты вместо секунды.
    """
    matches = {
        m.match_id: m for m in session.scalars(select(Match).where(Match.match_id.in_(match_ids)))
    }
    by_match: dict[int, list[PlayerMatchStat]] = {mid: [] for mid in matches}
    for row in session.scalars(
        select(PlayerMatchStat).where(PlayerMatchStat.match_id.in_(match_ids))
    ):
        by_match.setdefault(row.match_id, []).append(row)

    for match_id, match in matches.items():
        yield match, by_match.get(match_id, [])


def materialize(
    session: Session,
    *,
    since: datetime | None = None,
    batch_size: int = 500,
    force: bool = False,
) -> MaterializeResult:
    """Посчитать и сохранить фичи для устаревших матчей.

    `force` пересчитывает всё в окне, не глядя на версию, — нужно, когда меняется
    не состав фич, а исходные статы (например, матч перезабрали из реплея).
    """
    total_query = select(func.count()).select_from(Match)
    if since is not None:
        total_query = total_query.where(Match.start_time >= since)
    total = int(session.scalar(total_query) or 0)

    if force:
        query = select(Match.match_id)
        if since is not None:
            query = query.where(Match.start_time >= since)
        match_ids = list(session.scalars(query))
        skipped = 0
    else:
        match_ids = _stale_match_ids(session, since=since)
        skipped = max(total - len(match_ids), 0)

    computed_matches = 0
    computed_players = 0

    for start in range(0, len(match_ids), batch_size):
        chunk = match_ids[start : start + batch_size]
        existing_match_rows = {
            row.match_id: row
            for row in session.scalars(
                select(MatchFeature).where(MatchFeature.match_id.in_(chunk))
            )
        }
        existing_player_rows = {
            (row.match_id, row.account_id): row
            for row in session.scalars(
                select(PlayerMatchFeature).where(PlayerMatchFeature.match_id.in_(chunk))
            )
        }

        for match_row, stat_rows in _load(session, chunk):
            canonical = from_db(match_row, stat_rows)

            feature_row = existing_match_rows.get(canonical.match_id)
            if feature_row is None:
                feature_row = MatchFeature(match_id=canonical.match_id)
                session.add(feature_row)
            feature_row.features = match_features(canonical)
            feature_row.features_version = FEATURES_VERSION
            feature_row.computed_at = datetime.now(timezone.utc)
            computed_matches += 1

            for account_id, values in all_player_features(canonical).items():
                player_row = existing_player_rows.get((canonical.match_id, account_id))
                if player_row is None:
                    player_row = PlayerMatchFeature(
                        match_id=canonical.match_id, account_id=account_id
                    )
                    session.add(player_row)
                player_row.features = values
                player_row.features_version = FEATURES_VERSION
                player_row.start_time = canonical.start_time
                computed_players += 1

        session.flush()
        log.info("фичи: %d/%d матчей", min(start + batch_size, len(match_ids)), len(match_ids))

    return MaterializeResult(
        matches=computed_matches, players=computed_players, skipped_up_to_date=skipped
    )
