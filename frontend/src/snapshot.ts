// Статический источник данных для GitHub Pages.
//
// Страница на Pages работает без бэкенда: вся аналитика, которой нужна база и
// симуляции, посчитана заранее скриптом backend/tools/export_snapshot.py, а
// математика эмблем считается в браузере (src/engine/scoring.ts).
//
// Режим включается переменной сборки VITE_STATIC_DATA=1.

import type { RulesSnapshot, StatValue } from "./engine/scoring";

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

export interface RoleSnapshot {
  team_id: number;
  team_name: string;
  role: string;
  players: string[];
  games: number;
  last_game: string;
  stats: StatValue[];
  player_stats: PlayerStats[];
  timeline: TimelinePoint[];
  period_ratio: number;
  ceiling_ratio: number;
  titles: {
    key: string;
    label: string;
    bonus: number;
    condition: string;
    hit_rate: number | null;
    expected_bonus: number | null;
    estimator: string;
    note: string;
  }[];
}

export interface Snapshot {
  generated_at: string;
  rules: RulesSnapshot & { version: string; source: string; trait_bonus_mode: string };
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
    throw new Error(`не удалось загрузить снапшот: ${response.status}`);
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

/** Дата снапшота человеку — чтобы было видно, насколько данные свежие. */
export function formatGeneratedAt(value: string): string {
  const date = new Date(value);
  return date.toLocaleString("ru", { dateStyle: "medium", timeStyle: "short" });
}
