"""Pydantic-схемы API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TeamOut(BaseModel):
    team_id: int
    name: str
    tag: str | None = None
    compendium_name: str | None = None
    rating: float | None = None
    rd: float | None = None
    volatility: float | None = None
    matches_played: int = 0
    days_idle: float | None = None
    is_listable: bool = False


class RatingPoint(BaseModel):
    as_of: datetime
    rating: float
    rd: float
    matches_played: int


class RatingHistoryOut(BaseModel):
    team_id: int
    name: str | None = None
    points: list[RatingPoint]


class BucketProbabilityOut(BaseModel):
    team_id: int
    name: str | None = None
    probabilities: dict[str, float]
    advance: float
    expected_series: float


class PredictionPickOut(BaseModel):
    key: str
    pick: str
    label: str | None = None


class GroupPredictionOut(BaseModel):
    simulations: int
    teams: list[BucketProbabilityOut]
    plan: list[PredictionPickOut]
    expected_points: float
    expected_correct: float
    points_percentiles: dict[int, float]


class BracketMatchOut(BaseModel):
    match_key: str
    pick_team_id: int
    pick_name: str | None = None
    probability: float


class BracketPredictionOut(BaseModel):
    simulations: int
    champion_probability: dict[int, float]
    plan: list[BracketMatchOut]
    expected_points: float
    expected_correct: float


class EmblemIn(BaseModel):
    stat: str
    quality: str
    trait: str | None = None


class BannerIn(BaseModel):
    emblems: list[EmblemIn] = Field(min_length=1)


class ProjectionRequest(BaseModel):
    team_id: int
    role: str
    banner: BannerIn
    account_ids: list[int] | None = None
    simulations: int = 4000
    title_multiplier: float = 1.0
    series_distribution: dict[int, float] | None = None
    series_lengths: dict[int, float] | None = None
    history_days: int = 120


class ProjectionOut(BaseModel):
    role: str
    team_id: int
    team_name: str | None = None
    player_names: list[str] = []
    mean: float
    median: float
    floor_p5: float
    ceiling_p95: float
    std: float
    games_used: int
    expected_series: float
    unavailable_stats: list[str] = []


class BannerOptimiseRequest(BaseModel):
    team_id: int
    role: str
    available_emblems: list[EmblemIn] = Field(min_length=1)
    account_ids: list[int] | None = None
    slots: int | None = None
    shortlist: int = 40
    simulations: int = 2000
    top_n: int = 5
    history_days: int = 120


class BannerOptionOut(BaseModel):
    emblems: list[EmblemIn]
    mean: float
    ceiling_p95: float
    floor_p5: float


class RosterRequest(BaseModel):
    # Баннеры по ролям; если не заданы — берутся нейтральные наборы из presets.
    banners: dict[str, list[EmblemIn]] | None = None
    simulations: int = 4000
    series: int = 5
    min_games: int = 6
    top_n: int = 5
    history_days: int = 180


class RosterCandidateOut(BaseModel):
    role: str
    team_id: int
    team_name: str | None = None
    player_names: list[str] = []
    mean: float
    floor_p5: float
    ceiling_p95: float
    games_used: int


class RosterPickOut(BaseModel):
    role: str
    team_id: int
    team_name: str | None = None
    mean: float


class RosterOut(BaseModel):
    expected_total: float
    p5: float
    p95: float
    picks: list[RosterPickOut]


class RosterResponse(BaseModel):
    candidates: dict[str, list[RosterCandidateOut]]
    rosters: list[RosterOut]
    banners: dict[str, list[EmblemIn]]
    skipped: list[str] = []


class StatValueOut(BaseModel):
    stat: str
    label: str
    color: str
    units_per_game: float
    base_points: float
    p95_points: float
    p5_points: float
    availability: str
    negligible: bool


class SlotAdviceOut(BaseModel):
    slot: int
    color: str
    stat: str
    label: str
    quality: str
    trait: str | None
    percent: float
    base_points: float
    points: float
    alternatives: list[StatValueOut] = []


class BannerAdviceOut(BaseModel):
    role: str
    team_id: int
    team_name: str | None = None
    player_names: list[str] = []
    slots: list[SlotAdviceOut]
    expected_card_points: float
    period_mean: float | None = None
    period_ceiling: float | None = None


class BannerAdviceRequest(BaseModel):
    team_id: int
    role: str
    # Ограничить перебор тем, что реально доступно из роллов.
    qualities: list[str] | None = None
    traits: list[str | None] | None = None
    simulate: bool = True
    simulations: int = 3000
    top_n: int = 3
    history_days: int = 180
    series: int = 5


class StatReportRequest(BaseModel):
    team_id: int
    role: str
    history_days: int = 180
    include_unavailable: bool = False


class SwapRequest(BaseModel):
    team_id: int
    role: str
    banner: BannerIn
    slot: int
    candidate: EmblemIn
    history_days: int = 180


class SwapOut(BaseModel):
    before: float
    after: float
    delta: float
    delta_pct: float


class StatRankingOut(BaseModel):
    stat: str
    team_id: int
    team_name: str | None
    role: str
    player_names: list[str]
    units_per_game: float
    base_points: float
    p95_points: float
    games: int


class TitleAdviceOut(BaseModel):
    key: str
    label: str
    bonus: float
    condition: str
    hit_rate: float | None
    expected_bonus: float | None
    estimator: str
    note: str


class RolesOut(BaseModel):
    team_id: int
    team_name: str | None = None
    roles: dict[str, list[int]]
    player_names: dict[int, str | None]


class IngestResultOut(BaseModel):
    requested: int
    parsed: int
    unparsed: int


class StatSourceOut(BaseModel):
    stat: str
    label: str
    color: str
    availability: str
    note: str


class FantasyRulesOut(BaseModel):
    version: str
    source: str
    stats: list[dict]
    qualities: dict[str, float]
    traits: list[dict]
    banner_slots: int
    trait_bonus_mode: str
    sources: list[StatSourceOut]
