import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type RatingHistory, type Team } from "../api";
import { Button, Notice, Panel } from "./ui";

export default function TeamsPanel() {
  const [teams, setTeams] = useState<Team[]>([]);
  const [history, setHistory] = useState<RatingHistory | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setTeams(await api.teams());
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const recompute = async () => {
    setBusy(true);
    try {
      await api.recomputeRatings();
      await load();
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const showHistory = async (teamId: number) => {
    try {
      setHistory(await api.ratingHistory(teamId));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const chartData =
    history?.points.map((p) => ({
      date: p.as_of.slice(0, 10),
      rating: Math.round(p.rating),
      low: Math.round(p.rating - p.rd),
      high: Math.round(p.rating + p.rd),
    })) ?? [];

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <Panel
        title="Рейтинг команд"
        subtitle="Glicko-2: рейтинг ± RD. Чем выше RD, тем меньше данных и тем осторожнее прогноз."
        actions={
          <Button onClick={recompute} disabled={busy}>
            {busy ? "Считаю…" : "Пересчитать"}
          </Button>
        }
      >
        {error && <Notice kind="error">{error}</Notice>}
        {teams.length === 0 && !error && (
          <Notice>
            Данных пока нет. Загрузите матчи во вкладке «Данные», затем нажмите
            «Пересчитать».
          </Notice>
        )}
        {teams.length > 0 && (
          <div className="max-h-[28rem] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-[#16181e] text-[11px] tracking-wide text-neutral-400 uppercase">
                <tr>
                  <th className="py-2 text-left">Команда</th>
                  <th className="py-2 text-right">Рейтинг</th>
                  <th className="py-2 text-right">RD</th>
                  <th className="py-2 text-center">Надёжен</th>
                </tr>
              </thead>
              <tbody>
                {teams.map((team) => (
                  <tr
                    key={team.team_id}
                    onClick={() => void showHistory(team.team_id)}
                    className="cursor-pointer border-t border-[#2a2e3a] hover:bg-[#1d2029]"
                  >
                    <td className="py-1.5">
                      {team.name}
                      {team.compendium_name && (
                        <span className="ml-2 rounded bg-[#2a2e3a] px-1.5 py-0.5 text-[10px] text-[#c8a24a]">
                          TI15
                        </span>
                      )}
                    </td>
                    <td className="tabular py-1.5 text-right">
                      {team.rating ? Math.round(team.rating) : "—"}
                    </td>
                    <td className="tabular py-1.5 text-right text-neutral-400">
                      {team.rd ? Math.round(team.rd) : "—"}
                    </td>
                    <td className="py-1.5 text-center">
                      {team.is_listable ? (
                        <span className="text-emerald-400">✓</span>
                      ) : (
                        <span className="text-neutral-600">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel
        title="Тренд рейтинга"
        subtitle={
          history
            ? `${history.name ?? history.team_id}: полоса — интервал ±RD`
            : "Выберите команду в таблице слева"
        }
      >
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={chartData}>
              <CartesianGrid stroke="#2a2e3a" strokeDasharray="3 3" />
              <XAxis dataKey="date" stroke="#6b7280" fontSize={11} />
              <YAxis stroke="#6b7280" fontSize={11} domain={["auto", "auto"]} />
              <Tooltip
                contentStyle={{
                  background: "#16181e",
                  border: "1px solid #2a2e3a",
                  fontSize: 12,
                }}
              />
              <Line type="monotone" dataKey="high" stroke="#3f4451" dot={false} />
              <Line type="monotone" dataKey="rating" stroke="#c8a24a" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="low" stroke="#3f4451" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex h-[320px] items-center justify-center text-sm text-neutral-500">
            Нет данных для графика
          </div>
        )}
      </Panel>
    </div>
  );
}
