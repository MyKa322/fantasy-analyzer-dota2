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
import { GROUP_COLOR, heroIcon } from "../assets";
import { statPoints, type RulesSnapshot, type StatScoring } from "../engine/scoring";
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
import { Button, Field, Notice, Panel, Stat, chartTooltip, selectClass } from "./ui";

interface Row {
  player: MatchPlayer;
  radiant: boolean;
  hero: string;
  stats: Record<string, number>;
  points: Map<string, number>;
  role: string;
  banner: { color: string; stat: string; label: string; points: number }[];
  total: number;
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
): { color: string; stat: string; label: string; points: number }[] {
  const colors = rules.role_slots[role] ?? ["red", "red", "green"];
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
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // Правила и справочник героев лежат в снапшоте — он же нужен вкладке
    // эмблем, поэтому второй раз по сети не пойдёт.
    loadSnapshot().then(setSnapshot).catch(() => undefined);
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
      };
    });

    assignRoles(rows.filter((row) => row.radiant));
    assignRoles(rows.filter((row) => !row.radiant));
    for (const row of rows) {
      row.banner = neutralBanner(row.role, row.points, rules);
      row.total = row.banner.reduce((sum, slot) => sum + slot.points, 0);
    }

    return { rows, titles: evaluateTitles(match, rows, rules), parsed: isParsed(match) };
  }, [match, snapshot]);

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
                <table className="w-full min-w-[860px] text-xs">
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
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Panel>
          ))}

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
