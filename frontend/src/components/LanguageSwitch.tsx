import { LOCALES, LOCALE_NAME, localePath, useT } from "../i18n";
import { HTML_LANG } from "../i18n/site";

/**
 * Переключатель языка.
 *
 * Это именно ссылки, а не кнопки с перерисовкой: у каждой языковой версии свой
 * адрес и свой HTML с заголовком и описанием на нужном языке. Кнопка, меняющая
 * тексты на месте, оставила бы поисковику одну страницу вместо четырёх, а
 * человеку — адрес, который нельзя отправить в чат.
 */
export default function LanguageSwitch() {
  const { locale, t } = useT();

  return (
    <nav aria-label={t("app.language")} className="flex gap-1">
      {LOCALES.map((code) => (
        <a
          key={code}
          href={localePath(code)}
          hrefLang={HTML_LANG[code]}
          lang={HTML_LANG[code]}
          title={LOCALE_NAME[code]}
          aria-current={code === locale ? "true" : undefined}
          className={`rounded px-2 py-1 text-[11px] tracking-wide uppercase transition ${
            code === locale
              ? "border border-[#c8a24a] text-[#c8a24a]"
              : "border border-transparent text-neutral-500 hover:text-neutral-200"
          }`}
        >
          {code === "zh" ? "中文" : code}
        </a>
      ))}
    </nav>
  );
}
