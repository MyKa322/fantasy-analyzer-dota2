import { useEffect, useState } from "react";
import { api, type GroupPrediction, type PredictionsConfig } from "../api";
import { teamCrest } from "../assets";
import { useT } from "../i18n";
import { STATIC_MODE } from "../snapshot";
import { Button, Field, Notice, Panel, Stat, selectClass } from "./ui";

function heat(probability: number): string {
  if (probability >= 0.4) return "bg-[#c8a24a] text-black";
  if (probability >= 0.25) return "bg-[#8a6f33] text-neutral-100";
  if (probability >= 0.12) return "bg-[#4a3f24] text-neutral-200";
  if (probability >= 0.05) return "bg-[#2a2e3a] text-neutral-300";
  return "text-neutral-600";
}

export default function GroupPanel() {
  const { t, tx, tp, n } = useT();
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

  // На опубликованной странице симуляция уже посчитана и лежит в снапшоте:
  // разыграть турнир заново браузеру нечем. Поэтому там нет ни выбора числа
  // прогонов, ни кнопки — прогноз показывается сразу.
  useEffect(() => {
    if (STATIC_MODE) void run();
  }, []);

  const buckets = config?.buckets ?? [];

  // Ставка по каждой команде — чтобы отметить её прямо в таблице вероятностей.
  // Иначе рекомендация выглядит противоречием: у Team Yandex 4-1 вероятнее, чем
  // 4-0, а ставим мы на 4-0.
  const pickByTeam = new Map<number, string>(
    (prediction?.plan ?? [])
      .filter((pick) => pick.team_id != null)
      .map((pick) => [pick.team_id as number, pick.bucket]),
  );

  return (
    <div className="space-y-4">
      <Panel
        title={t("group.title")}
        subtitle={STATIC_MODE ? t("group.subtitleStatic") : t("group.subtitleLive")}
        actions={
          STATIC_MODE ? undefined : (
            <div className="flex items-end gap-3">
              <Field label={t("group.simulations")}>
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
                {busy ? t("group.simulating") : t("group.run")}
              </Button>
            </div>
          )
        }
      >
        {error && <Notice kind="error">{error}</Notice>}
        {!prediction && !error && (
          <Notice>{busy ? t("group.loading") : t("group.needRatings")}</Notice>
        )}

        {prediction && (
          <>
            <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
              <Stat
                label={t("group.expectedPoints")}
                value={n(prediction.expected_points)}
                hint={t("group.expectedPointsHint")}
              />
              <Stat
                label={t("group.expectedCorrect")}
                value={prediction.expected_correct.toFixed(2)}
                hint={t("group.expectedCorrectHint")}
              />
              <Stat
                label={t("group.medianPoints")}
                value={n(prediction.points_percentiles["50"] ?? 0)}
              />
              <Stat
                label={t("group.p95")}
                value={n(prediction.points_percentiles["95"] ?? 0)}
                hint={t("group.p95Hint")}
              />
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-[11px] tracking-wide text-neutral-400 uppercase">
                  <tr>
                    <th className="py-2 text-left">{t("common.team")}</th>
                    {buckets.map((b) => (
                      <th key={b.key} className="px-1 py-2 text-center" title={b.description}>
                        {b.label}
                      </th>
                    ))}
                    <th className="py-2 text-center">{t("group.advance")}</th>
                    <th className="py-2 text-center">{t("group.seriesColumn")}</th>
                  </tr>
                </thead>
                <tbody>
                  {prediction.teams.map((team) => (
                    <tr key={team.team_id} className="border-t border-[#2a2e3a]">
                      <td className="py-1.5">{team.name ?? team.team_id}</td>
                      {buckets.map((b) => {
                        const value = team.probabilities[b.key] ?? 0;
                        const picked = pickByTeam.get(team.team_id) === b.key;
                        return (
                          <td key={b.key} className="px-1 py-1 text-center">
                            <span
                              title={
                                picked
                                  ? t("group.ourPick")
                                  : `${b.label}: ${(value * 100).toFixed(1)}%`
                              }
                              className={`tabular inline-block w-14 rounded px-1 py-0.5 text-xs ${heat(value)} ${
                                picked ? "ring-2 ring-[#c8a24a] ring-offset-1 ring-offset-[#16181e]" : ""
                              }`}
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

            <p className="mt-2 text-[11px] text-neutral-500">
              {t("group.simulationsNote", {
                count: tp("plural.tournaments", prediction.simulations),
              })}
            </p>
            <p className="mt-1 text-[11px] text-neutral-500">
              <span className="mr-1 inline-block rounded px-1 ring-2 ring-[#c8a24a]">
                {t("group.circled")}
              </span>
              {tx("group.pickNote", {
                slots: (
                  <span className="tabular">{buckets.map((b) => b.slots).join("/")}</span>
                ),
              })}
            </p>
          </>
        )}
      </Panel>

      {prediction && (
        <Panel title={t("group.planTitle")} subtitle={t("group.planSubtitle")}>
          {/* Доска корзин, как на экране предсказаний: раскладка по местам, а не
              список строк. Разница не косметическая — ставится ровно столько
              команд, сколько в корзине мест, и это должно быть видно сразу. */}
          <div className="space-y-3">
            {buckets.map((bucket) => {
              const picked = prediction.plan.filter((pick) => pick.bucket === bucket.key);
              return (
                <section key={bucket.key}>
                  <header className="mb-1.5 flex items-baseline gap-2 border-b border-[#2a2e3a] pb-1">
                    <h3 className="text-sm tracking-wide text-[#c8a24a] uppercase">
                      {bucket.label}
                    </h3>
                    <span className="tabular text-[11px] text-neutral-500">
                      {picked.length}/{bucket.slots}
                    </span>
                    <span className="truncate text-[11px] text-neutral-600">
                      {bucket.description}
                    </span>
                  </header>

                  <div className="flex flex-wrap gap-2">
                    {picked.map((pick) => {
                      const team = prediction.teams.find((x) => x.team_id === pick.team_id);
                      const chance = team?.probabilities[bucket.key] ?? 0;
                      return (
                        <div
                          key={pick.team_id ?? pick.team_name}
                          className="flex w-[168px] items-center gap-2 rounded border border-[#2a2e3a] bg-[#1d2029] px-2 py-2"
                          title={`${bucket.label}: ${(chance * 100).toFixed(1)}%`}
                        >
                          {teamCrest(pick.team_name) ? (
                            <img
                              src={teamCrest(pick.team_name)!}
                              alt=""
                              className="h-8 w-8 shrink-0 object-contain"
                            />
                          ) : (
                            <span className="h-8 w-8 shrink-0 rounded bg-[#2a2e3a]" />
                          )}
                          <div className="min-w-0">
                            <div className="truncate text-xs text-neutral-100">{pick.team_name}</div>
                            <div className="tabular text-[11px] text-neutral-500">
                              {(chance * 100).toFixed(1)}%
                            </div>
                          </div>
                        </div>
                      );
                    })}
                    {/* Пустые места корзины: без них не видно, что доска ещё не
                        заполнена, а в зачёт идут именно все слоты. */}
                    {Array.from({ length: Math.max(bucket.slots - picked.length, 0) }).map(
                      (_, index) => (
                        <div
                          key={`empty-${index}`}
                          className="h-[52px] w-[168px] rounded border border-dashed border-[#2a2e3a]"
                        />
                      ),
                    )}
                  </div>
                </section>
              );
            })}
          </div>
        </Panel>
      )}
    </div>
  );
}
