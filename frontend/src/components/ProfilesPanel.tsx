import { useEffect, useMemo, useState } from "react";
import { api, type PlayerListItem, type TeamListItem } from "../api";
import { ROLE_LABEL, teamCrest } from "../assets";
import PlayerPortrait from "./PlayerPortrait";
import PlayerPage from "./PlayerPage";
import TeamPage from "./TeamPage";
import { games } from "../profiles";
import { Field, Notice, Panel, selectClass } from "./ui";

type View =
  | { kind: "list" }
  | { kind: "team"; id: number }
  | { kind: "player"; id: number };

export default function ProfilesPanel() {
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
        title="Команды и игроки"
        subtitle="Страница любой команды и любого игрока из базы: матчи, средние, герои, рейтинг — и наш анализ по ним. Данные — разобранные матчи OpenDota за последние полгода."
        actions={
          <div className="flex flex-wrap items-end gap-3">
            <Field label="Поиск">
              <input
                className={selectClass}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="ник или команда"
              />
            </Field>
            <Field label="Кого показывать">
              <select
                className={selectClass}
                value={scope}
                onChange={(e) => setScope(e.target.value)}
              >
                <option value="ti">Только TI15</option>
                <option value="all">Всех из базы</option>
              </select>
            </Field>
          </div>
        }
      >
        {error && <Notice kind="error">{error}</Notice>}
        {loading && !error && <Notice>Загружаю профили…</Notice>}
        {!loading && !error && (
          <p className="text-xs text-neutral-500">
            Команд: {shownTeams.length}, игроков: {shownPlayers.length}. Соперники по
            квалификациям попадают в базу вместе с матчами участников, поэтому список шире
            шестнадцати команд.
          </p>
        )}
      </Panel>

      {shownTeams.length > 0 && (
        <Panel title="Команды">
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
                      {games(team.games)}
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
        <Panel title="Игроки">
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
                    {player.team_name ?? "без команды"}
                    {player.role && ` · ${ROLE_LABEL[player.role] ?? player.role}`}
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
              Показаны первые 150 — уточните поиск.
            </p>
          )}
        </Panel>
      )}
    </div>
  );
}
