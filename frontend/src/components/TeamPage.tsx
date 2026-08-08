import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type ProfilePlayer, type ProfileTeam } from "../api";
import { teamCrest } from "../assets";
import { optimiseBanner } from "../engine/scoring";
import { useT } from "../i18n";
import { winRate } from "../profiles";
import { STATIC_MODE, loadSnapshot, type Snapshot } from "../snapshot";
import HeroPool, { HeroIcon } from "./HeroPool";
import PlayerPortrait from "./PlayerPortrait";
import TitleTable from "./TitleTable";
import TrendPanel, { SplitBar, TrendValue } from "./TrendPanel";
import { MatchTable, StatGrid } from "./profileBits";
import { Button, Notice, Panel, Stat, chartTooltip } from "./ui";

export default function TeamPage({
  teamId,
  onBack,
  onOpenPlayer,
  onOpenTeam,
}: {
  teamId: number;
  onBack: () => void;
  onOpenPlayer: (accountId: number) => void;
  onOpenTeam: (teamId: number) => void;
}) {
  const { t, tp, n, nc, role: roleLabel } = useT();
  const [team, setTeam] = useState<ProfileTeam | null>(null);
  const [roster, setRoster] = useState<ProfilePlayer[]>([]);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [titleRole, setTitleRole] = useState("core");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setTeam(null);
    setError(null);
    api
      .teamPage(teamId)
      .then(({ team: loaded, roster: players }) => {
        setTeam(loaded);
        setRoster(players);
      })
      .catch((e) => setError((e as Error).message));
  }, [teamId]);

  // Наш анализ живёт в снапшоте: он есть только для участников TI15.
  useEffect(() => {
    if (!STATIC_MODE) return;
    loadSnapshot().then(setSnapshot).catch(() => undefined);
  }, []);

  const analysis = useMemo(() => {
    if (!snapshot) return [];
    return snapshot.roles
      .filter((role) => role.team_id === teamId)
      .map((role) => {
        const best = optimiseBanner(role.role, role.stats, snapshot.rules, { topN: 1 })[0];
        return {
          role: role.role,
          players: role.players,
          games: role.games,
          top: role.stats.filter((s) => !s.negligible).slice(0, 3),
          card: best?.total ?? 0,
          period: (best?.total ?? 0) * role.period_ratio,
          ceiling: (best?.total ?? 0) * role.ceiling_ratio,
          emblems: best?.slots ?? [],
          titles: role.titles,
          heroes: role.heroes ?? [],
        };
      })
      .sort((a, b) => b.period - a.period);
  }, [snapshot, teamId]);

  // Титулы у ролей разные: у саппорта другой пул героев, а значит и другие
  // префиксы. Показываем по одной роли за раз, с переключателем.
  const roleTitles = useMemo(
    () =>
      analysis.find((row) => row.role === titleRole)?.titles ??
      analysis[0]?.titles ??
      [],
    [analysis, titleRole],
  );

  const group = useMemo(
    () => snapshot?.group?.teams.find((t) => t.team_id === teamId) ?? null,
    [snapshot, teamId],
  );
  const buckets = snapshot?.group?.buckets ?? [];
  // На какую корзину мы ставим именно эту команду. Показывать вероятности без
  // ставки — значит оставить читателя гадать, почему рекомендация расходится с
  // самым вероятным исходом.
  const pick = useMemo(
    () => snapshot?.group?.plan.find((p) => p.team_id === teamId)?.bucket ?? null,
    [snapshot, teamId],
  );

  if (error) {
    return (
      <Panel title={t("common.team")}>
        <Notice kind="error">{error}</Notice>
        <div className="mt-3">
          <Button variant="ghost" onClick={onBack}>
            {t("common.back")}
          </Button>
        </div>
      </Panel>
    );
  }

  if (!team) return <Panel title={t("common.team")}>{t("common.loading")}</Panel>;

  const crest = teamCrest(team.name);
  const losses = team.games - team.wins;
  const rosterNames = Object.fromEntries(
    roster.map((player) => [player.account_id, player.name ?? String(player.account_id)]),
  );

  return (
    <div className="space-y-4">
      <Panel
        actions={
          <Button variant="ghost" onClick={onBack}>
            {t("common.back")}
          </Button>
        }
      >
        <div className="flex flex-wrap items-center gap-4">
          {crest && <img src={crest} alt="" className="h-14 w-14 object-contain" />}
          <div>
            <h2 className="text-lg text-neutral-100">
              {team.name}
              {team.tag && <span className="ml-2 text-sm text-neutral-500">[{team.tag}]</span>}
            </h2>
            <p className="text-xs text-neutral-500">
              {team.is_ti ? t("team.isTi") : t("team.notTi")} ·{" "}
              {t("team.period", {
                from: team.first_game ?? "—",
                to: team.last_game ?? "—",
              })}
            </p>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat
            label={t("common.rating")}
            value={team.rating ? n(team.rating) : "—"}
            hint={
              team.rd ? t("team.rdHint", { rd: Math.round(team.rd) }) : undefined
            }
          />
          <Stat
            label={t("common.mapsShort")}
            value={team.games}
            hint={t("team.parsedHint", { n: team.parsed_games })}
          />
          <Stat
            label={t("common.wins")}
            value={`${team.wins}–${losses}`}
            hint={`${Math.round(winRate(team.wins, team.games) * 100)}%`}
          />
          <Stat
            label={t("team.averageGame")}
            value={
              team.team_averages.duration
                ? t("common.minutes", {
                    n: Math.round(team.team_averages.duration / 60),
                  })
                : "—"
            }
          />
        </div>
      </Panel>

      {team.trends && (
        <Panel title={t("trends.title")} subtitle={t("trends.teamSubtitle")}>
          <TrendPanel
            trends={team.trends}
            extra={
              <div className="grid gap-x-6 sm:grid-cols-2">
                <div>
                  <p className="mb-1 text-[11px] tracking-wide text-neutral-500 uppercase">
                    {t("trends.opposition")}
                  </p>
                  <TrendValue
                    label={t("trends.opponentRating")}
                    value={team.opponent_rating ? n(team.opponent_rating) : t("common.dash")}
                  />
                  {team.first_blood_rate != null && (
                    <TrendValue
                      label={t("trends.firstBlood")}
                      hint={t("trends.firstBloodHint")}
                      value={`${Math.round(team.first_blood_rate * 100)}%`}
                    />
                  )}
                </div>
                {team.vs_stronger && team.vs_stronger.games > 0 && (
                  <div>
                    <p className="mb-1 text-[11px] tracking-wide text-neutral-500 uppercase">
                      {t("trends.vsStronger")}
                    </p>
                    <SplitBar label={t("trends.stronger")} split={team.vs_stronger} />
                    <p className="mt-1 text-[11px] text-neutral-600">
                      {t("trends.strongerHint")}
                    </p>
                  </div>
                )}
              </div>
            }
          />
        </Panel>
      )}

      {team.rating_history.length > 2 && (
        <Panel title={t("team.ratingTitle")} subtitle={t("team.ratingSubtitle")}>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart
              data={team.rating_history.map((point) => ({
                d: point.d,
                r: point.r,
                band: [point.r - point.rd, point.r + point.rd],
              }))}
              margin={{ left: 10, right: 10 }}
            >
              <CartesianGrid stroke="#20232c" vertical={false} />
              <XAxis dataKey="d" stroke="#7C858F" fontSize={10} minTickGap={40} />
              <YAxis stroke="#7C858F" fontSize={11} width={50} domain={["auto", "auto"]} />
              <Tooltip
                {...chartTooltip}
                formatter={(value, name) =>
                  Array.isArray(value)
                    ? [
                        `${Math.round(value[0])} – ${Math.round(value[1])}`,
                        t("team.ratingBand"),
                      ]
                    : [
                        Math.round(Number(value)),
                        name === "r" ? t("team.ratingLine") : String(name),
                      ]
                }
              />
              <Area dataKey="band" stroke="none" fill="#3d7fb833" />
              <Line type="monotone" dataKey="r" stroke="#c8a24a" strokeWidth={2} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </Panel>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title={t("team.heroesTitle")} subtitle={t("team.heroesSubtitle")}>
          <HeroPool heroes={team.heroes ?? []} names={rosterNames} limit={12} />
        </Panel>

        <Panel title={t("team.rosterTitle")} subtitle={t("team.rosterSubtitle")}>
          <div className="space-y-1">
            {roster.map((player) => (
              <button
                key={player.account_id}
                onClick={() => onOpenPlayer(player.account_id)}
                className="flex w-full items-center gap-3 rounded border border-transparent px-2 py-1.5 text-left hover:border-[#2C3138] hover:bg-[#1C1F24]"
              >
                <PlayerPortrait teamName={team.name} nickname={player.name ?? "?"} size={32} />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm text-neutral-100">
                    {player.name ?? player.account_id}
                  </div>
                  <div className="text-[11px] text-neutral-500">
                    {player.role ? roleLabel(player.role) : t("role.unknown")}
                  </div>
                </div>
                <div className="text-right text-xs">
                  <div className="tabular text-neutral-300">
                    {nc(player.fantasy_units.kills ?? 0)}/
                    {nc(player.fantasy_units.deaths ?? 0)}/
                    {nc(player.averages.assists ?? 0)}
                  </div>
                  <div className="tabular text-[11px] text-neutral-500">
                    {tp("plural.maps", player.games)} ·{" "}
                    {Math.round(winRate(player.wins, player.games) * 100)}%
                  </div>
                </div>
              </button>
            ))}
          </div>
        </Panel>

        <Panel title={t("team.averagesTitle")} subtitle={t("team.averagesSubtitle")}>
          <StatGrid values={team.team_averages} hidden={["duration"]} />
          {team.parsed_games < team.games && (
            <p className="mt-3 text-[11px] text-neutral-500">
              {t("team.averagesNote", {
                parsed: team.parsed_games,
                total: team.games,
              })}
            </p>
          )}
        </Panel>
      </div>

      {analysis.length > 0 && (
        <Panel title={t("team.analysisTitle")} subtitle={t("team.analysisSubtitle")}>
          <div className="grid gap-3 md:grid-cols-3">
            {analysis.map((row) => (
              <div key={row.role} className="rounded border border-[#20232c] bg-[#1a1d24] p-3">
                <div className="text-[11px] tracking-wide text-neutral-500 uppercase">
                  {roleLabel(row.role)}
                </div>
                <div className="mt-0.5 text-sm text-neutral-100">{row.players.join(" & ")}</div>
                <div className="tabular mt-2 text-lg text-[#c8a24a]">{n(row.period)}</div>
                <div className="text-[11px] text-neutral-500">
                  {t("team.analysisPeriod", { ceiling: n(row.ceiling) })}
                </div>
                <div className="mt-2 space-y-0.5 text-[11px] text-neutral-400">
                  {row.emblems.map((slot) => (
                    <div key={slot.slot} className="flex justify-between gap-2">
                      <span className="truncate">{slot.label}</span>
                      <span className="tabular text-neutral-500">
                        {Math.round(slot.percent)}%
                      </span>
                    </div>
                  ))}
                </div>
                <div className="mt-2 text-[11px] text-neutral-600">
                  {t("team.analysisSample", { games: tp("plural.maps", row.games) })}
                </div>

                {row.heroes.length > 0 && (
                  <div className="mt-2 border-t border-[#20232c] pt-2">
                    <div className="mb-1 text-[10px] tracking-wide text-neutral-600 uppercase">
                      {t("team.mostPicked")}
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {row.heroes.slice(0, 6).map((hero) => (
                        <HeroIcon key={hero.id} id={hero.id} name={hero.name} size={26} />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>

          {roleTitles.length > 0 && (
            <div className="mt-4">
              <div className="mb-2 flex flex-wrap items-end gap-2">
                <span className="text-[11px] tracking-wide text-neutral-500 uppercase">
                  {t("team.titlesByRole")}
                </span>
                {analysis.map((row) => (
                  <button
                    key={row.role}
                    onClick={() => setTitleRole(row.role)}
                    className={`rounded border px-2 py-0.5 text-[11px] ${
                      titleRole === row.role
                        ? "border-[#c8a24a] text-[#c8a24a]"
                        : "border-[#2C3138] text-neutral-500"
                    }`}
                  >
                    {roleLabel(row.role)}
                  </button>
                ))}
              </div>
              <TitleTable titles={roleTitles} />
            </div>
          )}

          {group && (
            <div className="mt-4">
              <div className="mb-1 text-[11px] tracking-wide text-neutral-500 uppercase">
                {t("team.bucketsTitle")}
              </div>
              <div className="flex flex-wrap gap-2 text-xs">
                {buckets.map((bucket) => (
                  <span
                    key={bucket.key}
                    className={`rounded border px-2 py-1 ${
                      pick === bucket.key
                        ? "border-[#c8a24a] bg-[#1f1c14] text-[#c8a24a]"
                        : "border-[#2C3138] text-neutral-400"
                    }`}
                    title={
                      pick === bucket.key
                        ? t("team.bucketPick", { bucket: bucket.description })
                        : bucket.description
                    }
                  >
                    {bucket.label}{" "}
                    <span
                      className={`tabular ${pick === bucket.key ? "" : "text-neutral-200"}`}
                    >
                      {Math.round((group.probabilities[bucket.key] ?? 0) * 100)}%
                    </span>
                    {pick === bucket.key && (
                      <span className="ml-1">{t("team.bucketPickTag")}</span>
                    )}
                  </span>
                ))}
                <span className="rounded border border-[#2C3138] px-2 py-1 text-emerald-400">
                  {t("team.advances")}{" "}
                  <span className="tabular">{Math.round(group.advance * 100)}%</span>
                </span>
              </div>

              {pick && (
                <p className="mt-2 text-[11px] text-neutral-500">
                  {t("team.pickNote", {
                    slots: buckets.map((b) => b.slots).join("/"),
                  })}
                </p>
              )}
            </div>
          )}
        </Panel>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Panel title={t("common.matches")} subtitle={t("team.matchesSubtitle")}>
          <MatchTable matches={team.matches} onOpenTeam={onOpenTeam} />
        </Panel>

        <Panel
          title={t("team.opponentsTitle")}
          subtitle={t("team.opponentsSubtitle")}
        >
          <table className="w-full text-xs">
            <tbody>
              {team.opponents.map((opponent) => (
                <tr key={opponent.name} className="border-t border-[#20232c]">
                  <td className="py-1 text-neutral-300">{opponent.name}</td>
                  <td className="tabular py-1 text-right text-neutral-400">
                    {opponent.wins}–{opponent.games - opponent.wins}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      </div>
    </div>
  );
}
