// Кнопка «обновить данные» в шапке — для владельца страницы.
//
// Подписи здесь по-русски и мимо словарей i18n — тем же разменом, что и записи
// в истории изменений. Панель видит один человек: держать её тексты на
// двенадцати языках значит переводить то, чего никто, кроме него, не откроет.
//
// Панель показывается, только если в этом браузере лежит токен или в адресе
// стоит `?admin`. Для читателя её нет: ни кнопки, ни разметки.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  DEPLOY_WORKFLOW,
  GitHubError,
  REFRESH_WORKFLOW,
  TOKEN_SETUP_URL,
  dispatchRefresh,
  forgetToken,
  lastRunId,
  liveSnapshotTime,
  readToken,
  runAfter,
  runById,
  saveToken,
  type Run,
} from "../admin";

/** Как часто спрашиваем GitHub о состоянии прогона. */
const POLL_MS = 4000;
/** Сколько ждём появления запущенного прогона, прежде чем счесть, что он не поехал. */
const APPEAR_TIMEOUT_MS = 90_000;
/**
 * Сколько ждём публикацию после успешного пересчёта. Её запускает последний шаг
 * пересчёта, и только когда снапшот изменился: если за это время прогон не
 * появился — значит новых матчей не нашлось, и пересобирать нечего.
 */
const DEPLOY_WAIT_MS = 60_000;

type Phase = "idle" | "starting" | "refresh" | "deploy" | "done" | "unchanged" | "failed";

function RefreshIcon({ spinning }: { spinning?: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className={`h-4 w-4 ${spinning ? "animate-spin" : ""}`}
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 12a9 9 0 1 1-2.64-6.36" />
      <path d="M21 3v6h-6" />
    </svg>
  );
}

/** «42 минуты назад» по правилам языка — формы множественного числа не наши. */
function ago(iso: string): string {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60_000);
  const rtf = new Intl.RelativeTimeFormat("ru", { numeric: "auto" });
  if (minutes < 60) return rtf.format(-minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (hours < 24) return rtf.format(-hours, "hour");
  return rtf.format(-Math.round(hours / 24), "day");
}

/** Строка шага: точка состояния, подпись и ссылка на прогон в GitHub. */
function Step({
  label,
  state,
  run,
}: {
  label: string;
  state: "waiting" | "running" | "ok" | "fail" | "skip";
  run?: Run | null;
}) {
  const dot = {
    waiting: "bg-neutral-700",
    running: "bg-[#c8a24a] animate-pulse",
    ok: "bg-emerald-500",
    fail: "bg-red-500",
    skip: "bg-neutral-700",
  }[state];
  const text = state === "waiting" || state === "skip" ? "text-neutral-500" : "text-neutral-200";

  return (
    <div className="flex items-center gap-2 text-[11px]">
      <span className={`h-2 w-2 shrink-0 rounded-full ${dot}`} />
      <span className={text}>{label}</span>
      {run && (
        <a
          href={run.html_url}
          target="_blank"
          rel="noreferrer noopener"
          className="ml-auto text-neutral-500 underline decoration-dotted hover:text-[#c8a24a]"
        >
          прогон
        </a>
      )}
    </div>
  );
}

export default function AdminPanel({ generatedAt }: { generatedAt: string | null }) {
  const [token, setToken] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [unlocked, setUnlocked] = useState(false);
  const [open, setOpen] = useState(false);

  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [refreshRun, setRefreshRun] = useState<Run | null>(null);
  const [deployRun, setDeployRun] = useState<Run | null>(null);
  const [liveAt, setLiveAt] = useState<string | null>(null);

  // Номера прогонов на момент запуска: всё, что новее, запущено нами.
  const baseline = useRef({ refresh: 0, deploy: 0 });
  const since = useRef(0);
  const container = useRef<HTMLDivElement>(null);

  // Те же прогоны рядом в ref. Опрос читает их отсюда, а не из состояния:
  // GitHub на каждый запрос отдаёт новый объект, и зависимость эффекта от него
  // пересоздавала бы интервал на каждом ответе — опрос пошёл бы сплошным
  // потоком и выел лимит запросов за считанные минуты.
  const refreshRef = useRef<Run | null>(null);
  const deployRef = useRef<Run | null>(null);

  const setRefresh = useCallback((run: Run | null) => {
    refreshRef.current = run;
    setRefreshRun(run);
  }, []);
  const setDeploy = useCallback((run: Run | null) => {
    deployRef.current = run;
    setDeployRun(run);
  }, []);

  // Токен и признак `?admin` читаются после монтирования: статическая сборка
  // считает разметку один раз, и localStorage на этом этапе ещё нет.
  useEffect(() => {
    setToken(readToken());
    setUnlocked(new URLSearchParams(window.location.search).has("admin"));
  }, []);

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

  // Что лежит на сайте прямо сейчас — может быть свежее того, что открыто во
  // вкладке: снапшот грузится один раз за загрузку страницы.
  useEffect(() => {
    if (!open) return;
    liveSnapshotTime().then(setLiveAt);
  }, [open]);

  const busy = phase === "starting" || phase === "refresh" || phase === "deploy";

  const fail = useCallback((message: string) => {
    setError(message);
    setPhase("failed");
  }, []);

  const start = async () => {
    if (!token || busy) return;
    setError(null);
    setRefresh(null);
    setDeploy(null);
    setPhase("starting");
    try {
      // Точки отсчёта снимаем до запуска, иначе наш собственный прогон попадёт
      // в «уже существовавшие» и ждать пришлось бы следующего.
      const [refresh, deploy] = await Promise.all([
        lastRunId(token, REFRESH_WORKFLOW),
        lastRunId(token, DEPLOY_WORKFLOW),
      ]);
      await dispatchRefresh(token);
      baseline.current = { refresh, deploy };
      since.current = Date.now();
      setPhase("refresh");
    } catch (e) {
      fail(e instanceof GitHubError ? e.message : "не удалось запустить обновление");
    }
  };

  // Опрос состояния. Одним эффектом на обе стадии: они идут строго друг за
  // другом, и разделять их значило бы дублировать разбор ошибок и таймауты.
  useEffect(() => {
    if (phase !== "refresh" && phase !== "deploy") return;
    if (!token) return;
    let cancelled = false;

    const tick = async () => {
      try {
        if (phase === "refresh") {
          const known = refreshRef.current;
          if (!known) {
            const run = await runAfter(token, REFRESH_WORKFLOW, baseline.current.refresh);
            if (cancelled) return;
            if (run) setRefresh(run);
            else if (Date.now() - since.current > APPEAR_TIMEOUT_MS) {
              fail("прогон не появился — посмотрите вкладку Actions в репозитории");
            }
            return;
          }
          const run = await runById(token, known.id);
          if (cancelled) return;
          setRefresh(run);
          if (run.status !== "completed") return;
          if (run.conclusion !== "success") {
            fail(`пересчёт завершился с результатом «${run.conclusion}»`);
            return;
          }
          since.current = Date.now();
          setPhase("deploy");
          return;
        }

        const known = deployRef.current;
        if (!known) {
          const run = await runAfter(token, DEPLOY_WORKFLOW, baseline.current.deploy);
          if (cancelled) return;
          if (run) setDeploy(run);
          else if (Date.now() - since.current > DEPLOY_WAIT_MS) setPhase("unchanged");
          return;
        }
        const run = await runById(token, known.id);
        if (cancelled) return;
        setDeploy(run);
        if (run.status !== "completed") return;
        if (run.conclusion === "success") setPhase("done");
        else fail(`публикация завершилась с результатом «${run.conclusion}»`);
      } catch (e) {
        if (!cancelled) fail(e instanceof GitHubError ? e.message : "GitHub не отвечает");
      }
    };

    const timer = setInterval(() => void tick(), POLL_MS);
    void tick();
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [phase, token, fail, setRefresh, setDeploy]);

  if (!token && !unlocked) return null;

  const refreshState =
    phase === "refresh"
      ? "running"
      : phase === "deploy" || phase === "done" || phase === "unchanged"
        ? "ok"
        : phase === "failed" && refreshRun?.conclusion && refreshRun.conclusion !== "success"
          ? "fail"
          : "waiting";
  const deployState =
    phase === "deploy" ? "running" : phase === "done" ? "ok" : phase === "unchanged" ? "skip" : "waiting";

  return (
    <div ref={container} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-haspopup="dialog"
        title="Обновить данные"
        className={`relative flex items-center rounded border px-2 py-1 transition ${
          open || busy
            ? "border-[#c8a24a] text-[#c8a24a]"
            : "border-[#2a2e3a] text-neutral-400 hover:border-[#c8a24a] hover:text-[#c8a24a]"
        }`}
      >
        <RefreshIcon spinning={busy} />
        {phase === "done" && !open && (
          <span className="absolute -top-1 -right-1 h-2 w-2 rounded-full bg-emerald-500" />
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Обновление данных"
          className="absolute right-0 z-50 mt-2 w-[min(24rem,calc(100vw-3rem))] rounded-lg border border-[#2a2e3a] bg-[#16181e] p-4 shadow-xl"
        >
          <header className="mb-3 flex items-start justify-between gap-4">
            <div>
              <h2 className="text-sm font-semibold tracking-[0.14em] text-[#c8a24a] uppercase">
                Обновление данных
              </h2>
              <p className="mt-1 text-xs text-neutral-400">
                Забирает свежие матчи из OpenDota, пересчитывает аналитику и публикует
                страницу. Весь круг — около двух минут.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Закрыть"
              className="shrink-0 rounded px-1.5 text-neutral-500 hover:text-neutral-200"
            >
              ✕
            </button>
          </header>

          <div className="mb-3 space-y-1 rounded border border-[#20232c] bg-[#12141a] p-2.5 text-[11px]">
            <div className="flex justify-between gap-3">
              <span className="text-neutral-500">В этой вкладке</span>
              <span className="text-neutral-200">
                {generatedAt ? ago(generatedAt) : "—"}
              </span>
            </div>
            <div className="flex justify-between gap-3">
              <span className="text-neutral-500">На сайте</span>
              <span className="text-neutral-200">{liveAt ? ago(liveAt) : "—"}</span>
            </div>
            {liveAt && generatedAt && liveAt > generatedAt && (
              <p className="pt-1 text-amber-300">
                На сайте уже свежее — перезагрузите страницу.
              </p>
            )}
          </div>

          {token ? (
            <>
              <button
                type="button"
                onClick={start}
                disabled={busy}
                className="w-full rounded bg-[#c8a24a] px-3 py-2 text-xs font-medium text-black transition hover:bg-[#e0c987] disabled:cursor-not-allowed disabled:opacity-40"
              >
                {busy ? "Обновляю…" : "Обновить сейчас"}
              </button>

              {phase !== "idle" && (
                <div className="mt-3 space-y-1.5">
                  <Step label="Пересчёт данных" state={refreshState} run={refreshRun} />
                  <Step
                    label={
                      phase === "unchanged" ? "Публикация не нужна" : "Публикация страницы"
                    }
                    state={deployState}
                    run={deployRun}
                  />
                </div>
              )}

              {phase === "unchanged" && (
                <p className="mt-3 text-[11px] text-neutral-400">
                  Новых матчей не нашлось — снапшот не изменился. У OpenDota результат
                  появляется не сразу после матча, а когда разберётся реплей.
                </p>
              )}

              {phase === "done" && (
                <button
                  type="button"
                  onClick={() => window.location.reload()}
                  className="mt-3 w-full rounded border border-emerald-800 px-3 py-2 text-xs font-medium text-emerald-300 transition hover:bg-emerald-950"
                >
                  Готово — перезагрузить страницу
                </button>
              )}

              {error && <p className="mt-3 text-[11px] text-red-400">{error}</p>}

              <button
                type="button"
                onClick={() => {
                  forgetToken();
                  setToken(null);
                  setPhase("idle");
                }}
                className="mt-3 text-[11px] text-neutral-600 hover:text-neutral-300"
              >
                Забыть токен в этом браузере
              </button>
            </>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (!draft.trim()) return;
                saveToken(draft);
                setToken(draft.trim());
                setDraft("");
              }}
            >
              <label className="block text-[11px] text-neutral-400" htmlFor="admin-token">
                Личный токен GitHub
              </label>
              <input
                id="admin-token"
                type="password"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                autoComplete="off"
                placeholder="github_pat_…"
                className="mt-1 w-full rounded border border-[#2a2e3a] bg-[#12141a] px-2 py-1.5 text-xs text-neutral-200 outline-none focus:border-[#c8a24a]"
              />
              <button
                type="submit"
                className="mt-2 w-full rounded bg-[#c8a24a] px-3 py-2 text-xs font-medium text-black transition hover:bg-[#e0c987]"
              >
                Сохранить
              </button>
              <p className="mt-2 text-[11px] leading-relaxed text-neutral-500">
                Нужен{" "}
                <a
                  href={TOKEN_SETUP_URL}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="text-neutral-300 underline decoration-dotted hover:text-[#c8a24a]"
                >
                  fine-grained токен
                </a>{" "}
                на один этот репозиторий с правом <span className="text-neutral-300">Actions:
                Read and write</span>. Он останется в этом браузере и уйдёт только на
                api.github.com.
              </p>
            </form>
          )}
        </div>
      )}
    </div>
  );
}
