/**
 * ModelledDataBadge — persistent marker on surfaces that report points.
 *
 * The scoring formula is real, taken from the client glossary. The per-player
 * statistics driving every projection are generated. That distinction has to
 * stay visible: a tool that looks authoritative while running on invented
 * numbers is worse than one that says so.
 *
 * No dismiss affordance, and no prop to hide it.
 */
export default function ModelledDataBadge({ compact = false, className = '' }) {
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-md border px-2.5 py-1 ${className}`}
      style={{
        borderColor: 'var(--color-border)',
        color: 'var(--color-text-tertiary)',
        fontSize: 'var(--text-2xs)',
      }}
      title="Scoring values are real. Player statistics are generated, not actual match data."
    >
      <svg width="11" height="11" viewBox="0 0 12 12" aria-hidden="true" className="shrink-0">
        <circle cx="6" cy="6" r="5" fill="none" stroke="currentColor" strokeWidth="1.1" />
        <path d="M6 3.4 v3" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" />
        <circle cx="6" cy="8.4" r="0.55" fill="currentColor" />
      </svg>
      {compact ? 'Generated stats' : 'Real scoring · generated player stats'}
    </span>
  );
}
