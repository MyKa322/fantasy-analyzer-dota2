// Сырьё для пересчёта рейтинга: исходы карт с турниром и датой.
//
// Снапшот отвечает, что модель думает сейчас, и одного ответа мало: рейтинг
// зависит от того, какие матчи в него взяли, а это выбор. Здесь лежит то, из
// чего страница может собрать свою основу — только TI, всё кроме TI, последний
// месяц — и пересчитать рейтинг под неё.
//
// Файл отдельный и грузится по требованию: его спрашивает одна вкладка.

import { tr } from "./i18n";
import type { MapResult } from "./engine/rating";

/** Строка файла: время, турнир, radiant, dire, победил ли radiant. */
export type MatchRow = [ts: number, league: number, radiant: number, dire: number, win: number];

export interface MatchesFile {
  generated_at: string;
  /** Начало окна, YYYY-MM-DD. */
  since: string;
  days: number;
  /** Длина рейтингового периода — та же, которой посчитан снапшот. */
  period_days: number;
  leagues: Record<string, string>;
  /** Турниры самого события: по ним работает «только TI» и «без TI». */
  event_leagues: number[];
  teams: Record<string, string>;
  matches: MatchRow[];
}

let cached: MatchesFile | null = null;
let pending: Promise<MatchesFile> | null = null;

declare const __BUILD_ID__: string;

export async function loadMatches(): Promise<MatchesFile> {
  if (cached) return cached;
  pending ??= fetch(`${import.meta.env.BASE_URL}data/matches.json?v=${__BUILD_ID__}`).then(
    async (response) => {
      if (!response.ok) {
        throw new Error(tr().t("error.matches", { status: response.status }));
      }
      cached = (await response.json()) as MatchesFile;
      return cached;
    },
  );
  try {
    return await pending;
  } finally {
    pending = null;
  }
}

export interface Basis {
  /** Границы периода в секундах; null — без границы. */
  from: number | null;
  to: number | null;
  /** Выключенные турниры. Выключенных обычно меньше, чем включённых. */
  off: Set<number>;
}

/** Карты, попадающие в основу. */
export function selectMatches(file: MatchesFile, basis: Basis): MapResult[] {
  const result: MapResult[] = [];
  for (const [ts, league, radiant, dire, win] of file.matches) {
    if (basis.from != null && ts < basis.from) continue;
    if (basis.to != null && ts > basis.to) continue;
    if (basis.off.has(league)) continue;
    result.push({ ts, league, radiant, dire, radiantWin: win === 1 });
  }
  return result;
}

/** Сколько карт даёт каждый турнир внутри выбранного периода. */
export function leagueCounts(file: MatchesFile, from: number | null, to: number | null) {
  const counts = new Map<number, number>();
  for (const [ts, league] of file.matches) {
    if (from != null && ts < from) continue;
    if (to != null && ts > to) continue;
    counts.set(league, (counts.get(league) ?? 0) + 1);
  }
  return counts;
}

export const dayStart = (iso: string): number => Date.parse(`${iso}T00:00:00Z`) / 1000;
export const dayEnd = (iso: string): number => Date.parse(`${iso}T23:59:59Z`) / 1000;
export const toIso = (seconds: number): string =>
  new Date(seconds * 1000).toISOString().slice(0, 10);
