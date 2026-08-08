// Загрузка словаря нужного языка.
//
// Английский лежит в главном чанке: на нём написан оригинал, он же язык корня
// сайта и запасной вариант, если словарь языка не догрузился. Остальные языки
// Vite режет на отдельные чанки — дюжина словарей весит под треть мегабайта, и
// тащить их все ради одного читателя незачем.

import type { Locale } from "../site";
import { en, type Dictionary, type MessageKey } from "./en";

export { en };
export type { Dictionary, MessageKey };

type Loader = () => Promise<{ default: Dictionary }>;

/**
 * Импорты записаны литералами, а не собираются из строки: Vite ищет чанки
 * статическим анализом, и `import(`./${locale}`)` он либо не найдёт, либо
 * втянет все словари разом.
 */
const loaders: Record<Exclude<Locale, "en">, Loader> = {
  ru: () => import("./ru"),
  uk: () => import("./uk"),
  zh: () => import("./zh"),
  es: () => import("./es"),
  pt: () => import("./pt"),
  de: () => import("./de"),
  fr: () => import("./fr"),
  pl: () => import("./pl"),
  tr: () => import("./tr"),
  id: () => import("./id"),
  vi: () => import("./vi"),
};

export async function loadMessages(locale: Locale): Promise<Dictionary> {
  if (locale === "en") return en;
  try {
    return (await loaders[locale]()).default;
  } catch {
    // Чанк мог не догрузиться — на английском интерфейс останется рабочим, а
    // без словаря на странице были бы голые ключи.
    return en;
  }
}
