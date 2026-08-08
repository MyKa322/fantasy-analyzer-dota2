// Движок эмблем в браузере — копия аддитивной модели из backend/app/fantasy.
//
// На GitHub Pages бэкенда нет, но пересчитывать баннеры всё равно нужно: без
// этого страница превращается в картинку. Математика здесь дешёвая и полностью
// линейная по базовым очкам стата, поэтому снапшот отдаёт очки по каждому
// стату, а проценты и перебор комбинаций считаются на месте.
//
//   процент = 100 + бонус качества + собственный трейт (если условие выполнено)
//             + сумма эффектов соседей
//
// Эталон — девять карточек с экрана War Banner, они же покрыты тестами на
// бэкенде: 130/100/180, 150/180/120, 160/130/130.

/** Цвет группы эмблем — он же цвет слота на баннере. */
export type GroupColor = "red" | "blue" | "green";

/** Насколько статистику по стату вообще можно получить из OpenDota. */
export type Availability = "exact" | "approximate" | "unavailable";

export interface TraitRule {
  key: string;
  label: string;
  description: string;
  condition: string;
  effects: { scope: string; amount: number }[];
}

/** Правило начисления очков за стат — копия StatRule из backend/app/fantasy. */
export interface StatScoring {
  key: string;
  label: string;
  color: GroupColor;
  availability: Availability;
  note: string;
  /** per_unit | linear | flat | capped */
  kind?: string;
  per_unit?: number;
  base?: number;
  value_if_true?: number;
  max_points?: number;
}

/** Coaching Title: процент к очкам, если условие выполнено. */
export interface TitleRule {
  key: string;
  label: string;
  bonus: number;
  condition: string;
  estimator: string;
  /** Список героев — только у титулов-приставок, они же цветовые. */
  heroes?: string[];
}

export interface RulesSnapshot {
  qualities: Record<string, number>;
  traits: TraitRule[];
  role_slots: Record<string, string[]>;
  banner_slots: number;
  stats: StatScoring[];
  titles?: { prefixes: TitleRule[]; suffixes: TitleRule[] };
}

/**
 * Очки за стат до бонусов эмблемы.
 *
 * Тот же расчёт, что в `StatRule.points` на бэкенде: снапшот отдаёт вид правила
 * и коэффициенты, поэтому страница матча считает очки для любой карты, а не
 * только для тех, что посчитаны заранее.
 */
export function statPoints(rule: StatScoring, value: number): number {
  switch (rule.kind) {
    case "per_unit":
      return (rule.per_unit ?? 0) * value;
    case "linear":
      return (rule.base ?? 0) + (rule.per_unit ?? 0) * value;
    case "flat":
      return value ? (rule.value_if_true ?? 0) : 0;
    case "capped":
      return (rule.max_points ?? 0) * Math.min(Math.max(value, 0), 1);
    default:
      return 0;
  }
}

export interface Emblem {
  stat: string;
  quality: string;
  trait: string | null;
}

export interface StatValue {
  stat: string;
  label: string;
  color: GroupColor;
  units_per_game: number;
  base_points: number;
  p95_points: number;
  p5_points: number;
  availability: Availability;
  negligible: boolean;
  // Точечные данные по картам: медиана и квартиль против выбросов, доля карт
  // со статом (0,3 Рошана — это каждая третья игра) и свежая форма.
  median_points?: number;
  p75_points?: number;
  hit_rate?: number;
  trend?: number | null;
}

function traitByKey(rules: RulesSnapshot): Record<string, TraitRule> {
  return Object.fromEntries(rules.traits.map((t) => [t.key, t]));
}

/** Выполнено ли условие трейта на этом баннере. */
function conditionMet(trait: TraitRule, banner: Emblem[]): boolean {
  switch (trait.condition) {
    case "always":
      return true;
    case "all_qualities_distinct": {
      const qualities = banner.map((e) => e.quality);
      return new Set(qualities).size === qualities.length;
    }
    case "only_unique_on_banner":
      return banner.filter((e) => e.trait === trait.key).length === 1;
    case "at_least_3_friendly":
      return banner.filter((e) => e.trait === trait.key).length >= 3;
    default:
      return false;
  }
}

/**
 * Множитель каждой эмблемы (1.30 = 130% на карточке).
 * Соседство линейное: эмблемы стоят колонкой, у крайних по одному соседу.
 */
export function emblemMultipliers(banner: Emblem[], rules: RulesSnapshot): number[] {
  const traits = traitByKey(rules);
  const active = new Map<string, boolean>();
  for (const emblem of banner) {
    if (emblem.trait && traits[emblem.trait]) {
      active.set(emblem.trait, conditionMet(traits[emblem.trait], banner));
    }
  }

  return banner.map((emblem, index) => {
    let total = 1 + (rules.qualities[emblem.quality] ?? 0);

    if (emblem.trait && active.get(emblem.trait)) {
      for (const effect of traits[emblem.trait].effects) {
        if (effect.scope === "self_bonus" || effect.scope === "self_value") {
          total += effect.amount;
        }
      }
    }

    for (const neighbour of [index - 1, index + 1]) {
      if (neighbour < 0 || neighbour >= banner.length) continue;
      const key = banner[neighbour].trait;
      if (!key || !active.get(key)) continue;
      for (const effect of traits[key].effects) {
        if (effect.scope === "adjacent_value") total += effect.amount;
      }
    }

    return total;
  });
}

export interface SlotBreakdown {
  slot: number;
  color: GroupColor;
  stat: string;
  label: string;
  quality: string;
  trait: string | null;
  percent: number;
  base_points: number;
  points: number;
}

export function scoreBanner(
  banner: Emblem[],
  statValues: Map<string, StatValue>,
  rules: RulesSnapshot,
): { slots: SlotBreakdown[]; total: number } {
  const multipliers = emblemMultipliers(banner, rules);
  const slots = banner.map((emblem, index) => {
    const value = statValues.get(emblem.stat);
    const base = value?.base_points ?? 0;
    return {
      slot: index,
      color: value?.color ?? "red",
      stat: emblem.stat,
      label: value?.label ?? emblem.stat,
      quality: emblem.quality,
      trait: emblem.trait,
      percent: multipliers[index] * 100,
      base_points: base,
      points: base * multipliers[index],
    };
  });
  return { slots, total: slots.reduce((sum, s) => sum + s.points, 0) };
}

// --- свой инвентарь -----------------------------------------------------------

export interface InventoryFit {
  role: string;
  used: Emblem[];
  unused: Emblem[];
  slots: SlotBreakdown[];
  total: number;
}

function statColors(rules: RulesSnapshot): Map<string, GroupColor> {
  return new Map(rules.stats.map((s) => [s.key, s.color]));
}

/**
 * Каких цветов не хватает, чтобы вообще заполнить баннер роли.
 * Зависит только от инвентаря и роли: цвета слотов фиксированы.
 */
export function inventoryGaps(
  inventory: Emblem[],
  role: string,
  rules: RulesSnapshot,
): { color: GroupColor; need: number; have: number }[] {
  const colors = statColors(rules);
  const need = new Map<string, number>();
  for (const color of rules.role_slots[role] ?? []) {
    need.set(color, (need.get(color) ?? 0) + 1);
  }
  const have = new Map<string, number>();
  for (const emblem of inventory) {
    const color = colors.get(emblem.stat);
    if (color) have.set(color, (have.get(color) ?? 0) + 1);
  }
  return [...need.entries()]
    .filter(([color, count]) => (have.get(color) ?? 0) < count)
    .map(([color, count]) => ({
      color: color as GroupColor,
      need: count,
      have: have.get(color) ?? 0,
    }));
}

/**
 * Разложить имеющиеся эмблемы по слотам роли наилучшим образом.
 *
 * Обратная задача к optimiseBanner: качества и трейты уже выпали, менять их
 * нечем. Свободы две — какие три эмблемы взять и в каком порядке поставить:
 * Benevolent и Vampiric действуют на соседей, поэтому порядок решает.
 * Кандидаты в слот ограничены его цветом, так что перебор остаётся крошечным.
 */
export function fitInventory(
  role: string,
  inventory: Emblem[],
  statValues: StatValue[],
  rules: RulesSnapshot,
): InventoryFit | null {
  const slotColors = rules.role_slots[role] ?? [];
  if (inventoryGaps(inventory, role, rules).length) return null;

  const colors = statColors(rules);
  const byStat = new Map(statValues.map((v) => [v.stat, v]));
  const base = (stat: string) => byStat.get(stat)?.base_points ?? 0;

  const candidates = slotColors.map((color) =>
    inventory.map((_, i) => i).filter((i) => colors.get(inventory[i].stat) === color),
  );

  let bestTotal = -Infinity;
  let bestIndices: number[] = [];

  const walk = (slot: number, chosen: number[]) => {
    if (slot === slotColors.length) {
      const emblems = chosen.map((i) => inventory[i]);
      const multipliers = emblemMultipliers(emblems, rules);
      let total = 0;
      for (let i = 0; i < emblems.length; i++) total += base(emblems[i].stat) * multipliers[i];
      if (total > bestTotal) {
        bestTotal = total;
        bestIndices = [...chosen];
      }
      return;
    }
    for (const index of candidates[slot]) {
      if (chosen.includes(index)) continue;
      // Один и тот же стат дважды на баннере правилами запрещён.
      if (chosen.some((c) => inventory[c].stat === inventory[index].stat)) continue;
      chosen.push(index);
      walk(slot + 1, chosen);
      chosen.pop();
    }
  };
  walk(0, []);

  if (!bestIndices.length) return null;
  const used = bestIndices.map((i) => inventory[i]);
  const detailed = scoreBanner(used, byStat, rules);
  return {
    role,
    used,
    unused: inventory.filter((_, i) => !bestIndices.includes(i)),
    slots: detailed.slots,
    total: detailed.total,
  };
}

function cartesian<T>(pool: T[], length: number): T[][] {
  let result: T[][] = [[]];
  for (let i = 0; i < length; i++) {
    const next: T[][] = [];
    for (const prefix of result) for (const item of pool) next.push([...prefix, item]);
    result = next;
  }
  return result;
}

export interface BannerOption {
  emblems: Emblem[];
  slots: SlotBreakdown[];
  total: number;
}

/**
 * Перебор лучших баннеров для роли.
 *
 * Цвет слота задан ролью, поэтому кандидаты в каждый слот ограничены цветом.
 * Множители зависят только от качеств и трейтов, так что они считаются один раз
 * для всех комбинаций статов — иначе перебор раздувается в три четверти
 * миллиона расчётов вместо двадцати семи тысяч.
 */
export function optimiseBanner(
  role: string,
  statValues: StatValue[],
  rules: RulesSnapshot,
  options: {
    qualities?: string[];
    traits?: (string | null)[];
    statsPerSlot?: number;
    topN?: number;
  } = {},
): BannerOption[] {
  const colors = rules.role_slots[role] ?? ["red", "red", "green"];
  const qualities = options.qualities?.length
    ? options.qualities
    : Object.keys(rules.qualities);
  const traits = options.traits?.length
    ? options.traits
    : [null, ...rules.traits.map((t) => t.key)];
  const statsPerSlot = options.statsPerSlot ?? 3;
  const topN = options.topN ?? 3;

  const byStat = new Map(statValues.map((v) => [v.stat, v]));
  const usable = statValues.filter((v) => v.availability !== "unavailable");

  const slotCandidates = colors.map((color) =>
    usable
      .filter((v) => v.color === color)
      .sort((a, b) => b.base_points - a.base_points)
      .slice(0, statsPerSlot),
  );
  if (slotCandidates.some((pool) => pool.length === 0)) return [];

  // Один и тот же набор множителей для любых статов.
  const layouts: { qualities: string[]; traits: (string | null)[]; multipliers: number[] }[] = [];
  const probeStats = slotCandidates.map((pool) => pool[0].stat);
  for (const qualityCombo of cartesian(qualities, colors.length)) {
    for (const traitCombo of cartesian(traits, colors.length)) {
      const probe = probeStats.map((stat, i) => ({
        stat,
        quality: qualityCombo[i],
        trait: traitCombo[i],
      }));
      layouts.push({
        qualities: qualityCombo,
        traits: traitCombo,
        multipliers: emblemMultipliers(probe, rules),
      });
    }
  }

  // Комбинации статов собираем обходом: у слотов разные пулы, и дубликаты
  // статов на баннере запрещены правилами.
  const combos: string[][] = [];
  const walk = (index: number, current: string[]) => {
    if (index === slotCandidates.length) {
      if (new Set(current).size === current.length) combos.push([...current]);
      return;
    }
    for (const value of slotCandidates[index]) {
      current.push(value.stat);
      walk(index + 1, current);
      current.pop();
    }
  };
  walk(0, []);

  const scored: BannerOption[] = [];
  for (const stats of combos) {
    const base = stats.map((s) => byStat.get(s)?.base_points ?? 0);
    for (const layout of layouts) {
      let total = 0;
      for (let i = 0; i < base.length; i++) total += base[i] * layout.multipliers[i];
      scored.push({
        emblems: stats.map((stat, i) => ({
          stat,
          quality: layout.qualities[i],
          trait: layout.traits[i],
        })),
        slots: [],
        total,
      });
    }
  }

  scored.sort((a, b) => b.total - a.total);

  const seen = new Set<string>();
  const result: BannerOption[] = [];
  for (const option of scored) {
    const key = option.emblems.map((e) => `${e.stat}|${e.quality}|${e.trait}`).join(",");
    if (seen.has(key)) continue;
    seen.add(key);
    const detailed = scoreBanner(option.emblems, byStat, rules);
    result.push({ emblems: option.emblems, slots: detailed.slots, total: detailed.total });
    if (result.length >= topN) break;
  }
  return result;
}
