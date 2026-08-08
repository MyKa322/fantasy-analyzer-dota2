// Язык интерфейса.
//
// Локаль определяется адресом страницы, а не настройкой в браузере: русская
// версия лежит в корне, остальные — в /en/, /uk/, /zh/. Так у каждого языка
// есть собственный адрес, который можно дать ссылкой и который видит поисковик;
// переключатель просто уходит на соседний адрес.

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  type ReactNode,
} from "react";
import { en, loadMessages, type Dictionary, type MessageKey } from "./messages";
import {
  DEFAULT_LOCALE,
  INTL_LOCALE,
  LOCALES,
  SITE,
  type Locale,
} from "./site";

export { LOCALES, LOCALE_NAME, DEFAULT_LOCALE, type Locale } from "./site";
export { loadMessages } from "./messages";
export type { Dictionary, MessageKey } from "./messages";

type Params = Record<string, string | number>;

/**
 * Наборы форм множественного числа.
 *
 * Перечислены явно, а не выведены из словаря: у каждого набора обязаны быть все
 * четыре формы (one/few/many/other), и опечатка в базе ключа иначе молча
 * превратилась бы в «{n}» на странице.
 */
export type PluralKey =
  | "plural.maps"
  | "plural.options"
  | "plural.tournaments"
  | "plural.winStreak"
  | "plural.lossStreak";

/** Подстановка `{name}` — единственный формат, который нужен подписям. */
function fill(template: string, params?: Params): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in params ? String(params[name]) : match,
  );
}

/** Локаль из адреса: `/fantasy-analyzer-dota2/en/` -> `en`. */
export function localeFromPath(pathname: string, base: string): Locale {
  const rest = pathname.startsWith(base)
    ? pathname.slice(base.length)
    : pathname.replace(/^\//, "");
  const segment = rest.split("/")[0];
  return (LOCALES as readonly string[]).includes(segment)
    ? (segment as Locale)
    : DEFAULT_LOCALE;
}

/** Адрес языковой версии внутри текущей сборки. */
export function localePath(locale: Locale): string {
  const base = import.meta.env.BASE_URL;
  return locale === DEFAULT_LOCALE ? base : `${base}${locale}/`;
}

export interface Translator {
  locale: Locale;
  /** Подпись по ключу словаря. */
  t: (key: MessageKey, params?: Params) => string;
  /**
   * Подпись по ключу, собранному из данных (`title.${key}.condition`).
   * Запасной вариант обязателен: в снапшоте может появиться титул, которого в
   * словаре ещё нет, и показать его по-русски честнее, чем показать ключ.
   */
  tryT: (key: string, fallback: string, params?: Params) => string;
  /** Форма множественного числа по правилам языка. */
  tp: (base: PluralKey, count: number) => string;
  /** Название роли по её ключу в данных: `core` -> «Core Duo». */
  role: (role: string) => string;
  /** Название стата по ключу из базы: `camps_stacked` -> «Стаки». */
  stat: (stat: string) => string;
  /** Подпись с разметкой внутри: `{name}` заменяется на переданный узел. */
  tx: (key: MessageKey, nodes: Record<string, ReactNode>) => ReactNode[];
  /** Число в записи языка: разделитель разрядов у ru и en разный. */
  n: (value: number, digits?: number) => string;
  /**
   * Число с точностью по величине: тысячи — целыми, единицы — с двумя знаками.
   * Нужно там, где в одной таблице стоят и нетворс, и 0.3 Рошана за карту.
   */
  nc: (value: number) => string;
  /** Дата и время — для метки свежести данных. */
  dt: (value: string) => string;
}

const I18nContext = createContext<Translator | null>(null);

export function createTranslator(locale: Locale, dictionary: Dictionary = en): Translator {
  const intl = INTL_LOCALE[locale];
  const plurals = new Intl.PluralRules(intl);
  const words = dictionary as Record<string, string | undefined>;
  const fallback = en as Record<string, string | undefined>;

  const lookup = (key: string): string | null => {
    // Пустая строка в переводе — это не «нет перевода», а сознательный пропуск,
    // поэтому проверяется именно отсутствие ключа. Ключи, собранные из данных
    // (`title.crimson.condition`), в словаре могут и не значиться.
    return words[key] ?? fallback[key] ?? null;
  };

  const t = (key: MessageKey, params?: Params) =>
    fill(lookup(key) ?? key, params);

  return {
    locale,
    t,
    tryT: (key, fallback, params) => fill(lookup(key) ?? fallback, params),
    tp: (base: PluralKey, count: number) => {
      const form = lookup(`${base}.${plurals.select(count)}`) ?? lookup(`${base}.other`);
      return fill(form ?? "{n}", { n: count.toLocaleString(intl) });
    },
    role: (role) => lookup(`role.${role}`) ?? role,
    stat: (stat) => lookup(`stat.${stat}`) ?? stat,
    tx: (key, nodes) => {
      const template = lookup(key) ?? key;
      // Шаблон режется по плейсхолдерам, а не собирается конкатенацией: узлы
      // React нельзя вставить в строку, а порядок слов в языках разный.
      return template.split(/(\{\w+\})/).map((part, index) => {
        const name = part.match(/^\{(\w+)\}$/)?.[1];
        if (name && name in nodes) return <span key={index}>{nodes[name]}</span>;
        return part;
      });
    },
    n: (value, digits = 0) =>
      value.toLocaleString(intl, { maximumFractionDigits: digits }),
    nc: (value) => {
      const size = Math.abs(value);
      const digits = size >= 1000 ? 0 : size >= 10 ? 1 : 2;
      return value.toLocaleString(intl, {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      });
    },
    dt: (value) =>
      new Date(value).toLocaleString(intl, {
        dateStyle: "medium",
        timeStyle: "short",
      }),
  };
}

export function I18nProvider({
  locale,
  messages,
  children,
}: {
  locale: Locale;
  /** Словарь уже загружен: до первого рендера, вместе с манифестами картинок. */
  messages: Dictionary;
  children: ReactNode;
}) {
  const translator = useMemo(
    () => createTranslator(locale, messages),
    [locale, messages],
  );

  useEffect(() => {
    // Заголовок и lang уже стоят в HTML языковой версии, но в разработке
    // страница одна на все языки — без этого экранный диктор читал бы
    // английский текст с русскими правилами чтения.
    document.documentElement.lang = locale === "zh" ? "zh-Hans" : locale;
    document.title = SITE[locale].title;
  }, [locale]);

  return <I18nContext.Provider value={translator}>{children}</I18nContext.Provider>;
}

export function useT(): Translator {
  const translator = useContext(I18nContext);
  if (!translator) throw new Error("useT вызван вне I18nProvider");
  return translator;
}

/**
 * Переводчик вне React — для модулей загрузки данных, которые формируют
 * сообщения об ошибках до того, как что-то отрисовано.
 */
let ambient: Translator = createTranslator(DEFAULT_LOCALE, en);

export function setAmbient(locale: Locale, messages: Dictionary): void {
  ambient = createTranslator(locale, messages);
}

/** Словарь языка страницы — грузится один раз до первого рендера. */
export async function initLocale(locale: Locale): Promise<Dictionary> {
  const messages = await loadMessages(locale);
  setAmbient(locale, messages);
  return messages;
}

export function tr(): Translator {
  return ambient;
}
