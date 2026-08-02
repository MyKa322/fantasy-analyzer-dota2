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

export interface RulesSnapshot {
  qualities: Record<string, number>;
  traits: TraitRule[];
  role_slots: Record<string, string[]>;
  banner_slots: number;
  stats: {
    key: string;
    label: string;
    color: GroupColor;
    availability: Availability;
    note: string;
  }[];
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
