// Ручное обновление данных — для владельца страницы, не для читателей.
//
// Страница статическая: свежие числа появляются только после того, как GitHub
// Actions пересчитает снапшот и пересоберёт сайт. По расписанию это раз в
// сутки, но во время турнира матч идёт каждые пятьдесят минут, и ждать ночи
// незачем — весь круг занимает около двух минут. Здесь лежит то, чем кнопка
// в шапке дёргает те же самые workflow через API GitHub.
//
// Ключ доступа — личный токен владельца. Он лежит в localStorage его браузера и
// уходит только на api.github.com. В сборку его класть нельзя ни при каких
// условиях: страница публичная, и секрет в её коде — секрет для всех.

import { REPOSITORY_URL } from "./changelog";

const [OWNER, REPO] = new URL(REPOSITORY_URL).pathname.replace(/^\//, "").split("/");

const API = "https://api.github.com";
const BRANCH = "main";

/** Пересчитывает снапшот и коммитит его; в конце сам запускает публикацию. */
export const REFRESH_WORKFLOW = "refresh-data.yml";
/** Собирает страницу из снапшота и выкладывает на Pages. */
export const DEPLOY_WORKFLOW = "deploy.yml";

const TOKEN_KEY = "admin.github.token";

/** Где завести токен и с какими правами — подсказка в панели ведёт сюда. */
export const TOKEN_SETUP_URL = "https://github.com/settings/personal-access-tokens/new";

export interface Run {
  id: number;
  /** queued | in_progress | completed */
  status: string;
  /** success | failure | cancelled | … ; до конца прогона — null */
  conclusion: string | null;
  html_url: string;
  created_at: string;
}

/** Обращение к GitHub, у которого не получилось, — с человеческой причиной. */
export class GitHubError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

// localStorage бывает недоступен (приватный режим, отключённые куки). Панель от
// этого не должна падать: без токена она просто попросит его ввести заново.
export function readToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function saveToken(token: string): void {
  try {
    window.localStorage.setItem(TOKEN_KEY, token.trim());
  } catch {
    // Ничего: токен проживёт до перезагрузки страницы в памяти панели.
  }
}

export function forgetToken(): void {
  try {
    window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Ничего.
  }
}

async function api<T>(token: string, path: string, init?: RequestInit): Promise<T | null> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
    },
  });

  if (!response.ok) {
    // На нехватку прав GitHub намеренно отвечает 404, а не 403, чтобы не
    // подтверждать существование репозитория. Для владельца это выглядит как
    // «ничего не найдено», поэтому обе ошибки объясняем одинаково.
    if (response.status === 401 || response.status === 403 || response.status === 404) {
      throw new GitHubError(
        "Токен не подошёл: нужен доступ Actions (read and write) к этому репозиторию.",
        response.status,
      );
    }
    throw new GitHubError(`GitHub ответил ${response.status}`, response.status);
  }

  // Запуск workflow отвечает 204 без тела.
  return response.status === 204 ? null : ((await response.json()) as T);
}

/**
 * Номер последнего прогона workflow — точка отсчёта для ожидания нового.
 *
 * Ждём именно по номеру, а не по времени создания: часы браузера могут
 * расходиться с серверными на минуты, а номера прогонов монотонно растут, и
 * «больше запомненного» означает «этот запущен нами» без всяких допущений.
 */
export async function lastRunId(token: string, workflow: string): Promise<number> {
  const data = await api<{ workflow_runs: Run[] }>(
    token,
    `/repos/${OWNER}/${REPO}/actions/workflows/${workflow}/runs?per_page=1`,
  );
  return data?.workflow_runs[0]?.id ?? 0;
}

/** Запустить пересчёт. Глубину истории не передаём — у workflow свой умолчание. */
export async function dispatchRefresh(token: string): Promise<void> {
  await api(token, `/repos/${OWNER}/${REPO}/actions/workflows/${REFRESH_WORKFLOW}/dispatches`, {
    method: "POST",
    body: JSON.stringify({ ref: BRANCH }),
  });
}

/** Первый прогон workflow новее запомненного номера — или null, пока его нет. */
export async function runAfter(
  token: string,
  workflow: string,
  afterId: number,
): Promise<Run | null> {
  const data = await api<{ workflow_runs: Run[] }>(
    token,
    `/repos/${OWNER}/${REPO}/actions/workflows/${workflow}/runs?per_page=5`,
  );
  const runs = (data?.workflow_runs ?? []).filter((run) => run.id > afterId);
  // Список идёт от свежего к старому, а нужен самый ранний из новых: если за
  // время ожидания успело запуститься два, наш — первый.
  return runs.length ? runs[runs.length - 1] : null;
}

export async function runById(token: string, id: number): Promise<Run> {
  const run = await api<Run>(token, `/repos/${OWNER}/${REPO}/actions/runs/${id}`);
  if (!run) throw new GitHubError("прогон не найден", 404);
  return run;
}

/**
 * Время снапшота, который прямо сейчас лежит на сайте.
 *
 * Нужно, чтобы отличить «данные обновились» от «вкладка открыта со вчера».
 * Файл весит под мегабайт, а нужно из него одно поле, и оно первое, — поэтому
 * просим первые байты. Если Pages отдаст файл целиком, разбор всё равно
 * сработает: регулярное выражение найдёт метку в начале.
 */
export async function liveSnapshotTime(): Promise<string | null> {
  try {
    const response = await fetch(`${import.meta.env.BASE_URL}data/snapshot.json?t=${Date.now()}`, {
      headers: { Range: "bytes=0-255" },
      cache: "no-store",
    });
    if (!response.ok) return null;
    const head = await response.text();
    return /"generated_at":"([^"]+)"/.exec(head)?.[1] ?? null;
  } catch {
    return null;
  }
}
