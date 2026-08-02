import { useMemo, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import BannerColumn from '../components/BannerColumn.jsx';
import ModelledDataBadge from '../components/ModelledDataBadge.jsx';
import CountUp from '../components/CountUp.jsx';
import { ROLE_KEYS, ROLES } from '../data/scoring.js';
import { scoreLineup } from '../engine/scoring.js';

/**
 * Builder — three roles side by side.
 *
 * No advisor, no recommendations. The user selects the data; the interface
 * reports what it's worth.
 */
export default function Builder({ lineup }) {
  const [focusRole, setFocusRole] = useState('core');
  const navigate = useNavigate();
  const location = useLocation();
  const score = useMemo(() => scoreLineup(lineup), [lineup]);

  const open = (path) => navigate(path, { state: { backgroundLocation: location } });

  return (
    <div className="mx-auto w-full px-4 py-6 md:py-8" style={{ maxWidth: 'var(--width-page)' }}>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 style={{ fontSize: 'var(--text-xl)' }}>Banners</h1>
          <p
            className="mt-1"
            style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--text-sm)' }}
          >
            Only stats present on a banner score. Three roles, three teams.
          </p>
        </div>

        <div className="flex flex-wrap items-end gap-6">
          <ModelledDataBadge />
          <div className="text-right">
            <div className="label">Combined</div>
            <CountUp
              value={score.total}
              announce
              className="block font-semibold"
              style={{
                color: 'var(--color-text-heading)',
                fontSize: 'var(--text-2xl)',
                lineHeight: 1.05,
              }}
            />
          </div>
        </div>
      </div>

      {/* Role switch below lg, where only one banner fits */}
      <div
        className="mb-4 flex overflow-hidden rounded-md border lg:hidden"
        style={{ borderColor: 'var(--color-border)' }}
        role="tablist"
        aria-label="Role"
      >
        {ROLE_KEYS.map((r) => (
          <button
            key={r}
            role="tab"
            aria-selected={focusRole === r}
            onClick={() => setFocusRole(r)}
            className="min-h-touch flex-1"
            style={{
              background: focusRole === r ? 'var(--n-050)' : 'transparent',
              color: focusRole === r ? 'var(--n-950)' : 'var(--color-text-secondary)',
              fontSize: 'var(--text-sm)',
              fontWeight: 'var(--weight-medium)',
            }}
          >
            {ROLES[r].label}
          </button>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {ROLE_KEYS.map((roleKey) => (
          // min-w-0 stops grid items from being sized by their content
          <div
            key={roleKey}
            className={`min-w-0 ${focusRole === roleKey ? 'block' : 'hidden lg:block'}`}
          >
            <BannerColumn
              roleKey={roleKey}
              entry={lineup[roleKey]}
              onChangeTeam={(r) => open(`/build/${r}/team`)}
              onSelectEmblem={(r, slot) => open(`/build/${r}/emblem/${slot + 1}`)}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
