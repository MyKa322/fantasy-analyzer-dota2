/**
 * MODELLED PLAYER STATISTICS — FICTION. READ THIS BEFORE TRUSTING A NUMBER.
 *
 * Real per-player TI statistics are not obtainable offline, and the advisor
 * cannot rank teams without them. So these are generated: role-coherent,
 * internally consistent, deterministic from a fixed seed — and invented.
 *
 * Consequence: every projection this app produces is a demonstration of a
 * working method, not real fantasy advice. That is why ModelledDataBadge is
 * non-dismissable on every projecting surface. Do not remove it, and do not
 * present these figures as authoritative.
 *
 * The SCORING side (src/data/scoring.js) is entirely real. The split matters:
 * real formula, modelled inputs.
 */

import { TEAMS, playerSlug } from './teams.js';

// ---------------------------------------------------------------------------
// Deterministic PRNG — same player always gets the same stats across reloads,
// so screenshots and reviews are reproducible.
// ---------------------------------------------------------------------------
function hashString(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function mulberry32(seed) {
  return function () {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ---------------------------------------------------------------------------
// Per-position profiles. Mean per-game values.
// The shape is what matters: supports must out-ward cores by an order of
// magnitude, cores must out-farm supports, or the advisor's rankings are
// meaningless and the whole product's premise collapses.
// ---------------------------------------------------------------------------
const PROFILES = {
  carry: {
    position: 'Carry', positionShort: 'Pos 1',
    kills: 7.5, deaths: 3.2, creep_score: 380, gpm: 700, madstone: 12, tower_kills: 1.6,
    wards_placed: 0.3, camps_stacked: 1.2, runes_grabbed: 3.5, watchers_taken: 1.2,
    smokes_used: 0.4, lotuses_grabbed: 1.5,
    roshan_kills: 0.50, teamfight: 0.62, stuns: 12, tormentor_kills: 0.25,
    first_blood: 0.08, courier_kills: 0.06,
  },
  offlane: {
    position: 'Offlane', positionShort: 'Pos 3',
    kills: 5.5, deaths: 5.5, creep_score: 220, gpm: 480, madstone: 9, tower_kills: 0.9,
    wards_placed: 1.2, camps_stacked: 2.5, runes_grabbed: 2.0, watchers_taken: 1.5,
    smokes_used: 0.8, lotuses_grabbed: 1.2,
    roshan_kills: 0.30, teamfight: 0.75, stuns: 28, tormentor_kills: 0.20,
    first_blood: 0.14, courier_kills: 0.12,
  },
  mid: {
    position: 'Mid', positionShort: 'Pos 2',
    kills: 8.5, deaths: 4.0, creep_score: 330, gpm: 640, madstone: 11, tower_kills: 1.2,
    wards_placed: 0.4, camps_stacked: 1.0, runes_grabbed: 5.5, watchers_taken: 2.0,
    smokes_used: 0.9, lotuses_grabbed: 2.2,
    roshan_kills: 0.35, teamfight: 0.70, stuns: 18, tormentor_kills: 0.30,
    first_blood: 0.18, courier_kills: 0.10,
  },
  soft: {
    position: 'Soft Support', positionShort: 'Pos 4',
    kills: 4.5, deaths: 6.5, creep_score: 95, gpm: 330, madstone: 6, tower_kills: 0.4,
    wards_placed: 4.5, camps_stacked: 3.5, runes_grabbed: 2.5, watchers_taken: 2.5,
    smokes_used: 2.2, lotuses_grabbed: 2.0,
    roshan_kills: 0.15, teamfight: 0.78, stuns: 34, tormentor_kills: 0.15,
    first_blood: 0.22, courier_kills: 0.20,
  },
  hard: {
    position: 'Hard Support', positionShort: 'Pos 5',
    kills: 2.8, deaths: 7.2, creep_score: 55, gpm: 270, madstone: 4, tower_kills: 0.2,
    wards_placed: 7.5, camps_stacked: 4.5, runes_grabbed: 1.8, watchers_taken: 3.0,
    smokes_used: 1.8, lotuses_grabbed: 3.2,
    roshan_kills: 0.10, teamfight: 0.72, stuns: 30, tormentor_kills: 0.10,
    first_blood: 0.12, courier_kills: 0.25,
  },
};

const STAT_KEYS = [
  'kills', 'deaths', 'creep_score', 'gpm', 'madstone', 'tower_kills',
  'wards_placed', 'camps_stacked', 'runes_grabbed', 'watchers_taken',
  'smokes_used', 'lotuses_grabbed',
  'roshan_kills', 'teamfight', 'stuns', 'tormentor_kills',
  'first_blood', 'courier_kills',
];

/** Ratios must stay in 0..1; counting stats must stay non-negative. */
const RATIO_STATS = new Set(['teamfight', 'first_blood']);

function roleToProfile(roleKey, indexInRole) {
  if (roleKey === 'mid') return 'mid';
  if (roleKey === 'core') return indexInRole === 0 ? 'carry' : 'offlane';
  return indexInRole === 0 ? 'soft' : 'hard';
}

function round(value, key) {
  if (RATIO_STATS.has(key)) return Math.min(0.98, Math.max(0.02, +value.toFixed(3)));
  if (key === 'gpm' || key === 'creep_score' || key === 'stuns') return Math.max(0, Math.round(value));
  return Math.max(0, +value.toFixed(2));
}

/**
 * Build one player. Variance is ±18% per stat, plus a team-strength factor so
 * a top-seeded team's players genuinely outperform a bottom-seeded team's —
 * otherwise every team ranks identically and the advisor has nothing to say.
 */
function buildPlayer(team, name, roleKey, indexInRole) {
  const profileKey = roleToProfile(roleKey, indexInRole);
  const profile = PROFILES[profileKey];
  const rand = mulberry32(hashString(`${team.key}::${name}`));

  // seed 1 (best) -> ~1.10, seed 16 (worst) -> ~0.90
  const teamStrength = 1.10 - ((team.seed - 1) / 15) * 0.20;

  const stats = {};
  for (const key of STAT_KEYS) {
    const mean = profile[key];
    const variance = 1 + (rand() - 0.5) * 0.36;
    // Deaths invert: stronger teams die less
    const strength = key === 'deaths' ? 2 - teamStrength : teamStrength;
    stats[key] = round(mean * variance * strength, key);
  }

  return {
    name,
    slug: playerSlug(name, team.key),
    teamKey: team.key,
    teamName: team.name,
    teamDir: team.dir,
    role: roleKey,
    position: profile.position,
    positionShort: profile.positionShort,
    stats,
    modelled: true,
  };
}

export const PLAYERS = TEAMS.flatMap((team) =>
  ['core', 'mid', 'support'].flatMap((roleKey) =>
    team.roster[roleKey].map((name, i) => buildPlayer(team, name, roleKey, i))
  )
);

export const PLAYERS_BY_SLUG = Object.fromEntries(PLAYERS.map((p) => [p.slug, p]));

/** The players a given team contributes to a given role. */
export function playersFor(teamKey, roleKey) {
  return PLAYERS.filter((p) => p.teamKey === teamKey && p.role === roleKey);
}

/**
 * Dev-only sanity check on the generated data. If supports stop out-warding
 * cores, the advisor's reasoning becomes nonsense while still looking
 * plausible — the worst possible failure mode for this product.
 */
export function verifyModelCoherence() {
  const problems = [];
  const avg = (arr, k) => arr.reduce((s, p) => s + p.stats[k], 0) / arr.length;

  const cores = PLAYERS.filter((p) => p.role === 'core');
  const mids = PLAYERS.filter((p) => p.role === 'mid');
  const supports = PLAYERS.filter((p) => p.role === 'support');

  if (avg(supports, 'wards_placed') <= avg(cores, 'wards_placed') * 3) {
    problems.push('Supports do not clearly out-ward cores');
  }
  if (avg(cores, 'creep_score') <= avg(supports, 'creep_score') * 2) {
    problems.push('Cores do not clearly out-farm supports');
  }
  if (avg(mids, 'runes_grabbed') <= avg(supports, 'runes_grabbed')) {
    problems.push('Mids do not lead on runes');
  }
  if (avg(supports, 'camps_stacked') <= avg(cores, 'camps_stacked')) {
    problems.push('Supports do not lead on camps stacked');
  }
  if (PLAYERS.length !== 80) {
    problems.push(`Expected 80 players, generated ${PLAYERS.length}`);
  }

  return {
    ok: problems.length === 0,
    problems,
    summary: {
      players: PLAYERS.length,
      coreCS: Math.round(avg(cores, 'creep_score')),
      supportCS: Math.round(avg(supports, 'creep_score')),
      coreWards: +avg(cores, 'wards_placed').toFixed(2),
      supportWards: +avg(supports, 'wards_placed').toFixed(2),
      midRunes: +avg(mids, 'runes_grabbed').toFixed(2),
    },
  };
}
