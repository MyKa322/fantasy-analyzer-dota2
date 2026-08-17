// Статический источник данных для GitHub Pages.
//
// Страница на Pages работает без бэкенда: вся аналитика, которой нужна база и
// симуляции, посчитана заранее скриптом backend/tools/export_snapshot.py, а
// математика эмблем считается в браузере (src/engine/scoring.ts).
//
// Режим включается переменной сборки VITE_STATIC_DATA=1.

import type { RulesSnapshot, StatValue } from "./engine/scoring";
import { tr } from "./i18n";

export const STATIC_MODE = import.meta.env.VITE_STATIC_DATA === "1";

/** Вклад одного игрока роли — среднее по паре его не показывает. */
export interface PlayerStats {
  account_id: number;
  name: string | null;
  games: number;
  stats: {
    stat: string;
    units_per_game: number;
    base_points: number;
    p95_points: number;
    hit_rate: number;
    trend: number | null;
  }[];
}

/** Очки за каждую карту с нейтральным баннером: форма роли во времени. */
export interface TimelinePoint {
  d: string;
  p: number;
  w: number | null;
}

/** Герой в пуле роли, команды или игрока. */
export interface HeroPick {
  id: number;
  name: string;
  games: number;
  wins: number;
  players?: { account_id: number; games: number }[];
}

/** Замена в составе: играть будет один, а карты в выборке — другого. */
export interface Substitution {
  name: string;
  replaced: string;
  games: number;
}

export interface RoleSnapshot {
  team_id: number;
  team_name: string;
  role: string;
  players: string[];
  /** Пусто у всех ролей, где состав не менялся. */
  substitutions?: Substitution[];
  games: number;
  last_game: string;
  stats: StatValue[];
  player_stats: PlayerStats[];
  heroes: HeroPick[];
  timeline: TimelinePoint[];
  /** Во сколько раз счёт за период больше счёта за карту (базовое число серий). */
  period_ratio: number;
  ceiling_ratio: number;
  /** То же по каждому числу серий: "4" | "5" | "6" | "7". */
  period_ratios?: Record<string, number>;
  ceiling_ratios?: Record<string, number>;
  titles: {
    key: string;
    label: string;
    bonus: number;
    condition: string;
    hit_rate: number | null;
    expected_bonus: number | null;
    estimator: string;
    note: string;
    note_key?: string | null;
    note_params?: Record<string, string | number>;
  }[];
}

/** Одна серия сетки группового этапа. */
export interface StageSeries {
  round: number;
  /** Запись левой команды на входе в серию: «0-0», «1-0», … */
  record: string;
  left: { team_id: number; name: string; score: number };
  right: { team_id: number; name: string; score: number };
  winner_id: number | null;
  played_at: string;
  match_ids: number[];
}

/** Команда в аналитике этапа. Величины, которых нет, приходят null — не нулём. */
export interface StageTeamAnalytics {
  team_id: number;
  name: string;
  wins: number;
  losses: number;
  map_diff: number;
  rating: number | null;
  /** Сумма вероятностей выиграть каждую сыгранную серию. */
  expected_wins: number | null;
  /** Победы сверх ожидаемых: больше нуля — играет выше своего рейтинга. */
  performance: number | null;
  opponent_rating: number | null;
  /** +n подряд выигранных серий, -n подряд проигранных. */
  streak: number;
  status: "alive" | "advanced" | "eliminated";
  avg_duration_min: number | null;
  avg_kill_diff: number | null;
  upsets_won: number;
  upsets_lost: number;
}

export interface StageMatchup {
  left_id: number;
  right_id: number;
  left: string;
  right: string;
  left_win_probability: number | null;
  rating_gap: number | null;
  toss_up: boolean;
}

export interface StageAnalytics {
  started: boolean;
  upsets: number;
  teams: StageTeamAnalytics[];
  rounds: { round: number; series: number; decided: number; upsets: number; maps: number }[];
  matchups: StageMatchup[];
}

export interface Stage {
  /** Первый день турнира: до него матчей группового этапа не бывает. */
  starts: string | null;
  first_round: { left: string; right: string; left_id: number; right_id: number }[];
  wins_to_advance: number;
  losses_to_eliminate: number;
  series: StageSeries[];
  standings: { team_id: number; name: string; wins: number; losses: number }[];
  /** Аналитика этапа. Появилась позже сетки — у старых снапшотов её нет. */
  analytics?: StageAnalytics;
}

/** Место в сетке плей-офф: кто здесь играет и чем это кончилось. */
export interface PlayoffMatch {
  key: string;
  /** Раунд: ubqf, ubsf, ubf, lbr1, lbr2, lbsf, lbf, gf. */
  round: string;
  /** Сторона сетки: upper, lower, grand. */
  side: string;
  order: number;
  best_of: number;
  left: { team_id: number; name: string; score: number } | null;
  right: { team_id: number; name: string; score: number } | null;
  winner_id: number | null;
  played_at: string | null;
  match_ids: number[];
  /** Кто ещё может здесь оказаться, пока участники не определились. */
  candidates: number[];
  /** Вероятность дойти до этого места: id команды -> доля. */
  reach: Record<string, number>;
  /** Вероятность выиграть эту серию. */
  win: Record<string, number>;
}

/** Путь команды по сетке: факт слева, прогноз справа. */
export interface PlayoffTeam {
  team_id: number;
  name: string;
  series_won: number;
  series_lost: number;
  maps_won: number;
  maps_lost: number;
  /** upper — без поражений, lower — одно, out — вылетела, champion — чемпион. */
  bracket: string;
  /** Итоговое место, когда путь окончен: «1», «2», «3», «4», «5-6», «7-8». */
  place: string | null;
  next_slot: string | null;
  champion?: number;
  final?: number;
  top4?: number;
  places?: Record<string, number>;
  /** Ожидаемое число серий за плей-офф — от двух до шести. */
  expected_series?: number;
  /** Распределение числа серий: «сколько попыток выбить лучшую серию». */
  series?: Record<string, number>;
}

export interface Playoffs {
  starts: string | null;
  best_of: number;
  grand_final_best_of: number;
  started: boolean;
  matches: PlayoffMatch[];
  teams: PlayoffTeam[];
  simulations?: number;
  /** Рекомендованные 14 предсказаний: ключ места -> команда. */
  plan?: { key: string; team_id: number; name: string }[];
  expected_points?: number;
  expected_correct?: number;
  points_percentiles?: Record<string, number>;
}

/** Период Fantasy: свой состав, своё число серий, свой момент закрепления. */
export interface FantasyStage {
  key: string;
  label: string;
  starts: string | null;
  locks: string | null;
}

export interface Snapshot {
  generated_at: string;
  rules: RulesSnapshot & { version: string; source: string; trait_bonus_mode: string };
  /** id героя -> название. Нужен странице матча: в матче лежит только id. */
  heroes?: Record<string, string>;
  /** id предмета -> внутреннее имя: им названы иконки и лог покупок. */
  items?: Record<string, string>;
  teams: {
    team_id: number;
    name: string;
    opendota_name: string;
    rating: number | null;
    rd: number | null;
    listable: boolean;
  }[];
  group: {
    simulations: number;
    buckets: { key: string; label: string; description: string; slots: number }[];
    teams: {
      team_id: number;
      name: string;
      probabilities: Record<string, number>;
      advance: number;
      expected_series: number;
    }[];
    plan: { team_id: number; name: string; bucket: string }[];
    expected_points: number;
    expected_correct: number;
    points_percentiles: Record<string, number>;
  } | null;
  /** Сетка группового этапа. Появилась позже снапшота — может отсутствовать. */
  stage?: Stage;
  /** Сетка плей-офф. Пусто, пока состав восьмёрки не объявлен. */
  playoffs?: Playoffs | null;
  /** Периоды Fantasy: группа и основной этап со своими датами закрепления. */
  stages?: FantasyStage[];
  roles: RoleSnapshot[];
}

let cached: Snapshot | null = null;

/** Метка сборки — подставляется Vite, см. define в vite.config.ts. */
declare const __BUILD_ID__: string;

export async function loadSnapshot(): Promise<Snapshot> {
  if (cached) return cached;
  // Версия в адресе: имя файла между деплоями не меняется, поэтому без неё
  // браузер отдаёт вчерашний снапшот из кэша.
  const response = await fetch(
    `${import.meta.env.BASE_URL}data/snapshot.json?v=${__BUILD_ID__}`,
  );
  if (!response.ok) {
    throw new Error(tr().t("error.snapshot", { status: response.status }));
  }
  cached = (await response.json()) as Snapshot;
  return cached;
}

export function findRole(
  snapshot: Snapshot,
  teamId: number,
  role: string,
): RoleSnapshot | undefined {
  return snapshot.roles.find((r) => r.team_id === teamId && r.role === role);
}
