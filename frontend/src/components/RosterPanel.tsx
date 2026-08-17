import { useEffect, useState } from "react";
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
import { teamCrest } from "../assets";
import { MAIN_STAGE, useFantasyStage } from "../fantasyStage";
import { useT } from "../i18n";
import { STATIC_MODE } from "../snapshot";
import PlayerPortrait from "./PlayerPortrait";
import { Button, Field, Notice, Panel, Stat, chartTooltip, selectClass } from "./ui";

export default function RosterPanel() {
  const { t, n, role: roleLabel } = useT();
  const { stage } = useFantasyStage();
  const [data, setData] = useState<RosterResponse | null>(null);
  const [series, setSeries] = useState(5);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // В плей-офф число серий не выбирают: оно приходит из сетки и у каждой
  // команды своё — от двух серий до шести, в зависимости от того, как далеко
  // она пройдёт. Переключатель здесь означал бы выбор турнира, а не периода.
  const bracketDriven = stage === MAIN_STAGE;

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      setData(await api.roster({ series, stage, simulations: 4000, history_days: 180 }));
    } catch (e) {
      setError((e as Error).message);
      setData(null);
    } finally {
      setBusy(false);
    }
  };

  // На опубликованной странице считать нечего — коэффициенты уже посчитаны,
  // поэтому состав показывается сразу и пересобирается при смене периода.
  // С живым бэкендом каждый пересчёт — это тысячи симуляций, и там он по кнопке.
  useEffect(() => {
    if (STATIC_MODE) void run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage]);

  return (
    <div className="space-y-4">
      <Panel
        title={t("roster.title")}
        subtitle={bracketDriven ? t("roster.subtitleMain") : t("roster.subtitle")}
        actions={
          <div className="flex items-end gap-3">
            <Field
              label={t("roster.series")}
              hint={bracketDriven ? t("roster.seriesBracket") : t("roster.seriesHint")}
            >
              <select
                className={selectClass}
                value={series}
                disabled={bracketDriven}
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
              {busy ? t("common.calculating") : t("roster.run")}
            </Button>
          </div>
        }
      >
        {bracketDriven && (
          <div className="mb-3">
            <Notice>{t("roster.playoffNote")}</Notice>
          </div>
        )}
        {error && <Notice kind="error">{error}</Notice>}
        {!data && !error && (
          <Notice>
            {t("roster.needData")}{" "}
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
                              {roleLabel(pick.role)}
                            </span>
                            <span className="text-neutral-100">{pick.team_name}</span>
                            <span className="tabular ml-1 text-xs text-neutral-500">
                              {n(pick.mean)}
                            </span>
                          </span>
                        </span>
                      );
                    })}
                  </div>
                  <div className="tabular text-right">
                    <div className="text-[#c8a24a]">{n(roster.expected_total)}</div>
                    <div className="text-[11px] text-neutral-500">
                      p5 {n(roster.p5)} · p95 {n(roster.p95)}
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
              {t("roster.skipped", { teams: data.skipped.join("; ") })}
            </Notice>
          </div>
        )}
      </Panel>

      {data &&
        Object.entries(data.candidates).map(([role, candidates]) => (
          <Panel
            key={role}
            title={roleLabel(role)}
            subtitle={t("roster.bannerSubtitle", {
              banner: (data.banners[role] ?? []).map((e) => e.stat).join(" + "),
            })}
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
                <Tooltip {...chartTooltip} formatter={(value) => n(Number(value))} />
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
                  <th className="py-1 text-left">{t("common.team")}</th>
                  <th className="py-1 text-left">{t("common.players")}</th>
                  <th className="py-1 text-right">{t("common.expectation")}</th>
                  <th className="py-1 text-right">{t("common.ceiling")}</th>
                  <th className="py-1 text-right">{t("common.mapsShort")}</th>
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
                      {n(candidate.mean)}
                    </td>
                    <td className="tabular py-1 text-right text-[#c8a24a]">
                      {n(candidate.ceiling_p95)}
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
        <Panel title={t("roster.legendTitle")}>
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat
              label={t("common.expectation")}
              value={t("common.average")}
              hint={t("roster.legendMeanHint")}
            />
            <Stat
              label={t("roster.legendCeiling")}
              value={t("roster.legendCeilingValue")}
              hint={t("roster.legendCeilingHint")}
            />
            <Stat
              label={t("common.mapsShort")}
              value={t("roster.legendGames")}
              hint={t("roster.legendGamesHint")}
            />
          </div>
        </Panel>
      )}
    </div>
  );
}
