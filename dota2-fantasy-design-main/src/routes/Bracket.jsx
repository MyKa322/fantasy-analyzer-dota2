import { useMemo, useState } from 'react';
import TeamCrest from '../components/TeamCrest.jsx';
import ModelledDataBadge from '../components/ModelledDataBadge.jsx';
import { TEAMS } from '../data/teams.js';

/**
 * Bracket — the 16-team group stage laid out as outcome bands.
 *
 * Same grid as the client: eight columns, two rows, with band labels spanning
 * 1 / 2 / 5 columns above and 5 / 2 / 1 below. Rebuilt flat and minimal.
 *
 * Cards are selectable so this doubles as the base for a predictions view —
 * `selected` is local state here; lift it out and hand it a real prediction
 * model when you wire that up.
 */

/** Top row spans, left to right. Sums to 8. */
const TOP_BANDS = [
  { key: 'undefeated', span: 1, label: '4–0', note: 'One undefeated team' },
  { key: 'four-one',   span: 2, label: '4–1', note: 'Two teams with 4 wins and 1 loss' },
  { key: 'elim-win',   span: 5, label: 'Elimination round winner', note: 'Five teams that win in the elimination round' },
];

/** Bottom row spans, left to right. Sums to 8. */
const BOTTOM_BANDS = [
  { key: 'elim-loss', span: 5, label: 'Elimination round loser', note: 'Five teams that lose in the elimination round' },
  { key: 'one-four',  span: 2, label: '1–4', note: 'Two teams with 1 win and 4 losses' },
  { key: 'winless',   span: 1, label: '0–4', note: 'One unvictorious team' },
];

export default function Bracket() {
  const [selected, setSelected] = useState(null);

  const byBand = useMemo(() => {
    const map = {};
    for (const t of TEAMS) (map[t.band] ||= []).push(t);
    return map;
  }, []);

  const topTeams = TOP_BANDS.flatMap((b) => byBand[b.key] ?? []);
  const bottomTeams = BOTTOM_BANDS.flatMap((b) => byBand[b.key] ?? []);

  return (
    <div className="mx-auto w-full px-4 py-6 md:py-8" style={{ maxWidth: 'var(--width-page)' }}>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 style={{ fontSize: 'var(--text-xl)' }}>Group stage</h1>
          <p className="mt-1" style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--text-sm)' }}>
            Sixteen teams by outcome. Select a card to mark a prediction.
          </p>
        </div>
        <ModelledDataBadge compact />
      </div>

      {/* The grid scrolls horizontally on narrow screens rather than
          collapsing — the eight-column shape is the information. */}
      <div className="-mx-4 overflow-x-auto px-4 pb-2">
        <div className="min-w-[760px]">
          <BandRow bands={TOP_BANDS} position="top" />

          <div className="grid grid-cols-8 gap-2">
            {topTeams.map((t) => (
              <TeamCell
                key={t.key}
                team={t}
                selected={selected === t.key}
                onSelect={() => setSelected(selected === t.key ? null : t.key)}
              />
            ))}
          </div>

          <div className="my-2 grid grid-cols-8 gap-2">
            {bottomTeams.map((t) => (
              <TeamCell
                key={t.key}
                team={t}
                selected={selected === t.key}
                onSelect={() => setSelected(selected === t.key ? null : t.key)}
              />
            ))}
          </div>

          <BandRow bands={BOTTOM_BANDS} position="bottom" />
        </div>
      </div>
    </div>
  );
}

/** Band labels, spanning their columns and bracketed by hairlines. */
function BandRow({ bands, position }) {
  const isTop = position === 'top';
  return (
    <div className={`grid grid-cols-8 gap-2 ${isTop ? 'mb-2' : 'mt-2'}`}>
      {bands.map((b) => (
        <div
          key={b.key}
          className={`flex flex-col ${isTop ? 'justify-end' : 'justify-start'} px-1`}
          style={{ gridColumn: `span ${b.span} / span ${b.span}` }}
        >
          {!isTop && <div className="mb-2 h-px w-full" style={{ background: 'var(--color-border)' }} />}
          <div className="label text-center" style={{ color: 'var(--color-text-secondary)' }}>
            {b.label}
          </div>
          <div
            className="mt-0.5 text-center"
            style={{ color: 'var(--color-text-tertiary)', fontSize: 'var(--text-2xs)' }}
          >
            {b.note}
          </div>
          {isTop && <div className="mt-2 h-px w-full" style={{ background: 'var(--color-border)' }} />}
        </div>
      ))}
    </div>
  );
}

function TeamCell({ team, selected, onSelect }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className="flex flex-col items-center gap-3 rounded-md border p-3 transition-[background-color,border-color] duration-fast hover:bg-bg-hover"
      style={{
        background: selected ? 'var(--color-bg-raised)' : 'var(--color-bg-card)',
        borderColor: selected ? 'var(--n-050)' : 'var(--color-border)',
      }}
    >
      <TeamCrest crestFile={team.crestFile} name={team.name} size={56} dim={!selected} />
      <span
        className="w-full truncate text-center"
        style={{
          color: selected ? 'var(--color-text-heading)' : 'var(--color-text-secondary)',
          fontSize: 'var(--text-2xs)',
          fontWeight: 'var(--weight-medium)',
        }}
      >
        {team.name}
      </span>
    </button>
  );
}
