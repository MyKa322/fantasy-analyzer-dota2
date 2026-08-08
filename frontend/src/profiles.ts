// Профили команд и игроков для статического режима.
//
// Лежат отдельным файлом от snapshot.json и грузятся только при заходе на
// вкладку «Профили»: это полтора мегабайта матчей и героев, которые вкладке с
// эмблемами не нужны совсем.

import { tr } from "./i18n";

export interface ProfileMatch {
  id: number;
  /** Дата, YYYY-MM-DD. */
  d: string;
  /** Длительность, секунды. */
  dur: number;
  opp: string | null;
  opp_id: number | null;
  won: number | null;
  /** 1, если реплей разобран: у остальных нет ни вардов, ни станов. */
  parsed: number;
  league?: string;
  hero?: string;
  k?: number;
  /** Смерти. Ключ с подчёркиванием, потому что `d` уже занято датой. */
  d_?: number;
  a?: number;
  gpm?: number;
  xpm?: number;
  nw?: number;
}

export interface ProfileHero {
  id: number;
  name: string;
  games: number;
  wins: number;
}

export interface ProfileTitle {
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
}

/** Часть выборки: сторона карты, корзина по длительности, класс соперника. */
export interface ProfileSplit {
  key: string;
  games: number;
  wins: number;
}

/** Разрезы, которые одинаково читаются у команды и у игрока. */
export interface ProfileTrends {
  /** Последние 30 дней и предыдущие — до 90-го дня. */
  form: ProfileSplit;
  baseline: ProfileSplit;
  /** +3 — три победы подряд, −2 — два поражения. */
  streak: number;
  sides: ProfileSplit[];
  durations: ProfileSplit[];
}

/** Очки за карту по всему пулу статов роли — сравнимо внутри роли. */
export interface ProfileFantasyForm {
  maps: number;
  mean: number;
  median: number;
  best: number;
  p90: number;
  /** Коэффициент вариации: чем меньше, тем надёжнее ожидание за период. */
  spread: number;
}

export interface ProfilePlayer {
  account_id: number;
  name: string | null;
  /** Титулы считаются только участникам TI15 — их выбирают в состав. */
  titles?: ProfileTitle[];
  team_id: number | null;
  team_name: string | null;
  role: string | null;
  games: number;
  parsed_games: number;
  wins: number;
  first_game: string | null;
  last_game: string | null;
  /** Обычная статистика: ассисты, XPM, нетворт, урон. */
  averages: Record<string, number>;
  /** Fantasy-статы в единицах (килы, варды, секунды стана), не в очках. */
  fantasy_units: Record<string, number>;
  heroes: ProfileHero[];
  matches: ProfileMatch[];
  trends?: ProfileTrends | null;
  /** Сколько карт сыграно с какого лейна — по разметке OpenDota. */
  lanes?: Record<string, number>;
  hero_pool?: { distinct: number; top3_share: number } | null;
  fantasy_form?: ProfileFantasyForm | null;
}

export interface ProfileTeam {
  team_id: number;
  name: string;
  tag: string | null;
  is_ti: boolean;
  rating: number | null;
  rd: number | null;
  games: number;
  parsed_games: number;
  wins: number;
  first_game: string | null;
  last_game: string | null;
  team_averages: Record<string, number>;
  opponents: { name: string; games: number; wins: number }[];
  trends?: ProfileTrends | null;
  /** Средний рейтинг соперника за период — цена побед. */
  opponent_rating?: number | null;
  vs_stronger?: ProfileSplit | null;
  first_blood_rate?: number | null;
  rating_history: { d: string; r: number; rd: number }[];
  roster: number[];
  /** Пул героев всего состава: у каждого героя видно, кто из игроков его берёт. */
  heroes?: {
    id: number;
    name: string;
    games: number;
    wins: number;
    players?: { account_id: number; games: number }[];
  }[];
  matches: ProfileMatch[];
}

export interface Profiles {
  days: number;
  min_games: number;
  teams: ProfileTeam[];
  players: ProfilePlayer[];
}

let cached: Profiles | null = null;
let pending: Promise<Profiles> | null = null;

declare const __BUILD_ID__: string;

export async function loadProfiles(): Promise<Profiles> {
  if (cached) return cached;
  // Один запрос на всех: вкладка дёргает загрузку из нескольких мест сразу.
  pending ??= fetch(`${import.meta.env.BASE_URL}data/profiles.json?v=${__BUILD_ID__}`).then(
    async (response) => {
      if (!response.ok) {
        throw new Error(tr().t("error.profiles", { status: response.status }));
      }
      cached = (await response.json()) as Profiles;
      return cached;
    },
  );
  try {
    return await pending;
  } finally {
    pending = null;
  }
}

/** Победы в процентах — единообразно для команд и игроков. */
export function winRate(wins: number, games: number): number {
  return games ? wins / games : 0;
}
