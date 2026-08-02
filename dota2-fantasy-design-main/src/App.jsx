import { useEffect, useState } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import AppShell from './components/AppShell.jsx';
import Builder from './routes/Builder.jsx';
import Glossary from './routes/Glossary.jsx';
import TeamPicker from './routes/TeamPicker.jsx';
import EmblemPicker from './routes/EmblemPicker.jsx';
import Bracket from './routes/Bracket.jsx';
import { makeSampleLineup, setTeam, setEmblem } from './state/lineup.js';
import { EMBLEM_STATS } from './data/scoring.js';
import { verifyAgainstReference } from './engine/scoring.js';
import { verifyModelCoherence } from './data/players.js';
import { verifyAssets } from './data/assets.js';
import { TEAMS } from './data/teams.js';

/** Routes that render as an overlay on top of the builder. */
const OVERLAYS = ['/glossary', '/build/:role/team', '/build/:role/emblem/:slot'];

export default function App() {
  const [lineup, setLineup] = useState(makeSampleLineup);
  const location = useLocation();

  useEffect(() => {
    if (!import.meta.env.DEV) return;
    const eng = verifyAgainstReference();
    const mdl = verifyModelCoherence();
    const ast = verifyAssets(TEAMS, EMBLEM_STATS);
    console.groupCollapsed(
      `[integrity] engine:${eng.ok ? 'ok' : 'FAIL'} model:${mdl.ok ? 'ok' : 'FAIL'} assets:${ast.ok ? 'ok' : 'FAIL'}`
    );
    console.log('assets', ast.counts);
    console.log('model', mdl.summary);
    [...eng.failures, ...mdl.problems, ...ast.problems].forEach((p) => console.warn(p));
    console.groupEnd();
  }, []);

  const builder = <Builder lineup={lineup} />;

  // Overlays keep the builder mounted behind them. A cold deep-link has no
  // background location, so the base routes render the builder for overlay
  // paths too — back always lands somewhere real.
  const background = location.state?.backgroundLocation;

  return (
    <AppShell>
      <Routes location={background || location}>
        <Route path="/" element={<Navigate to="/build" replace />} />
        <Route path="/build" element={builder} />
        <Route path="/bracket" element={<Bracket />} />
        {OVERLAYS.map((p) => (
          <Route key={p} path={p} element={builder} />
        ))}
        <Route path="*" element={<Navigate to="/build" replace />} />
      </Routes>

      <Routes>
        <Route path="/glossary" element={<Glossary />} />
        <Route
          path="/build/:role/team"
          element={
            <TeamPicker
              lineup={lineup}
              onCommit={(role, teamKey) => setLineup((l) => setTeam(l, role, teamKey))}
            />
          }
        />
        <Route
          path="/build/:role/emblem/:slot"
          element={
            <EmblemPicker
              lineup={lineup}
              onApply={(role, slot, emblem) => setLineup((l) => setEmblem(l, role, slot, emblem))}
            />
          }
        />
        <Route path="*" element={null} />
      </Routes>
    </AppShell>
  );
}
