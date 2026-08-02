import { NavLink, useSearchParams, useLocation } from 'react-router-dom';
import { PERIODS } from '../data/scoring.js';

/**
 * AppShell — flat header, hairline rule, no ornament.
 *
 * Four primary destinations, capped so the mobile tab bar never compresses.
 * The roll-token counter is gone: this is an analytics tool, not a game
 * economy — the user sets the data directly.
 */

const NAV = [
  { to: '/build', label: 'Banners' },
  { to: '/matches', label: 'Matches' },
  { to: '/standings', label: 'Standings' },
  { to: '/bracket', label: 'Bracket' },
];

export default function AppShell({ children }) {
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const period = params.get('period') ?? 'group';

  const setPeriod = (key) => {
    const next = new URLSearchParams(params);
    if (key === 'group') next.delete('period');
    else next.set('period', key);
    setParams(next, { replace: true });
  };

  return (
    <div className="flex min-h-full flex-col" style={{ background: 'var(--color-bg-page)' }}>
      <header
        className="sticky top-0 z-header flex flex-wrap items-center gap-4 border-b px-4 py-3"
        style={{
          background: 'color-mix(in srgb, var(--color-bg-page) 88%, transparent)',
          borderColor: 'var(--color-border)',
          backdropFilter: 'blur(12px)',
        }}
      >
        <NavLink to="/build" className="flex min-h-touch items-center md:min-h-0">
          <span
            className="font-display font-semibold"
            style={{ color: 'var(--color-text-heading)', fontSize: 'var(--text-md)', letterSpacing: 'var(--track-tight)' }}
          >
            Fantasy
          </span>
        </NavLink>

        <nav className="hidden gap-1 md:flex" aria-label="Primary">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className="rounded-md px-3 py-2 transition-colors duration-fast"
              style={({ isActive }) => ({
                color: isActive ? 'var(--color-text-heading)' : 'var(--color-text-secondary)',
                background: isActive ? 'var(--color-bg-raised)' : 'transparent',
                fontSize: 'var(--text-sm)',
                fontWeight: 'var(--weight-medium)',
              })}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex flex-wrap items-center justify-end gap-2">
          <div
            className="flex overflow-hidden rounded-md border"
            style={{ borderColor: 'var(--color-border)' }}
            role="group"
            aria-label="Period"
          >
            {PERIODS.map((p) => (
              <button
                key={p.key}
                type="button"
                onClick={() => setPeriod(p.key)}
                aria-pressed={period === p.key}
                className="min-h-touch px-3 transition-colors duration-fast md:min-h-control"
                style={{
                  background: period === p.key ? 'var(--n-050)' : 'transparent',
                  color: period === p.key ? 'var(--n-950)' : 'var(--color-text-secondary)',
                  fontSize: 'var(--text-sm)',
                  fontWeight: 'var(--weight-medium)',
                }}
              >
                {p.label}
              </button>
            ))}
          </div>

          <NavLink
            to="/glossary"
            state={{ backgroundLocation: location }}
            className="flex min-h-touch items-center rounded-md px-3 md:min-h-control"
            style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--text-sm)' }}
          >
            Reference
          </NavLink>
        </div>
      </header>

      <main className="flex-1 pb-20 md:pb-8">{children}</main>

      <nav
        className="fixed inset-x-0 bottom-0 z-header flex border-t md:hidden"
        aria-label="Primary"
        style={{ background: 'var(--color-bg-base)', borderColor: 'var(--color-border)' }}
      >
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className="flex-1 py-4 text-center"
            style={({ isActive }) => ({
              minHeight: 'var(--touch-min)',
              color: isActive ? 'var(--color-text-heading)' : 'var(--color-text-tertiary)',
              fontSize: 'var(--text-xs)',
              fontWeight: 'var(--weight-medium)',
              boxShadow: isActive ? 'inset 0 1px 0 var(--n-050)' : 'none',
            })}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
