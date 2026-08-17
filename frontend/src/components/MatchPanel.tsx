// Страница матча: таблица как в любом статистическом сервисе плюс то, чего в
// них нет — очки компендиума за эту карту и разбор сработавших титулов.
//
// Данные берутся прямо из OpenDota по id матча, поэтому открывается любая игра,
// а не только те шестнадцать команд, что посчитаны в снапшоте. Правила начисления
// очков и справочник героев приходят из снапшота — они одни и те же для всех карт.

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { GROUP_COLOR, heroIcon, itemIcon, loadItemManifest } from "../assets";
import { roleSlots, statPoints, type RulesSnapshot, type StatScoring } from "../engine/scoring";
import { stageForDate } from "../fantasyStage";
import { findPair, loadHeadToHead, type HeadToHead } from "../headToHead";
import { useT } from "../i18n";
import {
  fantasyStats,
  isParsed,
  isRadiant,
  loadMatch,
  matchUrl,
  type MatchPlayer,
  type OpenDotaMatch,
} from "../opendota";
import { loadSnapshot, type Snapshot } from "../snapshot";
import MatchMap, { clock, type MapPlayer } from "./MatchMap";
import { Button, Field, Notice, Panel, Stat, chartTooltip, selectClass } from "./ui";

// Расходники в таймлайне покупок только мешают: тангошки и телепорты берут
// каждые пару минут, и за ними не видно предметов, которые собирали.
const CONSUMABLES = new Set([
  "tango",
  "tango_single",
  "flask",
  "clarity",
  "faerie_fire",
  "enchanted_mango",
  "branches",
  "tpscroll",
  "ward_observer",
  "ward_sentry",
  "ward_dispenser",
]);

const BUILD_LENGTH = 10;

interface Row {
  player: MatchPlayer;
  radiant: boolean;
  hero: string;
  stats: Record<string, number>;
  points: Map<string, number>;
  role: string;
  banner: { color: string; stat: string; label: string; points: number }[];
  total: number;
  /** Инвентарь на конец игры: внутренние имена предметов, пустые слоты — null. */
  items: (string | null)[];
  neutral: string | null;
  /** Порядок сборки: время покупки и предмет, без расходников. */
  build: { time: number; item: string }[];
}

/**
 * Роли компендиума по составу стороны.
 *
 * В матче их нет: OpenDota размечает лейн, а не позицию, и четвёртая с пятой
 * стоят на тех же лейнах, что кор с оффлейнером. Поэтому мид берётся по
 * разметке лейна, а Support Duo — двое с наименьшим нетвортом. Это догадка, и
 * подпись на странице так и говорит.
 */
function assignRoles(side: Row[]): void {
  const byNet = [...side].sort(
    (a, b) => (b.player.net_worth ?? 0) - (a.player.net_worth ?? 0),
  );
  const mid = side.find((row) => row.player.lane_role === 2) ?? byNet[1];
  const rest = byNet.filter((row) => row !== mid);

  for (const row of rest.slice(0, Math.max(0, rest.length - 2))) row.role = "core";
  for (const row of rest.slice(Math.max(0, rest.length - 2))) row.role = "support";
  if (mid) mid.role = "mid";
}

/**
 * Лучший баннер роли без бонусов эмблем: по одному стату на слот, цвет слота
 * фиксирован ролью. Это очки карты «как есть» — эмблемы умножают уже их.
 */
function neutralBanner(
  role: string,
  points: Map<string, number>,
  rules: RulesSnapshot,
  stage?: string,
): { color: string; stat: string; label: string; points: number }[] {
  const colors = roleSlots(rules, role, stage);
  const usable = rules.stats.filter((stat) => stat.availability !== "unavailable");
  const taken = new Set<string>();

  return colors.map((color) => {
    const best = usable
      .filter((stat) => stat.color === color && !taken.has(stat.key))
      .sort((a, b) => (points.get(b.key) ?? 0) - (points.get(a.key) ?? 0))[0];
    if (!best) return { color, stat: "", label: "—", points: 0 };
    taken.add(best.key);
    return {
      color,
      stat: best.key,
      label: best.label,
      points: points.get(best.key) ?? 0,
    };
  });
}

type TitleState = "yes" | "no" | "unknown";

interface TitleHit {
  key: string;
  label: string;
  bonus: number;
  condition: string;
  state: TitleState;
  who: string[];
}

/** Какие титулы сработали бы на этой карте. */
function evaluateTitles(match: OpenDotaMatch, rows: Row[], rules: RulesSnapshot): TitleHit[] {
  const titles = rules.titles;
  if (!titles) return [];

  const hits: TitleHit[] = [];
  for (const title of titles.prefixes) {
    const heroes = new Set(title.heroes ?? []);
    const who = rows.filter((row) => heroes.has(row.hero)).map((row) => row.hero);
    hits.push({
      key: title.key,
      label: title.label,
      bonus: title.bonus,
      condition: title.condition,
      state: heroes.size === 0 ? "unknown" : who.length ? "yes" : "no",
      who,
    });
  }

  const duration = match.duration;
  const firstBlood = match.first_blood_time ?? null;
  const losers = rows.filter((row) => row.radiant !== Boolean(match.radiant_win));

  const suffixState: Record<string, { state: TitleState; who: string[] }> = {
    // Длительность и результат карта знает про себя сама.
    decisive: { state: duration < 25 * 60 ? "yes" : "no", who: [] },
    lucky: { state: duration % 10 === 8 ? "yes" : "no", who: [] },
    underdog: {
      state: match.radiant_win == null ? "unknown" : "yes",
      who: losers.map((row) => row.hero),
    },
    // Ноль OpenDota ставит и до гонга, и когда события не поймала.
    patient: {
      state: firstBlood == null ? "unknown" : firstBlood >= 600 ? "yes" : "no",
      who: [],
    },
    flayed: { state: firstBlood ? "no" : "unknown", who: [] },
    // Серию по одной карте не восстановить, а смерть от Торментора и добивание
    // в фонтане OpenDota не размечает вовсе.
    clutch: { state: "unknown", who: [] },
    tormented: { state: "unknown", who: [] },
    cruel: { state: "unknown", who: [] },
  };

  for (const title of titles.suffixes) {
    const found = suffixState[title.key] ?? { state: "unknown" as TitleState, who: [] };
    hits.push({
      key: title.key,
      label: title.label,
      bonus: title.bonus,
      condition: title.condition,
      state: found.state,
      who: found.who,
    });
  }

  const order: Record<TitleState, number> = { yes: 0, no: 1, unknown: 2 };
  return hits.sort((a, b) => order[a.state] - order[b.state] || b.bonus - a.bonus);
}

function playerName(player: MatchPlayer): string {
  return player.name || player.personaname || (player.account_id ? String(player.account_id) : "—");
}

/** Внутреннее имя предмета -> подпись: `power_treads` -> `Power Treads`. */
function itemLabel(name: string): string {
  return name
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function ItemIcon({ name, size = 28 }: { name: string | null; size?: number }) {
  const icon = name ? itemIcon(name) : null;
  if (!name) {
    return (
      <span
        className="inline-block rounded-sm border border-[#20232c] bg-[#141720]"
        style={{ width: size, height: (size * 3) / 4 }}
      />
    );
  }
  return icon ? (
    <img
      src={icon}
      alt={itemLabel(name)}
      title={itemLabel(name)}
      className="rounded-sm object-cover"
      style={{ width: size, height: (size * 3) / 4 }}
    />
  ) : (
    <span
      className="inline-flex items-center justify-center rounded-sm border border-[#2a2e3a] text-[8px] text-neutral-500"
      style={{ width: size, height: (size * 3) / 4 }}
      title={itemLabel(name)}
    >
      {name.slice(0, 3)}
    </span>
  );
}

export default function MatchPanel({
  matchId,
  onOpen,
}: {
  matchId: number | null;
  onOpen: (id: number | null) => void;
}) {
  const { t, n, nc, dt, tryT, stat: statLabel, role: roleLabel } = useT();
  const [query, setQuery] = useState(matchId ? String(matchId) : "");
  const [match, setMatch] = useState<OpenDotaMatch | null>(null);
  // Манифест иконок грузится вне React: до него `itemIcon` честно отвечает
  // «иконки нет», поэтому предметы рисуются только после загрузки.
  const [iconsReady, setIconsReady] = useState(false);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [meetings, setMeetings] = useState<HeadToHead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // Правила и справочники героев с предметами лежат в снапшоте — он же нужен
    // вкладке эмблем, поэтому второй раз по сети не пойдёт. Манифест иконок
    // предметов и личные встречи нужны только здесь и грузятся вместе с ней.
    loadSnapshot().then(setSnapshot).catch(() => undefined);
    loadItemManifest().then(() => setIconsReady(true));
    loadHeadToHead().then(setMeetings).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!matchId) {
      setMatch(null);
      setError(null);
      return;
    }
    setQuery(String(matchId));
    setBusy(true);
    setError(null);
    loadMatch(matchId)
      .then(setMatch)
      .catch((e) => {
        setMatch(null);
        setError((e as Error).message);
      })
      .finally(() => setBusy(false));
  }, [matchId]);

  const analysis = useMemo(() => {
    if (!match || !snapshot) return null;
    const rules = snapshot.rules;
    const heroes = snapshot.heroes ?? {};
    const items = snapshot.items ?? {};
    const itemName = (id: number | undefined) =>
      id ? (items[String(id)] ?? null) : null;

    const rows: Row[] = match.players.map((player) => {
      const stats = fantasyStats(player);
      const points = new Map<string, number>(
        rules.stats.map((rule: StatScoring) => [rule.key, statPoints(rule, stats[rule.key] ?? 0)]),
      );
      return {
        player,
        radiant: isRadiant(player),
        hero: heroes[String(player.hero_id)] ?? `#${player.hero_id}`,
        stats,
        points,
        role: "core",
        banner: [],
        total: 0,
        items: [
          player.item_0,
          player.item_1,
          player.item_2,
          player.item_3,
          player.item_4,
          player.item_5,
        ].map(itemName),
        neutral: itemName(player.item_neutral),
        build: (player.purchase_log ?? [])
          .filter((entry) => !CONSUMABLES.has(entry.key))
          .slice(0, BUILD_LENGTH)
          .map((entry) => ({ time: entry.time, item: entry.key })),
      };
    });

    assignRoles(rows.filter((row) => row.radiant));
    assignRoles(rows.filter((row) => !row.radiant));
    // Период карты — по её дате: в основном этапе баннер на пять эмблем, и
    // очки за ту же игру считаются иначе, чем в группе. OpenDota отдаёт время
    // unix-секундами, периоды в снапшоте — календарными днями.
    const stage = stageForDate(
      snapshot.stages ?? [],
      new Date(match.start_time * 1000).toISOString(),
    );
    for (const row of rows) {
      row.banner = neutralBanner(row.role, row.points, rules, stage);
      row.total = row.banner.reduce((sum, slot) => sum + slot.points, 0);
    }

    return { rows, titles: evaluateTitles(match, rows, rules), parsed: isParsed(match) };
  }, [match, snapshot]);

  // Состав в том виде, в каком его читает карта: слот, ник, герой и сторона.
  // Отдельным списком, чтобы карта не разбирала матч во второй раз.
  const mapRoster = useMemo<MapPlayer[]>(
    () =>
      (analysis?.rows ?? []).map((row) => ({
        slot: row.player.player_slot,
        name: playerName(row.player),
        hero: row.hero,
        heroId: row.player.hero_id,
        radiant: row.radiant,
      })),
    [analysis],
  );

  const advantage = useMemo(() => {
    const gold = match?.radiant_gold_adv;
    if (!gold?.length) return [];
    const xp = match?.radiant_xp_adv ?? [];
    return gold.map((value, minute) => ({ m: minute, gold: value, xp: xp[minute] ?? 0 }));
  }, [match]);

  const submit = () => {
    const id = Number(query.replace(/\D/g, ""));
    onOpen(Number.isFinite(id) && id > 0 ? id : null);
  };

  const sides = analysis
    ? ([
        [true, analysis.rows.filter((row) => row.radiant)],
        [false, analysis.rows.filter((row) => !row.radiant)],
      ] as const)
    : [];

  // Личные встречи: пара ищется по id команд, а имена берутся из той же
  // выгрузки — в матче OpenDota команда бывает под старым названием.
  const meetingList = findPair(meetings, match?.radiant_team?.team_id, match?.dire_team?.team_id);
  const first = match?.radiant_team?.team_id;
  const record = meetingList.reduce(
    (acc, meeting) => {
      if (!meeting.w) acc.draws += 1;
      else if (meeting.w === first) acc.first += 1;
      else acc.second += 1;
      return acc;
    },
    { first: 0, second: 0, draws: 0 },
  );
  const teamName = (teamId: number | undefined | null) =>
    (teamId && meetings?.teams[String(teamId)]) ||
    (teamId === match?.radiant_team?.team_id
      ? (match?.radiant_team?.name ?? "Radiant")
      : (match?.dire_team?.name ?? "Dire"));

  return (
    <div className="space-y-4">
      <Panel
        title={t("match.title")}
        subtitle={t("match.subtitle")}
        actions={
          <div className="flex flex-wrap items-end gap-3">
            <Field label={t("match.idLabel")} hint={t("match.idHint")}>
              <input
                className={selectClass}
                value={query}
                inputMode="numeric"
                placeholder="8922016200"
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && submit()}
              />
            </Field>
            <Button onClick={submit} disabled={busy}>
              {busy ? t("common.loading") : t("match.open")}
            </Button>
          </div>
        }
      >
        {error && <Notice kind="error">{error}</Notice>}
        {!error && !match && !busy && (
          <div className="space-y-2 text-xs text-neutral-400">
            <p>{t("match.intro")}</p>
            <ul className="list-disc space-y-1 pl-5 text-neutral-500">
              <li>{t("match.introScoreboard")}</li>
              <li>{t("match.introFantasy")}</li>
              <li>{t("match.introTitles")}</li>
            </ul>
          </div>
        )}
      </Panel>

      {match && analysis && (
        <>
          <Panel>
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="text-lg text-neutral-100">
                  {match.radiant_team?.name ?? "Radiant"}
                  <span className="mx-2 text-neutral-500">vs</span>
                  {match.dire_team?.name ?? "Dire"}
                </h2>
                <p className="mt-1 text-xs text-neutral-500">
                  {match.league?.name ? `${match.league.name} · ` : ""}
                  {dt(new Date(match.start_time * 1000).toISOString())} ·{" "}
                  {t("common.minutes", { n: Math.round(match.duration / 60) })}
                </p>
              </div>
              <a
                href={matchUrl(match.match_id)}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-neutral-500 hover:text-[#c8a24a]"
              >
                {t("match.openDota")} ↗
              </a>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Stat
                label={t("match.score")}
                value={`${match.radiant_score ?? 0} : ${match.dire_score ?? 0}`}
              />
              <Stat
                label={t("match.winner")}
                value={
                  match.radiant_win == null
                    ? t("common.dash")
                    : match.radiant_win
                      ? (match.radiant_team?.name ?? "Radiant")
                      : (match.dire_team?.name ?? "Dire")
                }
              />
              <Stat
                label={t("match.firstBlood")}
                value={
                  match.first_blood_time
                    ? `${Math.floor(match.first_blood_time / 60)}:${String(
                        match.first_blood_time % 60,
                      ).padStart(2, "0")}`
                    : t("common.dash")
                }
              />
              <Stat
                label={t("match.length")}
                value={t("common.minutes", { n: Math.round(match.duration / 60) })}
                hint={`${match.duration % 60}s`}
              />
            </div>

            {!analysis.parsed && (
              <div className="mt-3">
                <Notice kind="warn">{t("match.unparsedWarning")}</Notice>
              </div>
            )}
          </Panel>

          {meetingList.length > 1 && (
            <Panel
              title={t("h2h.title")}
              subtitle={t("h2h.subtitle", { days: meetings?.days ?? 180 })}
            >
              <div className="mb-3 flex items-baseline gap-3 text-sm">
                <span className="text-neutral-300">{teamName(match.radiant_team?.team_id)}</span>
                <span className="tabular text-lg text-[#c8a24a]">
                  {record.first}–{record.second}
                </span>
                <span className="text-neutral-300">{teamName(match.dire_team?.team_id)}</span>
                {record.draws > 0 && (
                  <span className="text-[11px] text-neutral-500">
                    {t("h2h.unknown", { n: record.draws })}
                  </span>
                )}
              </div>
              <div className="max-h-64 overflow-y-auto">
                <table className="w-full min-w-[420px] text-xs">
                  <tbody>
                    {meetingList.map((meeting) => (
                      <tr
                        key={meeting.id}
                        className={`border-t border-[#20232c] ${
                          meeting.id === match.match_id ? "bg-[#1d2029]" : ""
                        }`}
                      >
                        <td className="py-1 whitespace-nowrap">
                          <a
                            href={`#/match/${meeting.id}`}
                            className="text-neutral-400 hover:text-[#c8a24a]"
                          >
                            {meeting.d}
                          </a>
                        </td>
                        <td className="py-1 text-neutral-300">
                          {meeting.w ? teamName(meeting.w) : t("common.dash")}
                        </td>
                        <td className="tabular py-1 text-right text-neutral-500">
                          {t("common.minutes", { n: Math.round(meeting.dur / 60) })}
                        </td>
                        <td className="max-w-[16rem] truncate py-1 pl-3 text-neutral-600">
                          {meeting.league ?? ""}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}

          {sides.map(([radiant, rows]) => (
            <Panel
              key={String(radiant)}
              title={
                radiant
                  ? (match.radiant_team?.name ?? "Radiant")
                  : (match.dire_team?.name ?? "Dire")
              }
              subtitle={
                match.radiant_win != null && match.radiant_win === radiant
                  ? t("match.won")
                  : t("match.lost")
              }
            >
              <div className="overflow-x-auto">
                <table className="w-full min-w-[1080px] text-xs">
                  <thead className="text-[11px] tracking-wide text-neutral-500 uppercase">
                    <tr>
                      <th className="py-1 text-left">{t("match.hero")}</th>
                      <th className="py-1 text-left">{t("common.player")}</th>
                      <th className="py-1 text-left">{t("common.role")}</th>
                      <th className="py-1 text-right">{t("common.kda")}</th>
                      <th className="py-1 text-right">{t("match.lastHits")}</th>
                      <th className="py-1 text-right">GPM / XPM</th>
                      <th className="py-1 text-right">{t("match.netWorth")}</th>
                      <th className="py-1 text-right">{t("match.heroDamage")}</th>
                      <th className="py-1 text-right">{t("match.wards")}</th>
                      <th className="py-1 text-right">{t("match.fantasy")}</th>
                      <th className="py-1 pl-3 text-left">{t("match.items")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => {
                      const icon = heroIcon(row.player.hero_id);
                      return (
                        <tr key={row.player.player_slot} className="border-t border-[#20232c]">
                          <td className="py-1">
                            <span className="flex items-center gap-2">
                              {icon && (
                                <img src={icon} alt="" className="h-5 w-8 rounded-sm object-cover" />
                              )}
                              <span className="text-neutral-300">{row.hero}</span>
                            </span>
                          </td>
                          <td className="py-1 text-neutral-200">{playerName(row.player)}</td>
                          <td className="py-1 text-neutral-500">{roleLabel(row.role)}</td>
                          <td className="tabular py-1 text-right text-neutral-300">
                            {row.player.kills ?? 0}/{row.player.deaths ?? 0}/
                            {row.player.assists ?? 0}
                          </td>
                          <td className="tabular py-1 text-right text-neutral-400">
                            {row.player.last_hits ?? 0}/{row.player.denies ?? 0}
                          </td>
                          <td className="tabular py-1 text-right text-neutral-400">
                            {row.player.gold_per_min ?? 0} / {row.player.xp_per_min ?? 0}
                          </td>
                          <td className="tabular py-1 text-right text-neutral-300">
                            {n(row.player.net_worth ?? 0)}
                          </td>
                          <td className="tabular py-1 text-right text-neutral-400">
                            {n(row.player.hero_damage ?? 0)}
                          </td>
                          <td className="tabular py-1 text-right text-neutral-400">
                            {row.player.obs_placed ?? 0}/{row.player.sen_placed ?? 0}
                          </td>
                          <td className="tabular py-1 text-right font-medium text-[#c8a24a]">
                            {n(row.total)}
                          </td>
                          <td className="py-1 pl-3">
                            {iconsReady && (
                              <span className="flex items-center gap-0.5">
                                {row.items.map((item, index) => (
                                  <ItemIcon key={index} name={item} size={26} />
                                ))}
                                {row.neutral && (
                                  <span className="ml-1">
                                    <ItemIcon name={row.neutral} size={22} />
                                  </span>
                                )}
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Panel>
          ))}

          {analysis.parsed && (
            <Panel title={t("map.title")} subtitle={t("map.subtitle")}>
              <MatchMap match={match} roster={mapRoster} />
            </Panel>
          )}

          {iconsReady && analysis.rows.some((row) => row.build.length > 0) && (
            <Panel title={t("match.buildTitle")} subtitle={t("match.buildSubtitle")}>
              <div className="space-y-2">
                {analysis.rows.map((row) => (
                  <div
                    key={row.player.player_slot}
                    className="flex items-start gap-3 border-b border-[#20232c] pb-2 last:border-0"
                  >
                    <div className="w-40 shrink-0 text-xs">
                      <div className="truncate text-neutral-200">{playerName(row.player)}</div>
                      <div className="truncate text-[11px] text-neutral-500">{row.hero}</div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {row.build.map((entry, index) => (
                        <div key={`${entry.item}-${index}`} className="text-center">
                          <ItemIcon name={entry.item} size={30} />
                          <div className="tabular text-[10px] text-neutral-500">
                            {clock(entry.time)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </Panel>
          )}

          <Panel title={t("match.fantasyTitle")} subtitle={t("match.fantasySubtitle")}>
            <div className="grid gap-2 sm:grid-cols-2">
              {[...analysis.rows]
                .sort((a, b) => b.total - a.total)
                .map((row) => (
                  <div
                    key={row.player.player_slot}
                    className="rounded border border-[#20232c] bg-[#1a1d24] px-3 py-2"
                  >
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="truncate text-xs text-neutral-200">
                        {playerName(row.player)}
                        <span className="ml-2 text-neutral-500">{row.hero}</span>
                      </span>
                      <span className="tabular text-sm text-[#c8a24a]">{n(row.total)}</span>
                    </div>
                    <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px]">
                      {row.banner.map((slot, index) => (
                        <span key={`${slot.stat}-${index}`} style={{ color: GROUP_COLOR[slot.color] }}>
                          {statLabel(slot.stat)}{" "}
                          <span className="tabular text-neutral-400">{n(slot.points)}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
            </div>
            <p className="mt-3 text-[11px] text-neutral-500">{t("match.fantasyNote")}</p>
          </Panel>

          {analysis.titles.length > 0 && (
            <Panel title={t("match.titlesTitle")} subtitle={t("match.titlesSubtitle")}>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[520px] text-xs">
                  <thead className="text-[11px] tracking-wide text-neutral-500 uppercase">
                    <tr>
                      <th className="py-1 text-left">{t("match.titleName")}</th>
                      <th className="py-1 text-right">{t("match.titleBonus")}</th>
                      <th className="py-1 text-center">{t("match.titleFired")}</th>
                      <th className="py-1 text-left">{t("match.titleCondition")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analysis.titles.map((title) => (
                      <tr key={title.key} className="border-t border-[#20232c]">
                        <td className="py-1 text-neutral-200">{title.label}</td>
                        <td className="tabular py-1 text-right text-neutral-400">
                          +{Math.round(title.bonus * 100)}%
                        </td>
                        <td className="py-1 text-center">
                          {title.state === "yes" ? (
                            <span className="text-emerald-400">✓</span>
                          ) : title.state === "no" ? (
                            <span className="text-neutral-600">—</span>
                          ) : (
                            <span className="text-neutral-500" title={t("match.titleUnknownHint")}>
                              ?
                            </span>
                          )}
                        </td>
                        <td className="py-1 text-neutral-500">
                          {tryT(`title.${title.key}.condition`, title.condition)}
                          {title.who.length > 0 && (
                            <span className="ml-1 text-neutral-400">
                              · {[...new Set(title.who)].join(", ")}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}

          {advantage.length > 2 && (
            <Panel title={t("match.advantageTitle")} subtitle={t("match.advantageSubtitle")}>
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={advantage} margin={{ left: 10, right: 10 }}>
                  <CartesianGrid stroke="#20232c" vertical={false} />
                  <XAxis dataKey="m" stroke="#7C858F" fontSize={10} minTickGap={30} />
                  <YAxis
                    stroke="#7C858F"
                    fontSize={11}
                    width={56}
                    tickFormatter={(value) => nc(Number(value) / 1000)}
                  />
                  <Tooltip
                    {...chartTooltip}
                    labelFormatter={(value) => t("common.minutes", { n: Number(value) })}
                    formatter={(value, name) => [
                      n(Number(value)),
                      name === "gold" ? t("match.goldAdvantage") : t("match.xpAdvantage"),
                    ]}
                  />
                  <ReferenceLine y={0} stroke="#3f4451" />
                  <Line type="monotone" dataKey="gold" stroke="#c8a24a" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="xp" stroke="#3d7fb8" strokeWidth={1.5} dot={false} />
                </LineChart>
              </ResponsiveContainer>
              <p className="mt-2 text-[11px] text-neutral-500">{t("match.advantageNote")}</p>
            </Panel>
          )}
        </>
      )}
    </div>
  );
}
