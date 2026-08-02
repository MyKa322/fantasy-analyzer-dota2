import EmblemIcon from './EmblemIcon.jsx';
import { EMBLEM_STATS, TIERS, TRAITS } from '../data/scoring.js';
import { fmtPoints } from '../engine/scoring.js';

/**
 * EmblemCard — one slot on a banner.
 *
 * The icon is the real fantasy_craft artwork at full fidelity. Group colour is
 * carried by a single left rule and the icon's ring — never by tinting the art
 * and never by flooding the card. That is what lets the icon be swapped to any
 * design while the slot's colour stays fixed.
 *
 * Colour is never the only channel: the stat name is always present in text.
 */
export default function EmblemCard({
  breakdown,
  onClick,
  selected = false,
  showPoints = true,
}) {
  const stat = EMBLEM_STATS[breakdown.stat];
  const tier = TIERS[breakdown.tier];
  const trait = TRAITS[breakdown.trait];
  const group = stat?.group ?? 'red';

  const sign = (n) => (n > 0 ? `+${n}%` : n < 0 ? `−${Math.abs(n)}%` : '0%');
  const Tag = onClick ? 'button' : 'div';

  return (
    <Tag
      data-group={group}
      onClick={onClick}
      type={onClick ? 'button' : undefined}
      aria-label={
        onClick
          ? `${stat?.label}, ${breakdown.percent} percent, ${fmtPoints(breakdown.points)} points. Change emblem.`
          : undefined
      }
      className={`group/card relative flex w-full items-center gap-3 overflow-hidden rounded-md border p-3 text-left
        transition-[background-color,border-color] duration-fast
        ${onClick ? 'cursor-pointer hover:bg-bg-hover' : ''}`}
      style={{
        background: 'var(--color-bg-card)',
        borderColor: selected ? 'var(--group-line)' : 'var(--color-border)',
      }}
    >
      {/* The single colour rule. 2px, full height, no fill behind the content. */}
      <span
        aria-hidden="true"
        className="absolute inset-y-0 left-0 w-[2px]"
        style={{ background: 'var(--group)' }}
      />

      <EmblemIcon asset={stat?.asset} label={stat?.label} className="ml-1" />

      <span className="min-w-0 flex-1">
        <span
          className="block truncate font-medium"
          style={{ color: 'var(--color-text-heading)', fontSize: 'var(--text-sm)' }}
        >
          {stat?.label}
        </span>
        <span
          className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5"
          style={{ color: 'var(--color-text-tertiary)', fontSize: 'var(--text-2xs)' }}
        >
          <span>
            {tier?.label} <span data-num>{sign(breakdown.tierBonus)}</span>
          </span>
          <span aria-hidden="true">·</span>
          <span>
            {trait?.label} <span data-num>{sign(breakdown.traitBonus)}</span>
          </span>
        </span>
      </span>

      <span className="shrink-0 text-right">
        <span
          data-num
          className="block font-semibold"
          style={{ color: 'var(--group)', fontSize: 'var(--text-md)' }}
        >
          {breakdown.percent}%
        </span>
        {showPoints && (
          <span
            data-num
            className="block"
            style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--text-xs)' }}
          >
            {fmtPoints(breakdown.points)}
          </span>
        )}
      </span>
    </Tag>
  );
}
