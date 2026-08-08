// Личные встречи команд.
//
// Отдельный файл рядом со снапшотом: страница матча спрашивает ровно один
// вопрос — «сколько раз эти двое уже играли и чем кончалось». Тащить ради него
// двухмегабайтные профили незачем, а держать в снапшоте — платить за них теми,
// кто на страницу матча не заходит.

import { tr } from "./i18n";

export interface HeadToHeadMatch {
  id: number;
  /** Дата, YYYY-MM-DD. */
  d: string;
  /** Команда со стороны Radiant. */
  r: number;
  /** Победитель; null, если исход неизвестен. */
  w: number | null;
  dur: number;
  league?: string;
}

export interface HeadToHead {
  days: number;
  teams: Record<string, string>;
  /** Ключ — два id команд по возрастанию через двоеточие. */
  pairs: Record<string, HeadToHeadMatch[]>;
}

let cached: HeadToHead | null = null;
let pending: Promise<HeadToHead> | null = null;

declare const __BUILD_ID__: string;

export async function loadHeadToHead(): Promise<HeadToHead> {
  if (cached) return cached;
  pending ??= fetch(`${import.meta.env.BASE_URL}data/head_to_head.json?v=${__BUILD_ID__}`).then(
    async (response) => {
      if (!response.ok) {
        throw new Error(tr().t("error.headToHead", { status: response.status }));
      }
      cached = (await response.json()) as HeadToHead;
      return cached;
    },
  );
  try {
    return await pending;
  } finally {
    pending = null;
  }
}

/** Ключ пары не зависит от того, кто из команд был на Radiant. */
export function pairKey(first: number, second: number): string {
  const [low, high] = first < second ? [first, second] : [second, first];
  return `${low}:${high}`;
}

export function findPair(
  data: HeadToHead | null,
  first: number | null | undefined,
  second: number | null | undefined,
): HeadToHeadMatch[] {
  if (!data || !first || !second) return [];
  return data.pairs[pairKey(first, second)] ?? [];
}
