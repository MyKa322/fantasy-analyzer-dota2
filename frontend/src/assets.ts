// Пути к ассетам: иконки эмблем, логотипы команд, портреты игроков.
//
// Иконки эмблем — исходные PNG из fantasy_craft: рисованные тайлы с тенями.
// Они НЕ тонируются и не маскируются — цвет группы живёт на рамке вокруг
// иконки, а не на самой картинке.

const EMBLEM_ASSET: Record<string, string> = {
  kills: "kills",
  deaths: "deaths",
  creep_score: "creep_score",
  gpm: "gpm",
  madstone_collected: "neutral_token",
  tower_kills: "towers_killed",
  wards_placed: "wards_placed",
  camps_stacked: "creeps_stacked",
  runes_grabbed: "rune",
  watchers_taken: "sentinel",
  smokes_used: "smoke",
  lotuses_grabbed: "lotus",
  roshan_kills: "roshan",
  teamfight_participation: "teamfight",
  stuns: "stuns",
  tormentor_kills: "tormentor",
  first_blood: "first_blood",
  courier_kills: "courier_kill",
};

export function emblemIcon(stat: string): string | null {
  const asset = EMBLEM_ASSET[stat];
  return asset ? asset_(`emblems/fantasy_emblem_${asset}_png.webp`) : null;
}

/**
 * Пути к статике учитывают base: на GitHub Pages страница живёт в подкаталоге
 * `/<repo>/`, и абсолютный путь от корня домена там ведёт в никуда.
 */
function asset_(relative: string): string {
  return `${import.meta.env.BASE_URL}assets/${relative}`;
}

// Название в компендиуме -> файл логотипа и папка с портретами.
const TEAM_ASSET: Record<string, { crest: string; players: string }> = {
  "Team Liquid": { crest: "TeamLiquid", players: "Liquid" },
  BoomBoys: { crest: "BoomBoys", players: "BoomBoys" },
  "Xtreme Gaming": { crest: "XtremeGaming", players: "XtremeGaming" },
  "Team Falcons": { crest: "TeamFalcons", players: "Falcons" },
  "Aurora Gaming": { crest: "AuroraGaming", players: "Aurora" },
  "Team Yandex": { crest: "TeamYandex", players: "TeamYandex" },
  "Iron Wing": { crest: "IronWings", players: "IronWings" },
  "Vici Gaming": { crest: "ViciGaming", players: "ViciGaming" },
  "Team Resilience": { crest: "TeamResilience", players: "Resilince" },
  "LGD Gaming": { crest: "LGDGaming", players: "LGDGaming" },
  OG: { crest: "OG", players: "OG" },
  GamerLegion: { crest: "GamerLegion", players: "GamerLegion" },
  "Nigma Galaxy": { crest: "NigmaGalaxy", players: "NigmaGalaxy" },
  Huligani: { crest: "Huligani", players: "Huligani" },
  "Team Vision": { crest: "TeamVision", players: "TeamVision" },
  "Team Spirit": { crest: "TeamSpirit", players: "TeamSpirit" },
};

export function teamCrest(name: string | null | undefined): string | null {
  if (!name) return null;
  const entry = TEAM_ASSET[name];
  return entry ? asset_(`teams/${entry.crest}.webp`) : null;
}

/**
 * Портреты сопоставляются через манифест, а не подбором имён файлов: в никах
 * OpenDota хватает украшений (`医者watson``, `Ace ♠`, `Mirage`雨`), которых в
 * именах файлов нет. Манифест собирается скриптом
 * `backend/tools/build_portrait_manifest.py` и лежит рядом с картинками.
 */
type PortraitManifest = Record<string, Record<string, string>>;

let manifest: PortraitManifest = {};

declare const __BUILD_ID__: string;

export async function loadPortraitManifest(): Promise<void> {
  try {
    // Та же причина, что и у снапшота: имя файла постоянное, содержимое — нет.
    const response = await fetch(`${asset_("players/manifest.json")}?v=${__BUILD_ID__}`);
    if (response.ok) manifest = await response.json();
  } catch {
    // без манифеста портреты просто заменятся инициалами
  }
}

/**
 * Иконки героев. В матче лежит только hero_id, а файлы названы внутренним
 * именем героя, поэтому связка идёт через манифест — он собирается скриптом
 * `backend/tools/build_hero_manifest.py`.
 */
let heroFiles: Record<string, string> = {};

export async function loadHeroManifest(): Promise<void> {
  try {
    const response = await fetch(`${asset_("heroes/manifest.json")}?v=${__BUILD_ID__}`);
    if (response.ok) heroFiles = await response.json();
  } catch {
    // без манифеста в списках останутся названия без картинок
  }
}

export function heroIcon(heroId: number | null | undefined): string | null {
  if (heroId == null) return null;
  const file = heroFiles[String(heroId)];
  return file ? asset_(`heroes/${file}`) : null;
}

/** Ник -> сравнимая форма: только латиница и цифры. */
export function normaliseNickname(nickname: string): string {
  return nickname
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
}

export function playerPortrait(
  teamName: string | null | undefined,
  nickname: string | null | undefined,
): string | null {
  if (!teamName || !nickname) return null;
  const entry = TEAM_ASSET[teamName];
  if (!entry) return null;
  const file = manifest[entry.players]?.[normaliseNickname(nickname)];
  return file ? asset_(`players/${entry.players}/${encodeURIComponent(file)}`) : null;
}

export const GROUP_COLOR: Record<string, string> = {
  red: "var(--group-red)",
  blue: "var(--group-blue)",
  green: "var(--group-green)",
};

export const GROUP_LINE: Record<string, string> = {
  red: "var(--group-red-line)",
  blue: "var(--group-blue-line)",
  green: "var(--group-green-line)",
};

export const GROUP_DIM: Record<string, string> = {
  red: "var(--group-red-dim)",
  blue: "var(--group-blue-dim)",
  green: "var(--group-green-dim)",
};

export const QUALITY_LABEL: Record<string, string> = {
  tier_1: "Tier I",
  tier_2: "Tier II",
  tier_3: "Tier III",
  tier_4: "Tier IV",
  tier_5: "Tier V",
};

export const TRAIT_LABEL: Record<string, string> = {
  fractal: "Fractal",
  benevolent: "Benevolent",
  vampiric: "Vampiric",
  unique: "Unique",
  friendly: "Friendly",
};

export const ROLE_LABEL: Record<string, string> = {
  core: "Core Duo",
  mid: "Mid",
  support: "Support Duo",
};
