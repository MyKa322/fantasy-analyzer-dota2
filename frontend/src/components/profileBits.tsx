// Общие куски страниц команды и игрока: таблица матчей, сетка средних,
// подписи статов. Вынесены отдельно, потому что обе страницы показывают одни и
// те же величины — просто про разные сущности.

import type { ProfileMatch } from "../api";
import { useT } from "../i18n";

export function StatGrid({
  values,
  hidden = [],
}: {
  values: Record<string, number>;
  hidden?: string[];
}) {
  const { locale, stat, nc } = useT();

  // Порядок — по переведённой подписи: ключи в данных английские, а читает
  // человек подпись на своём языке, и без сортировки таблица выглядит
  // перемешанной. Сравнение тоже по локали — в кириллице и латинице разный
  // алфавитный порядок.
  const rows = Object.entries(values)
    .filter(([key, value]) => !hidden.includes(key) && value !== 0)
    .sort(([a], [b]) => stat(a).localeCompare(stat(b), locale));
  if (!rows.length) return null;

  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-3">
      {rows.map(([key, value]) => (
        <div
          key={key}
          className="flex items-baseline justify-between border-b border-[#20232c] py-1 text-xs"
        >
          <span className="text-neutral-500">{stat(key)}</span>
          <span className="tabular text-neutral-200">{nc(value)}</span>
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
  const { t } = useT();

  if (!matches.length) {
    return <p className="text-xs text-neutral-500">{t("match.empty")}</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] text-xs">
        <thead className="text-[11px] tracking-wide text-neutral-500 uppercase">
          <tr>
            <th className="py-1 text-left">{t("match.date")}</th>
            <th className="py-1 text-left">{t("match.opponent")}</th>
            {showHero && <th className="py-1 text-left">{t("match.hero")}</th>}
            <th className="py-1 text-center">{t("match.result")}</th>
            <th className="py-1 text-right">{t("common.kda")}</th>
            <th className="py-1 text-right">GPM</th>
            <th className="py-1 text-right">{t("match.length")}</th>
          </tr>
        </thead>
        <tbody>
          {matches.map((match) => (
            <tr key={match.id} className="border-t border-[#20232c]">
              <td className="py-1 whitespace-nowrap">
                {/* Ссылка, а не кнопка: разбором карты делятся, и адрес должен
                    открываться у соседа тем же матчем. */}
                <a
                  href={`#/match/${match.id}`}
                  className="text-neutral-400 hover:text-[#c8a24a]"
                  title={t("match.openAnalysis")}
                >
                  {match.d}
                </a>
              </td>
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
                    title={t("match.unparsedHint")}
                  >
                    {t("match.unparsed")}
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
                {t("common.minutes", { n: Math.round(match.dur / 60) })}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
