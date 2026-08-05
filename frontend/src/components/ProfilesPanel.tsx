import { useEffect, useMemo, useState } from "react";
import { api, type PlayerListItem, type TeamListItem } from "../api";
import { teamCrest } from "../assets";
import { useT } from "../i18n";
import PlayerPortrait from "./PlayerPortrait";
import PlayerPage from "./PlayerPage";
import TeamPage from "./TeamPage";
import { Field, Notice, Panel, selectClass } from "./ui";

type View =
  | { kind: "list" }
  | { kind: "team"; id: number }
  | { kind: "player"; id: number };

export default function ProfilesPanel() {
  const { t, tp, role: roleLabel } = useT();
  const [view, setView] = useState<View>({ kind: "list" });
  const [teams, setTeams] = useState<TeamListItem[]>([]);
  const [players, setPlayers] = useState<PlayerListItem[]>([]);
  const [query, setQuery] = useState("");
  const [scope, setScope] = useState("ti");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.profileTeams(), api.profilePlayers()])
      .then(([loadedTeams, loadedPlayers]) => {
        setTeams(loadedTeams);
        setPlayers(loadedPlayers);
      })
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, []);

  const needle = query.trim().toLowerCase();
  const onlyTi = scope === "ti";

  const shownTeams = useMemo(
    () =>
      teams.filter(
        (team) =>
          (!onlyTi || team.is_ti) &&
          (!needle || team.name.toLowerCase().includes(needle)),
      ),
    [teams, needle, onlyTi],
  );

  const shownPlayers = useMemo(
    () =>
      players.filter(
        (player) =>
          (!onlyTi || player.is_ti) &&
          (!needle ||
            (player.name ?? "").toLowerCase().includes(needle) ||
            (player.team_name ?? "").toLowerCase().includes(needle)),
      ),
    [players, needle, onlyTi],
  );

  if (view.kind === "team") {
    return (
      <TeamPage
        teamId={view.id}
        onBack={() => setView({ kind: "list" })}
        onOpenPlayer={(id) => setView({ kind: "player", id })}
        onOpenTeam={(id) => setView({ kind: "team", id })}
      />
    );
  }

  if (view.kind === "player") {
    return (
      <PlayerPage
        accountId={view.id}
        onBack={() => setView({ kind: "list" })}
        onOpenTeam={(id) => setView({ kind: "team", id })}
      />
    );
  }

  return (
    <div className="space-y-4">
      <Panel
        title={t("profiles.title")}
        subtitle={t("profiles.subtitle")}
        actions={
          <div className="flex flex-wrap items-end gap-3">
            <Field label={t("profiles.search")}>
              <input
                className={selectClass}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t("profiles.searchPlaceholder")}
              />
            </Field>
            <Field label={t("profiles.scope")}>
              <select
                className={selectClass}
                value={scope}
                onChange={(e) => setScope(e.target.value)}
              >
                <option value="ti">{t("profiles.scopeTi")}</option>
                <option value="all">{t("profiles.scopeAll")}</option>
              </select>
            </Field>
          </div>
        }
      >
        {error && <Notice kind="error">{error}</Notice>}
        {loading && !error && <Notice>{t("profiles.loading")}</Notice>}
        {!loading && !error && (
          <p className="text-xs text-neutral-500">
            {t("profiles.counts", {
              teams: shownTeams.length,
              players: shownPlayers.length,
            })}
          </p>
        )}
      </Panel>

      {shownTeams.length > 0 && (
        <Panel title={t("common.teams")}>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {shownTeams.map((team) => {
              const crest = teamCrest(team.name);
              return (
                <button
                  key={team.team_id}
                  onClick={() => setView({ kind: "team", id: team.team_id })}
                  className="flex items-center gap-3 rounded border border-[#20232c] bg-[#1a1d24] px-3 py-2 text-left hover:border-[#c8a24a]"
                >
                  {crest ? (
                    <img src={crest} alt="" className="h-8 w-8 object-contain" />
                  ) : (
                    <span className="flex h-8 w-8 items-center justify-center rounded border border-[#2C3138] text-[10px] text-neutral-500">
                      {(team.tag ?? team.name).slice(0, 3)}
                    </span>
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm text-neutral-100">{team.name}</div>
                    <div className="text-[11px] text-neutral-500">
                      {tp("plural.maps", team.games)}
                      {team.is_ti && <span className="ml-1 text-[#c8a24a]">· TI15</span>}
                    </div>
                  </div>
                  <div className="tabular text-right text-xs text-neutral-400">
                    {team.rating ? Math.round(team.rating) : "—"}
                  </div>
                </button>
              );
            })}
          </div>
        </Panel>
      )}

      {shownPlayers.length > 0 && (
        <Panel title={t("common.players")}>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {shownPlayers.slice(0, 150).map((player) => (
              <button
                key={player.account_id}
                onClick={() => setView({ kind: "player", id: player.account_id })}
                className="flex items-center gap-3 rounded border border-[#20232c] bg-[#1a1d24] px-3 py-2 text-left hover:border-[#c8a24a]"
              >
                <PlayerPortrait
                  teamName={player.team_name}
                  nickname={player.name ?? "?"}
                  size={32}
                />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm text-neutral-100">
                    {player.name ?? player.account_id}
                  </div>
                  <div className="truncate text-[11px] text-neutral-500">
                    {player.team_name ?? t("profiles.noTeam")}
                    {player.role && ` · ${roleLabel(player.role)}`}
                  </div>
                </div>
                <div className="tabular text-right text-xs text-neutral-500">
                  {player.games}
                </div>
              </button>
            ))}
          </div>
          {shownPlayers.length > 150 && (
            <p className="mt-2 text-[11px] text-neutral-500">
              {t("profiles.truncated")}
            </p>
          )}
        </Panel>
      )}
    </div>
  );
}
