import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type RosterResponse } from "../api";
import { ROLE_LABEL, teamCrest } from "../assets";
import PlayerPortrait from "./PlayerPortrait";
import { Button, Field, Notice, Panel, Stat, selectClass } from "./ui";

export default function RosterPanel() {
  const [data, setData] = useState<RosterResponse | null>(null);
  const [series, setSeries] = useState(5);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      setData(await api.roster({ series, simulations: 4000, history_days: 180 }));
    } catch (e) {
      setError((e as Error).message);
      setData(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <Panel
        title="Подбор состава"
        subtitle="Кандидаты — игроки 16 команд TI15. Внутри роли все считаются по одному баннеру, иначе сравнение команд превратится в сравнение баннеров."
        actions={
          <div className="flex items-end gap-3">
            <Field label="Серий за период" hint="сколько матчей сыграет команда">
              <select
                className={selectClass}
                value={series}
                onChange={(e) => setSeries(Number(e.target.value))}
              >
                {[4, 5, 6, 7].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </Field>
            <Button onClick={run} disabled={busy}>
              {busy ? "Считаю…" : "Подобрать"}
            </Button>
          </div>
        }
      >
        {error && <Notice kind="error">{error}</Notice>}
        {!data && !error && (
          <Notice>
            Нужна загруженная история участников TI15:{" "}
            <code className="text-neutral-300">python tools/cli.py ingest-ti</code>
          </Notice>
        )}

        {data && data.rosters.length > 0 && (
          <div className="space-y-2">
            {data.rosters.map((roster, index) => (
              <div
                key={index}
                className={`rounded border px-3 py-2 ${
                  index === 0
                    ? "border-[#c8a24a] bg-[#1f1c14]"
                    : "border-[#2a2e3a] bg-[#1d2029]"
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex flex-wrap gap-5 text-sm">
                    {roster.picks.map((pick) => {
                      const crest = teamCrest(pick.team_name);
                      const players =
                        data.candidates[pick.role]?.find(
                          (c) => c.team_id === pick.team_id,
                        )?.player_names ?? [];
                      return (
                        <span key={pick.role} className="flex items-center gap-2">
                          {crest && <img src={crest} alt="" className="h-6 w-6 object-contain" />}
                          <span className="flex -space-x-2">
                            {players.map((nick) => (
                              <PlayerPortrait
                                key={nick}
                                teamName={pick.team_name}
                                nickname={nick}
                                size={28}
                              />
                            ))}
                          </span>
                          <span>
                            <span className="block text-[11px] text-neutral-500">
                              {ROLE_LABEL[pick.role]}
                            </span>
                            <span className="text-neutral-100">{pick.team_name}</span>
                            <span className="tabular ml-1 text-xs text-neutral-500">
                              {Math.round(pick.mean).toLocaleString("ru")}
                            </span>
                          </span>
                        </span>
                      );
                    })}
                  </div>
                  <div className="tabular text-right">
                    <div className="text-[#c8a24a]">
                      {Math.round(roster.expected_total).toLocaleString("ru")}
                    </div>
                    <div className="text-[11px] text-neutral-500">
                      p5 {Math.round(roster.p5).toLocaleString("ru")} · p95{" "}
                      {Math.round(roster.p95).toLocaleString("ru")}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {data && data.skipped.length > 0 && (
          <div className="mt-3">
            <Notice kind="warn">
              Пропущены из-за нехватки разобранных матчей: {data.skipped.join("; ")}
            </Notice>
          </div>
        )}
      </Panel>

      {data &&
        Object.entries(data.candidates).map(([role, candidates]) => (
          <Panel
            key={role}
            title={ROLE_LABEL[role] ?? role}
            subtitle={`Баннер сравнения: ${(data.banners[role] ?? [])
              .map((e) => e.stat)
              .join(" + ")}. Столбец — ожидание, усы — интервал p5…p95.`}
          >
            <ResponsiveContainer width="100%" height={Math.max(220, candidates.length * 34)}>
              <BarChart data={candidates} layout="vertical" margin={{ left: 40 }}>
                <CartesianGrid stroke="#2a2e3a" strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" stroke="#6b7280" fontSize={11} />
                <YAxis
                  type="category"
                  dataKey="team_name"
                  stroke="#9ca3af"
                  fontSize={11}
                  width={120}
                />
                <Tooltip
                  contentStyle={{
                    background: "#16181e",
                    border: "1px solid #2a2e3a",
                    fontSize: 12,
                  }}
                  formatter={(value) => Math.round(Number(value)).toLocaleString("ru")}
                />
                <Bar dataKey="mean" radius={[0, 3, 3, 0]}>
                  {candidates.map((_, index) => (
                    <Cell key={index} fill={index === 0 ? "#c8a24a" : "#4a5266"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>

            <table className="mt-2 w-full text-xs">
              <thead className="text-[11px] tracking-wide text-neutral-400 uppercase">
                <tr>
                  <th className="py-1 text-left">Команда</th>
                  <th className="py-1 text-left">Игроки</th>
                  <th className="py-1 text-right">Ожидание</th>
                  <th className="py-1 text-right">Потолок</th>
                  <th className="py-1 text-right">Карт</th>
                </tr>
              </thead>
              <tbody>
                {candidates.map((candidate) => (
                  <tr key={candidate.team_id} className="border-t border-[#20232c]">
                    <td className="py-1 text-neutral-200">
                      <span className="flex items-center gap-2">
                        {teamCrest(candidate.team_name) && (
                          <img
                            src={teamCrest(candidate.team_name)!}
                            alt=""
                            className="h-4 w-4 object-contain"
                          />
                        )}
                        {candidate.team_name}
                      </span>
                    </td>
                    <td className="py-1 text-neutral-500">
                      {candidate.player_names.join(", ")}
                    </td>
                    <td className="tabular py-1 text-right text-neutral-200">
                      {Math.round(candidate.mean).toLocaleString("ru")}
                    </td>
                    <td className="tabular py-1 text-right text-[#c8a24a]">
                      {Math.round(candidate.ceiling_p95).toLocaleString("ru")}
                    </td>
                    <td className="tabular py-1 text-right text-neutral-500">
                      {candidate.games_used}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
        ))}

      {data && (
        <Panel title="Как читать">
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat
              label="Ожидание"
              value="среднее"
              hint="сколько наберёт роль за период в среднем"
            />
            <Stat
              label="Потолок p95"
              value="удачный период"
              hint="в Fantasy решает именно он: в зачёт идёт лучшая серия"
            />
            <Stat
              label="Карт"
              value="объём выборки"
              hint="меньше 10 — оценка шумная"
            />
          </div>
        </Panel>
      )}
    </div>
  );
}
