// Иконки в шапке: что нового и откуда взялся сайт.
//
// Обе кнопки живут рядом с переключателем языка и намеренно не занимают места в
// навигации: это не разделы, а служебные ссылки, и вкладка ради них была бы
// перебором.

import { useEffect, useRef, useState } from "react";
import {
  APP_VERSION,
  CHANGELOG,
  REPOSITORY_URL,
  lastSeenVersion,
  markSeen,
  type ChangeKind,
} from "../changelog";
import { useT } from "../i18n";

const KIND_STYLE: Record<ChangeKind, string> = {
  added: "border-emerald-800 bg-emerald-950 text-emerald-300",
  changed: "border-sky-900 bg-sky-950 text-sky-300",
  fixed: "border-amber-900 bg-amber-950 text-amber-300",
};

function SparkIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-3.5 w-3.5" fill="currentColor">
      <path d="M12 2l1.9 5.6L19.5 9l-5.6 1.9L12 16.5l-1.9-5.6L4.5 9l5.6-1.4L12 2zM18 14l.9 2.6 2.6.9-2.6.9L18 21l-.9-2.6-2.6-.9 2.6-.9L18 14zM6 15l.7 2 2 .7-2 .7L6 20.4l-.7-2-2-.7 2-.7L6 15z" />
    </svg>
  );
}

function GitHubIcon() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" className="h-4 w-4" fill="currentColor">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}

/** Кнопка «что нового» с точкой непрочитанного и выпадающим списком. */
export function ChangelogButton() {
  const { t, d, locale } = useT();
  const [open, setOpen] = useState(false);
  const [seen, setSeen] = useState<string | null>(null);
  const container = useRef<HTMLDivElement>(null);

  // Читаем отметку после монтирования: на сервере рендера нет localStorage, а
  // при статической сборке разметка считается один раз на все языки.
  useEffect(() => setSeen(lastSeenVersion()), []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    const onClick = (e: MouseEvent) => {
      if (!container.current?.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onClick);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onClick);
    };
  }, [open]);

  const unseen = seen !== APP_VERSION;

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next) {
      markSeen(APP_VERSION);
      setSeen(APP_VERSION);
    }
  };

  return (
    <div ref={container} className="relative">
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        aria-haspopup="dialog"
        title={t("changelog.open")}
        className={`relative flex items-center gap-1.5 rounded border px-2 py-1 text-[11px] transition ${
          open
            ? "border-[#c8a24a] text-[#c8a24a]"
            : "border-[#2a2e3a] text-neutral-400 hover:border-[#c8a24a] hover:text-[#c8a24a]"
        }`}
      >
        <SparkIcon />
        <span className="tabular">v{APP_VERSION}</span>
        {unseen && (
          <span
            aria-label={t("changelog.unseen")}
            className="absolute -top-1 -right-1 h-2 w-2 rounded-full bg-[#c8a24a]"
          />
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label={t("changelog.title")}
          className="absolute right-0 z-50 mt-2 max-h-[70vh] w-[min(30rem,calc(100vw-3rem))] overflow-y-auto rounded-lg border border-[#2a2e3a] bg-[#16181e] p-4 shadow-xl"
        >
          <header className="mb-3 flex items-start justify-between gap-4">
            <div>
              <h2 className="text-sm font-semibold tracking-[0.14em] text-[#c8a24a] uppercase">
                {t("changelog.title")}
              </h2>
              <p className="mt-1 text-xs text-neutral-400">{t("changelog.subtitle")}</p>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label={t("changelog.close")}
              className="shrink-0 rounded px-1.5 text-neutral-500 hover:text-neutral-200"
            >
              ✕
            </button>
          </header>

          <div className="space-y-4">
            {CHANGELOG.map((entry) => (
              <section key={entry.version}>
                <div className="mb-1.5 flex items-baseline gap-2 border-b border-[#20232c] pb-1">
                  <span className="tabular text-xs font-semibold text-neutral-200">
                    v{entry.version}
                  </span>
                  <span className="text-[11px] text-neutral-500">{d(entry.date)}</span>
                  {entry.version === APP_VERSION && (
                    <span className="ml-auto rounded border border-[#c8a24a] px-1.5 py-0.5 text-[10px] tracking-wide text-[#c8a24a] uppercase">
                      {t("changelog.current")}
                    </span>
                  )}
                </div>
                <ul className="space-y-1.5">
                  {entry.items.map((item, index) => (
                    <li key={index} className="flex gap-2 text-[11px] text-neutral-300">
                      <span
                        className={`mt-px h-fit shrink-0 rounded border px-1.5 py-0.5 text-[10px] tracking-wide uppercase ${KIND_STYLE[item.kind]}`}
                      >
                        {t(`changelog.${item.kind}` as "changelog.added")}
                      </span>
                      <span>{locale === "ru" ? item.ru : item.en}</span>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/** Ссылка на репозиторий с исходниками. */
export function RepositoryLink() {
  const { t } = useT();
  return (
    <a
      href={REPOSITORY_URL}
      target="_blank"
      rel="noreferrer noopener"
      title={t("app.github")}
      aria-label={t("app.github")}
      className="flex items-center rounded border border-[#2a2e3a] px-2 py-1 text-neutral-400 transition hover:border-[#c8a24a] hover:text-[#c8a24a]"
    >
      <GitHubIcon />
    </a>
  );
}
