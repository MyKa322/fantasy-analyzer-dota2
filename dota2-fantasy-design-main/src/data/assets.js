/**
 * ASSET RESOLUTION
 *
 * players/, teams/, and fantasy_craft/ live at the project root rather than in
 * public/. Globbing them here lets Vite fingerprint and serve them without
 * duplicating ~90MB of portraits into public/.
 *
 * This module also absorbs every asset-kit inconsistency so nothing downstream
 * has to know about them:
 *   - teams/TeamFalcon.png (singular) vs players/TeamFalcons/ (plural)
 *   - filenames containing ` [ ] - which are hostile to URLs and shells
 */

const emblemFiles = import.meta.glob('../../fantasy_craft/*.png', {
  eager: true, query: '?url', import: 'default',
});
const teamFiles = import.meta.glob('../../teams/*.png', {
  eager: true, query: '?url', import: 'default',
});
const playerFiles = import.meta.glob('../../players/*/*.png', {
  eager: true, query: '?url', import: 'default',
});

/** fantasy_emblem_<name>_png.png -> <name> */
export const EMBLEM_ASSETS = Object.fromEntries(
  Object.entries(emblemFiles).map(([path, url]) => {
    const file = path.split('/').pop();
    const name = file.replace(/^fantasy_emblem_/, '').replace(/_png\.png$/, '');
    return [name, url];
  })
);

/** teams/<CrestFile>.png -> <CrestFile> */
export const CREST_ASSETS = Object.fromEntries(
  Object.entries(teamFiles).map(([path, url]) => [
    path.split('/').pop().replace(/\.png$/, ''),
    url,
  ])
);

/** players/<Dir>/<Name>.png -> "<Dir>/<Name>" */
export const PORTRAIT_ASSETS = Object.fromEntries(
  Object.entries(playerFiles).map(([path, url]) => {
    const parts = path.split('/');
    const name = parts.pop().replace(/\.png$/, '');
    const dir = parts.pop();
    return [`${dir}/${name}`, url];
  })
);

export function emblemAsset(assetName) {
  return EMBLEM_ASSETS[assetName] ?? null;
}

export function crestAsset(crestFile) {
  return CREST_ASSETS[crestFile] ?? null;
}

export function portraitAsset(dir, playerName) {
  return PORTRAIT_ASSETS[`${dir}/${playerName}`] ?? null;
}

/**
 * Dev-only integrity check. A missing portrait renders as an empty box that is
 * easy to miss in a grid of 80 — this fails loudly instead.
 */
export function verifyAssets(teams, emblemStats) {
  const problems = [];

  for (const t of teams) {
    if (!crestAsset(t.crestFile)) {
      problems.push(`Missing crest: teams/${t.crestFile}.png (${t.name})`);
    }
    const all = [...t.roster.core, ...t.roster.mid, ...t.roster.support];
    if (all.length !== 5) {
      problems.push(`${t.name} has ${all.length} players, expected 5`);
    }
    for (const p of all) {
      if (!portraitAsset(t.dir, p)) {
        problems.push(`Missing portrait: players/${t.dir}/${p}.png`);
      }
    }
  }

  for (const [key, stat] of Object.entries(emblemStats)) {
    if (!emblemAsset(stat.asset)) {
      problems.push(`Missing emblem: fantasy_craft/fantasy_emblem_${stat.asset}_png.png (${key})`);
    }
  }

  return {
    ok: problems.length === 0,
    problems,
    counts: {
      emblems: Object.keys(EMBLEM_ASSETS).length,
      crests: Object.keys(CREST_ASSETS).length,
      portraits: Object.keys(PORTRAIT_ASSETS).length,
    },
  };
}
