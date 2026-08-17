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
  type Emblem,
  type FantasyRules,
  type InventoryFit,
  type InventoryResponse,
} from "../api";
import { GROUP_COLOR, QUALITY_LABEL, ROLES, TRAIT_LABEL, teamCrest } from "../assets";
import { useFantasyStage } from "../fantasyStage";
import { useT } from "../i18n";
import EmblemCard from "./EmblemCard";
import PlayerPortrait from "./PlayerPortrait";
import { Button, Field, Notice, Panel, Stat, chartTooltip, selectClass } from "./ui";

const QUALITIES = ["tier_1", "tier_2", "tier_3", "tier_4", "tier_5"];
const TRAITS = ["fractal", "benevolent", "vampiric", "unique", "friendly"];
const STORAGE_KEY = "compendium.inventory.v1";

// Стартовый набор — пример, а не рекомендация: сразу видно, как это работает,
// и что красные эмблемы саппорту не подойдут ни при каких раскладах.
const EXAMPLE: Emblem[] = [
  { stat: "gpm", quality: "tier_4", trait: "benevolent" },
  { stat: "kills", quality: "tier_3", trait: null },
  { stat: "teamfight_participation", quality: "tier_3", trait: null },
];

function loadInventory(): Emblem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return EXAMPLE;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) && parsed.length ? parsed : EXAMPLE;
  } catch {
    return EXAMPLE;
  }
}

export default function InventoryAnalyzer() {
  const { t, tryT, tp, n, role: roleLabel } = useT();
  const { stage } = useFantasyStage();
  const [rules, setRules] = useState<FantasyRules | null>(null);
  const [inventory, setInventory] = useState<Emblem[]>(loadInventory);
  const [role, setRole] = useState("");
  const [result, setResult] = useState<InventoryResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.fantasyRules().then(setRules).catch((e) => setError((e as Error).message));
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(inventory));
    } catch {
      // приватный режим браузера — просто не сохраняем
    }
  }, [inventory]);

  // Пересчёт идёт сам: пауза нужна, чтобы правка нескольких эмблем подряд не
  // отправляла запрос на каждое нажатие.
  useEffect(() => {
    if (!inventory.length) {
      setResult(null);
      return;
    }
    let cancelled = false;
    setBusy(true);
    const timer = setTimeout(() => {
      api
        .inventory({ inventory, role: role || null, min_games: 5, stage })
        .then((r) => {
          if (!cancelled) {
            setResult(r);
            setError(null);
          }
        })
        .catch((e) => !cancelled && setError((e as Error).message))
        .finally(() => !cancelled && setBusy(false));
    }, 350);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [inventory, role, stage]);

  const statsByColor = useMemo(() => {
    const groups: Record<string, FantasyRules["stats"]> = { red: [], blue: [], green: [] };
    for (const stat of rules?.stats ?? []) groups[stat.color]?.push(stat);
    return groups;
  }, [rules]);

  const unavailable = useMemo(
    () =>
      new Set(
        (rules?.sources ?? [])
          .filter((s) => s.availability === "unavailable")
          .map((s) => s.stat),
      ),
    [rules],
  );

  const update = (index: number, patch: Partial<Emblem>) =>
    setInventory(inventory.map((e, i) => (i === index ? { ...e, ...patch } : e)));

  const remove = (index: number) =>
    setInventory(inventory.filter((_, i) => i !== index));

  const add = () =>
    setInventory([...inventory, { stat: "kills", quality: "tier_3", trait: null }]);

  const best = result?.fits[0];

  // Разница в пределах процента — это не преимущество, а разброс выборки.
  // Показывать одного победителя, когда данные не отличают его от следующих,
  // значит выдавать случайность за вывод.
  const TIE = 0.01;
  const tied = useMemo(() => {
    const fits = result?.fits ?? [];
    if (!fits.length) return [];
    const top = fits[0].expected_card_points;
    return fits.slice(1).filter((f) => f.expected_card_points >= top * (1 - TIE));
  }, [result]);

  const runnersUp = (result?.fits ?? []).slice(1, 3);

  /** Отставание от лидера — процент честнее, чем разница в очках. */
  const behind = (fit: InventoryFit) => {
    const top = result?.fits[0]?.expected_card_points ?? 0;
    if (!top) return "";
    return t("inventory.behind", { percent: n((1 - fit.expected_card_points / top) * 100, 1) });
  };

  const bestByRole = useMemo(() => {
    const map = new Map<string, InventoryFit>();
    for (const fit of result?.fits ?? []) if (!map.has(fit.role)) map.set(fit.role, fit);
    return [...map.values()];
  }, [result]);

  const chartData = (result?.fits ?? []).slice(0, 12).map((fit) => ({
    name: `${fit.team_name ?? fit.team_id} · ${roleLabel(fit.role)}`,
    points: Math.round(fit.period_mean ?? fit.expected_card_points),
    role: fit.role,
  }));

  const roleColor: Record<string, string> = {
    core: "var(--group-red)",
    mid: "var(--group-blue)",
    support: "var(--group-green)",
  };

  return (
    <div className="space-y-4">
      <Panel
        title={t("inventory.title")}
        subtitle={t("inventory.subtitle")}
        actions={
          <div className="flex flex-wrap items-end gap-3">
            <Field label={t("common.role")}>
              <select
                className={selectClass}
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                <option value="">{t("role.all")}</option>
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {roleLabel(r)}
                  </option>
                ))}
              </select>
            </Field>
            <Button onClick={add}>{t("inventory.add")}</Button>
          </div>
        }
      >
        <div className="space-y-2">
          {inventory.map((emblem, index) => (
            <div
              key={index}
              className="flex flex-wrap items-center gap-2 rounded border border-[#20232c] bg-[#1a1d24] px-3 py-2"
            >
              <span
                aria-hidden
                className="h-6 w-[3px] rounded"
                style={{
                  background:
                    GROUP_COLOR[
                      rules?.stats.find((s) => s.key === emblem.stat)?.color ?? "red"
                    ],
                }}
              />
              <select
                className={selectClass}
                value={emblem.stat}
                onChange={(e) => update(index, { stat: e.target.value })}
                aria-label={t("common.stat")}
              >
                {/* Цвет эмблемы = цвет слота, куда её вообще можно поставить.
                    Без группировки непонятно, почему GPM не подходит саппорту. */}
                {(["red", "blue", "green"] as const).map((color) => (
                  <optgroup key={color} label={t(`color.${color}`)}>
                    {statsByColor[color]?.map((stat) => (
                      <option key={stat.key} value={stat.key}>
                        {stat.label}
                        {unavailable.has(stat.key) ? t("inventory.noStat") : ""}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
              <select
                className={selectClass}
                value={emblem.quality}
                onChange={(e) => update(index, { quality: e.target.value })}
                aria-label={t("common.quality")}
              >
                {QUALITIES.map((q) => (
                  <option key={q} value={q}>
                    {QUALITY_LABEL[q]} (+{Math.round((rules?.qualities[q] ?? 0) * 100)}%)
                  </option>
                ))}
              </select>
              <select
                className={selectClass}
                value={emblem.trait ?? ""}
                onChange={(e) => update(index, { trait: e.target.value || null })}
                aria-label={t("common.trait")}
              >
                <option value="">{t("trait.noneOption")}</option>
                {TRAITS.map((trait) => (
                  <option
                    key={trait}
                    value={trait}
                    title={tryT(`trait.${trait}.description`, trait)}
                  >
                    {TRAIT_LABEL[trait]}
                  </option>
                ))}
              </select>
              {unavailable.has(emblem.stat) && (
                <span className="text-[11px] text-amber-300">
                  {t("inventory.zeroStat")}
                </span>
              )}
              <button
                onClick={() => remove(index)}
                className="ml-auto rounded border border-[#2C3138] px-2 py-1 text-[11px] text-neutral-500 hover:border-red-900 hover:text-red-300"
              >
                {t("common.remove")}
              </button>
            </div>
          ))}
        </div>

        {!inventory.length && (
          <div className="mt-3">
            <Notice>{t("inventory.empty")}</Notice>
          </div>
        )}

        {error && (
          <div className="mt-3">
            <Notice kind="error">{error}</Notice>
          </div>
        )}

        {result && Object.keys(result.gaps).length > 0 && (
          <div className="mt-3">
            <Notice kind="warn">
              {Object.entries(result.gaps).map(([roleKey, gaps]) => (
                <div key={roleKey}>
                  {t("inventory.gap", {
                    role: roleLabel(roleKey),
                    gaps: gaps.join(", "),
                  })}
                </div>
              ))}
            </Notice>
          </div>
        )}
      </Panel>

      {best && (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
          <Panel title={t("inventory.topTitle")} subtitle={t("inventory.topSubtitle")}>
            <div className="mb-3 flex items-center gap-3">
              {teamCrest(best.team_name) && (
                <img
                  src={teamCrest(best.team_name)!}
                  alt=""
                  className="h-10 w-10 object-contain"
                />
              )}
              <div className="flex gap-2">
                {best.player_names.map((nick) => (
                  <PlayerPortrait key={nick} teamName={best.team_name} nickname={nick} />
                ))}
              </div>
              <div>
                <div className="text-sm text-neutral-200">{best.team_name}</div>
                <div className="text-[11px] text-neutral-500">
                  {roleLabel(best.role)} · {best.player_names.join(" & ")} ·{" "}
                  {tp("plural.maps", best.games)}
                </div>
              </div>
            </div>

            <div className="space-y-2">
              {best.slots.map((slot) => (
                <EmblemCard key={slot.slot} slot={slot} />
              ))}
            </div>

            <div className="mt-3 grid grid-cols-3 gap-2">
              <Stat label={t("common.perMap")} value={n(best.expected_card_points)} />
              <Stat
                label={t("common.perPeriod")}
                value={best.period_mean ? n(best.period_mean) : "—"}
                hint={t("common.topTwoMaps")}
              />
              <Stat
                label={t("common.ceiling")}
                value={best.period_ceiling ? n(best.period_ceiling) : "—"}
              />
            </div>

            {/* Второй и третий вариант — рядом, а не под катом: разница между
                ними обычно внутри процента, и показывать одного победителя
                значит выдавать разброс выборки за вывод. */}
            {runnersUp.map((fit, index) => (
              <div
                key={`${fit.team_id}-${fit.role}`}
                className="mt-2 flex items-center gap-3 rounded border border-[#20232c] bg-[#1a1d24] px-3 py-2"
              >
                <span className="w-3 text-[11px] text-neutral-600">{index + 2}</span>
                {teamCrest(fit.team_name) && (
                  <img
                    src={teamCrest(fit.team_name)!}
                    alt=""
                    className="h-6 w-6 shrink-0 object-contain"
                  />
                )}
                <div className="min-w-0 flex-1">
                  <div className="truncate text-xs text-neutral-200">
                    {fit.team_name} · {roleLabel(fit.role)}
                  </div>
                  <div className="truncate text-[11px] text-neutral-500">
                    {fit.slots.map((s) => s.label).join(" → ")}
                  </div>
                </div>
                <div className="shrink-0 text-right">
                  <div className="tabular text-xs text-neutral-300">
                    {n(fit.expected_card_points)}
                  </div>
                  <div className="text-[11px] text-neutral-500">
                    {behind(fit)} · {tp("plural.maps", fit.games)}
                  </div>
                </div>
              </div>
            ))}

            {tied.length > 0 && (
              <p className="mt-3 rounded border border-[#3A4048] bg-[#1C1F24] px-3 py-2 text-[11px] leading-relaxed text-neutral-300">
                {t("inventory.tied", {
                  // Склонение — через tp: «2 варианта», а не «2 вариант(ов)».
                  count: tp("plural.options", tied.length),
                  teams: tied
                    .slice(0, 3)
                    .map((f) => `${f.team_name} (${f.games})`)
                    .join(", "),
                })}
              </p>
            )}

            {best.unused.length > 0 && (
              <p className="mt-3 text-[11px] text-neutral-500">
                {t("inventory.unused", {
                  stats: best.unused.map((e) => e.stat).join(", "),
                })}
              </p>
            )}
          </Panel>

          <div className="space-y-4">
            <Panel
              title={t("inventory.chartTitle")}
              subtitle={t("inventory.chartSubtitle")}
            >
              <ResponsiveContainer width="100%" height={Math.max(220, chartData.length * 26)}>
                <BarChart data={chartData} layout="vertical" margin={{ left: 30 }}>
                  <XAxis type="number" stroke="#7C858F" fontSize={11} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    stroke="#9AA3AE"
                    fontSize={10}
                    width={190}
                  />
                  <Tooltip
                    cursor={{ fill: "rgba(255,255,255,0.04)" }}
                    {...chartTooltip}
                    formatter={(value) => n(Number(value))}
                  />
                  <Bar dataKey="points" radius={[0, 3, 3, 0]}>
                    {chartData.map((row, i) => (
                      <Cell key={i} fill={roleColor[row.role]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Panel>

            {bestByRole.length > 1 && (
              <Panel
                title={t("inventory.byRoleTitle")}
                subtitle={t("inventory.byRoleSubtitle")}
              >
                <table className="w-full text-xs">
                  <thead className="text-[11px] tracking-wide text-neutral-500 uppercase">
                    <tr>
                      <th className="py-1 text-left">{t("common.role")}</th>
                      <th className="py-1 text-left">{t("inventory.pair")}</th>
                      <th className="py-1 text-left">{t("inventory.layout")}</th>
                      <th className="py-1 text-right">{t("common.perPeriod")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bestByRole.map((fit) => (
                      <tr key={fit.role} className="border-t border-[#20232c]">
                        <td className="py-1 text-neutral-300">{roleLabel(fit.role)}</td>
                        <td className="py-1 text-neutral-200">
                          {fit.team_name} · {fit.player_names.join(", ")}
                        </td>
                        <td className="py-1 text-neutral-500">
                          {fit.slots.map((s) => s.label).join(" → ")}
                        </td>
                        <td className="tabular py-1 text-right text-[#c8a24a]">
                          {n(fit.period_mean ?? fit.expected_card_points)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Panel>
            )}

            <Panel
              title={t("inventory.fullTitle")}
              subtitle={
                busy
                  ? t("inventory.recalculating")
                  : tp("plural.options", result?.fits.length ?? 0)
              }
            >
              <table className="w-full text-xs">
                <thead className="text-[11px] tracking-wide text-neutral-500 uppercase">
                  <tr>
                    <th className="py-1 text-left">{t("common.team")}</th>
                    <th className="py-1 text-left">{t("common.role")}</th>
                    <th className="py-1 text-left">{t("common.players")}</th>
                    <th className="py-1 text-right">{t("common.perMap")}</th>
                    <th className="py-1 text-right">{t("common.mapsShort")}</th>
                  </tr>
                </thead>
                <tbody>
                  {(result?.fits ?? []).map((fit, i) => (
                    <tr
                      key={`${fit.team_id}-${fit.role}`}
                      className={`border-t border-[#20232c] ${
                        i === 0 ? "text-[#c8a24a]" : "text-neutral-300"
                      }`}
                    >
                      <td className="py-1">
                        <span className="flex items-center gap-2">
                          {teamCrest(fit.team_name) && (
                            <img
                              src={teamCrest(fit.team_name)!}
                              alt=""
                              className="h-4 w-4 object-contain"
                            />
                          )}
                          {fit.team_name}
                        </span>
                      </td>
                      <td className="py-1 text-neutral-500">{roleLabel(fit.role)}</td>
                      <td className="py-1 text-neutral-500">{fit.player_names.join(", ")}</td>
                      <td className="tabular py-1 text-right">
                        {n(fit.expected_card_points)}
                      </td>
                      <td className="tabular py-1 text-right text-neutral-500">{fit.games}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Panel>
          </div>
        </div>
      )}
    </div>
  );
}
