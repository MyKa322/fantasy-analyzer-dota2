// Языковые версии страницы, мета-теги и sitemap — на этапе сборки.
//
// Приложение рисуется в браузере, а поисковику нужен готовый HTML: заголовок,
// описание и связный текст про то, что здесь считают. Поэтому сборка кладёт
// рядом с бандлом четыре страницы — по одной на язык, — и в каждой уже стоят
// свой <title>, своё описание, canonical и hreflang на соседние версии.
//
// Тексты берутся из того же файла, что читает интерфейс (src/i18n/site.ts):
// иначе заголовок вкладки и описание в выдаче однажды разъедутся.

import { readFileSync, mkdirSync, writeFileSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import type { Plugin } from "vite";
import {
  DEFAULT_LOCALE,
  HTML_LANG,
  LOCALES,
  LOCALE_NAME,
  OG_LOCALE,
  SITE,
  SITE_URL,
  localeUrl,
  type Locale,
} from "../src/i18n/site";

/** Картинка превью на каждый язык: собирается backend/tools/build_og_image.py. */
const OG_IMAGE: Record<Locale, string> = {
  en: "og-en.png",
  ru: "og.png",
  uk: "og-uk.png",
  zh: "og-zh.png",
  es: "og-es.png",
  pt: "og-pt.png",
  de: "og-de.png",
  fr: "og-fr.png",
  pl: "og-pl.png",
  tr: "og-tr.png",
  id: "og-id.png",
  vi: "og-vi.png",
};

const HEAD_MARK = ["<!--seo-head-->", "<!--/seo-head-->"] as const;
const BODY_MARK = ["<!--seo-intro-->", "<!--/seo-intro-->"] as const;

function escape(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

interface Snapshot {
  generated_at?: string;
  teams?: { name: string }[];
}

function readSnapshot(root: string): Snapshot {
  const path = resolve(root, "public/data/snapshot.json");
  if (!existsSync(path)) return {};
  try {
    return JSON.parse(readFileSync(path, "utf8")) as Snapshot;
  } catch {
    // Снапшота может не быть при первой сборке — страница соберётся без
    // списка команд, а не упадёт.
    return {};
  }
}

/** Мета-теги языковой версии: описание, canonical, hreflang, карточки соцсетей. */
export function head(locale: Locale, updated: string): string {
  const meta = SITE[locale];
  const url = localeUrl(locale);
  const image = `${SITE_URL}/${OG_IMAGE[locale]}`;

  const alternates = LOCALES.map(
    (code) =>
      `<link rel="alternate" hreflang="${HTML_LANG[code]}" href="${localeUrl(code)}" />`,
  ).join("\n    ");

  // Структурированные данные: WebApplication — про то, что это инструмент, а
  // не статья, и по нему выдача показывает страницу как приложение.
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "WebApplication",
    name: "Compendium Analyzer",
    alternateName: meta.title,
    url,
    inLanguage: HTML_LANG[locale],
    applicationCategory: "GameApplication",
    operatingSystem: "Any",
    browserRequirements: "Requires JavaScript",
    description: meta.description,
    image,
    isAccessibleForFree: true,
    offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
    about: { "@type": "VideoGame", name: "Dota 2" },
    dateModified: updated,
  };

  return [
    `<meta name="description" content="${escape(meta.description)}" />`,
    `<meta name="robots" content="index, follow, max-image-preview:large" />`,
    `<link rel="canonical" href="${url}" />`,
    alternates,
    `<link rel="alternate" hreflang="x-default" href="${localeUrl(DEFAULT_LOCALE)}" />`,
    `<meta property="og:type" content="website" />`,
    `<meta property="og:site_name" content="Compendium Analyzer" />`,
    `<meta property="og:title" content="${escape(meta.title)}" />`,
    `<meta property="og:description" content="${escape(meta.description)}" />`,
    `<meta property="og:url" content="${url}" />`,
    `<meta property="og:image" content="${image}" />`,
    `<meta property="og:image:width" content="1200" />`,
    `<meta property="og:image:height" content="630" />`,
    `<meta property="og:locale" content="${OG_LOCALE[locale]}" />`,
    ...LOCALES.filter((code) => code !== locale).map(
      (code) => `<meta property="og:locale:alternate" content="${OG_LOCALE[code]}" />`,
    ),
    `<meta name="twitter:card" content="summary_large_image" />`,
    `<meta name="twitter:title" content="${escape(meta.title)}" />`,
    `<meta name="twitter:description" content="${escape(meta.description)}" />`,
    `<meta name="twitter:image" content="${image}" />`,
    `<meta name="theme-color" content="#14161c" />`,
    `<script type="application/ld+json">${JSON.stringify(jsonLd)}</script>`,
  ].join("\n    ");
}

/**
 * Вводный блок внутри #root.
 *
 * Он же экран загрузки: манифесты портретов и иконок грузятся до первого
 * рендера, и раньше на их месте была пустая страница. Теперь там текст о том,
 * что за инструмент, — его видит и человек с медленной сетью, и краулер,
 * который не станет ждать выполнения скриптов.
 */
export function intro(locale: Locale, teams: string[]): string {
  const meta = SITE[locale];
  const items = meta.features.map((line) => `<li>${escape(line)}</li>`).join("");
  const languages = LOCALES.map(
    (code) =>
      `<a href="${localeUrl(code)}" hreflang="${HTML_LANG[code]}" lang="${HTML_LANG[code]}"` +
      `${code === locale ? ' aria-current="true"' : ""}>${LOCALE_NAME[code]}</a>`,
  ).join(" · ");

  return `<div class="intro">
      <p class="brand">COMPENDIUM ANALYZER</p>
      <h1>${escape(meta.headline)}</h1>
      <p class="lead">${escape(meta.intro)}</p>
      <ul>${items}</ul>
      ${teams.length ? `<h2>${escape(meta.teamsHeading)}</h2><p class="teams">${teams.map(escape).join(" · ")}</p><p class="note">${escape(meta.teamsNote)}</p>` : ""}
      <p class="languages">${languages}</p>
      <p class="note">${escape(meta.loading)}</p>
    </div>`;
}

function replace(html: string, marks: readonly [string, string], content: string): string {
  const start = html.indexOf(marks[0]);
  const end = html.indexOf(marks[1]);
  if (start < 0 || end < 0) {
    throw new Error(`в index.html нет меток ${marks[0]} … ${marks[1]}`);
  }
  return html.slice(0, start + marks[0].length) + content + html.slice(end);
}

export function page(html: string, locale: Locale, teams: string[], updated: string): string {
  const withHead = replace(html, HEAD_MARK, `\n    ${head(locale, updated)}\n    `);
  const withBody = replace(withHead, BODY_MARK, `\n    ${intro(locale, teams)}\n    `);
  return withBody
    .replace(/<html lang="[^"]*"/, `<html lang="${HTML_LANG[locale]}"`)
    .replace(/<title>[^<]*<\/title>/, `<title>${escape(SITE[locale].title)}</title>`);
}

export function sitemap(updated: string): string {
  const entries = LOCALES.map((locale) => {
    const alternates = LOCALES.map(
      (code) =>
        `    <xhtml:link rel="alternate" hreflang="${HTML_LANG[code]}" href="${localeUrl(code)}" />`,
    ).join("\n");
    return `  <url>
    <loc>${localeUrl(locale)}</loc>
    <lastmod>${updated.slice(0, 10)}</lastmod>
${alternates}
    <xhtml:link rel="alternate" hreflang="x-default" href="${localeUrl(DEFAULT_LOCALE)}" />
  </url>`;
  }).join("\n");

  return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">
${entries}
</urlset>
`;
}

export function robots(): string {
  // Каталог с данными закрывать не нужно и вредно: снапшот — это содержимое
  // страницы, а не служебный файл.
  return `User-agent: *
Allow: /

Sitemap: ${SITE_URL}/sitemap.xml
`;
}

export function seoPlugin(): Plugin {
  let root = process.cwd();
  let outDir = "dist";

  return {
    name: "compendium-seo",
    apply: "build",

    configResolved(config) {
      root = config.root;
      outDir = config.build.outDir;
    },

    closeBundle() {
      const dist = resolve(root, outDir);
      const indexPath = resolve(dist, "index.html");
      if (!existsSync(indexPath)) return;

      const snapshot = readSnapshot(root);
      const teams = (snapshot.teams ?? []).map((team) => team.name);
      const updated = snapshot.generated_at ?? new Date().toISOString();
      const html = readFileSync(indexPath, "utf8");

      for (const locale of LOCALES) {
        const target =
          locale === DEFAULT_LOCALE
            ? indexPath
            : resolve(dist, locale, "index.html");
        mkdirSync(dirname(target), { recursive: true });
        writeFileSync(target, page(html, locale, teams, updated), "utf8");
      }

      writeFileSync(resolve(dist, "sitemap.xml"), sitemap(updated), "utf8");
      writeFileSync(resolve(dist, "robots.txt"), robots(), "utf8");
      this.info?.(`языковых версий: ${LOCALES.length}, команд в описании: ${teams.length}`);
    },
  };
}
