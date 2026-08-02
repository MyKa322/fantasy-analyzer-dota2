/**
 * REAL SCORING DATA — The International 2025 Compendium fantasy.
 *
 * Every value in this file is taken verbatim from the in-client glossary.
 * NOTHING HERE IS INVENTED. Do not "tune" these numbers — if a projection
 * looks wrong, the modelled player stats (src/data/players.js) are the
 * fiction, not this file.
 *
 * Verified against the reference screenshots: the display formula
 *   displayed% = 100 + tierBonus + netTraitBonus
 * reproduces all nine emblem cards in the reference banner exactly.
 */

// ---------------------------------------------------------------------------
// Emblem colour groups. Colour is FIXED per slot and is never rerollable —
// only the stat within a colour, its tier, and its trait can change.
// ---------------------------------------------------------------------------
export const GROUPS = { RED: 'red', BLUE: 'blue', GREEN: 'green' };

/**
 * kind:
 *   'per'        points = rate * units
 *   'multiplier' points = rate * value          (GPM)
 *   'baseMinus'  points = base + rate * units   (Deaths: starts at 1950)
 *   'maxScaled'  points = rate * ratio(0..1)    (Teamfight participation)
 *   'chance'     points = rate * probability    (First Blood, expected value)
 */
/**
 * `unit` is singular and matches the client's glossary phrasing ("+234.00 per
 * camp stacked"). `unitPlural` exists because several of these do not survive
 * naive +s pluralisation — "camp stackeds", "lotuss", "Smoke of Deceits",
 * "second of stuns". The advisor speaks in averages, so it needs the plural.
 */
export const EMBLEM_STATS = {
  // --- RED ------------------------------------------------------------------
  kills:            { group: GROUPS.RED,   label: 'Kills',                   kind: 'per',        rate: 107,   unit: 'kill',            unitPlural: 'kills',              asset: 'kills' },
  deaths:           { group: GROUPS.RED,   label: 'Deaths',                  kind: 'baseMinus',  rate: -195,  base: 1950, unit: 'death', unitPlural: 'deaths',           asset: 'deaths' },
  creep_score:      { group: GROUPS.RED,   label: 'Creep Score',             kind: 'per',        rate: 3,     unit: 'last hit or deny', unitPlural: 'last hits and denies', asset: 'creep_score' },
  gpm:              { group: GROUPS.RED,   label: 'GPM',                     kind: 'multiplier', rate: 2,     unit: 'GPM',             unitPlural: 'GPM',                asset: 'gpm' },
  madstone:         { group: GROUPS.RED,   label: 'Madstone Collected',      kind: 'per',        rate: 13,    unit: 'madstone',        unitPlural: 'madstones',          asset: 'neutral_token' },
  tower_kills:      { group: GROUPS.RED,   label: 'Tower Kills',             kind: 'per',        rate: 352,   unit: 'tower last hit',  unitPlural: 'tower last hits',    asset: 'towers_killed' },

  // --- BLUE -----------------------------------------------------------------
  wards_placed:     { group: GROUPS.BLUE,  label: 'Wards Placed',            kind: 'per',        rate: 117,   unit: 'observer ward',   unitPlural: 'observer wards',     asset: 'wards_placed' },
  camps_stacked:    { group: GROUPS.BLUE,  label: 'Camps Stacked',           kind: 'per',        rate: 234,   unit: 'camp stacked',    unitPlural: 'camps stacked',      asset: 'creeps_stacked' },
  runes_grabbed:    { group: GROUPS.BLUE,  label: 'Runes Grabbed',           kind: 'per',        rate: 141,   unit: 'rune',            unitPlural: 'runes',              asset: 'rune' },
  watchers_taken:   { group: GROUPS.BLUE,  label: 'Watchers Taken',          kind: 'per',        rate: 147,   unit: 'watcher',         unitPlural: 'watchers',           asset: 'sentinel' },
  smokes_used:      { group: GROUPS.BLUE,  label: 'Smokes Used',             kind: 'per',        rate: 293,   unit: 'Smoke of Deceit', unitPlural: 'smokes',             asset: 'smoke' },
  lotuses_grabbed:  { group: GROUPS.BLUE,  label: 'Lotuses Grabbed',         kind: 'per',        rate: 176,   unit: 'lotus',           unitPlural: 'lotuses',            asset: 'lotus' },

  // --- GREEN ----------------------------------------------------------------
  roshan_kills:     { group: GROUPS.GREEN, label: 'Roshan Kills',            kind: 'per',        rate: 1172,  unit: 'Roshan kill',     unitPlural: 'Roshan kills',       asset: 'roshan' },
  teamfight:        { group: GROUPS.GREEN, label: 'Teamfight Participation', kind: 'maxScaled',  rate: 2124,  unit: 'participation',   unitPlural: 'participation',      asset: 'teamfight' },
  stuns:            { group: GROUPS.GREEN, label: 'Stuns',                   kind: 'per',        rate: 10,    unit: 'second of stun',  unitPlural: 'seconds of stun',    asset: 'stuns' },
  tormentor_kills:  { group: GROUPS.GREEN, label: 'Tormentor Kills',         kind: 'per',        rate: 879,   unit: 'Tormentor kill',  unitPlural: 'Tormentor kills',    asset: 'tormentor' },
  first_blood:      { group: GROUPS.GREEN, label: 'First Blood',             kind: 'chance',     rate: 1934,  unit: 'first blood',     unitPlural: 'first bloods',       asset: 'first_blood' },
  courier_kills:    { group: GROUPS.GREEN, label: 'Courier Kills',           kind: 'per',        rate: 703,   unit: 'courier kill',    unitPlural: 'courier kills',      asset: 'courier_kill' },
};

export const STATS_BY_GROUP = Object.entries(EMBLEM_STATS).reduce((acc, [key, s]) => {
  (acc[s.group] ||= []).push(key);
  return acc;
}, {});

// ---------------------------------------------------------------------------
// Emblem quality tiers
// ---------------------------------------------------------------------------
export const TIERS = {
  I:   { label: 'Tier I',   roman: 'I',   bonus: 10 },
  II:  { label: 'Tier II',  roman: 'II',  bonus: 30 },
  III: { label: 'Tier III', roman: 'III', bonus: 60 },
  IV:  { label: 'Tier IV',  roman: 'IV',  bonus: 100 },
  V:   { label: 'Tier V',   roman: 'V',   bonus: 150 },
};
export const TIER_KEYS = ['I', 'II', 'III', 'IV', 'V'];

// Higher tiers are rarer when rolling. Not from the client (the client doesn't
// publish odds) — this is a prototype affordance, flagged as such.
export const TIER_ROLL_WEIGHTS = { I: 34, II: 30, III: 20, IV: 11, V: 5 };

// ---------------------------------------------------------------------------
// Emblem traits.
//   self     — bonus this emblem grants itself when its condition holds
//   adjacent — bonus/penalty applied to NEIGHBOURING emblems
// "Incorruptible" appears in third-party guides but not in the supplied
// glossary, so it is deliberately excluded. See DESIGN_BRIEF.md.
// ---------------------------------------------------------------------------
export const TRAITS = {
  FRACTAL: {
    label: 'Fractal',
    self: 60,
    adjacent: 0,
    condition: 'allTiersDifferent',
    text: '+60% to the stat bonus if all emblem qualities on the banner are different.',
  },
  BENEVOLENT: {
    label: 'Benevolent',
    self: 0,
    adjacent: 20,
    condition: 'always',
    text: 'Provides a 20% bonus to the stat value of neighbouring emblems.',
  },
  VAMPIRIC: {
    label: 'Vampiric',
    self: 50,
    adjacent: -10,
    condition: 'always',
    text: 'Increases this emblem’s stat value by 50%, but lowers neighbouring emblems by 10%.',
  },
  UNIQUE: {
    label: 'Unique',
    self: 30,
    adjacent: 0,
    condition: 'onlyUnique',
    text: '+30% to the stat bonus if this is the only Unique emblem on the banner.',
  },
  FRIENDLY: {
    label: 'Friendly',
    self: 50,
    adjacent: 0,
    condition: 'threeFriendly',
    text: '+50% to the stat bonus if there are at least 3 Friendly emblems on the banner.',
  },
};
export const TRAIT_KEYS = Object.keys(TRAITS);

// ---------------------------------------------------------------------------
// Roles. Colour composition per banner is fixed and comes from the client.
// ---------------------------------------------------------------------------
export const ROLES = {
  core: {
    key: 'core',
    label: 'Core',
    pickTitle: 'Choose Your Core Duo',
    playerCount: 2,
    slots: [GROUPS.RED, GROUPS.RED, GROUPS.GREEN],
  },
  mid: {
    key: 'mid',
    label: 'Mid',
    pickTitle: 'Choose Your Mid Player',
    playerCount: 1,
    slots: [GROUPS.RED, GROUPS.BLUE, GROUPS.GREEN],
  },
  support: {
    key: 'support',
    label: 'Support',
    pickTitle: 'Choose Your Support Duo',
    playerCount: 2,
    slots: [GROUPS.BLUE, GROUPS.BLUE, GROUPS.GREEN],
  },
};
export const ROLE_KEYS = ['core', 'mid', 'support'];

// ---------------------------------------------------------------------------
// Coaching titles. Free to change — no token cost.
// Prefix conditions depend on hero colour/type, which this prototype does not
// simulate (see brief, Out of Scope). They are presented as conditional and
// are NOT resolved into projections.
// ---------------------------------------------------------------------------
export const PREFIXES = [
  { key: 'crimson',     label: 'Crimson',     bonus: 6,  text: 'when playing a red hero' },
  { key: 'cerulean',    label: 'Cerulean',    bonus: 11, text: 'when playing a blue hero' },
  { key: 'emerald',     label: 'Emerald',     bonus: 6,  text: 'when playing a green hero' },
  { key: 'royal',       label: 'Royal',       bonus: 10, text: 'when playing a purple hero' },
  { key: 'golden',      label: 'Golden',      bonus: 8,  text: 'when playing a yellow or brown hero' },
  { key: 'elemental',   label: 'Elemental',   bonus: 8,  text: 'when playing an Aquatic, Fiery, or Icy hero' },
  { key: 'otherworldly',label: 'Otherworldly',bonus: 7,  text: 'when playing an Undead, Demon, or Spirit hero' },
  { key: 'heroic',      label: 'Heroic',      bonus: 9,  text: 'when playing a Caped or Masked hero' },
];

export const SUFFIXES = [
  { key: 'tormented',   label: 'the Tormented',            bonus: 23, text: 'if any player dies to a Tormentor' },
  { key: 'flayed',      label: 'the Flayed Twins Acolyte', bonus: 9,  text: 'if any player gets first blood before the starting horn' },
  { key: 'patient',     label: 'the Patient',              bonus: 23, text: 'if first blood does not happen until after 10 minutes' },
  { key: 'underdog',    label: 'the Underdog',             bonus: 6,  text: 'in games where the player loses' },
  { key: 'decisive',    label: 'the Decisive',             bonus: 24, text: 'in games that last less than 25 minutes' },
  { key: 'clutch',      label: 'the Clutch',               bonus: 16, text: 'when playing the last possible match of a series' },
  { key: 'lucky',       label: 'the Lucky',                bonus: 21, text: 'if the match time ends with an 8' },
  { key: 'cruel',       label: 'the Cruel',                bonus: 13, text: 'if a player is killed in their own fountain' },
];

// ---------------------------------------------------------------------------
// Reward ladder — percentile to compendium points
// ---------------------------------------------------------------------------
export const REWARD_LADDER = [
  { percentile: 100, points: 12000 },
  { percentile: 99,  points: 11400 },
  { percentile: 95,  points: 10000 },
  { percentile: 90,  points: 8400 },
  { percentile: 80,  points: 5800 },
  { percentile: 60,  points: 3300 },
  { percentile: 40,  points: 1700 },
  { percentile: 20,  points: 400 },
  { percentile: 10,  points: 200 },
];

// ---------------------------------------------------------------------------
// Roll economy — ~40 tokens per stage, 3 options at a time
// ---------------------------------------------------------------------------
export const ROLL = {
  tokensPerPeriod: 40,
  optionsShown: 3,
  costPerRoll: 1,
};

export const PERIODS = [
  { key: 'group',    label: 'Group Stage', locked: false },
  { key: 'playoffs', label: 'Playoffs',    locked: false },
];

// ---------------------------------------------------------------------------
// Scoring resolution rules, surfaced in the glossary as prose.
// ---------------------------------------------------------------------------
export const SCORING_RULES = [
  'Once matches for a period begin, a snapshot of your roster is saved and used for scoring.',
  'Each player’s score is calculated individually in every game they participate in.',
  'Players receive points only for the stats present on their banner.',
  'Scores are averaged across all players in a role to produce that role’s score for a game.',
  'The top two scoring games within a series are used for the role’s final score for the match.',
  'If a role participates in more than one series in a period, the best scoring series is used.',
];
