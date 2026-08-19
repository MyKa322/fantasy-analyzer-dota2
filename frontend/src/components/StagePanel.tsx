// Групповой этап: сетка Swiss, раунд на вылет и личные встречи участников.
//
// Сетка рисуется целиком заранее, до единого сыгранного матча. Это не
// украшение: структура Swiss полностью задана форматом — после n раундов
// команд с k победами ровно 16·C(n,k)/2ⁿ, поэтому и число строк в каждой
// группе («1-0», «2-1», …) известно наперёд. Результаты приходят и занимают
// готовые места, а не создают их.

import { useEffect, useMemo, useState } from "react";
import { teamCrest } from "../assets";
import { loadHeadToHead, pairKey, type HeadToHead } from "../headToHead";
import { useT } from "../i18n";
import { loadSnapshot, type Stage, type StageSeries } from "../snapshot";
import StageAnalyticsPanel from "./StageAnalytics";
import { Notice, Panel } from "./ui";

/** Одна строка сетки: либо сыгранная серия, либо пустое место под неё. */
interface Slot {
  series: StageSeries | null;
}

interface RecordGroup {
  record: string;
  slots: Slot[];
}

/**
 * Сколько матчей в каждой группе каждого раунда.
 *
 * Считается разложением: каждая группа (побед, поражений) после раунда делится
 * пополам — половина выигрывает, половина проигрывает. Команды, набравшие
 * четыре победы или четыре поражения, из сетки уходят.
 */
function layout(teams: number, wins: number, losses: number, rounds: number): RecordGroup[][] {
  let buckets = new Map<string, number>([["0-0", teams]]);
  const result: RecordGroup[][] = [];

  for (let round = 0; round < rounds; round += 1) {
    const groups: RecordGroup[] = [];
    const next = new Map<string, number>();

    for (const [record, count] of buckets) {
      if (count < 2) continue;
      const [w, l] = record.split("-").map(Number);
      groups.push({ record, slots: Array.from({ length: count / 2 }, () => ({ series: null })) });

      const won = `${w + 1}-${l}`;
      const lost = `${w}-${l + 1}`;
      if (w + 1 < wins) next.set(won, (next.get(won) ?? 0) + count / 2);
      if (l + 1 < losses) next.set(lost, (next.get(lost) ?? 0) + count / 2);
    }

    if (!groups.length) break;
    result.push(groups);
    buckets = next;
  }
  return result;
}

function Crest({ name }: { name: string }) {
  const src = teamCrest(name);
  return src ? (
    <img src={src} alt="" className="h-4 w-4 shrink-0 object-contain" />
  ) : (
    <span className="h-4 w-4 shrink-0 rounded-sm bg-[#2a2e3a]" />
  );
}

/** Строка сетки. Пустая — это ещё не сыгранный матч, а не отсутствие данных. */
function SeriesRow({ series, pending }: { series: StageSeries | null; pending?: string[] }) {
  const { t } = useT();
  if (!series) {
    const [left, right] = pending ?? [];
    return (
      <div className="flex items-center gap-2 border-t border-[#20232c] px-2 py-1.5 text-[11px] text-neutral-600">
        <span className="flex flex-1 items-center gap-1.5 truncate">
          {left ? (
            <>
              <Crest name={left} />
              <span className="truncate text-neutral-400">{left}</span>
            </>
          ) : (
            t("stage.tbd")
          )}
        </span>
        <span className="tabular w-8 text-center">—</span>
        <span className="flex flex-1 items-center justify-end gap-1.5 truncate">
          {right ? (
            <>
              <span className="truncate text-neutral-400">{right}</span>
              <Crest name={right} />
            </>
          ) : (
            t("stage.tbd")
          )}
        </span>
      </div>
    );
  }

  const leftWon = series.winner_id === series.left.team_id;
  const rightWon = series.winner_id === series.right.team_id;
  const strong = "text-neutral-100";
  const faded = "text-neutral-500";

  return (
    <div className="flex items-center gap-2 border-t border-[#20232c] px-2 py-1.5 text-[11px]">
      <span className={`flex flex-1 items-center gap-1.5 truncate ${leftWon ? strong : faded}`}>
        <Crest name={series.left.name} />
        <span className="truncate">{series.left.name}</span>
      </span>
      <span className="tabular w-8 text-center text-neutral-300">
        {series.left.score}:{series.right.score}
      </span>
      <span
        className={`flex flex-1 items-center justify-end gap-1.5 truncate ${rightWon ? strong : faded}`}
      >
        <span className="truncate">{series.right.name}</span>
        <Crest name={series.right.name} />
      </span>
    </div>
  );
}

export default function StagePanel({ onOpen }: { onOpen?: (id: number) => void }) {
  const { t, n, d } = useT();
  const [stage, setStage] = useState<Stage | null>(null);
  const [h2h, setH2h] = useState<HeadToHead | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadSnapshot()
      .then((snapshot) => setStage(snapshot.stage ?? null))
      .catch((e) => setError((e as Error).message));
    loadHeadToHead().then(setH2h).catch(() => undefined);
  }, []);

  const rounds = useMemo(() => {
    if (!stage) return [];
    const grid = layout(16, stage.wins_to_advance, stage.losses_to_eliminate, 5);

    // Сыгранное раскладывается по готовым местам: раунд и запись у серии уже
    // посчитаны на бэкенде, здесь остаётся найти ей строку.
    for (const series of stage.series) {
      const groups = grid[series.round - 1];
      if (!groups) continue;
      const group =
        groups.find((g) => g.record === series.record) ??
        groups.find((g) => g.slots.some((s) => !s.series));
      const slot = group?.slots.find((s) => !s.series);
      if (slot) slot.series = series;
    }
    return grid;
  }, [stage]);

  /** Пары первого раунда объявлены заранее — показываем их до старта. */
  const firstRoundPairs = useMemo(
    () => (stage?.first_round ?? []).map((p) => [p.left, p.right] as [string, string]),
    [stage],
  );

  const elimination = useMemo(() => {
    const winners = stage?.wins_to_advance ?? 4;
    const losers = stage?.losses_to_eliminate ?? 4;
    return (stage?.standings ?? []).filter(
      (s) => s.wins === winners - 1 && s.losses === losers - 1,
    );
  }, [stage]);

  if (error) return <Notice kind="error">{error}</Notice>;
  if (!stage) return <Notice>{t("stage.loading")}</Notice>;

  const played = stage.series.length;

  return (
    <div className="space-y-4">
      <Panel
        title={t("stage.title")}
        subtitle={
          played
            ? t("stage.subtitlePlayed", { count: played })
            : t("stage.subtitleUpcoming", { date: stage.starts ? d(stage.starts) : "—" })
        }
      >
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {rounds.map((groups, index) => (
            <section key={index} className="rounded border border-[#2a2e3a] bg-[#1a1d24]">
              <header className="border-b border-[#2a2e3a] px-2 py-1.5 text-[11px] tracking-wide text-neutral-300 uppercase">
                {t("stage.round", { n: index + 1 })}
              </header>
              {groups.map((group) => (
                <div key={group.record}>
                  <div className="tabular bg-[#16181c] px-2 py-1 text-center text-[10px] text-neutral-500">
                    {group.record}
                  </div>
                  {group.slots.map((slot, slotIndex) => (
                    <SeriesRow
                      key={slotIndex}
                      series={slot.series}
                      pending={index === 0 ? firstRoundPairs[slotIndex] : undefined}
                    />
                  ))}
                </div>
              ))}
            </section>
          ))}
        </div>
      </Panel>

      {/* Аналитика идёт сразу за сеткой: сетка показывает результат, а этот
          блок — его смысл. У снапшотов, снятых до её появления, её просто нет. */}
      {stage.analytics && <StageAnalyticsPanel analytics={stage.analytics} />}

      <Panel title={t("stage.eliminationTitle")} subtitle={t("stage.eliminationSubtitle")}>
        {elimination.length ? (
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {elimination.map((team) => (
              <div
                key={team.team_id}
                className="flex items-center gap-2 rounded border border-[#2a2e3a] bg-[#1d2029] px-2 py-2 text-xs"
              >
                <Crest name={team.name} />
                <span className="truncate text-neutral-200">{team.name}</span>
                <span className="tabular ml-auto text-neutral-500">
                  {team.wins}-{team.losses}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <Notice>{t("stage.eliminationEmpty")}</Notice>
        )}
      </Panel>

      <Panel title={t("stage.standingsTitle")} subtitle={t("stage.standingsSubtitle")}>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="text-[11px] tracking-wide text-neutral-500 uppercase">
              <tr>
                <th className="py-1 text-left">{t("common.team")}</th>
                <th className="py-1 text-center">{t("stage.record")}</th>
                <th className="py-1 text-center" title={t("stage.mapRecordHint")}>
                  {t("common.mapRecord")}
                </th>
                <th className="py-1 text-left">{t("stage.headToHead")}</th>
              </tr>
            </thead>
            <tbody>
              {stage.standings.map((team) => {
                // Личные встречи именно с участниками группы: с кем из этих
                // пятнадцати команда уже играла и чем это кончалось.
                const meetings = stage.standings
                  .filter((other) => other.team_id !== team.team_id)
                  .map((other) => {
                    const games = h2h?.pairs[pairKey(team.team_id, other.team_id)] ?? [];
                    const wins = games.filter((g) => g.w === team.team_id).length;
                    return { other, games: games.length, wins };
                  })
                  .filter((row) => row.games > 0)
                  .sort((a, b) => b.games - a.games);

                return (
                  <tr key={team.team_id} className="border-t border-[#20232c]">
                    <td className="py-1">
                      <span className="flex items-center gap-2">
                        <Crest name={team.name} />
                        <span className="text-neutral-200">{team.name}</span>
                      </span>
                    </td>
                    <td className="tabular py-1 text-center text-neutral-300">
                      {team.wins}-{team.losses}
                    </td>
                    <td className="tabular py-1 text-center text-neutral-500">
                      {team.maps_won == null || team.maps_lost == null
                        ? "—"
                        : `${team.maps_won}-${team.maps_lost}`}
                    </td>
                    <td className="py-1 text-neutral-500">
                      {meetings.length ? (
                        <span className="flex flex-wrap gap-x-3 gap-y-0.5">
                          {meetings.slice(0, 6).map((row) => (
                            <span key={row.other.team_id} className="whitespace-nowrap">
                              {row.other.name}{" "}
                              <span className="tabular text-neutral-400">
                                {row.wins}:{row.games - row.wins}
                              </span>
                            </span>
                          ))}
                        </span>
                      ) : (
                        t("stage.noMeetings")
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Panel>

      {played > 0 && (
        <Panel title={t("stage.resultsTitle")} subtitle={t("stage.resultsSubtitle")}>
          <table className="w-full text-xs">
            <tbody>
              {stage.series.map((series) => (
                <tr key={series.match_ids[0]} className="border-t border-[#20232c]">
                  <td className="py-1 text-neutral-500">
                    {t("stage.round", { n: series.round })}
                  </td>
                  <td className="py-1 text-neutral-300">
                    {series.left.name} {series.left.score}:{series.right.score}{" "}
                    {series.right.name}
                  </td>
                  <td className="py-1 text-right">
                    {series.match_ids.map((id) => (
                      <button
                        key={id}
                        onClick={() => onOpen?.(id)}
                        className="ml-2 text-[11px] text-[#c8a24a] hover:underline"
                      >
                        {t("stage.openMap")}
                      </button>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}

      <p className="text-[11px] text-neutral-500">
        {t("stage.note", { maps: n(stage.series.reduce((sum, s) => sum + s.match_ids.length, 0)) })}
      </p>
    </div>
  );
}
