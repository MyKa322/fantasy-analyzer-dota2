// Основа оценки: какие матчи идут в рейтинг.
//
// Рейтинг на остальных страницах посчитан по одной основе — всё, что сыграно за
// полгода. Это разумная умолчательная основа и не единственно возможная: «как
// выглядит поле, если считать только по самому TI» и «как выглядит без него» —
// разные вопросы, и ответ на них не выводится из одного числа.
//
// Поэтому здесь выбор отдан читателю. Турниры выключаются тумблерами, период
// задаётся датами, а рейтинг и прогноз считаются заново прямо в браузере — по
// той же математике, что на бэкенде (`engine/rating.ts`, `engine/bracket.ts`).
// Рядом с каждым числом стоит базовое: интересна не величина, а сдвиг.

import { useEffect, useMemo, useState } from "react";
import { teamCrest } from "../assets";
import {
  dayEnd,
  dayStart,
  leagueCounts,
  loadMatches,
  selectMatches,
  toIso,
  type MatchesFile,
} from "../basis";
import { simulateBracket, type BracketSlot } from "../engine/bracket";
import { computeRatings, type Rating } from "../engine/rating";
import { useT } from "../i18n";
import { loadSnapshot, type Snapshot } from "../snapshot";
import { Button, Notice, Panel } from "./ui";

/** Прогонов симуляции: столько же, сколько на бэкенде, — чтобы сдвиг в колонке
 *  был сдвигом, а не шумом двух разных симуляций. Пересчёт занимает четверть
 *  секунды, вкладка от этого не встаёт. */
const RUNS = 20000;

interface Row {
  teamId: number;
  name: string;
  rating: Rating | null;
  maps: number;
  baseRating: number | null;
  champion: number | null;
  baseChampion: number | null;
}

export default function BasisPanel() {
  const { t, n } = useT();
  const [file, setFile] = useState<MatchesFile | null>(null);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [off, setOff] = useState<Set<number>>(new Set());
  const [from, setFrom] = useState<string>("");
  const [to, setTo] = useState<string>("");

  useEffect(() => {
    Promise.all([loadMatches(), loadSnapshot()])
      .then(([matches, snap]) => {
        setFile(matches);
        setSnapshot(snap);
        setFrom(matches.since);
        setTo(toIso(Math.max(...matches.matches.map((row) => row[0]))));
      })
      .catch((e) => setError((e as Error).message));
  }, []);

  const bounds = useMemo(
    () => ({
      from: from ? dayStart(from) : null,
      to: to ? dayEnd(to) : null,
    }),
    [from, to],
  );

  const counts = useMemo(
    () => (file ? leagueCounts(file, bounds.from, bounds.to) : new Map<number, number>()),
    [file, bounds],
  );

  const leagues = useMemo(() => {
    if (!file) return [];
    return Object.entries(file.leagues)
      .map(([id, name]) => ({ id: Number(id), name, maps: counts.get(Number(id)) ?? 0 }))
      .filter((league) => league.maps > 0)
      .sort((a, b) => b.maps - a.maps);
  }, [file, counts]);

  const selected = useMemo(
    () => (file ? selectMatches(file, { ...bounds, off }) : []),
    [file, bounds, off],
  );

  const history = useMemo(
    () => computeRatings(selected, file?.period_days ?? 7),
    [selected, file],
  );

  // Прогноз по выбранной основе и он же по базовой. Второй считается здесь, а
  // не берётся из снапшота, ровно ради колонки сдвига: две симуляции с разными
  // зёрнами разошлись бы на полпроцента даже при одинаковой основе, и сдвиг
  // показывал бы шум. С общим зерном одинаковая основа даёт ровный ноль.
  const forecast = useMemo(() => {
    const playoffs = snapshot?.playoffs;
    if (!playoffs?.structure) return null;
    const quarterfinals = playoffs.structure
      .filter((slot) => slot.sources.length === 0)
      .map((slot) => {
        const match = playoffs.matches.find((m) => m.key === slot.key);
        return match?.left && match.right
          ? ([match.left.team_id, match.right.team_id] as [number, number])
          : null;
      });
    if (quarterfinals.some((pair) => pair === null)) return null;

    return (ratings: Map<number, Rating>) =>
      simulateBracket({
        structure: playoffs.structure as BracketSlot[],
        quarterfinals: quarterfinals as [number, number][],
        ratings,
        bestOf: playoffs.best_of,
        grandFinalBestOf: playoffs.grand_final_best_of,
        temperature: snapshot?.calibration?.temperature ?? 1,
        results: new Map(
          playoffs.matches
            .filter((m) => m.winner_id != null)
            .map((m) => [m.key, m.winner_id as number]),
        ),
        participants: new Map(
          playoffs.matches
            .filter((m) => m.left && m.right)
            .map((m) => [m.key, [m.left!.team_id, m.right!.team_id] as [number, number]]),
        ),
        runs: RUNS,
      });
  }, [snapshot]);

  // Симуляция по пустому рейтингу — это восемь монеток, а не прогноз.
  const odds = useMemo(
    () => (forecast && selected.length > 0 ? forecast(history.ratings) : null),
    [forecast, history, selected.length],
  );

  const base = useMemo(() => {
    if (!file || !forecast) return null;
    const ratings = computeRatings(
      selectMatches(file, { from: null, to: null, off: new Set() }),
      file.period_days,
    );
    return { ratings, odds: forecast(ratings.ratings) };
  }, [file, forecast]);

  const rows: Row[] = useMemo(() => {
    if (!snapshot) return [];
    const playoffTeams = snapshot.playoffs?.teams ?? [];
    const source = playoffTeams.length
      ? playoffTeams.map((team) => ({ team_id: team.team_id, name: team.name }))
      : snapshot.teams.map((team) => ({ team_id: team.team_id, name: team.name }));
    return source
      .map((team) => ({
        teamId: team.team_id,
        name: team.name,
        rating: history.ratings.get(team.team_id) ?? null,
        maps: history.played.get(team.team_id) ?? 0,
        baseRating: base?.ratings.ratings.get(team.team_id)?.rating ?? null,
        champion: odds?.champion.get(team.team_id) ?? null,
        baseChampion: base?.odds.champion.get(team.team_id) ?? null,
      }))
      .sort((a, b) => (b.rating?.rating ?? 0) - (a.rating?.rating ?? 0));
  }, [snapshot, history, odds, base]);

  if (error) return <Notice kind="error">{error}</Notice>;
  if (!file || !snapshot) return <Notice>{t("basis.loading")}</Notice>;

  const toggle = (id: number) =>
    setOff((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const event = new Set(file.event_leagues);
  const only = (keep: (id: number) => boolean) =>
    setOff(new Set(leagues.filter((league) => !keep(league.id)).map((league) => league.id)));
  const period = (days: number | null) => {
    const last = Math.max(...file.matches.map((row) => row[0]));
    setTo(toIso(last));
    setFrom(days == null ? file.since : toIso(last - days * 86400));
  };

  const eventStart = snapshot.stage?.starts ?? null;

  return (
    <div className="space-y-4">
      <Panel title={t("basis.title")} subtitle={t("basis.subtitle")}>
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-[11px] text-neutral-500 uppercase">
            {t("basis.from")}
            <input
              type="date"
              value={from}
              min={file.since}
              onChange={(e) => setFrom(e.target.value)}
              className="rounded border border-[#2a2e3a] bg-[#1a1d24] px-2 py-1 text-xs text-neutral-200"
            />
          </label>
          <label className="flex flex-col gap-1 text-[11px] text-neutral-500 uppercase">
            {t("basis.to")}
            <input
              type="date"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              className="rounded border border-[#2a2e3a] bg-[#1a1d24] px-2 py-1 text-xs text-neutral-200"
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <Button variant="ghost" onClick={() => period(null)}>
              {t("basis.period.all", { days: file.days })}
            </Button>
            <Button variant="ghost" onClick={() => period(90)}>
              {t("basis.period.quarter")}
            </Button>
            <Button variant="ghost" onClick={() => period(30)}>
              {t("basis.period.month")}
            </Button>
            {eventStart && (
              <Button
                variant="ghost"
                onClick={() => {
                  setFrom(eventStart);
                  setTo(toIso(Math.max(...file.matches.map((row) => row[0]))));
                }}
              >
                {t("basis.period.event")}
              </Button>
            )}
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <Button variant="ghost" onClick={() => setOff(new Set())}>
            {t("basis.selectAll")}
          </Button>
          <Button variant="ghost" onClick={() => only((id) => event.has(id))}>
            {t("basis.selectEvent")}
          </Button>
          <Button variant="ghost" onClick={() => only((id) => !event.has(id))}>
            {t("basis.selectRest")}
          </Button>
        </div>

        <div className="mt-3 grid gap-x-6 gap-y-1 sm:grid-cols-2 lg:grid-cols-3">
          {leagues.map((league) => (
            <label
              key={league.id}
              className="flex cursor-pointer items-center gap-2 py-0.5 text-xs text-neutral-300"
            >
              <input
                type="checkbox"
                checked={!off.has(league.id)}
                onChange={() => toggle(league.id)}
                className="accent-[#c8a24a]"
              />
              <span className={`flex-1 truncate ${event.has(league.id) ? "text-[#c8a24a]" : ""}`}>
                {league.name || t("basis.noLeague")}
              </span>
              <span className="tabular text-neutral-500">{n(league.maps)}</span>
            </label>
          ))}
        </div>

        <p className="mt-3 text-[11px] text-neutral-500">
          {t("basis.summary", { maps: n(selected.length), periods: n(history.periods) })}
        </p>
      </Panel>

      <Panel title={t("basis.resultTitle")} subtitle={t("basis.resultSubtitle")}>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="text-[11px] tracking-wide text-neutral-500 uppercase">
              <tr>
                <th className="py-1 text-left">{t("common.team")}</th>
                <th className="py-1 text-center">{t("common.rating")}</th>
                <th className="py-1 text-center">{t("basis.delta")}</th>
                <th className="py-1 text-center">{t("common.mapsShort")}</th>
                <th className="py-1 text-center">{t("playoff.champion")}</th>
                <th className="py-1 text-center">{t("basis.delta")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.teamId} className="border-t border-[#20232c]">
                  <td className="py-1.5">
                    <span className="flex items-center gap-2">
                      <Crest name={row.name} />
                      <span className="text-neutral-200">{row.name}</span>
                    </span>
                  </td>
                  <td className="tabular py-1.5 text-center text-neutral-200">
                    {row.rating ? (
                      <>
                        {n(row.rating.rating, 0)}
                        <span className="text-neutral-600"> ±{n(row.rating.rd, 0)}</span>
                      </>
                    ) : (
                      <span className="text-neutral-600">{t("basis.noData")}</span>
                    )}
                  </td>
                  <td className="tabular py-1.5 text-center">
                    <Delta
                      value={
                        row.rating && row.baseRating != null
                          ? row.rating.rating - row.baseRating
                          : null
                      }
                      format={(value) => n(value, 0)}
                    />
                  </td>
                  <td className="tabular py-1.5 text-center text-neutral-400">{n(row.maps)}</td>
                  <td className="tabular py-1.5 text-center text-neutral-200">
                    {row.champion == null ? "—" : `${(row.champion * 100).toFixed(1)}%`}
                  </td>
                  <td className="tabular py-1.5 text-center">
                    <Delta
                      value={
                        row.champion != null && row.baseChampion != null
                          ? (row.champion - row.baseChampion) * 100
                          : null
                      }
                      format={(value) => `${n(value, 1)}%`}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-[11px] text-neutral-500">{t("basis.note")}</p>
      </Panel>
    </div>
  );
}

function Crest({ name }: { name: string }) {
  const src = teamCrest(name);
  return src ? (
    <img src={src} alt="" className="h-4 w-4 shrink-0 object-contain" />
  ) : (
    <span className="h-4 w-4 shrink-0 rounded-sm bg-[#2a2e3a]" />
  );
}

/** Сдвиг относительно базовой основы: знак важнее величины. */
function Delta({
  value,
  format,
}: {
  value: number | null;
  format: (value: number) => string;
}) {
  if (value == null) return <span className="text-neutral-600">—</span>;
  const rounded = Number(value.toFixed(1));
  if (rounded === 0) return <span className="text-neutral-600">0</span>;
  return (
    <span className={rounded > 0 ? "text-emerald-400" : "text-red-400"}>
      {rounded > 0 ? "+" : "−"}
      {format(Math.abs(value))}
    </span>
  );
}
