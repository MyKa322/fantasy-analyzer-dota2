/**
 * SCORING ENGINE
 *
 * Implements the real TI 2025 fantasy math. Verified against the reference
 * screenshots — see verifyAgainstReference() at the bottom, which reproduces
 * all nine emblem cards from the supplied banner exactly.
 *
 * The core formula, confirmed on every reference card:
 *
 *   displayed%  = 100 + tierBonus + netTraitBonus
 *   netTrait    = own trait's self-bonus (if its condition holds)
 *               + sum of neighbouring emblems' adjacent effects
 *   points      = baseStatPoints * (displayed% / 100)
 *
 * Adjacency is positional: emblems sit in a vertical column, so emblem i
 * neighbours i-1 and i+1. Slot 0 and slot 2 each have one neighbour.
 */

import { EMBLEM_STATS, TIERS, TRAITS } from '../data/scoring.js';

// ---------------------------------------------------------------------------
// Base stat points — what one emblem's stat is worth before any multipliers
// ---------------------------------------------------------------------------
export function baseStatPoints(statKey, playerStats) {
  const stat = EMBLEM_STATS[statKey];
  if (!stat) return 0;
  const v = playerStats?.[statKey] ?? 0;

  switch (stat.kind) {
    case 'per':        return stat.rate * v;
    case 'multiplier': return stat.rate * v;
    case 'baseMinus':  return stat.base + stat.rate * v;
    case 'maxScaled':  return stat.rate * Math.min(Math.max(v, 0), 1);
    case 'chance':     return stat.rate * Math.min(Math.max(v, 0), 1);
    default:           return 0;
  }
}

// ---------------------------------------------------------------------------
// Trait conditions
// ---------------------------------------------------------------------------
function traitConditionMet(condition, banner, index) {
  switch (condition) {
    case 'always':
      return true;
    case 'allTiersDifferent': {
      const tiers = banner.map((e) => e.tier);
      return new Set(tiers).size === tiers.length;
    }
    case 'onlyUnique':
      return banner.filter((e) => e.trait === 'UNIQUE').length === 1
        && banner[index].trait === 'UNIQUE';
    case 'threeFriendly':
      return banner.filter((e) => e.trait === 'FRIENDLY').length >= 3;
    default:
      return false;
  }
}

/**
 * Net trait contribution for one emblem, in percentage points.
 * Returns the breakdown too, because the UI has to show its work —
 * principle 1 of the brief.
 */
export function traitContribution(banner, index) {
  const emblem = banner[index];
  const trait = TRAITS[emblem.trait];
  let self = 0;
  let incoming = 0;
  const sources = [];

  if (trait) {
    const met = traitConditionMet(trait.condition, banner, index);
    if (met && trait.self !== 0) {
      self = trait.self;
      sources.push({ from: 'self', trait: emblem.trait, label: trait.label, value: trait.self });
    } else if (!met && trait.self !== 0) {
      // Condition unmet — surfaced so the UI can show it struck through
      sources.push({ from: 'self', trait: emblem.trait, label: trait.label, value: 0, unmet: true });
    }
  }

  // Neighbours push their `adjacent` effect onto this emblem
  for (const n of [index - 1, index + 1]) {
    if (n < 0 || n >= banner.length) continue;
    const nTrait = TRAITS[banner[n].trait];
    if (!nTrait || nTrait.adjacent === 0) continue;
    if (!traitConditionMet(nTrait.condition, banner, n)) continue;
    incoming += nTrait.adjacent;
    sources.push({
      from: 'neighbour',
      slot: n,
      trait: banner[n].trait,
      label: nTrait.label,
      value: nTrait.adjacent,
    });
  }

  return { total: self + incoming, self, incoming, sources };
}

// ---------------------------------------------------------------------------
// The displayed percentage on an emblem card
// ---------------------------------------------------------------------------
export function emblemPercent(banner, index) {
  const emblem = banner[index];
  const tierBonus = TIERS[emblem.tier]?.bonus ?? 0;
  const trait = traitContribution(banner, index);
  return {
    percent: 100 + tierBonus + trait.total,
    tierBonus,
    traitBonus: trait.total,
    traitDetail: trait,
  };
}

// ---------------------------------------------------------------------------
// Full breakdown for one emblem — this is what PointBreakdown renders
// ---------------------------------------------------------------------------
export function emblemBreakdown(banner, index, playerStats) {
  const emblem = banner[index];
  const stat = EMBLEM_STATS[emblem.stat];
  const base = baseStatPoints(emblem.stat, playerStats);
  const { percent, tierBonus, traitBonus, traitDetail } = emblemPercent(banner, index);
  const points = base * (percent / 100);

  return {
    stat: emblem.stat,
    statLabel: stat?.label ?? emblem.stat,
    group: stat?.group,
    units: playerStats?.[emblem.stat] ?? 0,
    unitLabel: stat?.unit,
    base,
    tier: emblem.tier,
    tierBonus,
    trait: emblem.trait,
    traitBonus,
    traitDetail,
    percent,
    points,
  };
}

/**
 * Score one player against one banner.
 * Players receive points ONLY for stats present on their banner — the single
 * most important rule in the whole system, and the reason a bad emblem is
 * so costly.
 */
export function scorePlayer(banner, playerStats) {
  const emblems = banner.map((_, i) => emblemBreakdown(banner, i, playerStats));
  const total = emblems.reduce((sum, e) => sum + e.points, 0);
  return { emblems, total };
}

/**
 * Averaged stat block across a role's players. A role scores as the average of
 * its players, so this is what the banner is evaluated against.
 */
export function averageStats(players) {
  if (!players?.length) return {};
  return Object.keys(players[0].stats).reduce((acc, k) => {
    acc[k] = players.reduce((s, p) => s + (p.stats[k] ?? 0), 0) / players.length;
    return acc;
  }, {});
}

/**
 * Score a role: average across the players in that role, per the client rule
 * "We then average the score of all players for a role."
 */
export function scoreRole(banner, players) {
  if (!players?.length) return { total: 0, perPlayer: [] };
  const perPlayer = players.map((p) => ({
    player: p,
    ...scorePlayer(banner, p.stats),
  }));
  const total = perPlayer.reduce((s, r) => s + r.total, 0) / perPlayer.length;
  return { total, perPlayer };
}

/** Combined lineup score across all three roles. */
export function scoreLineup(lineup) {
  const roles = {};
  let total = 0;
  for (const [roleKey, entry] of Object.entries(lineup)) {
    const r = scoreRole(entry.banner, entry.players);
    roles[roleKey] = r;
    total += r.total;
  }
  return { total, roles };
}

// ---------------------------------------------------------------------------
// Formatting — every score in this product goes through here so rounding is
// consistent and tabular alignment holds.
// ---------------------------------------------------------------------------
export function fmtPoints(n) {
  if (!isFinite(n)) return '0';
  const r = Math.round(n);
  return r.toLocaleString('en-US');
}

export function fmtCompact(n) {
  const a = Math.abs(n);
  if (a >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return Math.round(n).toString();
}

export function fmtDelta(n) {
  const sign = n > 0 ? '+' : n < 0 ? '−' : '';
  return `${sign}${fmtCompact(Math.abs(n))}`;
}

// ---------------------------------------------------------------------------
// SELF-VERIFICATION against the reference screenshots.
// Runs in dev only. If the engine ever drifts from the client's behaviour,
// this fails loudly rather than silently producing plausible wrong numbers.
// ---------------------------------------------------------------------------
export function verifyAgainstReference() {
  const cases = [
    {
      name: 'Core banner',
      banner: [
        { stat: 'creep_score', tier: 'II', trait: 'FRIENDLY' },
        { stat: 'stuns',       tier: 'I',  trait: 'FRACTAL' },
        { stat: 'gpm',         tier: 'II', trait: 'VAMPIRIC' },
      ],
      expect: [130, 100, 180],
    },
    {
      name: 'Mid banner',
      banner: [
        { stat: 'gpm',         tier: 'II', trait: 'UNIQUE' },
        { stat: 'smokes_used', tier: 'II', trait: 'VAMPIRIC' },
        { stat: 'teamfight',   tier: 'II', trait: 'FRACTAL' },
      ],
      expect: [150, 180, 120],
    },
    {
      name: 'Support banner',
      banner: [
        { stat: 'lotuses_grabbed', tier: 'III', trait: 'FRACTAL' },
        { stat: 'roshan_kills',    tier: 'II',  trait: 'FRACTAL' },
        { stat: 'smokes_used',     tier: 'II',  trait: 'FRIENDLY' },
      ],
      expect: [160, 130, 130],
    },
  ];

  const failures = [];
  for (const c of cases) {
    const got = c.banner.map((_, i) => emblemPercent(c.banner, i).percent);
    got.forEach((g, i) => {
      if (g !== c.expect[i]) {
        failures.push(`${c.name} slot ${i}: expected ${c.expect[i]}%, got ${g}%`);
      }
    });
  }

  if (failures.length) {
    console.error('[scoring engine] REFERENCE MISMATCH:\n' + failures.join('\n'));
    return { ok: false, failures };
  }
  return { ok: true, failures: [] };
}
