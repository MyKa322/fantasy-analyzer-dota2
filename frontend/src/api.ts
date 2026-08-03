// Клиент бэкенда. Типы повторяют схемы FastAPI из app/api/schemas.py.
//
// У клиента два режима. С локальным бэкендом всё идёт по HTTP; на GitHub Pages
// сервера нет, и те же методы читают предрассчитанный снапшот, а баннеры
// считают в браузере. Компоненты разницы не видят.

import {
  fitInventory,
  inventoryGaps,
  optimiseBanner,
  scoreBanner,
  type Availability,
  type GroupColor,
  type RulesSnapshot,
  type StatValue,
} from "./engine/scoring";
import { STATIC_MODE, findRole, loadSnapshot } from "./snapshot";
import {
  loadProfiles,
  type ProfileHero,
  type ProfileMatch,
  type ProfilePlayer,
  type ProfileTeam,
} from "./profiles";

export type { ProfileHero, ProfileMatch, ProfilePlayer, ProfileTeam };

export type { Availability, GroupColor, StatValue };

export interface Team {
  team_id: number;
  name: string;
  tag: string | null;
  compendium_name: string | null;
  rating: number | null;
  rd: number | null;
  volatility: number | null;
  matches_played: number;
  days_idle: number | null;
  is_listable: boolean;
}

export interface RatingPoint {
  as_of: string;
  rating: number;
  rd: number;
  matches_played: number;
}

export interface RatingHistory {
  team_id: number;
  name: string | null;
  points: RatingPoint[];
}

export interface BucketProbability {
  team_id: number;
  name: string | null;
  probabilities: Record<string, number>;
  advance: number;
  expected_series: number;
}

export interface PredictionPick {
  key: string;
  pick: string;
  label: string | null;
}

export interface GroupPrediction {
  simulations: number;
  teams: BucketProbability[];
  plan: PredictionPick[];
  expected_points: number;
  expected_correct: number;
  points_percentiles: Record<string, number>;
}

export interface StatRule {
  key: string;
  label: string;
  color: GroupColor;
  kind: string;
  per_unit: number;
  base: number;
  value_if_true: number;
  max_points: number;
}

export interface TraitRule {
  key: string;
  label: string;
  description: string;
  condition: string;
  effects: { scope: string; amount: number }[];
}

export interface StatSource {
  stat: string;
  label: string;
  color: string;
  availability: Availability;
  note: string;
}

export interface FantasyRules {
  version: string;
  source: string;
  stats: StatRule[];
  qualities: Record<string, number>;
  traits: TraitRule[];
  banner_slots: number;
  trait_bonus_mode: string;
  sources: StatSource[];
}

export interface PredictionsConfig {
  version: string;
  event: string;
  teams: string[];
  team_ids: Record<string, number | null>;
  buckets: { key: string; label: string; description: string; slots: number }[];
  group_points: Record<string, number>;
  playoff_points: Record<string, number>;
  bracket_slots: string[];
}

export interface Emblem {
  stat: string;
  quality: string;
  trait: string | null;
}

export interface Projection {
  role: string;
  team_id: number;
  team_name: string | null;
  player_names: string[];
  mean: number;
  median: number;
  floor_p5: number;
  ceiling_p95: number;
  std: number;
  games_used: number;
  expected_series: number;
  unavailable_stats: string[];
}

export interface BannerOption {
  emblems: Emblem[];
  mean: number;
  ceiling_p95: number;
  floor_p5: number;
}

export interface RosterCandidate {
  role: string;
  team_id: number;
  team_name: string | null;
  player_names: string[];
  mean: number;
  floor_p5: number;
  ceiling_p95: number;
  games_used: number;
}

export interface RosterPick {
  role: string;
  team_id: number;
  team_name: string | null;
  mean: number;
}

export interface Roster {
  expected_total: number;
  p5: number;
  p95: number;
  picks: RosterPick[];
}

export interface RosterResponse {
  candidates: Record<string, RosterCandidate[]>;
  rosters: Roster[];
  banners: Record<string, Emblem[]>;
  skipped: string[];
}

export interface SlotAdvice {
  slot: number;
  color: GroupColor;
  stat: string;
  label: string;
  quality: string;
  trait: string | null;
  percent: number;
  base_points: number;
  points: number;
  alternatives: StatValue[];
}

export interface BannerAdvice {
  role: string;
  team_id: number;
  team_name: string | null;
  player_names: string[];
  slots: SlotAdvice[];
  expected_card_points: number;
  period_mean: number | null;
  period_ceiling: number | null;
}

export interface PlayerStatValue {
  stat: string;
  label: string;
  color: GroupColor;
  units_per_game: number;
  base_points: number;
  p95_points: number;
  hit_rate: number;
  trend: number | null;
}

/** Разбивка роли по игрокам: кто именно набирает очки внутри пары. */
export interface PlayerProfile {
  account_id: number;
  name: string | null;
  games: number;
  values: PlayerStatValue[];
}

export interface TimelinePoint {
  d: string;
  p: number;
  w: number | null;
}

export interface RoleTimeline {
  role: string;
  team_id: number;
  banner: Emblem[];
  points: TimelinePoint[];
}

export interface InventoryFit {
  role: string;
  team_id: number;
  team_name: string | null;
  player_names: string[];
  slots: SlotAdvice[];
  expected_card_points: number;
  period_mean: number | null;
  period_ceiling: number | null;
  unused: Emblem[];
  games: number;
}

export interface InventoryResponse {
  fits: InventoryFit[];
  /** Роли, которые из этого инвентаря не собрать: цвет -> чего не хватает. */
  gaps: Record<string, string[]>;
}

export interface StatRanking {
  stat: string;
  team_id: number;
  team_name: string | null;
  role: string;
  player_names: string[];
  units_per_game: number;
  base_points: number;
  p95_points: number;
  games: number;
}

export interface TitleAdvice {
  key: string;
  label: string;
  bonus: number;
  condition: string;
  hit_rate: number | null;
  expected_bonus: number | null;
  estimator: string;
  note: string;
}

export interface TeamListItem {
  team_id: number;
  name: string;
  opendota_name?: string | null;
  tag: string | null;
  is_ti: boolean;
  games: number;
  rating: number | null;
  rd: number | null;
}

export interface PlayerListItem {
  account_id: number;
  name: string | null;
  team_id: number | null;
  team_name: string | null;
  role: string | null;
  is_ti: boolean;
  games: number;
}

export interface TeamRoles {
  team_id: number;
  team_name: string | null;
  roles: Record<string, number[]>;
  player_names: Record<string, string | null>;
}

// --- профили ------------------------------------------------------------------
// Живой бэкенд отдаёт развёрнутые имена полей, статический снапшот — короткие
// (в нём эти строки повторяются сотнями тысяч раз). Компоненты работают с одной
// формой, поэтому ответы API приводятся к формату снапшота прямо здесь.

interface MatchRowResponse {
  match_id: number;
  start_time: string;
  duration: number;
  league_name: string | null;
  opponent_id: number | null;
  opponent_name: string | null;
  won: boolean | null;
  is_parsed: boolean;
  hero_name: string | null;
  kills: number | null;
  deaths: number | null;
  assists: number | null;
  gpm: number | null;
  xpm: number | null;
  net_worth: number | null;
}

interface PlayerPageResponse {
  account_id: number;
  name: string | null;
  team_id: number | null;
  team_name: string | null;
  role: string | null;
  games: number;
  parsed_games: number;
  wins: number;
  first_game: string | null;
  last_game: string | null;
  averages: Record<string, number>;
  fantasy_units: Record<string, number>;
  heroes: ProfileHero[];
  matches: MatchRowResponse[];
}

interface TeamPageResponse {
  team_id: number;
  name: string;
  compendium_name: string | null;
  tag: string | null;
  rating: number | null;
  rd: number | null;
  games: number;
  parsed_games: number;
  wins: number;
  first_game: string | null;
  last_game: string | null;
  team_averages: Record<string, number>;
  opponents: { name: string; games: number; wins: number }[];
  rating_history: { as_of: string; rating: number; rd: number }[];
  roster: PlayerPageResponse[];
  matches: MatchRowResponse[];
}

function liveMatch(row: MatchRowResponse): ProfileMatch {
  return {
    id: row.match_id,
    d: row.start_time.slice(0, 10),
    dur: row.duration,
    opp: row.opponent_name,
    opp_id: row.opponent_id,
    won: row.won == null ? null : Number(row.won),
    parsed: Number(row.is_parsed),
    league: row.league_name ?? undefined,
    hero: row.hero_name ?? undefined,
    k: row.kills ?? undefined,
    d_: row.deaths ?? undefined,
    a: row.assists ?? undefined,
    gpm: row.gpm ?? undefined,
    xpm: row.xpm ?? undefined,
    nw: row.net_worth ?? undefined,
  };
}

function livePlayer(page: PlayerPageResponse): ProfilePlayer {
  return { ...page, matches: page.matches.map(liveMatch) };
}

function liveTeam(page: TeamPageResponse): ProfileTeam {
  return {
    team_id: page.team_id,
    name: page.compendium_name ?? page.name,
    tag: page.tag,
    is_ti: page.compendium_name != null,
    rating: page.rating,
    rd: page.rd,
    games: page.games,
    parsed_games: page.parsed_games,
    wins: page.wins,
    first_game: page.first_game?.slice(0, 10) ?? null,
    last_game: page.last_game?.slice(0, 10) ?? null,
    team_averages: page.team_averages,
    opponents: page.opponents,
    rating_history: page.rating_history.map((point) => ({
      d: point.as_of.slice(0, 10),
      r: point.rating,
      rd: point.rd,
    })),
    roster: page.roster.map((p) => p.account_id),
    matches: page.matches.map(liveMatch),
  };
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

const OFFLINE_MESSAGE =
  "Эта операция требует локального бэкенда — на опубликованной странице данные " +
  "берутся из снапшота, который обновляется по расписанию.";

function offline(): never {
  throw new ApiError(OFFLINE_MESSAGE, 501);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // тело не JSON — оставляем статус
    }
    throw new ApiError(detail, response.status);
  }
  return response.json() as Promise<T>;
}

const live = {
  fantasyRules: () => request<FantasyRules>("/config/fantasy"),
  predictionsConfig: () => request<PredictionsConfig>("/config/predictions"),

  teams: (compendiumOnly = false) =>
    request<Team[]>(`/teams?compendium_only=${compendiumOnly}`),
  ratingHistory: (teamId: number) =>
    request<RatingHistory>(`/teams/${teamId}/rating-history`),
  recomputeRatings: () =>
    request<{ teams: number; snapshots: number; listable: number }>(
      "/ratings/recompute",
      { method: "POST" },
    ),

  groupPrediction: (simulations: number, teamIds?: number[]) => {
    const params = new URLSearchParams({ simulations: String(simulations) });
    teamIds?.forEach((id) => params.append("team_ids", String(id)));
    return request<GroupPrediction>(`/predictions/group?${params}`);
  },

  teamRoles: (teamId: number, historyDays = 120) =>
    request<TeamRoles>(`/fantasy/roles/${teamId}?history_days=${historyDays}`),

  project: (payload: {
    team_id: number;
    role: string;
    banner: { emblems: Emblem[] };
    simulations?: number;
    history_days?: number;
    series_distribution?: Record<number, number>;
  }) =>
    request<Projection>("/fantasy/project", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  optimiseBanner: (payload: {
    team_id: number;
    role: string;
    available_emblems: Emblem[];
    slots?: number;
    simulations?: number;
    history_days?: number;
    top_n?: number;
  }) =>
    request<BannerOption[]>("/fantasy/optimise-banner", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  roster: (payload?: {
    simulations?: number;
    series?: number;
    min_games?: number;
    top_n?: number;
    history_days?: number;
  }) =>
    request<RosterResponse>("/fantasy/roster", {
      method: "POST",
      body: JSON.stringify(payload ?? {}),
    }),

  statReport: (payload: {
    team_id: number;
    role: string;
    history_days?: number;
    include_unavailable?: boolean;
  }) =>
    request<StatValue[]>("/fantasy/stat-report", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  bestBanner: (payload: {
    team_id: number;
    role: string;
    qualities?: string[] | null;
    traits?: (string | null)[] | null;
    simulate?: boolean;
    simulations?: number;
    top_n?: number;
    history_days?: number;
    series?: number;
  }) =>
    request<BannerAdvice[]>("/fantasy/best-banner", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  playerReport: (payload: { team_id: number; role: string; history_days?: number }) =>
    request<PlayerProfile[]>("/fantasy/players", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  timeline: (payload: { team_id: number; role: string; history_days?: number }) =>
    request<RoleTimeline>("/fantasy/timeline", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  inventory: (payload: {
    inventory: Emblem[];
    role?: string | null;
    history_days?: number;
    min_games?: number;
    top_n?: number;
  }) =>
    request<InventoryResponse>("/fantasy/inventory", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  statRanking: (stat: string, role?: string, minGames = 5) => {
    const params = new URLSearchParams({ min_games: String(minGames) });
    if (role) params.set("role", role);
    return request<StatRanking[]>(`/fantasy/stat-ranking/${stat}?${params}`);
  },

  titles: (payload: { team_id: number; role: string; history_days?: number }) =>
    request<TitleAdvice[]>("/fantasy/titles", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  profileTeams: () => request<TeamListItem[]>("/profiles/teams"),
  profilePlayers: (tiOnly = false) =>
    request<PlayerListItem[]>(`/profiles/players?ti_only=${tiOnly}`),

  teamPage: async (teamId: number, days = 180) => {
    const page = await request<TeamPageResponse>(
      `/profiles/teams/${teamId}?days=${days}`,
    );
    return {
      team: liveTeam(page),
      roster: page.roster.map(livePlayer),
    };
  },

  playerPage: async (accountId: number, days = 180) => {
    const page = await request<PlayerPageResponse>(
      `/profiles/players/${accountId}?days=${days}`,
    );
    return livePlayer(page);
  },

  ingestProFeed: (daysBack = 30, maxPages = 10) =>
    request<{ requested: number; parsed: number; unparsed: number }>(
      `/ingest/pro-feed?days_back=${daysBack}&max_pages=${maxPages}`,
      { method: "POST" },
    ),
  ingestTeam: (teamId: number, daysBack = 120) =>
    request<{ requested: number; parsed: number; unparsed: number }>(
      `/ingest/team/${teamId}?days_back=${daysBack}`,
      { method: "POST" },
    ),
  resolveTeams: () =>
    request<Record<string, number | null>>("/ingest/resolve-teams", {
      method: "POST",
    }),
};

// --- статический режим --------------------------------------------------------
// На GitHub Pages бэкенда нет. Всё, что требует базы и симуляций, читается из
// снапшота; математика эмблем считается прямо в браузере тем же аддитивным
// движком, что и на сервере.

const staticApi: typeof live = {
  fantasyRules: async () => {
    const { rules } = await loadSnapshot();
    return {
      version: rules.version,
      source: rules.source,
      stats: rules.stats as unknown as StatRule[],
      qualities: rules.qualities,
      traits: rules.traits as unknown as TraitRule[],
      banner_slots: rules.banner_slots,
      trait_bonus_mode: rules.trait_bonus_mode,
      sources: rules.stats.map((s) => ({
        stat: s.key,
        label: s.label,
        color: s.color,
        availability: s.availability,
        note: s.note,
      })),
    };
  },

  predictionsConfig: async () => {
    const snapshot = await loadSnapshot();
    return {
      version: snapshot.rules.version,
      event: "The International 2026 (TI15)",
      teams: snapshot.teams.map((t) => t.name),
      team_ids: Object.fromEntries(snapshot.teams.map((t) => [t.name, t.team_id])),
      buckets: snapshot.group?.buckets ?? [],
      group_points: {},
      playoff_points: {},
      bracket_slots: [],
    };
  },

  teams: async () => {
    const snapshot = await loadSnapshot();
    return snapshot.teams.map((t) => ({
      team_id: t.team_id,
      name: t.name,
      tag: null,
      compendium_name: t.name,
      rating: t.rating,
      rd: t.rd,
      volatility: null,
      matches_played: 0,
      days_idle: null,
      is_listable: t.listable,
    }));
  },

  ratingHistory: async () => offline(),
  recomputeRatings: async () => offline(),

  groupPrediction: async () => {
    const snapshot = await loadSnapshot();
    if (!snapshot.group) return offline();
    return {
      simulations: snapshot.group.simulations,
      teams: snapshot.group.teams.map((t) => ({
        team_id: t.team_id,
        name: t.name,
        probabilities: t.probabilities,
        advance: t.advance,
        expected_series: t.expected_series,
      })),
      plan: snapshot.group.plan.map((p) => ({
        key: p.name,
        pick: p.bucket,
        label:
          snapshot.group?.buckets.find((b) => b.key === p.bucket)?.label ?? p.bucket,
      })),
      expected_points: snapshot.group.expected_points,
      expected_correct: snapshot.group.expected_correct,
      points_percentiles: snapshot.group.points_percentiles,
    };
  },

  teamRoles: async (teamId: number) => {
    const snapshot = await loadSnapshot();
    const roles = snapshot.roles.filter((r) => r.team_id === teamId);
    return {
      team_id: teamId,
      team_name: roles[0]?.team_name ?? null,
      roles: Object.fromEntries(roles.map((r) => [r.role, []])),
      player_names: {},
    };
  },

  project: async () => offline(),
  optimiseBanner: async () => offline(),

  roster: async (payload) => {
    const snapshot = await loadSnapshot();
    const candidates: Record<string, RosterCandidate[]> = {};
    const byRole: Record<string, { team_id: number; team_name: string; mean: number }[]> = {};

    // Число серий за период — не косметика: в зачёт идёт лучшая серия, и каждая
    // дополнительная попытка поднимает ожидание. Коэффициенты на каждый вариант
    // посчитаны при экспорте; если их нет (старый снапшот), берём базовый.
    const series = String(payload?.series ?? 5);

    for (const role of snapshot.roles) {
      const banner = neutralBannerFor(role.role, snapshot.rules);
      const values = new Map(role.stats.map((s) => [s.stat, s]));
      const card = scoreBanner(banner, values, snapshot.rules).total;
      const periodRatio = role.period_ratios?.[series] ?? role.period_ratio;
      const ceilingRatio = role.ceiling_ratios?.[series] ?? role.ceiling_ratio;
      const mean = card * periodRatio;
      candidates[role.role] ??= [];
      candidates[role.role].push({
        role: role.role,
        team_id: role.team_id,
        team_name: role.team_name,
        player_names: role.players,
        mean,
        floor_p5: mean * 0.85,
        ceiling_p95: card * ceilingRatio,
        games_used: role.games,
      });
      byRole[role.role] ??= [];
      byRole[role.role].push({ team_id: role.team_id, team_name: role.team_name, mean });
    }

    for (const role of Object.keys(candidates)) {
      candidates[role].sort((a, b) => b.mean - a.mean);
    }

    // Лучшие сочетания из трёх разных команд.
    const rosters: Roster[] = [];
    const roles = Object.keys(byRole);
    if (roles.length === 3) {
      for (const core of byRole[roles[0]] ?? []) {
        for (const mid of byRole[roles[1]] ?? []) {
          if (mid.team_id === core.team_id) continue;
          for (const support of byRole[roles[2]] ?? []) {
            if (support.team_id === core.team_id || support.team_id === mid.team_id) continue;
            const picks = [
              { role: roles[0], ...core },
              { role: roles[1], ...mid },
              { role: roles[2], ...support },
            ];
            const total = picks.reduce((s, p) => s + p.mean, 0);
            rosters.push({
              expected_total: total,
              p5: total * 0.85,
              p95: total * 1.15,
              picks,
            });
          }
        }
      }
      rosters.sort((a, b) => b.expected_total - a.expected_total);
    }

    return {
      candidates,
      rosters: rosters.slice(0, payload?.top_n ?? 5),
      banners: {},
      skipped: [],
    };
  },

  statReport: async (payload) => {
    const snapshot = await loadSnapshot();
    const role = findRole(snapshot, payload.team_id, payload.role);
    if (!role) return offline();
    return payload.include_unavailable
      ? role.stats
      : role.stats.filter((s) => s.availability !== "unavailable");
  },

  bestBanner: async (payload) => {
    const snapshot = await loadSnapshot();
    const role = findRole(snapshot, payload.team_id, payload.role);
    if (!role) return offline();

    const options = optimiseBanner(payload.role, role.stats, snapshot.rules, {
      qualities: payload.qualities ?? undefined,
      traits: payload.traits ?? undefined,
      topN: payload.top_n ?? 3,
    });

    return options.map((option) => ({
      role: payload.role,
      team_id: payload.team_id,
      team_name: role.team_name,
      player_names: role.players,
      slots: option.slots.map((s) => ({ ...s, alternatives: [] })),
      expected_card_points: option.total,
      period_mean: option.total * role.period_ratio,
      period_ceiling: option.total * role.ceiling_ratio,
    }));
  },

  playerReport: async (payload) => {
    const snapshot = await loadSnapshot();
    const role = findRole(snapshot, payload.team_id, payload.role);
    if (!role) return offline();
    const meta = new Map(role.stats.map((s) => [s.stat, s]));
    return role.player_stats.map((player) => ({
      account_id: player.account_id,
      name: player.name,
      games: player.games,
      values: player.stats.map((v) => ({
        ...v,
        label: meta.get(v.stat)?.label ?? v.stat,
        color: meta.get(v.stat)?.color ?? ("red" as GroupColor),
      })),
    }));
  },

  timeline: async (payload) => {
    const snapshot = await loadSnapshot();
    const role = findRole(snapshot, payload.team_id, payload.role);
    if (!role) return offline();
    return {
      role: role.role,
      team_id: role.team_id,
      banner: neutralBannerFor(role.role, snapshot.rules),
      points: role.timeline,
    };
  },

  inventory: async (payload) => {
    const snapshot = await loadSnapshot();

    // Нехватка цветов зависит только от инвентаря и роли, поэтому считается до
    // перебора команд: саппорта без двух синих не собрать ни с кем.
    const gaps: Record<string, string[]> = {};
    for (const role of Object.keys(snapshot.rules.role_slots)) {
      if (payload.role && role !== payload.role) continue;
      const missing = inventoryGaps(payload.inventory, role, snapshot.rules);
      if (missing.length) {
        gaps[role] = missing.map((m) => `${m.color}: нужно ${m.need}, есть ${m.have}`);
      }
    }

    const fits: InventoryFit[] = [];
    for (const role of snapshot.roles) {
      if (payload.role && role.role !== payload.role) continue;
      if (gaps[role.role]) continue;
      if (role.games < (payload.min_games ?? 5)) continue;
      const fit = fitInventory(role.role, payload.inventory, role.stats, snapshot.rules);
      if (!fit) continue;
      fits.push({
        role: role.role,
        team_id: role.team_id,
        team_name: role.team_name,
        player_names: role.players,
        slots: fit.slots.map((s) => ({ ...s, alternatives: [] })),
        expected_card_points: fit.total,
        period_mean: fit.total * role.period_ratio,
        period_ceiling: fit.total * role.ceiling_ratio,
        unused: fit.unused,
        games: role.games,
      });
    }
    fits.sort((a, b) => b.expected_card_points - a.expected_card_points);
    return { fits: fits.slice(0, payload.top_n ?? 48), gaps };
  },

  statRanking: async (stat: string, role?: string) => {
    const snapshot = await loadSnapshot();
    return snapshot.roles
      .filter((r) => !role || r.role === role)
      .map((r) => ({ role: r, value: r.stats.find((s) => s.stat === stat) }))
      .filter((entry) => entry.value)
      .map(({ role: r, value }) => ({
        stat,
        team_id: r.team_id,
        team_name: r.team_name,
        role: r.role,
        player_names: r.players,
        units_per_game: value!.units_per_game,
        base_points: value!.base_points,
        p95_points: value!.p95_points,
        games: r.games,
      }))
      .sort((a, b) => b.base_points - a.base_points);
  },

  titles: async (payload) => {
    const snapshot = await loadSnapshot();
    const role = findRole(snapshot, payload.team_id, payload.role);
    return role ? role.titles : offline();
  },

  profileTeams: async () => {
    const profiles = await loadProfiles();
    return profiles.teams.map((team) => ({
      team_id: team.team_id,
      name: team.name,
      opendota_name: team.name,
      tag: team.tag,
      is_ti: team.is_ti,
      games: team.games,
      rating: team.rating,
      rd: team.rd,
    }));
  },

  profilePlayers: async (tiOnly = false) => {
    const profiles = await loadProfiles();
    const ti = new Set(profiles.teams.filter((t) => t.is_ti).map((t) => t.team_id));
    return profiles.players
      .map((player) => ({
        account_id: player.account_id,
        name: player.name,
        team_id: player.team_id,
        team_name: player.team_name,
        role: player.role,
        is_ti: player.team_id != null && ti.has(player.team_id),
        games: player.games,
      }))
      .filter((player) => !tiOnly || player.is_ti);
  },

  teamPage: async (teamId: number) => {
    const profiles = await loadProfiles();
    const team = profiles.teams.find((t) => t.team_id === teamId);
    if (!team) return offline();
    const byId = new Map(profiles.players.map((p) => [p.account_id, p]));
    return {
      team,
      roster: team.roster
        .map((id) => byId.get(id))
        .filter((p): p is ProfilePlayer => p != null),
    };
  },

  playerPage: async (accountId: number) => {
    const profiles = await loadProfiles();
    const player = profiles.players.find((p) => p.account_id === accountId);
    return player ?? offline();
  },

  ingestProFeed: async () => offline(),
  ingestTeam: async () => offline(),
  resolveTeams: async () => offline(),
};

// Те же нейтральные наборы, что и в backend/app/fantasy/presets.py: порядок
// статов соответствует цветам слотов роли. Расхождение здесь означало бы, что
// опубликованная страница и локальный расчёт дают разные числа.
const NEUTRAL_ROLE_STATS: Record<string, string[]> = {
  core: ["gpm", "kills", "teamfight_participation"],
  mid: ["gpm", "runes_grabbed", "teamfight_participation"],
  support: ["wards_placed", "camps_stacked", "stuns"],
};

function neutralBannerFor(role: string, rules: RulesSnapshot): Emblem[] {
  const stats = NEUTRAL_ROLE_STATS[role] ?? NEUTRAL_ROLE_STATS.core;
  const colors = rules.role_slots[role] ?? [];
  return colors.map((_, index) => ({
    stat: stats[index],
    quality: "tier_3",
    trait: null,
  }));
}

export const api = STATIC_MODE ? staticApi : live;
