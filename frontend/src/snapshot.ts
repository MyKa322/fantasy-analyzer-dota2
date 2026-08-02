// Статический источник данных для GitHub Pages.
//
// Страница на Pages работает без бэкенда: вся аналитика, которой нужна база и
// симуляции, посчитана заранее скриптом backend/tools/export_snapshot.py, а
// математика эмблем считается в браузере (src/engine/scoring.ts).
//
// Режим включается переменной сборки VITE_STATIC_DATA=1.

import type { RulesSnapshot, StatValue } from "./engine/scoring";

export const STATIC_MODE = import.meta.env.VITE_STATIC_DATA === "1";

export interface RoleSnapshot {
  team_id: number;
  team_name: string;
  role: string;
  players: string[];
  games: number;
  stats: StatValue[];
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

export async function loadSnapshot(): Promise<Snapshot> {
  if (cached) return cached;
  const response = await fetch(`${import.meta.env.BASE_URL}data/snapshot.json`);
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
