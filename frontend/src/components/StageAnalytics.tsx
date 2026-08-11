// Аналитика группового этапа: не «что произошло», а «что это значит».
//
// Главный столбец таблицы — не запись, а разрыв между фактическими победами и
// ожидаемыми. Запись 3-1 сама по себе не различает провал фаворита и подвиг
// аутсайдера; разрыв различает.
//
// До старта турнира таблица пуста по существу, и вместо нулей показывается
// разбор объявленного первого раунда — единственное, что в этот момент вообще
// можно посчитать.

import { teamCrest } from "../assets";
import { useT } from "../i18n";
import type { StageAnalytics as Analytics, StageTeamAnalytics } from "../snapshot";
import { Notice, Panel } from "./ui";

function Crest({ name }: { name: string }) {
  const src = teamCrest(name);
  return src ? (
    <img src={src} alt="" className="h-4 w-4 shrink-0 object-contain" />
  ) : (
    <span className="h-4 w-4 shrink-0 rounded-sm bg-[#2a2e3a]" />
  );
}

/** Полоса шансов в паре: ширина слева — вероятность победы левой команды. */
function OddsBar({ left }: { left: number }) {
  return (
    <div className="flex h-1.5 overflow-hidden rounded-full bg-[#2a2e3a]">
      <div className="bg-[#c8a24a]" style={{ width: `${left * 100}%` }} />
      <div className="flex-1 bg-[#4a5060]" />
    </div>
  );
}

function StatusBadge({ status }: { status: StageTeamAnalytics["status"] }) {
  const { t } = useT();
  if (status === "alive") return null;
  const styles =
    status === "advanced"
      ? "border-emerald-800 bg-emerald-950 text-emerald-300"
      : "border-red-900 bg-red-950 text-red-300";
  return (
    <span className={`rounded border px-1.5 py-0.5 text-[10px] tracking-wide uppercase ${styles}`}>
      {t(status === "advanced" ? "stageAnalytics.advanced" : "stageAnalytics.eliminated")}
    </span>
  );
}

/** Разрыв с ожиданием — единственное число здесь, у которого есть знак. */
function Performance({ value }: { value: number | null }) {
  const { n } = useT();
  if (value === null) return <span className="text-neutral-600">—</span>;
  const tone =
    value > 0.25 ? "text-emerald-400" : value < -0.25 ? "text-red-400" : "text-neutral-400";
  return (
    <span className={`tabular ${tone}`}>
      {value > 0 ? "+" : ""}
      {n(value, 2)}
    </span>
  );
}

function Streak({ value }: { value: number }) {
  if (!value) return <span className="text-neutral-600">—</span>;
  const tone = value > 0 ? "text-emerald-400" : "text-red-400";
  return (
    <span className={`tabular ${tone}`}>
      {value > 0 ? "W" : "L"}
      {Math.abs(value)}
    </span>
  );
}

export default function StageAnalyticsPanel({ analytics }: { analytics: Analytics }) {
  const { t, n } = useT();

  // До старта считать по сыгранному нечего — показываем только пары.
  if (!analytics.started) {
    return (
      <Panel
        title={t("stageAnalytics.previewTitle")}
        subtitle={t("stageAnalytics.previewSubtitle")}
      >
        {analytics.matchups.length ? (
          <div className="grid gap-2 md:grid-cols-2">
            {analytics.matchups.map((m) => {
              const p = m.left_win_probability;
              return (
                <div
                  key={`${m.left_id}-${m.right_id}`}
                  className="rounded border border-[#2a2e3a] bg-[#1a1d24] px-3 py-2"
                >
                  <div className="mb-1.5 flex items-center gap-2 text-[11px]">
                    <Crest name={m.left} />
                    <span className="truncate text-neutral-200">{m.left}</span>
                    <span className="tabular ml-auto shrink-0 text-neutral-400">
                      {p === null ? "—" : `${n(p * 100, 0)}% : ${n((1 - p) * 100, 0)}%`}
                    </span>
                  </div>
                  {p !== null && <OddsBar left={p} />}
                  <div className="mt-1.5 flex items-center gap-2 text-[11px]">
                    <Crest name={m.right} />
                    <span className="truncate text-neutral-200">{m.right}</span>
                    {m.toss_up && (
                      <span className="ml-auto shrink-0 rounded border border-[#c8a24a] px-1.5 py-0.5 text-[10px] tracking-wide text-[#c8a24a] uppercase">
                        {t("stageAnalytics.tossUp")}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <Notice>{t("stageAnalytics.noMatchups")}</Notice>
        )}
      </Panel>
    );
  }

  const leaders = [...analytics.teams]
    .filter((team) => team.performance !== null && team.wins + team.losses > 0)
    .sort((a, b) => (b.performance ?? 0) - (a.performance ?? 0));

  return (
    <div className="space-y-4">
      <Panel title={t("stageAnalytics.title")} subtitle={t("stageAnalytics.subtitle")}>
        <div className="overflow-x-auto">
          <table className="w-full text-xs whitespace-nowrap">
            <thead className="text-[11px] tracking-wide text-neutral-500 uppercase">
              <tr>
                <th className="py-1 text-left">{t("common.team")}</th>
                <th className="py-1 text-center">{t("stage.record")}</th>
                <th className="py-1 text-center">{t("stageAnalytics.mapDiff")}</th>
                <th className="py-1 text-center">{t("stageAnalytics.expected")}</th>
                <th className="py-1 text-center">{t("stageAnalytics.performance")}</th>
                <th className="py-1 text-center">{t("stageAnalytics.schedule")}</th>
                <th className="py-1 text-center">{t("stageAnalytics.streak")}</th>
                <th className="py-1 text-center">{t("stageAnalytics.upsets")}</th>
              </tr>
            </thead>
            <tbody>
              {analytics.teams.map((team) => (
                <tr key={team.team_id} className="border-t border-[#20232c]">
                  <td className="py-1">
                    <span className="flex items-center gap-2">
                      <Crest name={team.name} />
                      <span className="text-neutral-200">{team.name}</span>
                      <StatusBadge status={team.status} />
                    </span>
                  </td>
                  <td className="tabular py-1 text-center text-neutral-300">
                    {team.wins}-{team.losses}
                  </td>
                  <td className="tabular py-1 text-center text-neutral-400">
                    {team.map_diff > 0 ? "+" : ""}
                    {team.map_diff}
                  </td>
                  <td className="tabular py-1 text-center text-neutral-400">
                    {team.expected_wins === null ? "—" : n(team.expected_wins, 2)}
                  </td>
                  <td className="py-1 text-center">
                    <Performance value={team.performance} />
                  </td>
                  <td className="tabular py-1 text-center text-neutral-400">
                    {team.opponent_rating === null ? "—" : n(team.opponent_rating, 0)}
                  </td>
                  <td className="py-1 text-center">
                    <Streak value={team.streak} />
                  </td>
                  <td className="tabular py-1 text-center text-neutral-400">
                    {team.upsets_won || team.upsets_lost
                      ? `${team.upsets_won}/${team.upsets_lost}`
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-[11px] text-neutral-500">{t("stageAnalytics.note")}</p>
      </Panel>

      {leaders.length > 0 && (
        <Panel
          title={t("stageAnalytics.leadersTitle")}
          subtitle={t("stageAnalytics.leadersSubtitle")}
        >
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {leaders.slice(0, 3).map((team) => (
              <div
                key={team.team_id}
                className="rounded border border-[#2a2e3a] bg-[#1d2029] px-3 py-2"
              >
                <div className="flex items-center gap-2 text-xs">
                  <Crest name={team.name} />
                  <span className="truncate text-neutral-200">{team.name}</span>
                  <span className="ml-auto">
                    <Performance value={team.performance} />
                  </span>
                </div>
                <p className="mt-1 text-[11px] text-neutral-500">
                  {t("stageAnalytics.leaderLine", {
                    record: `${team.wins}-${team.losses}`,
                    expected: team.expected_wins === null ? "—" : n(team.expected_wins, 2),
                  })}
                </p>
              </div>
            ))}
          </div>
        </Panel>
      )}

      {analytics.rounds.length > 0 && (
        <Panel
          title={t("stageAnalytics.roundsTitle")}
          subtitle={t("stageAnalytics.roundsSubtitle")}
        >
          <table className="w-full text-xs">
            <thead className="text-[11px] tracking-wide text-neutral-500 uppercase">
              <tr>
                <th className="py-1 text-left">{t("stageAnalytics.round")}</th>
                <th className="py-1 text-center">{t("stageAnalytics.seriesCount")}</th>
                <th className="py-1 text-center">{t("stageAnalytics.maps")}</th>
                <th className="py-1 text-center">{t("stageAnalytics.upsets")}</th>
              </tr>
            </thead>
            <tbody>
              {analytics.rounds.map((round) => (
                <tr key={round.round} className="border-t border-[#20232c]">
                  <td className="py-1 text-neutral-300">
                    {t("stage.round", { n: round.round })}
                  </td>
                  <td className="tabular py-1 text-center text-neutral-400">
                    {round.decided}/{round.series}
                  </td>
                  <td className="tabular py-1 text-center text-neutral-400">{round.maps}</td>
                  <td className="tabular py-1 text-center text-neutral-400">
                    {round.decided ? `${round.upsets} (${n((round.upsets / round.decided) * 100, 0)}%)` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}
    </div>
  );
}
