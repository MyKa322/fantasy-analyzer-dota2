import { useEffect, useState } from "react";
import {
  api,
  type BannerOption,
  type Emblem,
  type FantasyRules,
  type Projection,
  type Team,
  type TeamRoles,
} from "../api";
import { ROLES } from "../assets";
import { useT } from "../i18n";
import { Button, COLOR_CLASS, Field, Notice, Panel, Stat, selectClass } from "./ui";

function emptyEmblem(stat: string): Emblem {
  return { stat, quality: "tier_3", trait: null };
}

export default function FantasyPanel() {
  const { t, n, role: roleLabel } = useT();
  const [rules, setRules] = useState<FantasyRules | null>(null);
  const [teams, setTeams] = useState<Team[]>([]);
  const [teamId, setTeamId] = useState<number | null>(null);
  const [role, setRole] = useState("core");
  const [roles, setRoles] = useState<TeamRoles | null>(null);
  const [emblems, setEmblems] = useState<Emblem[]>([]);
  const [projection, setProjection] = useState<Projection | null>(null);
  const [options, setOptions] = useState<BannerOption[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.fantasyRules().then((loaded) => {
      setRules(loaded);
      setEmblems([emptyEmblem("kills"), emptyEmblem("gpm"), emptyEmblem("creep_score")]);
    });
    api.teams().then((loaded) => {
      setTeams(loaded);
      if (loaded.length > 0) setTeamId(loaded[0].team_id);
    });
  }, []);

  useEffect(() => {
    if (teamId == null) return;
    setRoles(null);
    api
      .teamRoles(teamId, 365)
      .then(setRoles)
      .catch(() => setRoles(null));
  }, [teamId]);

  const unavailable = new Set(
    rules?.sources.filter((s) => s.availability === "unavailable").map((s) => s.stat) ?? [],
  );
  const approximate = new Set(
    rules?.sources.filter((s) => s.availability === "approximate").map((s) => s.stat) ?? [],
  );

  const updateEmblem = (index: number, patch: Partial<Emblem>) => {
    setEmblems((current) =>
      current.map((emblem, i) => (i === index ? { ...emblem, ...patch } : emblem)),
    );
  };

  const project = async () => {
    if (teamId == null) return;
    setBusy(true);
    setError(null);
    try {
      setProjection(
        await api.project({
          team_id: teamId,
          role,
          banner: { emblems },
          simulations: 5000,
          history_days: 365,
        }),
      );
    } catch (e) {
      setError((e as Error).message);
      setProjection(null);
    } finally {
      setBusy(false);
    }
  };

  const optimise = async () => {
    if (teamId == null) return;
    setBusy(true);
    setError(null);
    try {
      setOptions(
        await api.optimiseBanner({
          team_id: teamId,
          role,
          available_emblems: emblems,
          slots: Math.min(emblems.length, rules?.banner_slots ?? emblems.length),
          simulations: 2000,
          history_days: 365,
          top_n: 3,
        }),
      );
    } catch (e) {
      setError((e as Error).message);
      setOptions([]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <Panel
        title="War Banner"
        subtitle={t("fantasy.subtitle")}
        actions={
          <div className="flex items-end gap-3">
            <Field label={t("common.team")}>
              <select
                className={selectClass}
                value={teamId ?? ""}
                onChange={(e) => setTeamId(Number(e.target.value))}
              >
                {teams.map((team) => (
                  <option key={team.team_id} value={team.team_id}>
                    {team.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t("common.role")}>
              <select
                className={selectClass}
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {roleLabel(r)}
                  </option>
                ))}
              </select>
            </Field>
          </div>
        }
      >
        {roles && (
          <p className="mb-3 text-xs text-neutral-400">
            {t("fantasy.lineup")}{" "}
            {(roles.roles[role] ?? [])
              .map((id) => roles.player_names[String(id)] ?? id)
              .join(", ") || t("fantasy.lineupUnknown")}
          </p>
        )}

        <div className="space-y-2">
          {emblems.map((emblem, index) => (
            <div
              key={index}
              className="grid grid-cols-[1.5fr_1fr_1fr_auto] items-end gap-2 rounded border border-[#2a2e3a] bg-[#1d2029] p-2"
            >
              <Field label={t("fantasy.slot", { n: index + 1 })}>
                <select
                  className={selectClass}
                  value={emblem.stat}
                  onChange={(e) => updateEmblem(index, { stat: e.target.value })}
                >
                  {rules?.stats.map((stat) => (
                    <option key={stat.key} value={stat.key}>
                      {stat.label}
                      {unavailable.has(stat.key) ? t("fantasy.noData") : ""}
                      {approximate.has(stat.key) ? t("fantasy.approximate") : ""}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label={t("common.quality")}>
                <select
                  className={selectClass}
                  value={emblem.quality}
                  onChange={(e) => updateEmblem(index, { quality: e.target.value })}
                >
                  {Object.entries(rules?.qualities ?? {}).map(([key, bonus]) => (
                    <option key={key} value={key}>
                      {key.replace("tier_", "Tier ")} (+{Math.round(bonus * 100)}%)
                    </option>
                  ))}
                </select>
              </Field>
              <Field label={t("common.trait")}>
                <select
                  className={selectClass}
                  value={emblem.trait ?? ""}
                  onChange={(e) =>
                    updateEmblem(index, { trait: e.target.value || null })
                  }
                >
                  <option value="">—</option>
                  {rules?.traits.map((trait) => (
                    <option key={trait.key} value={trait.key}>
                      {trait.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Button
                variant="danger"
                onClick={() => setEmblems(emblems.filter((_, i) => i !== index))}
              >
                {t("common.remove")}
              </Button>
            </div>
          ))}
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            variant="ghost"
            onClick={() => setEmblems([...emblems, emptyEmblem("stuns")])}
            disabled={emblems.length >= (rules?.banner_slots ?? 5)}
          >
            {t("fantasy.addEmblem")}
          </Button>
          <Button onClick={project} disabled={busy || emblems.length === 0}>
            {busy ? t("common.calculating") : t("fantasy.project")}
          </Button>
          <Button variant="ghost" onClick={optimise} disabled={busy || emblems.length < 2}>
            {t("fantasy.optimise")}
          </Button>
        </div>

        {error && (
          <div className="mt-3">
            <Notice kind="error">{error}</Notice>
          </div>
        )}
      </Panel>

      {projection && (
        <Panel
          title={t("fantasy.projectionTitle")}
          subtitle={t("fantasy.projectionSubtitle")}
        >
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <Stat label={t("common.expectation")} value={n(projection.mean)} />
            <Stat label={t("common.median")} value={n(projection.median)} />
            <Stat label={t("fantasy.floor")} value={n(projection.floor_p5)} />
            <Stat label={t("fantasy.ceiling")} value={n(projection.ceiling_p95)} />
            <Stat label={t("fantasy.sample")} value={projection.games_used} />
          </div>
          {projection.unavailable_stats.length > 0 && (
            <div className="mt-3">
              <Notice kind="warn">
                {t("fantasy.unavailable", {
                  stats: projection.unavailable_stats.join(", "),
                })}
              </Notice>
            </div>
          )}
        </Panel>
      )}

      {options.length > 0 && (
        <Panel
          title={t("fantasy.optionsTitle")}
          subtitle={t("fantasy.optionsSubtitle")}
        >
          <div className="space-y-2">
            {options.map((option, index) => (
              <div
                key={index}
                className="flex flex-wrap items-center justify-between gap-3 rounded border border-[#2a2e3a] bg-[#1d2029] px-3 py-2"
              >
                <div className="flex flex-wrap gap-2">
                  {option.emblems.map((emblem, i) => {
                    const stat = rules?.stats.find((s) => s.key === emblem.stat);
                    return (
                      <span key={i} className="text-xs">
                        <span className={COLOR_CLASS[stat?.color ?? "red"]}>
                          {stat?.label ?? emblem.stat}
                        </span>
                        <span className="text-neutral-500">
                          {" "}
                          {emblem.quality.replace("tier_", "T")}
                          {emblem.trait ? `/${emblem.trait}` : ""}
                        </span>
                      </span>
                    );
                  })}
                </div>
                <div className="tabular text-sm text-[#c8a24a]">
                  {n(option.mean)}
                  <span className="ml-2 text-xs text-neutral-500">
                    p95 {n(option.ceiling_p95)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      )}

      {rules && (
        <Panel
          title={t("fantasy.tableTitle")}
          subtitle={t("fantasy.tableSubtitle", {
            version: rules.version,
            source: rules.source,
          })}
        >
          <div className="grid gap-x-6 gap-y-1 text-xs sm:grid-cols-2 lg:grid-cols-3">
            {rules.stats.map((stat) => {
              const source = rules.sources.find((s) => s.stat === stat.key);
              return (
                <div
                  key={stat.key}
                  className="flex items-baseline justify-between border-b border-[#20232c] py-1"
                >
                  <span className={COLOR_CLASS[stat.color]}>
                    {stat.label}
                    {source?.availability === "unavailable" && (
                      <span className="ml-1 text-neutral-600" title={source.note}>
                        {t("fantasy.noDataShort")}
                      </span>
                    )}
                    {source?.availability === "approximate" && (
                      <span className="ml-1 text-neutral-600" title={source.note}>
                        {t("fantasy.approximateShort")}
                      </span>
                    )}
                  </span>
                  <span className="tabular text-neutral-300">
                    {stat.kind === "linear"
                      ? `${stat.base} / ${stat.per_unit}`
                      : stat.kind === "flat"
                        ? stat.value_if_true
                        : stat.kind === "capped"
                          ? t("fantasy.upTo", { n: stat.max_points ?? 0 })
                          : stat.per_unit}
                  </span>
                </div>
              );
            })}
          </div>
        </Panel>
      )}
    </div>
  );
}
