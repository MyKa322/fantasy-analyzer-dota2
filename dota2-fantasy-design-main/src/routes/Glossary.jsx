import RouteOverlay from '../components/RouteOverlay.jsx';
import EmblemIcon from '../components/EmblemIcon.jsx';
import {
  EMBLEM_STATS, STATS_BY_GROUP, TIERS, TIER_KEYS, TRAITS,
  PREFIXES, SUFFIXES, REWARD_LADDER, SCORING_RULES, ROLES, ROLE_KEYS,
} from '../data/scoring.js';

/**
 * Reference — the scoring engine's constants, rendered for humans.
 *
 * Every figure reads out of src/data/scoring.js, the same module the maths
 * uses, so this page cannot drift from what the app actually computes.
 */

function valueText(stat) {
  const n = (v) => v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  switch (stat.kind) {
    case 'per':        return `+${n(stat.rate)} per ${stat.unit}`;
    case 'multiplier': return `GPM × ${n(stat.rate)}`;
    case 'baseMinus':  return `${n(stat.base)} base, ${n(stat.rate)} per ${stat.unit}`;
    case 'maxScaled':  return `up to ${n(stat.rate)}`;
    case 'chance':     return `${n(stat.rate)} if achieved`;
    default:           return '';
  }
}

const GROUP_LABEL = { red: 'Red', blue: 'Blue', green: 'Green' };

export default function Glossary() {
  return (
    <RouteOverlay title="Reference" size="full">
      <div className="grid gap-8 lg:grid-cols-2">
        {/* ---- Scoring values ---------------------------------------------- */}
        <section>
          <H>Base point values</H>
          <P>
            Per game, before tier and trait multipliers. A player scores only for the
            stats present on their banner.
          </P>
          <div className="mt-4 flex flex-col">
            {['red', 'blue', 'green'].map((g) => (
              <div key={g} data-group={g} className="mb-5">
                <div className="mb-2 flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full" style={{ background: 'var(--group)' }} />
                  <span className="label" style={{ color: 'var(--group)' }}>
                    {GROUP_LABEL[g]}
                  </span>
                </div>
                {STATS_BY_GROUP[g].map((key) => {
                  const s = EMBLEM_STATS[key];
                  return (
                    <div
                      key={key}
                      className="flex items-center gap-3 border-b py-2"
                      style={{ borderColor: 'var(--color-border)' }}
                    >
                      <EmblemIcon asset={s.asset} size="28px" ring={false} />
                      <span
                        className="min-w-0 flex-1 truncate"
                        style={{ color: 'var(--color-text-primary)', fontSize: 'var(--text-sm)' }}
                      >
                        {s.label}
                      </span>
                      <span
                        data-num
                        className="shrink-0 text-right"
                        style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--text-xs)' }}
                      >
                        {valueText(s)}
                      </span>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </section>

        {/* ---- Modifiers and rules ----------------------------------------- */}
        <div className="flex flex-col gap-8">
          <section>
            <H>Banner composition</H>
            <P>Emblem colour is fixed per slot. Any icon can occupy any slot.</P>
            <div className="mt-3 flex flex-col gap-2">
              {ROLE_KEYS.map((r) => (
                <div key={r} className="flex items-center gap-3">
                  <span className="w-20 shrink-0" style={{ color: 'var(--color-text-primary)', fontSize: 'var(--text-sm)' }}>
                    {ROLES[r].label}
                  </span>
                  <span className="flex gap-1.5">
                    {ROLES[r].slots.map((g, i) => (
                      <span
                        key={i}
                        data-group={g}
                        className="h-5 w-5 rounded-sm border"
                        style={{ background: 'var(--group-dim)', borderColor: 'var(--group-line)' }}
                        title={GROUP_LABEL[g]}
                      />
                    ))}
                  </span>
                  <span style={{ color: 'var(--color-text-tertiary)', fontSize: 'var(--text-xs)' }}>
                    {ROLES[r].playerCount === 1 ? '1 player' : '2 players'}
                  </span>
                </div>
              ))}
            </div>
          </section>

          <section>
            <H>Tiers</H>
            <div className="mt-3 flex flex-wrap gap-2">
              {TIER_KEYS.map((k) => (
                <span
                  key={k}
                  className="rounded-md border px-3 py-1.5"
                  style={{ borderColor: 'var(--color-border)', fontSize: 'var(--text-sm)' }}
                >
                  {TIERS[k].label}{' '}
                  <span data-num style={{ color: 'var(--color-text-secondary)' }}>
                    +{TIERS[k].bonus}%
                  </span>
                </span>
              ))}
            </div>
          </section>

          <section>
            <H>Traits</H>
            <P>Adjacency applies to the emblems directly above and below on the same banner.</P>
            <div className="mt-3 flex flex-col gap-2">
              {Object.entries(TRAITS).map(([key, t]) => (
                <div key={key} className="border-b pb-2" style={{ borderColor: 'var(--color-border)' }}>
                  <span style={{ color: 'var(--color-text-heading)', fontSize: 'var(--text-sm)', fontWeight: 500 }}>
                    {t.label}
                  </span>
                  <p className="mt-0.5" style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--text-xs)', lineHeight: 1.5 }}>
                    {t.text}
                  </p>
                </div>
              ))}
            </div>
          </section>

          <section>
            <H>Scoring resolution</H>
            <ol className="mt-3 flex flex-col gap-1.5">
              {SCORING_RULES.map((rule, i) => (
                <li key={i} className="flex gap-3">
                  <span data-num className="shrink-0" style={{ color: 'var(--color-text-tertiary)', fontSize: 'var(--text-xs)' }}>
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <span style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--text-sm)' }}>{rule}</span>
                </li>
              ))}
            </ol>
          </section>

          <section>
            <H>Coach titles</H>
            <div className="mt-3 grid gap-4 sm:grid-cols-2">
              <TitleList heading="Prefixes" items={PREFIXES} />
              <TitleList heading="Suffixes" items={SUFFIXES} />
            </div>
            <P className="mt-3">
              Prefix conditions depend on hero colour, which this prototype does not
              model. They are listed but not applied to projections.
            </P>
          </section>

          <section>
            <H>Reward ladder</H>
            <table className="mt-3 w-full">
              <thead>
                <tr>
                  <th className="label pb-2 text-left">Percentile</th>
                  <th className="label pb-2 text-right">Points</th>
                </tr>
              </thead>
              <tbody>
                {REWARD_LADDER.map((r) => (
                  <tr key={r.percentile} className="border-b" style={{ borderColor: 'var(--color-border)' }}>
                    <td className="py-1.5" style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--text-sm)' }}>
                      {r.percentile}
                    </td>
                    <td className="py-1.5 text-right" style={{ color: 'var(--color-text-primary)', fontSize: 'var(--text-sm)' }}>
                      {r.points.toLocaleString('en-US')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </div>
      </div>
    </RouteOverlay>
  );
}

function H({ children }) {
  return <h2 style={{ fontSize: 'var(--text-md)' }}>{children}</h2>;
}

function P({ children, className = '' }) {
  return (
    <p
      className={`mt-1.5 ${className}`}
      style={{
        color: 'var(--color-text-secondary)',
        fontSize: 'var(--text-sm)',
        lineHeight: 'var(--leading-normal)',
        maxWidth: 'var(--width-prose)',
      }}
    >
      {children}
    </p>
  );
}

function TitleList({ heading, items }) {
  return (
    <div>
      <div className="label mb-2">{heading}</div>
      <div className="flex flex-col gap-1">
        {items.map((t) => (
          <div key={t.key} style={{ fontSize: 'var(--text-xs)' }}>
            <span style={{ color: 'var(--color-text-primary)' }}>{t.label}</span>{' '}
            <span data-num style={{ color: 'var(--color-text-secondary)' }}>+{t.bonus}%</span>{' '}
            <span style={{ color: 'var(--color-text-tertiary)' }}>{t.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
