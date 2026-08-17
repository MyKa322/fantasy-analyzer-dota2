// Период Fantasy — один выбор на всю страницу.
//
// Компендиум считает Fantasy по этапам: у группового этапа свой состав, у
// основного свой, и закрепляются они в разные дни. Разница не в подписи: в
// группе команда играет 4-6 серий подряд, а в плей-офф — от двух до шести, и
// сколько именно, зависит от того, как далеко она пройдёт по сетке. В зачёт
// идёт лучшая серия периода, поэтому число попыток решает больше, чем кажется.
//
// Выбор общий, а не по панели: подбор состава, анализатор эмблем и разбор
// инвентаря отвечают на один и тот же вопрос про один и тот же период. Разойтись
// им нельзя — иначе на одной вкладке состав собран под плей-офф, а на соседней
// оценён по группе.

import { useEffect, useState, useSyncExternalStore } from "react";
import { loadSnapshot, type FantasyStage, type RoleSnapshot } from "./snapshot";

export const GROUP_STAGE = "group";
export const MAIN_STAGE = "main";

const STORAGE_KEY = "fantasy.stage";

function stored(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    // Приватный режим: выбор просто не переживёт перезагрузку.
    return null;
  }
}

let selected: string | null = stored();
const listeners = new Set<() => void>();

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function setStage(key: string): void {
  selected = key;
  try {
    window.localStorage.setItem(STORAGE_KEY, key);
  } catch {
    // см. stored()
  }
  listeners.forEach((listener) => listener());
}

/** Этапы из снапшота — грузятся один раз на страницу. */
let cached: Promise<FantasyStage[]> | null = null;

function loadStages(): Promise<FantasyStage[]> {
  cached ??= loadSnapshot()
    .then((snapshot) => snapshot.stages ?? [])
    .catch(() => []);
  return cached;
}

/** Сколько дней осталось до закрепления состава. null — уже закреплён. */
export function locksIn(stage: FantasyStage | undefined, now = new Date()): number | null {
  if (!stage?.locks) return null;
  const locks = new Date(`${stage.locks.slice(0, 10)}T12:00:00`);
  const days = Math.ceil((locks.getTime() - now.getTime()) / 86_400_000);
  return days > 0 ? days : null;
}

/**
 * Период, которому принадлежит дата: последний из начавшихся к этому дню.
 *
 * Нужен там, где вопрос не «что я выбрал», а «по каким правилам считалась эта
 * карта»: баннер основного этапа на две эмблемы длиннее группового, и карта
 * плей-офф стоит других очков, чем карта той же команды в группе.
 */
export function stageForDate(
  stages: FantasyStage[],
  date: string | null | undefined,
): string | undefined {
  if (!date) return undefined;
  const day = date.slice(0, 10);
  const started = stages.filter((stage) => stage.starts && stage.starts.slice(0, 10) <= day);
  return started[started.length - 1]?.key;
}

/**
 * Этап по умолчанию — ближайший, состав которого ещё не закреплён.
 *
 * Именно он и нужен: закрепить состав прошлого этапа нельзя, а смотреть на его
 * прогноз незачем — там уже не прогноз, а результат.
 */
function defaultStage(stages: FantasyStage[], now = new Date()): string {
  const open = stages.find((stage) => locksIn(stage, now) !== null);
  return open?.key ?? stages[stages.length - 1]?.key ?? GROUP_STAGE;
}

export interface StageState {
  stages: FantasyStage[];
  /** Выбранный этап. Пока снапшот не загружен — групповой. */
  stage: string;
  current: FantasyStage | undefined;
  setStage: (key: string) => void;
}

export function useFantasyStage(): StageState {
  const [stages, setStages] = useState<FantasyStage[]>([]);
  const choice = useSyncExternalStore(
    subscribe,
    () => selected,
    () => null,
  );

  useEffect(() => {
    let alive = true;
    loadStages().then((loaded) => {
      if (alive) setStages(loaded);
    });
    return () => {
      alive = false;
    };
  }, []);

  const known = stages.some((stage) => stage.key === choice);
  const stage = known && choice ? choice : defaultStage(stages);

  return {
    stages,
    stage,
    current: stages.find((entry) => entry.key === stage),
    setStage,
  };
}

/**
 * Коэффициенты периода для роли: во сколько раз счёт за период больше счёта за
 * карту. Для группы это выбранное число серий, для основного этапа —
 * распределение по сетке, посчитанное при экспорте.
 *
 * `null` означает, что в этом периоде роль не наберёт ничего: команды нет в
 * плей-офф. Это ответ, а не отсутствие данных, и панели показывают его как есть.
 */
export function periodRatios(
  role: RoleSnapshot,
  stage: string,
  series: number,
): { period: number; ceiling: number } | null {
  if (stage === MAIN_STAGE) {
    const period = role.period_ratios?.[MAIN_STAGE];
    const ceiling = role.ceiling_ratios?.[MAIN_STAGE];
    return period == null || ceiling == null ? null : { period, ceiling };
  }
  return {
    period: role.period_ratios?.[String(series)] ?? role.period_ratio,
    ceiling: role.ceiling_ratios?.[String(series)] ?? role.ceiling_ratio,
  };
}
