import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type ProfilePlayer } from "../api";
import { GROUP_COLOR, ROLE_LABEL, teamCrest } from "../assets";
import { games, winRate } from "../profiles";
import { STATIC_MODE, loadSnapshot, type Snapshot } from "../snapshot";
import PlayerPortrait from "./PlayerPortrait";
import { AVERAGE_LABEL, MatchTable, StatGrid, UNIT_LABEL, formatNumber } from "./profileBits";
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
        label: meta.get(value.stat)?.label ?? value.stat,
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
  }, [snapshot, player]);

  if (error) {
    return (
      <Panel title="Игрок">
        <Notice kind="error">{error}</Notice>
        <div className="mt-3">
          <Button variant="ghost" onClick={onBack}>
            ← К списку
          </Button>
        </div>
      </Panel>
    );
  }

  if (!player) return <Panel title="Игрок">Загружаю…</Panel>;

  const losses = player.games - player.wins;
  const crest = teamCrest(player.team_name);
  const heroData = player.heroes.slice(0, 10).map((hero) => ({
    ...hero,
    rate: hero.games ? hero.wins / hero.games : 0,
  }));

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
                "команда не определена"
              )}
              {player.role && <span>· {ROLE_LABEL[player.role] ?? player.role}</span>}
              <span>
                · матчи с {player.first_game ?? "—"} по {player.last_game ?? "—"}
              </span>
            </p>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat label="Карт" value={player.games} hint={`${player.parsed_games} с реплеем`} />
          <Stat
            label="Победы"
            value={`${player.wins}–${losses}`}
            hint={`${Math.round(winRate(player.wins, player.games) * 100)}%`}
          />
          <Stat
            label="К/С/А"
            value={`${formatNumber(player.fantasy_units.kills ?? 0)}/${formatNumber(
              player.fantasy_units.deaths ?? 0,
            )}/${formatNumber(player.averages.assists ?? 0)}`}
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
          title="Обычная статистика"
          subtitle="Средние за карту по разобранным матчам — то, что OpenDota отдаёт напрямую."
        >
          <StatGrid values={player.averages} labels={AVERAGE_LABEL} />
        </Panel>

        <Panel
          title="Fantasy-статы в единицах"
          subtitle="Те же величины, что считает компендиум, — но здесь именно единицы: варды, стаки, секунды стана. Во сколько очков они превращаются, зависит от эмблем."
        >
          <StatGrid values={player.fantasy_units} labels={UNIT_LABEL} />
        </Panel>
      </div>

      {heroData.length > 0 && (
        <Panel
          title="Пул героев"
          subtitle="Карт за период и доля побед на каждом. Цвет столбца — победы: зелёный выше половины, красный ниже."
        >
          <ResponsiveContainer width="100%" height={Math.max(200, heroData.length * 26)}>
            <BarChart data={heroData} layout="vertical" margin={{ left: 30 }}>
              <XAxis type="number" stroke="#7C858F" fontSize={11} allowDecimals={false} />
              <YAxis
                type="category"
                dataKey="name"
                stroke="#9AA3AE"
                fontSize={11}
                width={140}
              />
              <Tooltip
                cursor={{ fill: "rgba(255,255,255,0.04)" }}
                contentStyle={{
                  background: "#16181C",
                  border: "1px solid #2C3138",
                  fontSize: 12,
                }}
                formatter={(value, _name, item) => [
                  `${games(Number(value))} · ${Math.round((item.payload.rate ?? 0) * 100)}% побед`,
                  item.payload.name,
                ]}
              />
              <Bar dataKey="games" radius={[0, 3, 3, 0]}>
                {heroData.map((hero) => (
                  <Cell
                    key={hero.id}
                    fill={hero.rate >= 0.5 ? "var(--group-green)" : "var(--group-red)"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      )}

      {fantasy && (
        <Panel
          title="Наш анализ"
          subtitle={
            fantasy.solo
              ? "Очки Fantasy, которые приносит его игра, по каждому стату."
              : `Очки Fantasy по его собственным картам. В зачёт идёт среднее по роли, поэтому рядом — доля в паре${
                  fantasy.partners.length ? ` с ${fantasy.partners.join(", ")}` : ""
                }.`
          }
        >
          <div className="mb-3 flex flex-wrap items-center gap-3 text-xs">
            <span className="text-neutral-400">
              Роль: {ROLE_LABEL[fantasy.role] ?? fantasy.role}
            </span>
            {!fantasy.solo && (
              <span className="flex items-center gap-2 text-neutral-400">
                Вклад в пару
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
                <th className="py-1 text-left">Стат</th>
                <th className="py-1 text-right">За карту</th>
                <th className="py-1 text-right">Карт со статом</th>
                <th className="py-1 text-right">Его очки</th>
                <th className="py-1 text-right">Очки роли</th>
                <th className="py-1 text-right">Форма</th>
              </tr>
            </thead>
            <tbody>
              {fantasy.rows.map((row) => (
                <tr key={row.stat} className="border-t border-[#20232c]">
                  <td className="py-1" style={{ color: GROUP_COLOR[row.color] }}>
                    {row.label}
                  </td>
                  <td className="tabular py-1 text-right text-neutral-400">
                    {formatNumber(row.units_per_game)}
                  </td>
                  <td className="tabular py-1 text-right text-neutral-500">
                    {Math.round(row.hit_rate * 100)}%
                  </td>
                  <td className="tabular py-1 text-right text-neutral-100">
                    {Math.round(row.base_points).toLocaleString("ru")}
                  </td>
                  <td className="tabular py-1 text-right text-neutral-500">
                    {Math.round(row.rolePoints).toLocaleString("ru")}
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

      <Panel title="Матчи" subtitle="Последние карты за период — с героем и результатом.">
        <MatchTable matches={player.matches} showHero onOpenTeam={onOpenTeam} />
      </Panel>
    </div>
  );
}
