import { useEffect, useMemo, useState } from "react";
import { api, type ProfilePlayer } from "../api";
import { GROUP_COLOR, teamCrest } from "../assets";
import { useT } from "../i18n";
import { winRate } from "../profiles";
import { STATIC_MODE, loadSnapshot, type Snapshot } from "../snapshot";
import HeroPool from "./HeroPool";
import PlayerPortrait from "./PlayerPortrait";
import TitleTable from "./TitleTable";
import { MatchTable, StatGrid } from "./profileBits";
import { Button, Notice, Panel, Stat } from "./ui";

export default function PlayerPage({
  accountId,
  onBack,
  onOpenTeam,
}: {
  accountId: number;
  onBack: () => void;
  onOpenTeam: (teamId: number) => void;
}) {
  const { t, n, nc, stat: statLabel, role: roleLabel } = useT();
  const [player, setPlayer] = useState<ProfilePlayer | null>(null);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPlayer(null);
    setError(null);
    api
      .playerPage(accountId)
      .then(setPlayer)
      .catch((e) => setError((e as Error).message));
  }, [accountId]);

  useEffect(() => {
    if (!STATIC_MODE) return;
    loadSnapshot().then(setSnapshot).catch(() => undefined);
  }, []);

  // Наш анализ: сколько очков Fantasy приносит игра именно этого игрока и какую
  // часть пары он тянет. Берётся из разбивки роли — там он посчитан отдельно.
  const fantasy = useMemo(() => {
    if (!snapshot || !player) return null;
    const role = snapshot.roles.find((r) =>
      r.player_stats.some((p) => p.account_id === player.account_id),
    );
    if (!role) return null;
    const mine = role.player_stats.find((p) => p.account_id === player.account_id);
    if (!mine) return null;

    const meta = new Map(role.stats.map((s) => [s.stat, s]));
    const rows = mine.stats
      .map((value) => ({
        ...value,
        label: statLabel(value.stat),
        color: meta.get(value.stat)?.color ?? "red",
        rolePoints: meta.get(value.stat)?.base_points ?? 0,
      }))
      .sort((a, b) => b.base_points - a.base_points)
      .slice(0, 10);

    const mineTotal = mine.stats.reduce((sum, s) => sum + s.base_points, 0);
    const pairTotal = role.player_stats.reduce(
      (sum, p) => sum + p.stats.reduce((inner, s) => inner + s.base_points, 0),
      0,
    );

    return {
      role: role.role,
      teamName: role.team_name,
      partners: role.players.filter((name) => name !== player.name),
      rows,
      share: pairTotal ? mineTotal / pairTotal : 1,
      solo: role.player_stats.length < 2,
    };
  }, [snapshot, player, statLabel]);

  if (error) {
    return (
      <Panel title={t("common.player")}>
        <Notice kind="error">{error}</Notice>
        <div className="mt-3">
          <Button variant="ghost" onClick={onBack}>
            {t("common.back")}
          </Button>
        </div>
      </Panel>
    );
  }

  if (!player) return <Panel title={t("common.player")}>{t("common.loading")}</Panel>;

  const losses = player.games - player.wins;
  const crest = teamCrest(player.team_name);
  // Сигнатурный — не просто частый: на одной-двух картах процент побед ничего
  // не значит, поэтому нужен и объём, и результат.
  const signature = player.heroes
    .filter((hero) => hero.games >= 3 && hero.wins / hero.games > 0.5)
    .slice(0, 4);

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
          <PlayerPortrait teamName={player.team_name} nickname={player.name ?? "?"} size={56} />
          <div>
            <h2 className="text-lg text-neutral-100">{player.name ?? player.account_id}</h2>
            <p className="flex items-center gap-2 text-xs text-neutral-500">
              {crest && <img src={crest} alt="" className="h-4 w-4 object-contain" />}
              {player.team_id ? (
                <button
                  onClick={() => onOpenTeam(player.team_id!)}
                  className="hover:text-[#c8a24a]"
                >
                  {player.team_name ?? player.team_id}
                </button>
              ) : (
                t("player.noTeam")
              )}
              {player.role && <span>· {roleLabel(player.role)}</span>}
              <span>
                ·{" "}
                {t("team.period", {
                  from: player.first_game ?? "—",
                  to: player.last_game ?? "—",
                })}
              </span>
            </p>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat
            label={t("common.mapsShort")}
            value={player.games}
            hint={t("team.parsedHint", { n: player.parsed_games })}
          />
          <Stat
            label={t("common.wins")}
            value={`${player.wins}–${losses}`}
            hint={`${Math.round(winRate(player.wins, player.games) * 100)}%`}
          />
          <Stat
            label={t("common.kda")}
            value={`${nc(player.fantasy_units.kills ?? 0)}/${nc(
              player.fantasy_units.deaths ?? 0,
            )}/${nc(player.averages.assists ?? 0)}`}
          />
          <Stat
            label="GPM / XPM"
            value={`${Math.round(player.fantasy_units.gpm ?? 0)} / ${Math.round(
              player.averages.xpm ?? 0,
            )}`}
          />
        </div>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel
          title={t("player.averagesTitle")}
          subtitle={t("player.averagesSubtitle")}
        >
          <StatGrid values={player.averages} />
        </Panel>

        <Panel title={t("player.unitsTitle")} subtitle={t("player.unitsSubtitle")}>
          <StatGrid values={player.fantasy_units} />
        </Panel>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {player.heroes.length > 0 && (
          <Panel
            title={t("player.heroesTitle")}
            subtitle={t("player.heroesSubtitle")}
          >
            <HeroPool heroes={player.heroes} limit={12} />
            {signature.length > 0 && (
              <p className="mt-3 text-[11px] text-neutral-500">
                {t("player.signature")}{" "}
                <span className="text-neutral-300">
                  {signature.map((h) => h.name).join(", ")}
                </span>{" "}
                {t("player.signatureNote")}
              </p>
            )}
          </Panel>
        )}

        {(player.titles?.length ?? 0) > 0 && (
          <Panel
            title={t("player.titlesTitle")}
            subtitle={t("player.titlesSubtitle")}
          >
            <TitleTable titles={player.titles ?? []} limit={8} />
          </Panel>
        )}
      </div>

      {fantasy && (
        <Panel
          title={t("team.analysisTitle")}
          subtitle={
            fantasy.solo
              ? t("player.analysisSolo")
              : t("player.analysisPair", {
                  partners: fantasy.partners.length
                    ? t("player.analysisPartners", {
                        names: fantasy.partners.join(", "),
                      })
                    : "",
                })
          }
        >
          <div className="mb-3 flex flex-wrap items-center gap-3 text-xs">
            <span className="text-neutral-400">
              {t("player.roleLine", { role: roleLabel(fantasy.role) })}
            </span>
            {!fantasy.solo && (
              <span className="flex items-center gap-2 text-neutral-400">
                {t("player.pairShare")}
                <span className="h-2 w-32 overflow-hidden rounded bg-[#20232c]">
                  <span
                    className="block h-full rounded bg-[#c8a24a]"
                    style={{ width: `${Math.round(fantasy.share * 100)}%` }}
                  />
                </span>
                <span className="tabular text-neutral-200">
                  {Math.round(fantasy.share * 100)}%
                </span>
              </span>
            )}
          </div>

          <table className="w-full text-xs">
            <thead className="text-[11px] tracking-wide text-neutral-500 uppercase">
              <tr>
                <th className="py-1 text-left">{t("common.stat")}</th>
                <th className="py-1 text-right">{t("common.perMap")}</th>
                <th className="py-1 text-right">{t("common.mapsWithStat")}</th>
                <th className="py-1 text-right">{t("player.ownPoints")}</th>
                <th className="py-1 text-right">{t("player.rolePoints")}</th>
                <th className="py-1 text-right">{t("common.form")}</th>
              </tr>
            </thead>
            <tbody>
              {fantasy.rows.map((row) => (
                <tr key={row.stat} className="border-t border-[#20232c]">
                  <td className="py-1" style={{ color: GROUP_COLOR[row.color] }}>
                    {row.label}
                  </td>
                  <td className="tabular py-1 text-right text-neutral-400">
                    {nc(row.units_per_game)}
                  </td>
                  <td className="tabular py-1 text-right text-neutral-500">
                    {Math.round(row.hit_rate * 100)}%
                  </td>
                  <td className="tabular py-1 text-right text-neutral-100">
                    {n(row.base_points)}
                  </td>
                  <td className="tabular py-1 text-right text-neutral-500">
                    {n(row.rolePoints)}
                  </td>
                  <td className="tabular py-1 text-right">
                    {row.trend == null ? (
                      <span className="text-neutral-600">—</span>
                    ) : (
                      <span
                        className={
                          row.trend >= 1.05
                            ? "text-emerald-400"
                            : row.trend <= 0.95
                              ? "text-red-400"
                              : "text-neutral-400"
                        }
                      >
                        {row.trend >= 1 ? "↑" : "↓"} {Math.abs(Math.round((row.trend - 1) * 100))}%
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}

      <Panel title={t("common.matches")} subtitle={t("player.matchesSubtitle")}>
        <MatchTable matches={player.matches} showHero onOpenTeam={onOpenTeam} />
      </Panel>
    </div>
  );
}
