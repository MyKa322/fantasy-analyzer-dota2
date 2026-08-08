// Разбор одного матча по публичному API OpenDota.
//
// Единственное место, где страница ходит не к своим данным: снапшот считается
// заранее и знает только матчи участников TI, а страница матча должна открывать
// любой id — в том числе вчерашний паб и матч квалификации.
//
// Запрос идёт прямо из браузера: у api.opendota.com открытый CORS, и прокси
// свой заводить незачем — на GitHub Pages его всё равно негде держать. Ключ не
// нужен, но без него действует общий лимит (60 запросов в минуту), поэтому
// разобранный матч кэшируется на время сессии.

import { tr } from "./i18n";

const BASE = "https://api.opendota.com/api";

/** Варда в логе: координаты в сетке 64…192, время — секунды от начала игры. */
export interface WardEntry {
  time: number;
  x: number;
  y: number;
  player_slot?: number;
  /** Идентификатор сущности: по нему постановка сходится со снятием. */
  ehandle?: number;
}

export interface PurchaseEntry {
  time: number;
  key: string;
}

/** Событие матча: вышки, Рошан, аегис, первая кровь. */
export interface ObjectiveEntry {
  time: number;
  type: string;
  key?: string | number;
  unit?: string;
  player_slot?: number;
  team?: number;
  slot?: number;
}

export interface TeamfightEntry {
  start: number;
  end: number;
  last_death?: number;
  deaths?: number;
  /** По игроку: где он умирал в этом файте, {x: {y: количество}}. */
  players?: { deaths_pos?: Record<string, Record<string, number>> }[];
}

/** Игрок в матче — только те поля, которые страница действительно читает. */
export interface MatchPlayer {
  account_id?: number | null;
  personaname?: string | null;
  name?: string | null;
  hero_id: number;
  player_slot: number;
  isRadiant?: boolean;
  lane_role?: number | null;
  level?: number;
  kills?: number;
  deaths?: number;
  assists?: number;
  last_hits?: number;
  denies?: number;
  gold_per_min?: number;
  xp_per_min?: number;
  net_worth?: number;
  total_gold?: number;
  hero_damage?: number;
  tower_damage?: number;
  hero_healing?: number;
  obs_placed?: number | null;
  sen_placed?: number | null;
  camps_stacked?: number | null;
  rune_pickups?: number | null;
  stuns?: number | null;
  teamfight_participation?: number | null;
  roshan_kills?: number | null;
  tower_kills?: number | null;
  courier_kills?: number | null;
  firstblood_claimed?: number | null;
  item_uses?: Record<string, number> | null;
  killed?: Record<string, number> | null;
  // Инвентарь на момент конца игры: id предметов, имена — в справочнике снапшота.
  item_0?: number;
  item_1?: number;
  item_2?: number;
  item_3?: number;
  item_4?: number;
  item_5?: number;
  item_neutral?: number;
  // Логи разобранного реплея. У неразобранного матча их нет вовсе.
  obs_log?: WardEntry[] | null;
  sen_log?: WardEntry[] | null;
  obs_left_log?: WardEntry[] | null;
  sen_left_log?: WardEntry[] | null;
  purchase_log?: PurchaseEntry[] | null;
}

export interface MatchTeam {
  team_id?: number;
  name?: string | null;
  tag?: string | null;
}

export interface OpenDotaMatch {
  match_id: number;
  start_time: number;
  duration: number;
  radiant_win: boolean | null;
  radiant_score?: number;
  dire_score?: number;
  first_blood_time?: number | null;
  league?: { name?: string | null } | null;
  radiant_team?: MatchTeam | null;
  dire_team?: MatchTeam | null;
  /** null у матча без разобранного реплея. */
  version?: number | null;
  patch?: number | null;
  series_id?: number | null;
  series_type?: number | null;
  radiant_gold_adv?: number[] | null;
  radiant_xp_adv?: number[] | null;
  objectives?: ObjectiveEntry[] | null;
  teamfights?: TeamfightEntry[] | null;
  players: MatchPlayer[];
}

/**
 * Координаты OpenDota -> доля стороны миникарты.
 *
 * В логах лежит игровая сетка: играбельная часть карты укладывается в 64…192 по
 * обеим осям, ось Y растёт на север. Проверено по `lane_pos`: у радиантского
 * керри центр масс попадает в правый нижний угол, у даерского — в левый
 * верхний, миды сходятся к центру.
 */
export function mapPosition(x: number, y: number): { left: number; top: number } {
  return { left: ((x - 64) / 128) * 100, top: ((192 - y) / 128) * 100 };
}

const cache = new Map<number, OpenDotaMatch>();

export async function loadMatch(matchId: number): Promise<OpenDotaMatch> {
  const cached = cache.get(matchId);
  if (cached) return cached;

  let response: Response;
  try {
    response = await fetch(`${BASE}/matches/${matchId}`);
  } catch {
    // Сюда попадают и обрыв сети, и блокировка запроса расширением — различить
    // их из fetch нельзя, поэтому сообщение общее.
    throw new Error(tr().t("match.errorNetwork"));
  }

  if (response.status === 404) throw new Error(tr().t("match.errorNotFound"));
  if (response.status === 429) throw new Error(tr().t("match.errorRateLimit"));
  if (!response.ok) {
    throw new Error(tr().t("match.errorStatus", { status: response.status }));
  }

  const match = (await response.json()) as OpenDotaMatch;
  if (!match || !Array.isArray(match.players)) {
    throw new Error(tr().t("match.errorNotFound"));
  }
  cache.set(matchId, match);
  return match;
}

/**
 * Разобран ли реплей.
 *
 * Признак тот же, что на бэкенде: у неразобранного матча нет ни станов, ни
 * вардов, и половина Fantasy-статов у него — нули, а не «игрок ничего не делал».
 */
export function isParsed(match: OpenDotaMatch): boolean {
  if (match.version == null) return false;
  return match.players.some((player) => player.stuns != null);
}

const LOTUS_ITEMS = ["famango", "great_famango"] as const;

function num(value: number | null | undefined): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

/**
 * Fantasy-статы игрока — порт `extract_player_stats` из backend/app/ingest.
 *
 * Недоступные статы возвращаются нулями, а не пропускаются: страница показывает
 * их отдельной пометкой, иначе читатель решит, что игрок их просто не набрал.
 */
export function fantasyStats(player: MatchPlayer): Record<string, number> {
  const uses = player.item_uses ?? {};
  const killed = player.killed ?? {};

  return {
    kills: num(player.kills),
    deaths: num(player.deaths),
    creep_score: num(player.last_hits) + num(player.denies),
    gpm: num(player.gold_per_min),
    madstone_collected: 0,
    tower_kills: num(player.tower_kills),
    wards_placed: num(player.obs_placed),
    camps_stacked: num(player.camps_stacked),
    runes_grabbed: num(player.rune_pickups),
    watchers_taken: 0,
    smokes_used: num(uses.smoke_of_deceit),
    lotuses_grabbed: LOTUS_ITEMS.reduce((sum, item) => sum + num(uses[item]), 0),
    roshan_kills: num(player.roshan_kills),
    teamfight_participation: num(player.teamfight_participation),
    stuns: num(player.stuns),
    tormentor_kills: num(killed.npc_dota_miniboss),
    first_blood: num(player.firstblood_claimed),
    courier_kills: num(player.courier_kills),
  };
}

/** Сторона игрока: у OpenDota она закодирована старшим битом слота. */
export function isRadiant(player: MatchPlayer): boolean {
  return player.isRadiant ?? player.player_slot < 128;
}

/** Ссылка на матч на самой OpenDota — чтобы было куда уйти за деталями. */
export function matchUrl(matchId: number): string {
  return `https://www.opendota.com/matches/${matchId}`;
}
