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
    # Чтобы связать ставку со строкой таблицы вероятностей, не сверяя названия.
    team_id: int | None = None


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
    median_points: float = 0.0
    p75_points: float = 0.0
    # Доля карт, где стат случился хотя бы раз.
    hit_rate: float = 0.0
    # Очки за последние 30 дней к предыдущим 60; None — карт слишком мало.
    trend: float | None = None


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


class PlayerProfileOut(BaseModel):
    """Вклад одного игрока роли: среднее по паре не показывает, кто его делает."""

    account_id: int
    name: str | None = None
    games: int
    values: list[StatValueOut]


class TimelinePointOut(BaseModel):
    """Одна карта: дата, очки с нейтральным баннером, победа."""

    d: str
    p: float
    w: int | None = None


class TimelineOut(BaseModel):
    role: str
    team_id: int
    banner: list[EmblemIn]
    points: list[TimelinePointOut]


class InventoryRequest(BaseModel):
    """Эмблемы, которые уже есть у игрока, и под кого их подбирать."""

    inventory: list[EmblemIn]
    role: str | None = None
    history_days: int = 180
    min_games: int = 5
    top_n: int = 16


class InventoryFitOut(BaseModel):
    role: str
    team_id: int
    team_name: str | None = None
    player_names: list[str] = []
    slots: list[SlotAdviceOut]
    expected_card_points: float
    period_mean: float | None = None
    period_ceiling: float | None = None
    unused: list[EmblemIn] = []
    games: int


class InventoryResponse(BaseModel):
    fits: list[InventoryFitOut]
    # Роли, которые из этого инвентаря не собрать, с указанием нехватки.
    gaps: dict[str, list[str]] = {}


class TitleAdviceOut(BaseModel):
    key: str
    label: str
    bonus: float
    condition: str
    hit_rate: float | None
    expected_bonus: float | None
    estimator: str
    note: str
    # Пояснение ключом словаря интерфейса и числа к нему: страница переведена на
    # четыре языка, и собрать фразу из готовой русской строки нельзя.
    note_key: str = ""
    note_params: dict[str, float | int | str] = {}


# --- профили команд и игроков -------------------------------------------------


class MatchRowOut(BaseModel):
    """Строка в списке матчей. Пустые поля — матч без разобранного реплея."""

    match_id: int
    start_time: datetime
    duration: int
    league_name: str | None = None
    opponent_id: int | None = None
    opponent_name: str | None = None
    won: bool | None = None
    is_parsed: bool
    hero_id: int | None = None
    hero_name: str | None = None
    kills: float | None = None
    deaths: float | None = None
    assists: float | None = None
    gpm: float | None = None
    xpm: float | None = None
    net_worth: float | None = None


class HeroRowOut(BaseModel):
    hero_id: int
    name: str
    games: int
    wins: int


class HeroPickOut(BaseModel):
    """Герой в пуле роли или команды — с разбивкой, кто из игроков его берёт."""

    hero_id: int
    name: str
    games: int
    wins: int
    players: list[dict[str, int]] = []


class SplitOut(BaseModel):
    """Часть выборки: сторона карты, корзина по длительности, класс соперника."""

    key: str
    games: int
    wins: int


class TrendsOut(BaseModel):
    form: SplitOut
    baseline: SplitOut
    streak: int
    sides: list[SplitOut] = []
    durations: list[SplitOut] = []


class HeroPoolOut(BaseModel):
    distinct: int
    top3_share: float


class FantasyFormOut(BaseModel):
    """Очки за карту по всему пулу статов роли — сравнимо внутри роли."""

    maps: int
    mean: float
    median: float
    best: float
    p90: float
    spread: float


class PlayerPageOut(BaseModel):
    """Страница игрока: обычная статистика отдельно, Fantasy-единицы отдельно."""

    account_id: int
    name: str | None = None
    team_id: int | None = None
    team_name: str | None = None
    role: str | None = None
    position: int | None = None
    games: int
    parsed_games: int
    wins: int
    win_rate: float
    first_game: datetime | None = None
    last_game: datetime | None = None
    averages: dict[str, float] = {}
    fantasy_units: dict[str, float] = {}
    heroes: list[HeroRowOut] = []
    matches: list[MatchRowOut] = []
    trends: TrendsOut | None = None
    lanes: dict[str, int] = {}
    hero_pool: HeroPoolOut | None = None
    fantasy_form: FantasyFormOut | None = None


class TeamPageOut(BaseModel):
    team_id: int
    name: str
    compendium_name: str | None = None
    tag: str | None = None
    rating: float | None = None
    rd: float | None = None
    volatility: float | None = None
    rating_history: list[dict[str, float | str]] = []
    games: int
    parsed_games: int
    wins: int
    win_rate: float
    first_game: datetime | None = None
    last_game: datetime | None = None
    roster: list[PlayerPageOut] = []
    matches: list[MatchRowOut] = []
    team_averages: dict[str, float] = {}
    opponents: list[dict[str, str | int]] = []
    trends: TrendsOut | None = None
    opponent_rating: float | None = None
    vs_stronger: SplitOut | None = None
    first_blood_rate: float | None = None


class TeamListItemOut(BaseModel):
    team_id: int
    name: str
    opendota_name: str | None = None
    tag: str | None = None
    is_ti: bool
    games: int
    rating: float | None = None
    rd: float | None = None


class PlayerListItemOut(BaseModel):
    account_id: int
    name: str | None = None
    team_id: int | None = None
    team_name: str | None = None
    role: str | None = None
    is_ti: bool
    games: int


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
