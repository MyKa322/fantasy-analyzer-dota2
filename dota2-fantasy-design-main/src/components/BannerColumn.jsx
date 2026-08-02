import EmblemCard from './EmblemCard.jsx';
import TeamCrest from './TeamCrest.jsx';
import PlayerPortrait from './PlayerPortrait.jsx';
import CountUp from './CountUp.jsx';
import Button from './Button.jsx';
import { ROLES } from '../data/scoring.js';
import { emblemBreakdown, scoreRole, averageStats } from '../engine/scoring.js';

/**
 * BannerColumn — one role: its team, its players, its three emblems.
 *
 * Same structure as before (it works), rebuilt in the minimal language: flat
 * surface, hairline border, no ornament. The only colour is the team crest and
 * the three emblem rules.
 */
export default function BannerColumn({ roleKey, entry, onChangeTeam, onSelectEmblem }) {
  const role = ROLES[roleKey];
  const players = entry.players ?? [];
  const banner = entry.banner;

  const roleScore = scoreRole(banner, players);
  const avg = averageStats(players);
  const breakdowns = banner.map((_, i) => emblemBreakdown(banner, i, avg));

  return (
    <section
      className="flex flex-col overflow-hidden rounded-lg border"
      style={{ background: 'var(--color-bg-base)', borderColor: 'var(--color-border)' }}
      aria-label={`${role.label} banner`}
    >
      {/* ---- Identity ---------------------------------------------------- */}
      <header className="flex items-center gap-3 border-b p-4" style={{ borderColor: 'var(--color-border)' }}>
        <TeamCrest crestFile={entry.team?.crestFile} name={entry.team?.name} size={44} eager />

        <div className="min-w-0 flex-1">
          <div className="label">{role.label}</div>
          <div
            className="truncate font-medium"
            style={{ color: 'var(--color-text-heading)', fontSize: 'var(--text-base)' }}
          >
            {entry.team?.name}
          </div>
        </div>

        <Button size="sm" onClick={() => onChangeTeam?.(roleKey)}>
          Change
        </Button>
      </header>

      {/* ---- Players ------------------------------------------------------ */}
      <div className="flex gap-2 px-4 pt-3">
        {players.map((p) => (
          <span
            key={p.slug}
            className="min-w-0 flex-1 truncate"
            style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--text-sm)' }}
            title={`${p.name} · ${p.position}`}
          >
            {p.name}
            <span style={{ color: 'var(--color-text-tertiary)' }}> · {p.positionShort}</span>
          </span>
        ))}
      </div>

      {/* ---- Emblems ------------------------------------------------------ */}
      <div className="flex flex-col gap-2 p-4">
        {breakdowns.map((b, i) => (
          <EmblemCard key={i} breakdown={b} onClick={() => onSelectEmblem?.(roleKey, i)} />
        ))}
      </div>

      {/* ---- Role total --------------------------------------------------- */}
      <div
        className="flex items-baseline justify-between border-t px-4 py-3"
        style={{ borderColor: 'var(--color-border)' }}
      >
        <span className="label">{role.label} total</span>
        <CountUp
          value={roleScore.total}
          className="font-semibold"
          style={{ color: 'var(--color-text-heading)', fontSize: 'var(--text-xl)' }}
        />
      </div>

      {/* ---- Portraits ---------------------------------------------------- */}
      <div className="relative mt-auto flex" style={{ background: 'var(--n-950)' }}>
        {players.map((p) => (
          <PlayerPortrait
            key={p.slug}
            teamDir={p.teamDir}
            name={p.name}
            height={168}
            className="min-w-0 flex-1"
            eager
          />
        ))}
        {/* Soft fade into the card instead of a hard cut */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 top-0 h-16"
          style={{ background: 'linear-gradient(180deg, var(--color-bg-base) 0%, transparent 100%)' }}
        />
      </div>
    </section>
  );
}
