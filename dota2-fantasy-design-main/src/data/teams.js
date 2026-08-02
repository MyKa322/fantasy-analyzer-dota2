/**
 * TEAMS & ROSTERS — 16 teams, 80 players.
 *
 * Team names, player names, and the group-stage outcome bands are REAL, taken
 * from the supplied assets and the reference bracket screenshot.
 *
 * Role assignments are best-effort from known competitive positions. Where a
 * player's position was ambiguous, a plausible assignment was made — this is
 * part of the modelled layer, not the real layer. See DESIGN_BRIEF.md.
 *
 * `crestFile` exists because the asset kit is inconsistent: teams/TeamFalcon.png
 * is singular while players/TeamFalcons/ is plural. Rather than rename the
 * user's files, the mismatch is absorbed here.
 */

/** Group-stage outcome bands, read from the reference bracket screenshot. */
export const BRACKET_BANDS = [
  { key: 'undefeated', label: '4-0',                       note: 'One undefeated team' },
  { key: 'four-one',   label: '4-1',                       note: 'Two teams with 4 wins and 1 loss' },
  { key: 'elim-win',   label: 'Elimination Round Winner',  note: 'Five teams that win in the Elimination Round' },
  { key: 'elim-loss',  label: 'Elimination Round Loser',   note: 'Five teams that lose in the Elimination Round' },
  { key: 'one-four',   label: '1-4',                       note: 'Two teams with 1 win and 4 losses' },
  { key: 'winless',    label: '0-4',                       note: 'One unvictorious team' },
];

export const TEAMS = [
  {
    key: 'team-yandex', name: 'Team Yandex', dir: 'TeamYandex', crestFile: 'TeamYandex',
    band: 'undefeated', seed: 1,
    roster: { core: ['Malady', 'watson'], mid: ['DM'], support: ['Saksa', 'CHIRA_JUNIOR'] },
  },
  {
    key: 'team-vision', name: 'Team Vision', dir: 'TeamVision', crestFile: 'TeamVision',
    band: 'four-one', seed: 2,
    roster: { core: ['Satanic', 'Noticed'], mid: ['No[o]ne-'], support: ['9Class', 'Dukalis'] },
  },
  {
    key: 'boomboys', name: 'BoomBoys', dir: 'BoomBoys', crestFile: 'BoomBoys',
    band: 'four-one', seed: 3,
    roster: { core: ['Kiritych', 'MieRo'], mid: ['gpk'], support: ['Kataomi`', 'Save-'] },
  },
  {
    key: 'team-falcons', name: 'Team Falcons', dir: 'TeamFalcons', crestFile: 'TeamFalcon',
    band: 'elim-win', seed: 4,
    roster: { core: ['skiter', 'AMMAR_THE_F'], mid: ['Malr1ne'], support: ['Cr1t-', 'Sneyking'] },
  },
  {
    key: 'lgd-gaming', name: 'LGD Gaming', dir: 'LGDGaming', crestFile: 'LGDGaming',
    band: 'elim-win', seed: 5,
    roster: { core: ['Yuma', 'TaiLung'], mid: ['Thiolicor'], support: ['kj', 'Wisper'] },
  },
  {
    key: 'team-liquid', name: 'Team Liquid', dir: 'TeamLiquid', crestFile: 'TeamLiquid',
    band: 'elim-win', seed: 6,
    roster: { core: ['miCKe', 'Boxi'], mid: ['Nisha'], support: ['Ace', 'tOfu'] },
  },
  {
    key: 'aurora-gaming', name: 'Aurora Gaming', dir: 'AuroraGaming', crestFile: 'AuroraGaming',
    band: 'elim-win', seed: 7,
    roster: { core: ['Nightfall', 'Ws'], mid: ['Mira'], support: ['Kaori', 'Mikoto'] },
  },
  {
    key: 'team-spirit', name: 'Team Spirit', dir: 'TeamSpirit', crestFile: 'TeamSpirit',
    band: 'elim-win', seed: 8,
    roster: { core: ['Yatoro', 'Collapse'], mid: ['Larl'], support: ['rue', 'not_me'] },
  },
  {
    key: 'vici-gaming', name: 'Vici Gaming', dir: 'ViciGaming', crestFile: 'ViciGaming',
    band: 'elim-loss', seed: 9,
    roster: { core: ['Xm', 'Faith_bian'], mid: ['y`'], support: ['XinQ', 'shiro'] },
  },
  {
    key: 'team-resilience', name: 'Team Resilience', dir: 'TeamResilience', crestFile: 'TeamResilience',
    band: 'elim-loss', seed: 10,
    roster: { core: ['planet', 'zzq'], mid: ['niu'], support: ['Echo', 'Erika'] },
  },
  {
    key: 'gamerlegion', name: 'GamerLegion', dir: 'GamerLegion', crestFile: 'GamerLegion',
    band: 'elim-loss', seed: 11,
    roster: { core: ['Ghost', 'RCY'], mid: ['Bignum'], support: ['Fayde', 'Speeed'] },
  },
  {
    key: 'huligani', name: 'Huligani', dir: 'Huligani', crestFile: 'Huligani',
    band: 'elim-loss', seed: 12,
    roster: { core: ['Mirage', 'Vazya'], mid: ['sayuw'], support: ['RESPECT', 'ssnovv1'] },
  },
  {
    key: 'nigma-galaxy', name: 'Nigma Galaxy', dir: 'NigmaGalaxy', crestFile: 'NigmaGalaxy',
    band: 'elim-loss', seed: 13,
    roster: { core: ['OmaR', 'lorenof'], mid: ['SumaiL'], support: ['GH', 'Davai'] },
  },
  {
    key: 'xtreme-gaming', name: 'Xtreme Gaming', dir: 'XtremeGaming', crestFile: 'XtremeGaming',
    band: 'one-four', seed: 14,
    roster: { core: ['Ame', 'Xxs'], mid: ['NothingToSay'], support: ['fy', 'xNova'] },
  },
  {
    key: 'iron-wings', name: 'Iron Wings', dir: 'IronWings', crestFile: 'IronWings',
    band: 'one-four', seed: 15,
    roster: { core: ['Pure', '33'], mid: ['bzm'], support: ['Ari', 'Whitemon'] },
  },
  {
    key: 'og', name: 'OG', dir: 'OG', crestFile: 'OG',
    band: 'winless', seed: 16,
    roster: { core: ['Raven', 'Natsumi'], mid: ['Yopaj'], support: ['Skem', 'Tims'] },
  },
];

export const TEAMS_BY_KEY = Object.fromEntries(TEAMS.map((t) => [t.key, t]));

/**
 * URL-safe player slug derived from the DISPLAY NAME, never the filename.
 * The asset kit contains `Kataomi`.png`, `y`.png`, `No[o]ne-.png` and
 * `Save-.png`, none of which survive a URL intact.
 */
export function playerSlug(name, teamKey) {
  const base = name
    .toLowerCase()
    .replace(/[`'"]/g, '')
    .replace(/[[\]()]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return `${teamKey}-${base || 'player'}`;
}
