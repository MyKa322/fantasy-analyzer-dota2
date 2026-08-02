import { useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import RouteOverlay from '../components/RouteOverlay.jsx';
import TeamCrest from '../components/TeamCrest.jsx';
import PlayerPortrait from '../components/PlayerPortrait.jsx';
import Button from '../components/Button.jsx';
import { ROLES } from '../data/scoring.js';
import { TEAMS } from '../data/teams.js';
import { playersFor } from '../data/players.js';
import { scoreRole, fmtPoints } from '../engine/scoring.js';
import { usedTeamKeys } from '../state/lineup.js';

/**
 * TeamPicker — /build/:role/team
 *
 * A plain grid of all 16 teams, in seed order. No ranking and no
 * recommendation: the user chooses. Each card shows the players it supplies
 * for this role and what that team currently projects, so the choice is
 * informed without being made for them.
 */
export default function TeamPicker({ lineup, onCommit }) {
  const { role } = useParams();
  const navigate = useNavigate();
  const roleKey = ROLES[role] ? role : 'core';
  const entry = lineup[roleKey];

  const [choice, setChoice] = useState(entry.teamKey);

  // Every team is selectable for every role, including one already used
  // elsewhere — a full single-team lineup is a legitimate configuration.
  // Where a team is already in use we say so, but never block it.
  const usedElsewhere = usedTeamKeys(lineup, roleKey);

  const cards = useMemo(
    () =>
      TEAMS.map((team) => {
        const players = playersFor(team.key, roleKey);
        return {
          team,
          players,
          total: scoreRole(entry.banner, players).total,
          alsoUsed: usedElsewhere.includes(team.key),
        };
      }),
    [roleKey, entry.banner, usedElsewhere.join(',')]
  );

  const commit = () => {
    if (choice !== entry.teamKey) onCommit?.(roleKey, choice);
    navigate('/build', { replace: true });
  };

  return (
    <RouteOverlay title={`${ROLES[roleKey].label} team`} size="full">
      <p
        className="mb-5"
        style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--text-sm)' }}
      >
        Projections use your current {ROLES[roleKey].label.toLowerCase()} banner. Any
        team can be used for any number of roles.
      </p>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
        {cards.map(({ team, players, total, alsoUsed }) => {
          const selected = choice === team.key;
          return (
            <button
              key={team.key}
              type="button"
              onClick={() => setChoice(team.key)}
              aria-pressed={selected}
              className="flex cursor-pointer flex-col overflow-hidden rounded-md border text-left transition-[background-color,border-color] duration-fast hover:bg-bg-hover"
              style={{
                background: selected ? 'var(--color-bg-raised)' : 'var(--color-bg-card)',
                borderColor: selected ? 'var(--n-050)' : 'var(--color-border)',
              }}
            >
              <span className="flex items-center gap-2 p-3">
                <TeamCrest crestFile={team.crestFile} name={team.name} size={28} dim={!selected} />
                <span className="min-w-0 flex-1">
                  <span
                    className="block truncate font-medium"
                    style={{ color: 'var(--color-text-heading)', fontSize: 'var(--text-xs)' }}
                  >
                    {team.name}
                  </span>
                  {alsoUsed && (
                    <span
                      className="block truncate"
                      style={{ color: 'var(--color-text-tertiary)', fontSize: 'var(--text-2xs)' }}
                    >
                      In use elsewhere
                    </span>
                  )}
                </span>
              </span>

              <span className="flex" style={{ background: 'var(--n-950)' }}>
                {players.map((p) => (
                  <PlayerPortrait
                    key={p.slug}
                    teamDir={p.teamDir}
                    name={p.name}
                    height={92}
                    className="min-w-0 flex-1"
                  />
                ))}
              </span>

              <span className="flex items-baseline justify-between gap-2 p-3">
                <span className="min-w-0 truncate" style={{ color: 'var(--color-text-tertiary)', fontSize: 'var(--text-2xs)' }}>
                  {players.map((p) => p.name).join(', ')}
                </span>
                <span data-num style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--text-xs)' }}>
                  {fmtPoints(total)}
                </span>
              </span>
            </button>
          );
        })}
      </div>

      <div className="mt-6 flex justify-end gap-2">
        <Button variant="ghost" onClick={() => navigate('/build', { replace: true })}>
          Cancel
        </Button>
        <Button variant="primary" onClick={commit} disabled={choice === entry.teamKey}>
          Select
        </Button>
      </div>
    </RouteOverlay>
  );
}
