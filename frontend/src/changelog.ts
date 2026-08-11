// История изменений страницы.
//
// Тексты записей лежат здесь на двух языках, а не в словарях i18n, и это
// осознанный размен. Записи копятся вечно и никогда не переиспользуются: через
// год их будет полсотни, и держать полсотни строк на двенадцати языках —
// работа, которую никто не будет делать, а незаполненные ключи превратятся в
// ошибку сборки. Поэтому переводится обрамление («Добавлено», «Что нового»), а
// сами записи показываются по-русски или по-английски, с английским как
// запасным вариантом для остальных языков.

export type ChangeKind = "added" | "changed" | "fixed";

export interface ChangelogItem {
  kind: ChangeKind;
  en: string;
  ru: string;
}

export interface ChangelogEntry {
  version: string;
  /** Дата в ISO — форматируется под язык читателя. */
  date: string;
  items: ChangelogItem[];
}

/** Новое сверху: список читают с начала и до первой знакомой версии. */
export const CHANGELOG: ChangelogEntry[] = [
  {
    version: "0.4.0",
    date: "2026-08-11",
    items: [
      {
        kind: "added",
        en: "Group stage analytics: expected wins against actual, strength of schedule, upsets and streaks — a 3-1 record now shows whether it was a favourite stumbling or an underdog overperforming.",
        ru: "Аналитика группового этапа: ожидаемые победы против фактических, сила календаря, апсеты и серии — теперь по записи 3-1 видно, провал это фаворита или подвиг аутсайдера.",
      },
      {
        kind: "added",
        en: "Before the tournament starts, the announced first round is broken down pair by pair with win probabilities and a toss-up marker.",
        ru: "До старта турнира объявленный первый раунд разбирается по парам: вероятности победы и пометка равных пар.",
      },
      {
        kind: "added",
        en: "This changelog, and a link to the source repository.",
        ru: "Этот список изменений и ссылка на репозиторий с исходниками.",
      },
      {
        kind: "changed",
        en: "Under the hood: forecast models are now measured by walk-forward backtesting — log loss, Brier score and calibration — so a change either improves the number or does not ship.",
        ru: "Под капотом: модели прогноза теперь измеряются бэктестом вперёд по времени — log loss, Brier и калибровка, — поэтому изменение либо улучшает число, либо не выходит.",
      },
      {
        kind: "changed",
        en: "Under the hood: match, team and player metrics moved to a single versioned feature store instead of being recomputed differently in three places.",
        ru: "Под капотом: метрики матчей, команд и игроков переехали в единую версионируемую витрину фич вместо трёх разных расчётов одного и того же.",
      },
    ],
  },
  {
    version: "0.3.0",
    date: "2026-08-10",
    items: [
      {
        kind: "added",
        en: "The Swiss bracket: the grid is drawn in full in advance and results take the places already waiting for them.",
        ru: "Сетка Swiss: рисуется целиком заранее, а результаты занимают готовые места.",
      },
      {
        kind: "added",
        en: "Roster substitutions: a newcomer is projected from the slot he took over, and the page says so instead of passing it off as his own record.",
        ru: "Замены в составе: пришедший игрок оценивается по слоту, который занял, и страница говорит об этом, а не выдаёт это за его статистику.",
      },
      {
        kind: "fixed",
        en: "Sample-size correction: a player with eight maps no longer outranks a player with a hundred on noise alone.",
        ru: "Поправка на размер выборки: игрок с восемью картами больше не обходит игрока со ста на одном лишь шуме.",
      },
    ],
  },
  {
    version: "0.2.0",
    date: "2026-08-09",
    items: [
      {
        kind: "added",
        en: "Match map with a scrubbable timeline: wards, deaths and objectives in layers you can filter, instead of a pile of markers.",
        ru: "Карта матча с лентой времени: варды, смерти и цели по слоям с фильтрами вместо каши из маркеров.",
      },
      {
        kind: "added",
        en: "Item purchases on the match page and head-to-head history between teams.",
        ru: "Покупки предметов на странице матча и история личных встреч команд.",
      },
    ],
  },
  {
    version: "0.1.0",
    date: "2026-08-08",
    items: [
      {
        kind: "added",
        en: "Twelve languages with English as the site's base, match breakdowns and profile splits for teams and players.",
        ru: "Двенадцать языков с английской базой сайта, разбор матчей и разрезы профилей команд и игроков.",
      },
      {
        kind: "added",
        en: "Hero analyzer and Coaching Title estimates from the hero pool.",
        ru: "Анализатор героев и оценка Coaching Titles по пулу героев.",
      },
    ],
  },
];

/** Текущая версия страницы — верхняя запись списка. */
export const APP_VERSION = CHANGELOG[0]?.version ?? "0.0.0";

/** Адрес репозитория: используется и ссылкой в шапке, и в разметке страницы. */
export const REPOSITORY_URL = "https://github.com/MyKa322/fantasy-analyzer-dota2";

const SEEN_KEY = "changelog.seen";

/**
 * Читал ли посетитель текущую версию.
 *
 * Сравнение по строке, а не по порядку версий: список всё равно читают сверху,
 * и любое несовпадение с последней версией означает, что показать точку стоит.
 * localStorage может быть недоступен (приватный режим, отключённые куки) — тогда
 * точка просто не появится, и это лучше, чем упавшая шапка.
 */
export function lastSeenVersion(): string | null {
  try {
    return window.localStorage.getItem(SEEN_KEY);
  } catch {
    return null;
  }
}

export function markSeen(version: string): void {
  try {
    window.localStorage.setItem(SEEN_KEY, version);
  } catch {
    // Ничего: непрочитанная точка вернётся на следующий заход, и только.
  }
}
