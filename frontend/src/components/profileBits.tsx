// Общие куски страниц команды и игрока: таблица матчей, сетка средних,
// подписи статов. Вынесены отдельно, потому что обе страницы показывают одни и
// те же величины — просто про разные сущности.

import type { ProfileMatch } from "../api";
import { formatDuration } from "../profiles";

/** Человеческие названия полей обычной статистики. */
export const AVERAGE_LABEL: Record<string, string> = {
  assists: "Ассисты",
  xpm: "XPM",
  net_worth: "Нетворт",
  hero_damage: "Урон по героям",
  tower_damage: "Урон по строениям",
  hero_healing: "Лечение",
  last_hits: "Добивания",
  denies: "Денаи",
  obs_placed: "Обзорные варды",
  sen_placed: "Сентри",
  level: "Уровень",
  gold_spent: "Потрачено золота",
};

/** Fantasy-статы в единицах: те же названия, что в глоссарии компендиума. */
export const UNIT_LABEL: Record<string, string> = {
  kills: "Килы",
  deaths: "Смерти",
  creep_score: "Крипы (CS)",
  gpm: "GPM",
  tower_kills: "Вышки",
  wards_placed: "Варды",
  camps_stacked: "Стаки",
  runes_grabbed: "Руны",
  smokes_used: "Смоки",
  lotuses_grabbed: "Лотосы",
  roshan_kills: "Рошаны",
  teamfight_participation: "Участие в файтах",
  stuns: "Станы, сек",
  tormentor_kills: "Торменторы",
  first_blood: "Первая кровь",
  courier_kills: "Курьеры",
  madstone_collected: "Мадстоуны",
  watchers_taken: "Наблюдатели",
};

export function formatNumber(value: number): string {
  if (Math.abs(value) >= 1000) return Math.round(value).toLocaleString("ru");
  if (Math.abs(value) >= 10) return value.toFixed(1);
  return value.toFixed(2);
}

export function StatGrid({
  values,
  labels,
  hidden = [],
}: {
  values: Record<string, number>;
  labels: Record<string, string>;
  hidden?: string[];
}) {
  // Порядок — по названию: ключи в данных английские, а читает человек русские
  // подписи, и без сортировки таблица выглядит перемешанной.
  const rows = Object.entries(values)
    .filter(([key, value]) => !hidden.includes(key) && value !== 0)
    .sort(([a], [b]) => (labels[a] ?? a).localeCompare(labels[b] ?? b, "ru"));
  if (!rows.length) return null;

  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-3">
      {rows.map(([key, value]) => (
        <div
          key={key}
          className="flex items-baseline justify-between border-b border-[#20232c] py-1 text-xs"
        >
          <span className="text-neutral-500">{labels[key] ?? key}</span>
          <span className="tabular text-neutral-200">{formatNumber(value)}</span>
        </div>
      ))}
    </div>
  );
}

export function MatchTable({
  matches,
  showHero = false,
  onOpenTeam,
}: {
  matches: ProfileMatch[];
  showHero?: boolean;
  onOpenTeam?: (teamId: number) => void;
}) {
  if (!matches.length) {
    return <p className="text-xs text-neutral-500">Матчей за период нет.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] text-xs">
        <thead className="text-[11px] tracking-wide text-neutral-500 uppercase">
          <tr>
            <th className="py-1 text-left">Дата</th>
            <th className="py-1 text-left">Соперник</th>
            {showHero && <th className="py-1 text-left">Герой</th>}
            <th className="py-1 text-center">Итог</th>
            <th className="py-1 text-right">К/С/А</th>
            <th className="py-1 text-right">GPM</th>
            <th className="py-1 text-right">Длина</th>
          </tr>
        </thead>
        <tbody>
          {matches.map((match) => (
            <tr key={match.id} className="border-t border-[#20232c]">
              <td className="py-1 whitespace-nowrap text-neutral-400">{match.d}</td>
              <td className="py-1 text-neutral-300">
                {match.opp_id && onOpenTeam ? (
                  <button
                    onClick={() => onOpenTeam(match.opp_id!)}
                    className="hover:text-[#c8a24a]"
                  >
                    {match.opp ?? match.opp_id}
                  </button>
                ) : (
                  (match.opp ?? "—")
                )}
                {!match.parsed && (
                  <span
                    className="ml-1 text-[10px] text-neutral-600"
                    title="Реплей не разобран: вардов, станов и участия в файтах в нём нет"
                  >
                    без реплея
                  </span>
                )}
              </td>
              {showHero && (
                <td className="py-1 text-neutral-400">{match.hero ?? "—"}</td>
              )}
              <td className="py-1 text-center">
                {match.won == null ? (
                  <span className="text-neutral-600">—</span>
                ) : match.won ? (
                  <span className="text-emerald-400">W</span>
                ) : (
                  <span className="text-red-400">L</span>
                )}
              </td>
              <td className="tabular py-1 text-right text-neutral-300">
                {match.k != null
                  ? `${match.k}/${match.d_ ?? 0}/${match.a ?? 0}`
                  : "—"}
              </td>
              <td className="tabular py-1 text-right text-neutral-400">
                {match.gpm != null ? Math.round(match.gpm) : "—"}
              </td>
              <td className="tabular py-1 text-right text-neutral-500">
                {formatDuration(match.dur)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
