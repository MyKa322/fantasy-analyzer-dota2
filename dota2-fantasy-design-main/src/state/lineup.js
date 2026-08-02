import { ROLES, ROLE_KEYS, STATS_BY_GROUP, TIER_ROLL_WEIGHTS, TRAIT_KEYS } from '../data/scoring.js';
import { TEAMS, TEAMS_BY_KEY } from '../data/teams.js';
import { playersFor } from '../data/players.js';

/**
 * Lineup state.
 *
 * A lineup is three roles. Each role holds a chosen TEAM (not players — you
 * pick a team and receive its players for that role) and a BANNER of three
 * emblems whose colour groups are fixed by the role.
 */

function pickWeighted(weights, rand) {
  const total = Object.values(weights).reduce((a, b) => a + b, 0);
  let r = rand() * total;
  for (const [key, w] of Object.entries(weights)) {
    r -= w;
    if (r <= 0) return key;
  }
  return Object.keys(weights)[0];
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

/**
 * Build a banner whose emblem colours match the role's fixed composition.
 *
 * Stats must be unique across the banner — the client glossary is explicit:
 * "there are no duplicate stats on a War Banner". Core and Support have two
 * slots of the same colour, so without this exclusion they routinely roll the
 * same stat twice.
 */
export function makeBanner(roleKey, rand = Math.random) {
  const taken = new Set();
  return ROLES[roleKey].slots.map((group) => {
    const pool = STATS_BY_GROUP[group].filter((s) => !taken.has(s));
    const stat = pool[Math.floor(rand() * pool.length)];
    taken.add(stat);
    return {
      stat,
      tier: pickWeighted(TIER_ROLL_WEIGHTS, rand),
      trait: TRAIT_KEYS[Math.floor(rand() * TRAIT_KEYS.length)],
    };
  });
}

// Rolling was removed: this is an analytics tool, so emblems are chosen
// directly in EmblemPicker rather than rolled against a token economy.
// makeBanner survives only to seed a sensible starting lineup.

/**
 * A deterministic sample lineup, so the skip path and any screenshot are
 * reproducible. Uses three different teams, as the real system requires.
 */
export function makeSampleLineup() {
  const rand = mulberry32(20260801);
  const teams = { core: 'team-vision', mid: 'team-falcons', support: 'xtreme-gaming' };

  return ROLE_KEYS.reduce((acc, roleKey) => {
    const teamKey = teams[roleKey];
    acc[roleKey] = {
      teamKey,
      team: TEAMS_BY_KEY[teamKey],
      players: playersFor(teamKey, roleKey),
      banner: makeBanner(roleKey, rand),
    };
    return acc;
  }, {});
}

export function setTeam(lineup, roleKey, teamKey) {
  return {
    ...lineup,
    [roleKey]: {
      ...lineup[roleKey],
      teamKey,
      team: TEAMS_BY_KEY[teamKey],
      players: playersFor(teamKey, roleKey),
    },
  };
}

export function setEmblem(lineup, roleKey, slotIndex, emblem) {
  const banner = lineup[roleKey].banner.map((e, i) => (i === slotIndex ? emblem : e));
  return { ...lineup, [roleKey]: { ...lineup[roleKey], banner } };
}

/** Teams already used elsewhere in the lineup — the client picks 3 distinct. */
export function usedTeamKeys(lineup, exceptRole) {
  return ROLE_KEYS
    .filter((r) => r !== exceptRole)
    .map((r) => lineup[r]?.teamKey)
    .filter(Boolean);
}

export { TEAMS, ROLES, ROLE_KEYS };
