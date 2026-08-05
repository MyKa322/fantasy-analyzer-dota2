// Языки сайта и то, что о нём должен знать поисковик.
//
// Файл намеренно без React и без импортов: его читает не только приложение, но
// и сборка (vite.config.ts), которая из этих же строк делает <title>, описание,
// hreflang и вводный блок для краулера. Держать тексты в двух местах — верный
// способ получить страницу, где заголовок вкладки на одном языке, а описание в
// выдаче на другом.

export const LOCALES = ["ru", "en", "uk", "zh"] as const;

export type Locale = (typeof LOCALES)[number];

/** Язык по умолчанию: на нём написан оригинал, он же лежит в корне сайта. */
export const DEFAULT_LOCALE: Locale = "ru";

/** Подпись в переключателе — всегда на своём языке, а не в переводе. */
export const LOCALE_NAME: Record<Locale, string> = {
  ru: "Русский",
  en: "English",
  uk: "Українська",
  zh: "中文",
};

/** Значение атрибута lang и тега hreflang. */
export const HTML_LANG: Record<Locale, string> = {
  ru: "ru",
  en: "en",
  uk: "uk",
  zh: "zh-Hans",
};

/** Форма локали для Intl: разделитель другой, чем в HTML. */
export const INTL_LOCALE: Record<Locale, string> = {
  ru: "ru-RU",
  en: "en-US",
  uk: "uk-UA",
  zh: "zh-CN",
};

/** og:locale — у Open Graph свой формат, с подчёркиванием. */
export const OG_LOCALE: Record<Locale, string> = {
  ru: "ru_RU",
  en: "en_US",
  uk: "uk_UA",
  zh: "zh_CN",
};

/** Канонический адрес опубликованной страницы. */
export const SITE_URL = "https://myka322.github.io/fantasy-analyzer-dota2";

/** Адрес языковой версии: русская лежит в корне, остальные — в подкаталогах. */
export function localeUrl(locale: Locale, base = `${SITE_URL}/`): string {
  return locale === DEFAULT_LOCALE ? base : `${base}${locale}/`;
}

export interface SiteMeta {
  /** <title> и og:title. До 60 символов — иначе выдача обрежет. */
  title: string;
  /** meta description и og:description. 140–160 символов. */
  description: string;
  /** Заголовок вводного блока — того, что видно до загрузки приложения. */
  headline: string;
  /** Два-три предложения о том, что здесь считают. */
  intro: string;
  /** Что умеет страница — списком. */
  features: string[];
  teamsHeading: string;
  /** Подпись под списком команд. */
  teamsNote: string;
  /** Строка «загружаю» для тех, у кого приложение ещё не отрисовалось. */
  loading: string;
}

/**
 * Тексты для поисковика и для первого экрана.
 *
 * Это не дубль интерфейса: краулеру нужен связный текст про то, что за
 * страница, а интерфейс состоит из подписей к таблицам. Поэтому описание
 * написано отдельно и словами, которые люди набирают в поиске.
 */
export const SITE: Record<Locale, SiteMeta> = {
  ru: {
    title: "Compendium Analyzer — Fantasy и Predictions для The International 2026",
    description:
      "Аналитика компендиума TI15: подбор War Banner и эмблем по ролям, прогноз очков Fantasy Draft, вероятности корзин Swiss, рейтинги Glicko-2, страницы всех команд и игроков по данным OpenDota.",
    headline: "Аналитика компендиума The International 2026",
    intro:
      "Считает две вещи, на которых в компендиуме теряют больше всего очков: какие эмблемы поставить на War Banner каждой роли и как расставить предсказания группового этапа. Обе задачи решаются по реальным матчам участников из OpenDota, а не по ценам из глоссария.",
    features: [
      "Подбор эмблем War Banner для Core Duo, Mid и Support Duo — перебором всех комбинаций с учётом трейтов",
      "Свой инвентарь эмблем: кому из шестнадцати команд выпавшие роллы принесут больше всего очков",
      "Прогноз очков Fantasy Draft за период — с потолком, полом и разбросом по картам",
      "Вероятности корзин Swiss и готовая расстановка предсказаний под максимум очков",
      "Coaching Titles: сколько реально даст титул, а не сколько написано в описании",
      "Страницы команд и игроков: статистика OpenDota, пул героев, рейтинг Glicko-2 и наш анализ",
    ],
    teamsHeading: "Участники The International 2026",
    teamsNote:
      "У каждой команды есть страница с матчами, средними за карту, пулом героев и разбором по ролям.",
    loading: "Загружаю данные…",
  },
  en: {
    title: "Compendium Analyzer — TI15 Fantasy and Predictions",
    description:
      "The International 2026 compendium analytics: War Banner emblem picks per role, Fantasy Draft point projections, Swiss bracket probabilities, Glicko-2 ratings and full team and player pages built from OpenDota data.",
    headline: "The International 2026 compendium analytics",
    intro:
      "Two things decide most of the points a compendium loses: which emblems go on each role's War Banner, and how the group stage predictions are laid out. Both are computed from the attending teams' real OpenDota matches, not from the glossary price list.",
    features: [
      "War Banner emblem picks for Core Duo, Mid and Support Duo — every combination checked, traits included",
      "Your own emblem inventory: which of the sixteen teams turns your rolls into the most points",
      "Fantasy Draft point projection for the period, with ceiling, floor and per-map spread",
      "Swiss bucket probabilities and a ready prediction layout optimised for expected points",
      "Coaching Titles ranked by what they actually pay out, not by the percentage printed on them",
      "Team and player pages: OpenDota statistics, hero pool, Glicko-2 rating and our own analysis",
    ],
    teamsHeading: "The International 2026 teams",
    teamsNote:
      "Every team has a page with its matches, per-map averages, hero pool and a role-by-role breakdown.",
    loading: "Loading data…",
  },
  uk: {
    title: "Compendium Analyzer — Fantasy і Predictions для The International 2026",
    description:
      "Аналітика компендіума TI15: добір емблем War Banner за ролями, прогноз очок Fantasy Draft, імовірності кошиків Swiss, рейтинги Glicko-2 та сторінки всіх команд і гравців за даними OpenDota.",
    headline: "Аналітика компендіума The International 2026",
    intro:
      "Рахує дві речі, на яких у компендіумі втрачають найбільше очок: які емблеми поставити на War Banner кожної ролі та як розставити передбачення групового етапу. Обидві задачі розв'язуються за реальними матчами учасників з OpenDota, а не за цінами з глосарія.",
    features: [
      "Добір емблем War Banner для Core Duo, Mid і Support Duo — перебором усіх комбінацій із урахуванням трейтів",
      "Власний інвентар емблем: кому з шістнадцяти команд ваші роли принесуть найбільше очок",
      "Прогноз очок Fantasy Draft за період — зі стелею, підлогою та розкидом по картах",
      "Імовірності кошиків Swiss і готова розстановка передбачень під максимум очок",
      "Coaching Titles: скільки титул дасть насправді, а не скільки написано в описі",
      "Сторінки команд і гравців: статистика OpenDota, пул героїв, рейтинг Glicko-2 та наш аналіз",
    ],
    teamsHeading: "Учасники The International 2026",
    teamsNote:
      "У кожної команди є сторінка з матчами, середніми за карту, пулом героїв і розбором за ролями.",
    loading: "Завантажую дані…",
  },
  zh: {
    title: "Compendium Analyzer — TI15 梦幻联赛与赛果预测分析",
    description:
      "TI15 勇士令状数据分析：按位置推荐战旗纹章搭配、梦幻联赛积分预测、瑞士轮分组概率、Glicko-2 战队评分，以及基于 OpenDota 数据的战队与选手主页。",
    headline: "The International 2026 勇士令状数据分析",
    intro:
      "勇士令状里最容易丢分的有两件事：每个位置的战旗该放哪些纹章，以及小组赛的预测该怎么排。这两件事都按参赛队伍在 OpenDota 上的真实比赛来算，而不是照搬说明里的分值。",
    features: [
      "为 Core Duo、Mid 和 Support Duo 推荐战旗纹章——穷举所有组合，并计入特性之间的相互影响",
      "输入自己已有的纹章：这套纹章放在十六支队伍中的哪一对身上得分最高",
      "梦幻联赛赛段积分预测——含上限、下限和逐场波动",
      "瑞士轮各分组概率，以及按期望得分最优排好的预测方案",
      "教练称号按实际能拿到的加成排序，而不是按称号上写的百分比",
      "战队与选手主页：OpenDota 数据、英雄池、Glicko-2 评分，以及我们自己的分析",
    ],
    teamsHeading: "TI15 参赛队伍",
    teamsNote: "每支队伍都有主页：比赛列表、场均数据、英雄池和分位置的拆解。",
    loading: "正在加载数据…",
  },
};
