import { useEffect, useState } from "react";
import { api, type GroupPrediction, type PredictionsConfig } from "../api";
import { Button, Field, Notice, Panel, Stat, selectClass } from "./ui";

function heat(probability: number): string {
  if (probability >= 0.4) return "bg-[#c8a24a] text-black";
  if (probability >= 0.25) return "bg-[#8a6f33] text-neutral-100";
  if (probability >= 0.12) return "bg-[#4a3f24] text-neutral-200";
  if (probability >= 0.05) return "bg-[#2a2e3a] text-neutral-300";
  return "text-neutral-600";
}

export default function GroupPanel() {
  const [config, setConfig] = useState<PredictionsConfig | null>(null);
  const [prediction, setPrediction] = useState<GroupPrediction | null>(null);
  const [simulations, setSimulations] = useState(20000);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.predictionsConfig().then(setConfig).catch(() => undefined);
  }, []);

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      setPrediction(await api.groupPrediction(simulations));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const buckets = config?.buckets ?? [];

  return (
    <div className="space-y-4">
      <Panel
        title="Групповой этап"
        subtitle="Swiss 16 команд: до 4 побед или 4 поражений, затем Elimination Round. Каждый прогон разыгрывает турнир целиком."
        actions={
          <div className="flex items-end gap-3">
            <Field label="Симуляций">
              <select
                className={selectClass}
                value={simulations}
                onChange={(e) => setSimulations(Number(e.target.value))}
              >
                <option value={2000}>2 000</option>
                <option value={20000}>20 000</option>
                <option value={100000}>100 000</option>
              </select>
            </Field>
            <Button onClick={run} disabled={busy}>
              {busy ? "Симулирую…" : "Рассчитать"}
            </Button>
          </div>
        }
      >
        {error && <Notice kind="error">{error}</Notice>}
        {!prediction && !error && (
          <Notice>
            Нужны рейтинги 16 участников. Загрузите матчи, пересчитайте рейтинги и
            запустите расчёт.
          </Notice>
        )}

        {prediction && (
          <>
            <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
              <Stat
                label="Ожидаемые очки"
                value={Math.round(prediction.expected_points).toLocaleString("ru")}
                hint="при оптимальной расстановке"
              />
              <Stat
                label="Угадано в среднем"
                value={prediction.expected_correct.toFixed(2)}
                hint="из 16 слотов"
              />
              <Stat
                label="Медиана очков"
                value={Math.round(prediction.points_percentiles["50"] ?? 0).toLocaleString("ru")}
              />
              <Stat
                label="95-й перцентиль"
                value={Math.round(prediction.points_percentiles["95"] ?? 0).toLocaleString("ru")}
                hint="удачный сценарий"
              />
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-[11px] tracking-wide text-neutral-400 uppercase">
                  <tr>
                    <th className="py-2 text-left">Команда</th>
                    {buckets.map((b) => (
                      <th key={b.key} className="px-1 py-2 text-center" title={b.description}>
                        {b.label}
                      </th>
                    ))}
                    <th className="py-2 text-center">Проход</th>
                    <th className="py-2 text-center">Серий</th>
                  </tr>
                </thead>
                <tbody>
                  {prediction.teams.map((team) => (
                    <tr key={team.team_id} className="border-t border-[#2a2e3a]">
                      <td className="py-1.5">{team.name ?? team.team_id}</td>
                      {buckets.map((b) => {
                        const value = team.probabilities[b.key] ?? 0;
                        return (
                          <td key={b.key} className="px-1 py-1 text-center">
                            <span
                              className={`tabular inline-block w-14 rounded px-1 py-0.5 text-xs ${heat(value)}`}
                            >
                              {(value * 100).toFixed(1)}%
                            </span>
                          </td>
                        );
                      })}
                      <td className="tabular py-1.5 text-center text-emerald-400">
                        {(team.advance * 100).toFixed(1)}%
                      </td>
                      <td className="tabular py-1.5 text-center text-neutral-400">
                        {team.expected_series.toFixed(1)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Panel>

      {prediction && (
        <Panel
          title="Рекомендованные предсказания"
          subtitle="Расстановка подобрана под максимум ожидаемых очков, а не под самые вероятные исходы по отдельности — шкала начисления нелинейная."
        >
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {prediction.plan.map((pick) => (
              <div
                key={pick.key}
                className="rounded border border-[#2a2e3a] bg-[#1d2029] px-3 py-2"
              >
                <div className="text-sm text-neutral-100">{pick.key}</div>
                <div className="text-xs text-[#c8a24a]">{pick.label ?? pick.pick}</div>
              </div>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}
