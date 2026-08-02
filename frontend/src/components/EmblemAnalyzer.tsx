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
import {
  api,
  type BannerAdvice,
  type StatRanking,
  type StatValue,
  type Team,
  type TitleAdvice,
} from "../api";
import { GROUP_COLOR, ROLE_LABEL, teamCrest } from "../assets";
import EmblemCard from "./EmblemCard";
import PlayerPortrait from "./PlayerPortrait";
import { Button, Field, Notice, Panel, Stat, selectClass } from "./ui";

const ROLES = ["core", "mid", "support"];
const QUALITIES = ["tier_1", "tier_2", "tier_3", "tier_4", "tier_5"];
const TRAITS = ["fractal", "benevolent", "vampiric", "unique", "friendly"];

export default function EmblemAnalyzer() {
  const [teams, setTeams] = useState<Team[]>([]);
  const [teamId, setTeamId] = useState<number | null>(null);
  const [role, setRole] = useState("core");
  const [restrict, setRestrict] = useState(false);
  const [qualities, setQualities] = useState<string[]>(QUALITIES);
  const [traits, setTraits] = useState<string[]>(TRAITS);

  const [advices, setAdvices] = useState<BannerAdvice[]>([]);
  const [stats, setStats] = useState<StatValue[]>([]);
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
      const [banner, report, titleAdvice] = await Promise.all([
        api.bestBanner({
          ...payload,
          qualities: restrict ? qualities : null,
          traits: restrict ? traits : null,
          simulate: true,
          simulations: 3000,
          top_n: 3,
        }),
        api.statReport(payload),
        api.titles(payload),
      ]);
      setAdvices(banner);
      setStats(report);
      setTitles(titleAdvice);
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

  return (
    <div className="space-y-4">
      <Panel
        title="Анализатор эмблем"
        subtitle="Цвет каждого слота задан ролью и не рероллится — меняются только стат внутри цвета, качество и трейт. Перебор идёт по всем комбинациям сразу, потому что трейты зависят друг от друга."
        actions={
          <div className="flex flex-wrap items-end gap-3">
            <Field label="Команда">
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
            <Field label="Роль">
              <select
                className={selectClass}
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {ROLE_LABEL[r]}
                  </option>
                ))}
              </select>
            </Field>
            <Button onClick={analyse} disabled={busy || teamId == null}>
              {busy ? "Считаю…" : "Подобрать эмблемы"}
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
          Искать только среди того, что выпало из роллов
        </label>

        {restrict && (
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <div>
              <div className="mb-1 text-[11px] tracking-wide text-neutral-500 uppercase">
                Доступные качества
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
                Доступные трейты
              </div>
              <div className="flex flex-wrap gap-1">
                {TRAITS.map((t) => (
                  <button
                    key={t}
                    onClick={() => toggle(traits, t, setTraits)}
                    className={`rounded border px-2 py-1 text-[11px] ${
                      traits.includes(t)
                        ? "border-[#c8a24a] text-[#c8a24a]"
                        : "border-[#2C3138] text-neutral-500"
                    }`}
                  >
                    {t}
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
            <Notice>Выберите команду и роль, затем нажмите «Подобрать эмблемы».</Notice>
          </div>
        )}
      </Panel>

      {best && (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
          <Panel
            title="Лучший War Banner"
            subtitle={`${ROLE_LABEL[best.role]} · ${best.player_names.join(" & ")}`}
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

            <div className="space-y-2">
              {best.slots.map((slot) => (
                <EmblemCard key={slot.slot} slot={slot} />
              ))}
            </div>

            <div className="mt-3 grid grid-cols-3 gap-2">
              <Stat
                label="За карту"
                value={Math.round(best.expected_card_points).toLocaleString("ru")}
              />
              <Stat
                label="За период"
                value={
                  best.period_mean
                    ? Math.round(best.period_mean).toLocaleString("ru")
                    : "—"
                }
                hint="топ-2 карты лучшей серии"
              />
              <Stat
                label="Потолок"
                value={
                  best.period_ceiling
                    ? Math.round(best.period_ceiling).toLocaleString("ru")
                    : "—"
                }
              />
            </div>

            {advices.length > 1 && (
              <div className="mt-4">
                <div className="mb-1 text-[11px] tracking-wide text-neutral-500 uppercase">
                  Альтернативы
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
                      {Math.round(a.expected_card_points).toLocaleString("ru")}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <div className="space-y-4">
            <Panel
              title="Что стоит каждый стат"
              subtitle="Не цена из глоссария, а цена, умноженная на объём: сколько очков стат приносит именно этим игрокам. Нажмите на столбец — покажу, кто в этом лучший на TI."
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
                    contentStyle={{
                      background: "#16181C",
                      border: "1px solid #2C3138",
                      fontSize: 12,
                    }}
                    formatter={(value) => Math.round(Number(value)).toLocaleString("ru")}
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
                    <th className="py-1 text-left">Стат</th>
                    <th className="py-1 text-right">За карту</th>
                    <th className="py-1 text-right">Очков</th>
                    <th className="py-1 text-right">Потолок</th>
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
                        {s.units_per_game.toLocaleString("ru", {
                          maximumFractionDigits: 2,
                        })}
                      </td>
                      <td className="tabular py-1 text-right text-neutral-200">
                        {Math.round(s.base_points).toLocaleString("ru")}
                      </td>
                      <td className="tabular py-1 text-right text-neutral-500">
                        {Math.round(s.p95_points).toLocaleString("ru")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Panel>

            {rankedStat && ranking.length > 0 && (
              <Panel
                title={`Кто лучший: ${ranking[0].stat}`}
                subtitle="Среди всех команд TI15 в этой роли — по базовым очкам за карту."
              >
                <table className="w-full text-xs">
                  <thead className="text-[11px] tracking-wide text-neutral-500 uppercase">
                    <tr>
                      <th className="py-1 text-left">Команда</th>
                      <th className="py-1 text-left">Игроки</th>
                      <th className="py-1 text-right">За карту</th>
                      <th className="py-1 text-right">Очков</th>
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
                          {r.units_per_game.toLocaleString("ru", {
                            maximumFractionDigits: 2,
                          })}
                        </td>
                        <td className="tabular py-1 text-right">
                          {Math.round(r.base_points).toLocaleString("ru")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Panel>
            )}

            {titles.length > 0 && (
              <Panel
                title="Coaching Titles"
                subtitle="Титулы меняются бесплатно, поэтому их стоит подбирать под конкретную роль. Ожидаемый бонус = процент × доля игр, где условие выполнялось."
              >
                <table className="w-full text-xs">
                  <tbody>
                    {titles.slice(0, 8).map((t) => (
                      <tr key={t.key} className="border-t border-[#20232c]">
                        <td className="py-1 text-neutral-200">{t.label}</td>
                        <td className="py-1 text-neutral-500">{t.condition}</td>
                        <td className="tabular py-1 text-right text-neutral-400">
                          +{Math.round(t.bonus * 100)}%
                        </td>
                        <td className="tabular py-1 text-right">
                          {t.expected_bonus != null ? (
                            <span className="text-[#c8a24a]">
                              ≈+{(t.expected_bonus * 100).toFixed(1)}%
                            </span>
                          ) : (
                            <span className="text-neutral-600" title={t.note}>
                              не оценить
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Panel>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
