import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  api,
  type BannerAdvice,
  type HeroPick,
  type PlayerProfile,
  type RoleTimeline,
  type StatRanking,
  type StatValue,
  type Team,
  type TitleAdvice,
} from "../api";
import { GROUP_COLOR, ROLES, teamCrest } from "../assets";
import { MAIN_STAGE, useFantasyStage } from "../fantasyStage";
import { useT } from "../i18n";
import EmblemCard from "./EmblemCard";
import HeroPool from "./HeroPool";
import PlayerPortrait from "./PlayerPortrait";
import TitleTable from "./TitleTable";
import { Button, Field, Notice, Panel, Stat, chartTooltip, selectClass } from "./ui";

const QUALITIES = ["tier_1", "tier_2", "tier_3", "tier_4", "tier_5"];
const TRAITS = ["fractal", "benevolent", "vampiric", "unique", "friendly"];

export default function EmblemAnalyzer() {
  const { t, tryT, tp, n, role: roleLabel } = useT();
  const { stage } = useFantasyStage();
  const [teams, setTeams] = useState<Team[]>([]);
  const [teamId, setTeamId] = useState<number | null>(null);
  const [role, setRole] = useState("core");
  const [restrict, setRestrict] = useState(false);
  const [qualities, setQualities] = useState<string[]>(QUALITIES);
  const [traits, setTraits] = useState<string[]>(TRAITS);

  const [advices, setAdvices] = useState<BannerAdvice[]>([]);
  const [stats, setStats] = useState<StatValue[]>([]);
  const [players, setPlayers] = useState<PlayerProfile[]>([]);
  const [heroes, setHeroes] = useState<HeroPick[]>([]);
  const [timeline, setTimeline] = useState<RoleTimeline | null>(null);
  const [titles, setTitles] = useState<TitleAdvice[]>([]);
  const [ranking, setRanking] = useState<StatRanking[]>([]);
  const [rankedStat, setRankedStat] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.teams(true).then((loaded) => {
      const list = loaded.length ? loaded : [];
      setTeams(list);
      if (list.length) setTeamId(list[0].team_id);
    });
  }, []);

  const teamName = useMemo(
    () => teams.find((t) => t.team_id === teamId)?.compendium_name ?? null,
    [teams, teamId],
  );

  const analyse = async () => {
    if (teamId == null) return;
    setBusy(true);
    setError(null);
    try {
      const payload = { team_id: teamId, role, history_days: 180 };
      const [banner, report, titleAdvice, profiles, form, pool] = await Promise.all([
        api.bestBanner({
          ...payload,
          qualities: restrict ? qualities : null,
          traits: restrict ? traits : null,
          simulate: true,
          simulations: 3000,
          top_n: 3,
          // Очки за период зависят от этапа: в плей-офф серий у команды меньше,
          // а у вылетевшей их нет вовсе.
          stage,
        }),
        api.statReport(payload),
        api.titles(payload),
        api.playerReport(payload),
        api.timeline(payload),
        api.heroPool(payload),
      ]);
      setAdvices(banner);
      setStats(report);
      setTitles(titleAdvice);
      setPlayers(profiles);
      setTimeline(form);
      setHeroes(pool);
      setRanking([]);
      setRankedStat(null);
    } catch (e) {
      setError((e as Error).message);
      setAdvices([]);
    } finally {
      setBusy(false);
    }
  };

  const showRanking = async (stat: string) => {
    setRankedStat(stat);
    try {
      setRanking(await api.statRanking(stat, role));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const toggle = (list: string[], value: string, set: (v: string[]) => void) =>
    set(list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);

  const best = advices[0];
  const chartData = stats
    .filter((s) => !s.negligible)
    .slice(0, 10)
    .map((s) => ({ ...s, name: s.label }));

  // Форма: очки за каждую карту плюс скользящее среднее по пяти. Без сглаживания
  // за разбросом отдельных карт тренда не видно, а без самих карт — не видно
  // разброса, ради которого в Fantasy и берут нестабильных игроков.
  const formData = useMemo(() => {
    const points = timeline?.points ?? [];
    return points.map((point, index) => {
      const window = points.slice(Math.max(0, index - 4), index + 1);
      return {
        ...point,
        avg: Math.round(window.reduce((sum, p) => sum + p.p, 0) / window.length),
      };
    });
  }, [timeline]);

  const formMean = formData.length
    ? formData.reduce((sum, p) => sum + p.p, 0) / formData.length
    : 0;

  const rosterNames = useMemo(
    () =>
      Object.fromEntries(
        players.map((p) => [p.account_id, p.name ?? String(p.account_id)]),
      ),
    [players],
  );

  // Кто в паре что делает: строки — статы, столбцы — игроки.
  const playerRows = useMemo(
    () =>
      stats
        .filter((s) => !s.negligible)
        .slice(0, 8)
        .map((s) => ({
          stat: s.stat,
          label: s.label,
          color: s.color,
          cells: players.map((p) => p.values.find((v) => v.stat === s.stat) ?? null),
        })),
    [stats, players],
  );

  // Насколько роль держится на одном человеке — по очкам того самого баннера.
  const bannerShare = useMemo(() => {
    if (!best || !players.length) return [];
    const totals = players.map((player) => ({
      name: player.name ?? String(player.account_id),
      games: player.games,
      points: best.slots.reduce((sum, slot) => {
        const value = player.values.find((v) => v.stat === slot.stat);
        return sum + (value ? value.base_points * (slot.percent / 100) : 0);
      }, 0),
    }));
    const sum = totals.reduce((s, t) => s + t.points, 0);
    return totals.map((t) => ({ ...t, share: sum ? t.points / sum : 0 }));
  }, [players, best]);

  return (
    <div className="space-y-4">
      <Panel
        title={t("emblems.title")}
        subtitle={t("emblems.subtitle")}
        actions={
          <div className="flex flex-wrap items-end gap-3">
            <Field label={t("common.team")}>
              <select
                className={selectClass}
                value={teamId ?? ""}
                onChange={(e) => setTeamId(Number(e.target.value))}
              >
                {teams.map((t) => (
                  <option key={t.team_id} value={t.team_id}>
                    {t.compendium_name ?? t.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t("common.role")}>
              <select
                className={selectClass}
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {roleLabel(r)}
                  </option>
                ))}
              </select>
            </Field>
            <Button onClick={analyse} disabled={busy || teamId == null}>
              {busy ? t("common.calculating") : t("emblems.run")}
            </Button>
          </div>
        }
      >
        <label className="flex items-center gap-2 text-xs text-neutral-400">
          <input
            type="checkbox"
            checked={restrict}
            onChange={(e) => setRestrict(e.target.checked)}
          />
          {t("emblems.restrict")}
        </label>

        {restrict && (
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <div>
              <div className="mb-1 text-[11px] tracking-wide text-neutral-500 uppercase">
                {t("emblems.qualities")}
              </div>
              <div className="flex flex-wrap gap-1">
                {QUALITIES.map((q) => (
                  <button
                    key={q}
                    onClick={() => toggle(qualities, q, setQualities)}
                    className={`rounded border px-2 py-1 text-[11px] ${
                      qualities.includes(q)
                        ? "border-[#c8a24a] text-[#c8a24a]"
                        : "border-[#2C3138] text-neutral-500"
                    }`}
                  >
                    {q.replace("tier_", "T")}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <div className="mb-1 text-[11px] tracking-wide text-neutral-500 uppercase">
                {t("emblems.traits")}
              </div>
              <div className="flex flex-wrap gap-1">
                {TRAITS.map((trait) => (
                  <button
                    key={trait}
                    onClick={() => toggle(traits, trait, setTraits)}
                    title={tryT(`trait.${trait}.description`, trait)}
                    className={`rounded border px-2 py-1 text-[11px] ${
                      traits.includes(trait)
                        ? "border-[#c8a24a] text-[#c8a24a]"
                        : "border-[#2C3138] text-neutral-500"
                    }`}
                  >
                    {trait}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="mt-3">
            <Notice kind="error">{error}</Notice>
          </div>
        )}
        {!best && !error && !busy && (
          <div className="mt-3">
            <Notice>{t("emblems.empty")}</Notice>
          </div>
        )}
      </Panel>

      {best && (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
          <Panel
            title={t("emblems.best")}
            subtitle={`${roleLabel(best.role)} · ${best.player_names.join(" & ")}`}
          >
            <div className="mb-3 flex items-center gap-3">
              {teamCrest(teamName) && (
                <img src={teamCrest(teamName)!} alt="" className="h-10 w-10 object-contain" />
              )}
              <div className="flex gap-2">
                {best.player_names.map((nick) => (
                  <PlayerPortrait key={nick} teamName={teamName} nickname={nick} />
                ))}
              </div>
            </div>

            {/* Команда вне сетки: в основном этапе она не сыграет ни серии, и
                любые очки за период у неё нулевые — это про выбор состава,
                а не сноска под таблицей. */}
            {stage === MAIN_STAGE && best.period_mean == null && (
              <div className="mb-3">
                <Notice kind="warn">{t("emblems.notInPlayoffs")}</Notice>
              </div>
            )}

            {/* Замена в составе: цифры принадлежат не тому, кто выйдет играть,
                и об этом надо сказать до эмблем, а не в сноске под ними. */}
            {(best.substitutions ?? []).map((sub) => (
              <div
                key={sub.name}
                className="mb-3 rounded border border-[#3A4048] bg-[#1C1F24] px-3 py-2"
              >
                <div className="text-[11px] tracking-wide text-neutral-400 uppercase">
                  {t("emblems.substitution")}
                </div>
                <p className="mt-1 text-xs leading-relaxed text-neutral-300">
                  {t("emblems.substitutionNote", {
                    name: sub.name,
                    replaced: sub.replaced,
                    games: sub.games,
                  })}
                </p>
              </div>
            ))}

            <div className="space-y-2">
              {best.slots.map((slot) => (
                <EmblemCard key={slot.slot} slot={slot} />
              ))}
            </div>

            <div className="mt-3 grid grid-cols-3 gap-2">
              <Stat label={t("common.perMap")} value={n(best.expected_card_points)} />
              <Stat
                label={t("common.perPeriod")}
                value={best.period_mean ? n(best.period_mean) : "—"}
                hint={t("common.topTwoMaps")}
              />
              <Stat
                label={t("common.ceiling")}
                value={best.period_ceiling ? n(best.period_ceiling) : "—"}
              />
            </div>

            {advices.length > 1 && (
              <div className="mt-4">
                <div className="mb-1 text-[11px] tracking-wide text-neutral-500 uppercase">
                  {t("emblems.alternatives")}
                </div>
                {advices.slice(1).map((a, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between border-t border-[#20232c] py-1 text-xs"
                  >
                    <span className="text-neutral-400">
                      {a.slots.map((s) => s.label).join(" · ")}
                    </span>
                    <span className="tabular text-neutral-300">
                      {n(a.expected_card_points)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <div className="space-y-4">
            <Panel
              title={t("emblems.statsTitle")}
              subtitle={t("emblems.statsSubtitle")}
            >
              <ResponsiveContainer width="100%" height={Math.max(240, chartData.length * 30)}>
                <BarChart data={chartData} layout="vertical" margin={{ left: 30 }}>
                  <XAxis type="number" stroke="#7C858F" fontSize={11} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    stroke="#9AA3AE"
                    fontSize={11}
                    width={140}
                  />
                  <Tooltip
                    cursor={{ fill: "rgba(255,255,255,0.04)" }}
                    {...chartTooltip}
                    formatter={(value) => n(Number(value))}
                  />
                  <Bar
                    dataKey="base_points"
                    radius={[0, 3, 3, 0]}
                    onClick={(entry) => showRanking((entry as unknown as StatValue).stat)}
                    cursor="pointer"
                  >
                    {chartData.map((s) => (
                      <Cell key={s.stat} fill={GROUP_COLOR[s.color]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>

              <table className="mt-2 w-full text-xs">
                <thead className="text-[11px] tracking-wide text-neutral-500 uppercase">
                  <tr>
                    <th className="py-1 text-left">{t("common.stat")}</th>
                    <th className="py-1 text-right">{t("common.perMap")}</th>
                    <th className="py-1 text-right" title={t("common.mapsWithStatHint")}>
                      {t("common.mapsWithStat")}
                    </th>
                    <th className="py-1 text-right">{t("common.median")}</th>
                    <th className="py-1 text-right">{t("common.points")}</th>
                    <th className="py-1 text-right">{t("common.ceiling")}</th>
                    <th className="py-1 text-right" title={t("common.formHint")}>
                      {t("common.form")}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {stats.slice(0, 12).map((s) => (
                    <tr
                      key={s.stat}
                      onClick={() => showRanking(s.stat)}
                      className="cursor-pointer border-t border-[#20232c] hover:bg-[#1C1F24]"
                    >
                      <td className="py-1" style={{ color: GROUP_COLOR[s.color] }}>
                        {s.label}
                      </td>
                      <td className="tabular py-1 text-right text-neutral-400">
                        {n(s.units_per_game, 2)}
                      </td>
                      <td className="tabular py-1 text-right text-neutral-500">
                        {s.hit_rate != null ? `${Math.round(s.hit_rate * 100)}%` : "—"}
                      </td>
                      <td className="tabular py-1 text-right text-neutral-400">
                        {s.median_points != null ? n(s.median_points) : "—"}
                      </td>
                      <td className="tabular py-1 text-right text-neutral-200">
                        {n(s.base_points)}
                      </td>
                      <td className="tabular py-1 text-right text-neutral-500">
                        {n(s.p95_points)}
                      </td>
                      <td className="tabular py-1 text-right">
                        {s.trend == null ? (
                          <span
                            className="text-neutral-600"
                            title={t("common.formNoSample")}
                          >
                            —
                          </span>
                        ) : (
                          <span
                            className={
                              s.trend >= 1.05
                                ? "text-emerald-400"
                                : s.trend <= 0.95
                                  ? "text-red-400"
                                  : "text-neutral-400"
                            }
                          >
                            {s.trend >= 1 ? "↑" : "↓"}{" "}
                            {Math.abs(Math.round((s.trend - 1) * 100))}%
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Panel>

            {formData.length > 3 && (
              <Panel
                title={t("emblems.formTitle")}
                subtitle={t("emblems.formSubtitle", {
                  banner: (timeline?.banner ?? []).map((e) => e.stat).join(", "),
                })}
              >
                <ResponsiveContainer width="100%" height={220}>
                  <AreaChart data={formData} margin={{ left: 10, right: 10 }}>
                    <CartesianGrid stroke="#20232c" vertical={false} />
                    <XAxis dataKey="d" stroke="#7C858F" fontSize={10} minTickGap={40} />
                    <YAxis stroke="#7C858F" fontSize={11} width={50} />
                    <Tooltip
                      {...chartTooltip}
                      formatter={(value, name) => [
                        n(Number(value)),
                        name === "p" ? t("emblems.formMap") : t("emblems.formAvg"),
                      ]}
                    />
                    <ReferenceLine
                      y={formMean}
                      stroke="#c8a24a"
                      strokeDasharray="4 4"
                      label={{
                        value: t("common.average"),
                        fill: "#c8a24a",
                        fontSize: 10,
                        position: "insideTopRight",
                      }}
                    />
                    <Area
                      type="monotone"
                      dataKey="p"
                      stroke="#3d7fb8"
                      fill="#3d7fb833"
                      strokeWidth={1}
                    />
                    <Line
                      type="monotone"
                      dataKey="avg"
                      stroke="#c8a24a"
                      strokeWidth={2}
                      dot={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </Panel>
            )}

            {playerRows.length > 0 && players.length > 1 && (
              <Panel
                title={t("emblems.pairTitle")}
                subtitle={t("emblems.pairSubtitle")}
              >
                <table className="w-full text-xs">
                  <thead className="text-[11px] tracking-wide text-neutral-500 uppercase">
                    <tr>
                      <th className="py-1 text-left">{t("common.stat")}</th>
                      {players.map((p) => (
                        <th key={p.account_id} className="py-1 text-right">
                          {p.name ?? p.account_id}
                          <div className="text-[10px] normal-case text-neutral-600">
                            {tp("plural.maps", p.games)}
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {playerRows.map((row) => {
                      const top = Math.max(
                        ...row.cells.map((c) => c?.units_per_game ?? 0),
                      );
                      return (
                        <tr key={row.stat} className="border-t border-[#20232c]">
                          <td className="py-1" style={{ color: GROUP_COLOR[row.color] }}>
                            {row.label}
                          </td>
                          {row.cells.map((cell, i) => (
                            <td
                              key={i}
                              className={`tabular py-1 text-right ${
                                cell && cell.units_per_game === top && top > 0
                                  ? "text-neutral-100"
                                  : "text-neutral-500"
                              }`}
                            >
                              {cell ? n(cell.units_per_game, 2) : "—"}
                            </td>
                          ))}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>

                {bannerShare.length > 1 && (
                  <div className="mt-3 space-y-1">
                    <div className="text-[11px] tracking-wide text-neutral-500 uppercase">
                      {t("emblems.bannerShare")}
                    </div>
                    {bannerShare.map((entry) => (
                      <div key={entry.name} className="flex items-center gap-2 text-xs">
                        <span className="w-28 truncate text-neutral-300">{entry.name}</span>
                        <span className="h-2 flex-1 overflow-hidden rounded bg-[#20232c]">
                          <span
                            className="block h-full rounded bg-[#c8a24a]"
                            style={{ width: `${Math.round(entry.share * 100)}%` }}
                          />
                        </span>
                        <span className="tabular w-10 text-right text-neutral-400">
                          {Math.round(entry.share * 100)}%
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </Panel>
            )}

            {rankedStat && ranking.length > 0 && (
              <Panel
                title={t("emblems.rankingTitle", { stat: ranking[0].stat })}
                subtitle={t("emblems.rankingSubtitle")}
              >
                <table className="w-full text-xs">
                  <thead className="text-[11px] tracking-wide text-neutral-500 uppercase">
                    <tr>
                      <th className="py-1 text-left">{t("common.team")}</th>
                      <th className="py-1 text-left">{t("common.players")}</th>
                      <th className="py-1 text-right">{t("common.perMap")}</th>
                      <th className="py-1 text-right">{t("common.points")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ranking.slice(0, 10).map((r, i) => (
                      <tr
                        key={r.team_id}
                        className={`border-t border-[#20232c] ${i === 0 ? "text-[#c8a24a]" : "text-neutral-300"}`}
                      >
                        <td className="py-1">
                          <span className="flex items-center gap-2">
                            {teamCrest(r.team_name) && (
                              <img
                                src={teamCrest(r.team_name)!}
                                alt=""
                                className="h-4 w-4 object-contain"
                              />
                            )}
                            {r.team_name}
                          </span>
                        </td>
                        <td className="py-1 text-neutral-500">
                          {r.player_names.join(", ")}
                        </td>
                        <td className="tabular py-1 text-right">
                          {n(r.units_per_game, 2)}
                        </td>
                        <td className="tabular py-1 text-right">{n(r.base_points)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Panel>
            )}

            {heroes.length > 0 && (
              <Panel
                title={t("emblems.heroesTitle")}
                subtitle={t("emblems.heroesSubtitle")}
              >
                <HeroPool heroes={heroes} names={rosterNames} limit={10} />
              </Panel>
            )}

            {titles.length > 0 && (
              <Panel
                title="Coaching Titles"
                subtitle={t("emblems.titlesSubtitle")}
              >
                <TitleTable titles={titles} limit={10} />
              </Panel>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
