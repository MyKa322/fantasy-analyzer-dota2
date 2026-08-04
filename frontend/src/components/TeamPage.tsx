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
import { ROLE_LABEL, teamCrest } from "../assets";
import { optimiseBanner } from "../engine/scoring";
import { games, winRate } from "../profiles";
import { STATIC_MODE, loadSnapshot, type Snapshot } from "../snapshot";
import PlayerPortrait from "./PlayerPortrait";
import { AVERAGE_LABEL, MatchTable, StatGrid, UNIT_LABEL, formatNumber } from "./profileBits";
import { Button, Notice, Panel, Stat, chartTooltip } from "./ui";

const TEAM_AVERAGE_LABEL: Record<string, string> = {
  ...UNIT_LABEL,
  ...AVERAGE_LABEL,
  duration: "Длительность, сек",
};

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
  const [team, setTeam] = useState<ProfileTeam | null>(null);
  const [roster, setRoster] = useState<ProfilePlayer[]>([]);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
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
        };
      })
      .sort((a, b) => b.period - a.period);
  }, [snapshot, teamId]);

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
      <Panel title="Команда">
        <Notice kind="error">{error}</Notice>
        <div className="mt-3">
          <Button variant="ghost" onClick={onBack}>
            ← К списку
          </Button>
        </div>
      </Panel>
    );
  }

  if (!team) return <Panel title="Команда">Загружаю…</Panel>;

  const crest = teamCrest(team.name);
  const losses = team.games - team.wins;

  return (
    <div className="space-y-4">
      <Panel
        actions={
          <Button variant="ghost" onClick={onBack}>
            ← К списку
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
              {team.is_ti ? "Участник TI15" : "Не участвует в TI15"} · матчи с{" "}
              {team.first_game ?? "—"} по {team.last_game ?? "—"}
            </p>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat
            label="Рейтинг"
            value={team.rating ? Math.round(team.rating).toLocaleString("ru") : "—"}
            hint={team.rd ? `± ${Math.round(team.rd)} неопределённость` : undefined}
          />
          <Stat label="Карт" value={team.games} hint={`${team.parsed_games} с реплеем`} />
          <Stat
            label="Победы"
            value={`${team.wins}–${losses}`}
            hint={`${Math.round(winRate(team.wins, team.games) * 100)}%`}
          />
          <Stat
            label="Средняя игра"
            value={
              team.team_averages.duration
                ? `${Math.round(team.team_averages.duration / 60)} мин`
                : "—"
            }
          />
        </div>
      </Panel>

      {team.rating_history.length > 2 && (
        <Panel
          title="Рейтинг во времени"
          subtitle="Glicko-2 пересчитывается хронологически, без заглядывания в будущее. Полоса — неопределённость RD: чем реже команда играет, тем она шире."
        >
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
                    ? [`${Math.round(value[0])} – ${Math.round(value[1])}`, "разброс"]
                    : [Math.round(Number(value)), name === "r" ? "рейтинг" : String(name)]
                }
              />
              <Area dataKey="band" stroke="none" fill="#3d7fb833" />
              <Line type="monotone" dataKey="r" stroke="#c8a24a" strokeWidth={2} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </Panel>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel
          title="Состав"
          subtitle="Порядок — по числу карт за период: стенд-ины видно, но они не вытесняют основу."
        >
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
                    {player.role ? (ROLE_LABEL[player.role] ?? player.role) : "роль не размечена"}
                  </div>
                </div>
                <div className="text-right text-xs">
                  <div className="tabular text-neutral-300">
                    {formatNumber(player.fantasy_units.kills ?? 0)}/
                    {formatNumber(player.fantasy_units.deaths ?? 0)}/
                    {formatNumber(player.averages.assists ?? 0)}
                  </div>
                  <div className="tabular text-[11px] text-neutral-500">
                    {games(player.games)} · {Math.round(winRate(player.wins, player.games) * 100)}%
                  </div>
                </div>
              </button>
            ))}
          </div>
        </Panel>

        <Panel
          title="Средние за карту"
          subtitle="Суммарно по пятерым — так читается стиль команды: сколько убивает, как фармит, сколько ставит вардов."
        >
          <StatGrid
            values={team.team_averages}
            labels={TEAM_AVERAGE_LABEL}
            hidden={["duration"]}
          />
          {team.parsed_games < team.games && (
            <p className="mt-3 text-[11px] text-neutral-500">
              Средние считаются по {team.parsed_games} картам с разобранным реплеем из{" "}
              {team.games}: в остальных OpenDota не отдаёт ни вардов, ни станов, и включать
              их значило бы занизить всё сразу.
            </p>
          )}
        </Panel>
      </div>

      {analysis.length > 0 && (
        <Panel
          title="Наш анализ"
          subtitle="То же, что на вкладке «Эмблемы», но собранное про эту команду: лучший баннер каждой роли и во что он превращается за период."
        >
          <div className="grid gap-3 md:grid-cols-3">
            {analysis.map((row) => (
              <div key={row.role} className="rounded border border-[#20232c] bg-[#1a1d24] p-3">
                <div className="text-[11px] tracking-wide text-neutral-500 uppercase">
                  {ROLE_LABEL[row.role] ?? row.role}
                </div>
                <div className="mt-0.5 text-sm text-neutral-100">{row.players.join(" & ")}</div>
                <div className="tabular mt-2 text-lg text-[#c8a24a]">
                  {Math.round(row.period).toLocaleString("ru")}
                </div>
                <div className="text-[11px] text-neutral-500">
                  за период · потолок {Math.round(row.ceiling).toLocaleString("ru")}
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
                <div className="mt-2 text-[11px] text-neutral-600">{games(row.games)} в выборке</div>
              </div>
            ))}
          </div>

          {group && (
            <div className="mt-4">
              <div className="mb-1 text-[11px] tracking-wide text-neutral-500 uppercase">
                Групповой этап: вероятности корзин
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
                        ? `${bucket.description} — наша ставка на эту команду`
                        : bucket.description
                    }
                  >
                    {bucket.label}{" "}
                    <span
                      className={`tabular ${pick === bucket.key ? "" : "text-neutral-200"}`}
                    >
                      {Math.round((group.probabilities[bucket.key] ?? 0) * 100)}%
                    </span>
                    {pick === bucket.key && <span className="ml-1">· ставка</span>}
                  </span>
                ))}
                <span className="rounded border border-[#2C3138] px-2 py-1 text-emerald-400">
                  проходит дальше{" "}
                  <span className="tabular">{Math.round(group.advance * 100)}%</span>
                </span>
              </div>

              {pick && (
                <p className="mt-2 text-[11px] text-neutral-500">
                  Ставка не обязана совпадать с самым вероятным исходом команды: слотов в
                  каждой корзине фиксированное число ({buckets.map((b) => b.slots).join("/")}),
                  и расстановка подбирается целиком, под максимум угаданных, а не по каждой
                  команде отдельно.
                </p>
              )}
            </div>
          )}
        </Panel>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Panel title="Матчи" subtitle="К/С/А — суммарно по команде за карту.">
          <MatchTable matches={team.matches} onOpenTeam={onOpenTeam} />
        </Panel>

        <Panel title="С кем играли" subtitle="Соперники за период и счёт по картам.">
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
