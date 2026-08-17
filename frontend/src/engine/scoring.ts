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

/** Раскладка баннера одного периода: сколько слотов и какого цвета. */
export interface StageLayout {
  slots: number;
  role_slots: Record<string, string[]>;
  /** Нейтральный набор статов роли — тот же, что считает бэкенд. */
  neutral_stats?: Record<string, string[]>;
}

export interface RulesSnapshot {
  qualities: Record<string, number>;
  traits: TraitRule[];
  role_slots: Record<string, string[]>;
  banner_slots: number;
  stats: StatScoring[];
  titles?: { prefixes: TitleRule[]; suffixes: TitleRule[] };
  /** Периоды с другой раскладкой: в основном этапе у роли пять эмблем. */
  stages?: Record<string, StageLayout>;
}

/**
 * Цвета слотов роли в этом периоде.
 *
 * Раскладка задана периодом: групповой этап играется тремя эмблемами, основной
 * — пятью. Старый снапшот про периоды не знает, и тогда остаётся базовая.
 */
export function roleSlots(
  rules: RulesSnapshot,
  role: string,
  stage?: string,
): string[] {
  const layout = stage ? rules.stages?.[stage] : undefined;
  return layout?.role_slots[role] ?? rules.role_slots[role] ?? [];
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
  stage?: string,
): { color: GroupColor; need: number; have: number }[] {
  const colors = statColors(rules);
  const need = new Map<string, number>();
  for (const color of roleSlots(rules, role, stage)) {
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
  stage?: string,
): InventoryFit | null {
  const slotColors = roleSlots(rules, role, stage);
  if (inventoryGaps(inventory, role, rules, stage).length) return null;

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

export interface BannerOption {
  emblems: Emblem[];
  slots: SlotBreakdown[];
  total: number;
}

/** Трейт двумя числами: что даёт себе и что соседям. Порт banner_search.py. */
interface TraitMath {
  key: string | null;
  own: number;
  adjacent: number;
  condition: string;
}

function traitMath(rules: RulesSnapshot, keys: (string | null)[]): TraitMath[] {
  const byKey = traitByKey(rules);
  return keys.map((key) => {
    const rule = key ? byKey[key] : undefined;
    if (!rule) return { key: null, own: 0, adjacent: 0, condition: "always" };
    let own = 0;
    let adjacent = 0;
    for (const effect of rule.effects) {
      if (effect.scope === "self_bonus" || effect.scope === "self_value") own += effect.amount;
      if (effect.scope === "adjacent_value") adjacent += effect.amount;
    }
    return { key, own, adjacent, condition: rule.condition };
  });
}

/** Подмножества условных трейтов: какие условия считаем сработавшими. */
function subsets<T>(items: T[]): T[][] {
  const result: T[][] = [[]];
  for (const item of items) {
    for (const existing of [...result]) result.push([...existing, item]);
  }
  return result;
}

/**
 * Подбор лучших баннеров для роли.
 *
 * Полный перебор качеств и трейтов — это |качества|^слотов × |трейты|^слотов.
 * На трёх слотах это 27 тысяч, на пяти (основной этап) — двадцать четыре
 * миллиона, и браузер на этом встаёт. Считать столько и не нужно: счёт баннера
 * раскладывается на независимые по слотам слагаемые
 *
 *     счёт = Σ base_i · (1 + качество_i + свой трейт_i)
 *          + Σ эффект_на_соседей(трейт_i) · (сумма base соседей i),
 *
 * и слоты связывают между собой только условия трейтов: Fractal требует все
 * качества разными, Unique — что он на баннере один, Friendly — что таких
 * эмблем хотя бы три. Поэтому перебираются варианты «какие условия сработали»
 * (их восемь), а внутри каждого выбор идёт послотно. Тот же алгоритм и с теми же
 * доводами живёт в backend/app/fantasy/banner_search.py.
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
    stage?: string;
  } = {},
): BannerOption[] {
  const colors = roleSlots(rules, role, options.stage);
  if (!colors.length) return [];

  const qualityKeys = options.qualities?.length
    ? options.qualities
    : Object.keys(rules.qualities);
  const qualities = qualityKeys
    .map((key) => ({ key, bonus: rules.qualities[key] ?? 0 }))
    .sort((a, b) => b.bonus - a.bonus);
  if (!qualities.length) return [];

  const traitKeys = options.traits?.length
    ? options.traits
    : [null, ...rules.traits.map((t) => t.key)];
  const pool = traitMath(rules, traitKeys);
  const conditional = pool.filter((t) => t.key && t.condition !== "always");

  const byStat = new Map(statValues.map((v) => [v.stat, v]));
  const usable = statValues.filter((v) => v.availability !== "unavailable");

  // Пул слота не может быть меньше числа слотов того же цвета: повторять стат
  // на баннере нельзя, а у кора в основном этапе три красных слота.
  const sameColor = new Map<string, number>();
  for (const color of colors) sameColor.set(color, (sameColor.get(color) ?? 0) + 1);
  const slotCandidates = colors.map((color) =>
    usable
      .filter((v) => v.color === color)
      .sort((a, b) => b.base_points - a.base_points)
      .slice(0, Math.max(options.statsPerSlot ?? 3, (sameColor.get(color) ?? 1) + 1)),
  );
  if (slotCandidates.some((pool) => pool.length === 0)) return [];

  // Комбинации статов: у слотов разные пулы, дубликаты запрещены правилами.
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

  const found = new Map<string, { emblems: Emblem[]; total: number }>();

  for (const stats of combos) {
    const base = stats.map((s) => byStat.get(s)?.base_points ?? 0);
    const neighbours = base.map(
      (_, i) => (i > 0 ? base[i - 1] : 0) + (i + 1 < base.length ? base[i + 1] : 0),
    );

    for (const active of subsets(conditional)) {
      const activeKeys = new Set(active.map((t) => t.key));
      const distinct = active.some((t) => t.condition === "all_qualities_distinct");
      if (distinct && qualities.length < colors.length) continue;

      // Качества: при активном Fractal — все разные, и больший бонус уходит
      // слоту с большими базовыми очками; иначе везде лучшее качество.
      const quality: { key: string; bonus: number }[] = [];
      if (distinct) {
        const order = base.map((_, i) => i).sort((a, b) => base[b] - base[a]);
        order.forEach((slot, rank) => {
          quality[slot] = qualities[rank];
        });
      } else {
        for (let i = 0; i < colors.length; i++) quality[i] = qualities[0];
      }

      const works = (trait: TraitMath) =>
        trait.key === null || trait.condition === "always" || activeKeys.has(trait.key);
      const value = (slot: number, trait: TraitMath) =>
        base[slot] * (1 + quality[slot].bonus + (works(trait) ? trait.own : 0)) +
        (works(trait) ? trait.adjacent : 0) * neighbours[slot];

      const allowed = pool.filter(
        (t) => t.key === null || t.condition === "always" || activeKeys.has(t.key),
      );
      const exactlyOne = allowed.filter((t) => t.condition === "only_unique_on_banner");
      const atLeastThree = allowed.filter((t) => t.condition === "at_least_3_friendly");
      const free = allowed.filter((t) => !exactlyOne.includes(t));
      if (!free.length || exactlyOne.length > colors.length) continue;

      // Трейт «ровно один на баннере» перебирается по слотам: вариантов мало, а
      // выбор слота меняет всё остальное распределение. Такой трейт в правилах
      // ровно один (Unique); появится второй — этот контекст просто пропустится,
      // и оптимум будет найден среди остальных.
      if (exactlyOne.length > 1) continue;
      const slotsForOne: number[][] =
        exactlyOne.length === 0 ? [[]] : colors.map((_, i) => [i]);

      for (const forced of slotsForOne) {
        const chosen: TraitMath[] = new Array(colors.length).fill(free[0]);
        forced.forEach((slot, index) => {
          chosen[slot] = exactlyOne[index];
        });
        const freeSlots = colors
          .map((_, i) => i)
          .filter((i) => !forced.includes(i));
        for (const slot of freeSlots) {
          chosen[slot] = free.reduce((best, t) =>
            value(slot, t) > value(slot, best) ? t : best,
          );
        }

        // «Не меньше трёх» — количество доводится там, где замена дешевле всего.
        let short = false;
        for (const trait of atLeastThree) {
          const need = 3 - chosen.filter((t) => t === trait).length;
          if (need <= 0) continue;
          const spare = freeSlots
            .filter((i) => chosen[i] !== trait)
            .sort(
              (a, b) =>
                value(a, chosen[a]) - value(a, trait) - (value(b, chosen[b]) - value(b, trait)),
            );
          if (spare.length < need) {
            short = true;
            break;
          }
          for (const slot of spare.slice(0, need)) chosen[slot] = trait;
        }
        if (short) continue;

        const emblems = stats.map((stat, i) => ({
          stat,
          quality: quality[i].key,
          trait: chosen[i].key,
        }));
        const key = emblems.map((e) => `${e.stat}|${e.quality}|${e.trait}`).join(",");
        if (found.has(key)) continue;
        // Итоговое число — по настоящей формуле множителей: разложение выбирает
        // вариант, формула его считает.
        const multipliers = emblemMultipliers(emblems, rules);
        let total = 0;
        for (let i = 0; i < base.length; i++) total += base[i] * multipliers[i];
        found.set(key, { emblems, total });
      }
    }
  }

  return [...found.values()]
    .sort((a, b) => b.total - a.total)
    .slice(0, options.topN ?? 3)
    .map((option) => {
      const detailed = scoreBanner(option.emblems, byStat, rules);
      return { emblems: option.emblems, slots: detailed.slots, total: detailed.total };
    });
}
