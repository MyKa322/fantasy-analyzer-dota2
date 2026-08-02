import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import RouteOverlay from '../components/RouteOverlay.jsx';
import EmblemIcon from '../components/EmblemIcon.jsx';
import EmblemCard from '../components/EmblemCard.jsx';
import Button from '../components/Button.jsx';
import { ROLES, EMBLEM_STATS, TIERS, TIER_KEYS, TRAITS, TRAIT_KEYS } from '../data/scoring.js';
import { emblemBreakdown, scoreRole, averageStats, fmtPoints } from '../engine/scoring.js';

/**
 * EmblemPicker — /build/:role/emblem/:slot
 *
 * Direct selection, not a roll. The user picks the data: any of the 18 emblem
 * icons, any tier, any trait.
 *
 * The slot's COLOUR is fixed and never changes — that's the constraint the
 * design is built around. Any icon can sit in any slot; the ring and rule stay
 * the slot's colour.
 */
export default function EmblemPicker({ lineup, onApply }) {
  const { role, slot } = useParams();
  const navigate = useNavigate();

  const roleKey = ROLES[role] ? role : 'core';
  const slotIndex = Math.min(Math.max(parseInt(slot, 10) - 1, 0), 2);
  const entry = lineup[roleKey];
  const group = ROLES[roleKey].slots[slotIndex];
  const avg = averageStats(entry.players);

  const [draft, setDraft] = useState(entry.banner[slotIndex]);

  const trial = entry.banner.map((e, i) => (i === slotIndex ? draft : e));
  const preview = emblemBreakdown(trial, slotIndex, avg);
  const now = scoreRole(entry.banner, entry.players).total;
  const next = scoreRole(trial, entry.players).total;
  const delta = next - now;

  const set = (patch) => setDraft((d) => ({ ...d, ...patch }));
  const apply = () => {
    onApply(roleKey, slotIndex, draft);
    navigate('/build', { replace: true });
  };

  const allStats = Object.keys(EMBLEM_STATS);

  return (
    <RouteOverlay title={`${ROLES[roleKey].label} · Slot ${slotIndex + 1}`} size="full">
      <div data-group={group} className="grid gap-8 lg:grid-cols-[300px_1fr]">
        {/* ---- Preview ---------------------------------------------------- */}
        <div className="flex flex-col gap-4">
          <div>
            <div className="label mb-2">Preview</div>
            <EmblemCard breakdown={preview} />
          </div>

          <dl className="flex flex-col gap-2 rounded-md border p-4" style={{ borderColor: 'var(--color-border)' }}>
            <Stat label={`${ROLES[roleKey].label} total`} value={fmtPoints(next)} strong />
            <Stat
              label="Change"
              value={`${delta > 0 ? '↑' : delta < 0 ? '↓' : ''} ${fmtPoints(Math.abs(delta))}`}
              muted={delta === 0}
            />
          </dl>

          <p style={{ color: 'var(--color-text-tertiary)', fontSize: 'var(--text-xs)' }}>
            This slot is fixed to the {group} colour. Any icon can be placed here —
            the colour does not change.
          </p>

          <div className="mt-auto flex gap-2">
            <Button variant="primary" onClick={apply} className="flex-1">
              Apply
            </Button>
            <Button variant="ghost" onClick={() => navigate('/build', { replace: true })}>
              Cancel
            </Button>
          </div>
        </div>

        {/* ---- Choices ----------------------------------------------------- */}
        <div className="flex flex-col gap-7">
          <Section title="Emblem" hint="All 18 available. Colour stays fixed to the slot.">
            <div className="grid grid-cols-[repeat(auto-fill,minmax(96px,1fr))] gap-2">
              {allStats.map((key) => {
                const s = EMBLEM_STATS[key];
                const active = draft.stat === key;
                return (
                  <button
                    key={key}
                    type="button"
                    onClick={() => set({ stat: key })}
                    aria-pressed={active}
                    className="flex flex-col items-center gap-2 rounded-md border p-2 transition-[background-color,border-color] duration-fast hover:bg-bg-hover"
                    style={{
                      background: active ? 'var(--group-dim)' : 'var(--color-bg-card)',
                      borderColor: active ? 'var(--group)' : 'var(--color-border)',
                    }}
                  >
                    <EmblemIcon asset={s.asset} size="var(--icon-tile-lg)" ring={false} />
                    <span
                      className="text-center leading-tight"
                      style={{
                        color: active ? 'var(--color-text-heading)' : 'var(--color-text-secondary)',
                        fontSize: 'var(--text-2xs)',
                      }}
                    >
                      {s.label}
                    </span>
                  </button>
                );
              })}
            </div>
          </Section>

          <Section title="Tier">
            <div className="flex flex-wrap gap-2">
              {TIER_KEYS.map((k) => (
                <Chip key={k} active={draft.tier === k} onClick={() => set({ tier: k })}>
                  {TIERS[k].label}
                  <span data-num style={{ color: 'var(--color-text-tertiary)' }}>
                    +{TIERS[k].bonus}%
                  </span>
                </Chip>
              ))}
            </div>
          </Section>

          <Section title="Trait">
            <div className="grid gap-2 sm:grid-cols-2">
              {TRAIT_KEYS.map((k) => {
                const active = draft.trait === k;
                return (
                  <button
                    key={k}
                    type="button"
                    onClick={() => set({ trait: k })}
                    aria-pressed={active}
                    className="rounded-md border p-3 text-left transition-[background-color,border-color] duration-fast hover:bg-bg-hover"
                    style={{
                      background: active ? 'var(--group-dim)' : 'var(--color-bg-card)',
                      borderColor: active ? 'var(--group)' : 'var(--color-border)',
                    }}
                  >
                    <span
                      className="block font-medium"
                      style={{ color: 'var(--color-text-heading)', fontSize: 'var(--text-sm)' }}
                    >
                      {TRAITS[k].label}
                    </span>
                    <span
                      className="mt-1 block"
                      style={{ color: 'var(--color-text-tertiary)', fontSize: 'var(--text-2xs)', lineHeight: 1.5 }}
                    >
                      {TRAITS[k].text}
                    </span>
                  </button>
                );
              })}
            </div>
          </Section>
        </div>
      </div>
    </RouteOverlay>
  );
}

function Section({ title, hint, children }) {
  return (
    <section>
      <div className="mb-3 flex items-baseline gap-3">
        <h2 style={{ fontSize: 'var(--text-md)' }}>{title}</h2>
        {hint && (
          <span style={{ color: 'var(--color-text-tertiary)', fontSize: 'var(--text-xs)' }}>{hint}</span>
        )}
      </div>
      {children}
    </section>
  );
}

function Chip({ active, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className="inline-flex min-h-touch items-center gap-2 rounded-md border px-3 transition-[background-color,border-color] duration-fast hover:bg-bg-hover md:min-h-control"
      style={{
        background: active ? 'var(--group-dim)' : 'var(--color-bg-card)',
        borderColor: active ? 'var(--group)' : 'var(--color-border)',
        color: 'var(--color-text-primary)',
        fontSize: 'var(--text-sm)',
      }}
    >
      {children}
    </button>
  );
}

function Stat({ label, value, strong = false, muted = false }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="label">{label}</dt>
      <dd
        data-num
        className={strong ? 'font-semibold' : ''}
        style={{
          color: muted ? 'var(--color-text-tertiary)' : 'var(--color-text-heading)',
          fontSize: strong ? 'var(--text-lg)' : 'var(--text-sm)',
        }}
      >
        {value}
      </dd>
    </div>
  );
}
