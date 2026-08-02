# Design Brief: Dota 2 Fantasy Analytics

**Feature slug**: `dota-fantasy`
**Date**: 2026-08-01 · **Revised**: 2026-08-01
**Deliverable**: Working UI shell (React + Vite + Tailwind, generated stats), to be adapted onto the author's own analytics

---

## ⚠ Revision — direction change

The original brief described a *recommendation engine* wrapped in a *Heraldic Deco*
aesthetic. Both were wrong for what this product is. Superseded as follows:

| Was | Now |
| --- | --- |
| Advisor ranks teams and tells you what to reroll | **No advisor.** The user selects the data themselves. Removed entirely. |
| Roll tokens, 3 random options, spend-to-change | **Direct selection.** Any of the 18 emblems, any tier, any trait, chosen outright. No token economy. |
| Heraldic Deco — parchment, gold bevels, Cinzel, grain | **Modern minimalist** — flat neutral surfaces, hairline borders, no ornament. |
| Emblem PNGs tinted via CSS mask | **Emblem artwork rendered as-is.** The mask reduced detailed illustrations to flat silhouettes. Icons are images now, never tinted. |
| Emblem colour derived from the stat's group | **Colour is fixed to the slot.** Any icon can go in any slot; the slot's colour never changes. |

Sections below are updated to match. The scoring data, engine, IA, and asset
handling notes are unchanged and still accurate.

---

## Problem

You are three rolls into your War Banner and you have no idea whether you just made it better.

The Dota 2 Compendium fantasy client tells you an emblem is worth **180%**. It does not tell you 180% *of what*. It does not tell you that a 180% Smokes Used emblem on a support who averages 1.4 smokes a game is worth a fraction of a 130% Wards Placed emblem on the same player. It does not tell you that your Vampiric emblem is quietly draining 10% from the two emblems beside it. And once your banner is set, it does not help you answer the only question that actually matters: **given these three emblems, which team should I slot into this role?**

So players roll on feel. They chase Tier V because bigger numbers look better, they pick teams by reputation instead of by fit, and they find out at the end of the period that a stat they never scored in was occupying a third of their banner. The information needed to play well exists — it is spread across a glossary modal, a percentage badge, and knowledge of pro players' stat profiles that almost nobody holds in their head at once.

The friction is not that the game is hard. It is that the interface withholds the arithmetic.

## Solution

A banner builder that does the math out loud.

You see your three War Banners — Core, Mid, Support — laid out as they are in the client, but every percentage is accompanied by what it is actually worth. Roll an emblem and you do not just watch a stat change; you watch a projected point total move, and you see which direction it moved. Adjacency effects are drawn, not buried in a glossary: when you hover a Vampiric emblem, the two emblems it is draining dim and show their penalty.

Then the part the client does not do at all. Once your emblems are set, the interface turns around and **recommends**. It ranks all sixteen teams for each role against *your specific banner*, and tells you why: "Xtreme Gaming for Support — fy and xNova average 12.4 observer wards between them, and your banner is wards-weighted." It flags the weakest link in your build and what to do about it: "Your green emblem is Stuns. Rerolling to Teamfight Participation projects +6.1k. Keep the Tier IV — you will not beat it easily." It distinguishes what to change from what to keep, because roll tokens are finite.

The result is a fantasy tool where a player who has never read a guide can make guide-quality decisions, and see the reasoning well enough to eventually stop needing it.

## Experience Principles

1. **Show the math, not just the multiplier** — Every percentage in this interface is one hover away from the points it represents. `GPM 180%` is never displayed without `≈ 2,140 pts` nearby. The client's mystique is the thing we are removing; if a number appears, its derivation is reachable.

2. **Advise, never decide** — The system ranks, projects, and explains, then stops. It does not auto-roll, auto-pick, or hide options it scored badly. A recommendation always shows its reasoning and its runner-up, because a player who disagrees with the advisor needs to be able to see what the advisor saw. Guidance that cannot be audited is just a slot machine with better manners.

3. **Ceremony where it counts, clarity everywhere else** — The roll is the emotional peak of this product and it gets full theatre: the token spends, the three options land, the emblem mutates, the projection recalculates. Everything else — tables, glossary, standings — is plain, dense, and fast. Spectacle is a budget, and it is spent entirely on the moment of change.

## Aesthetic Direction

- **Philosophy**: **Modern minimalist.** Closest to Dieter Rams in the `/frontend-design` set — less but better, nothing decorative without function — executed dark. Flat neutral surfaces, hairline borders, generous space, no gradients on chrome, no shadows except overlays, no ornament.

- **The organising rule**: **the interface is greyscale; colour means something.** The only saturated colour in the product is the emblem group colour (red / blue / green) and each team's own crest. Nothing decorative is ever coloured. This is what makes it read as a tool rather than a game skin, and it is the constraint everything else follows from.

- **Tone**: Quiet, precise, fast. The user is reading numbers and changing inputs. The interface should get out of the way.

- **Type**: Space Grotesk (headings, geometric with character), Manrope (body/UI), JetBrains Mono for **every figure** — a mono numeric face is the honest choice here: perfect column alignment, and numbers read as data rather than prose.

- **Reference points**:
  - Modern analytics and data tooling — Linear, Vercel, Datadog-class density without the clutter
  - The emblem artwork itself, which is detailed and dark and needs a quiet frame around it

- **Anti-references**:
  - The previous direction — parchment, gold bevels, letterspaced serif caps, grain overlays
  - Generic AI aesthetic — purple-to-pink gradients, rounded-2xl shadow-xl glass, Inter
  - Any UI that spends colour on decoration, which would collapse the one rule the system rests on
  - Skeuomorphic game chrome. This is an analytics tool that happens to be about Dota.

## Existing Patterns

Greenfield. Codebase scan found no `tokens.css`, no `variables.css`, no `theme.css`, no `:root` custom property declarations, no `tailwind.config.*`, no `components.json`, no `.storybook/`, no component directories, no `package.json`, and no font loading of any kind. The only pre-existing directory is `.claude/`.

**This brief therefore defines the vocabulary rather than extending one.** Nothing here needs to respect a prior system.

- **Typography**: none established. To be set in Phase 4. Direction: a display face with heraldic/deco character for role titles and numerals (candidates: Cinzel, Marcellus, Trajan-adjacent), paired with a highly legible small-caps-capable sans for labels and a tabular-figure face for all point values. Tabular numerals are non-negotiable — this interface is full of aligned four- and five-digit scores.
- **Colors**: none established. To be derived in Phase 4 directly from the supplied screenshots. Known structure: warm dark ground, aged gold accent, parchment/tan banner field, cream text, plus three fixed emblem hues (red / blue / green) that are semantic and must not be repurposed decoratively. One cool dark-slate surface exists for the team chooser and must be reconciled deliberately rather than accidentally.
- **Spacing**: none established. 4px base scale to be set in Phase 4.
- **Components**: none exist. Full inventory below is new.

### Supplied assets (real, in-repo)

| Path | Contents | Format |
| --- | --- | --- |
| `fantasy_craft/` | 18 emblem glyphs | 128×128 PNG, pure white on transparent |
| `players/<Team>/` | 80 player portraits (16 teams × 5) | 1024×1024 PNG, transparent cutout, front-facing |
| `teams/` | 16 team logos | 256×256 PNG, **full-colour** embroidered patch, transparent |

Two distinct asset classes, and they need opposite handling:

- **Emblems are white-on-transparent** and must be **tinted** to their semantic group colour (red / blue / green) plus glowed. Tint and glow are first-class token primitives, not one-off filters.
- **Team logos arrive in full brand colour** and must **never** be tinted. Team Spirit and Xtreme Gaming are white only because their real logos are white; LGD is blue/red, Nigma purple, OG green, Aurora teal, Iron Wing gold.

This creates the palette's central constraint: **sixteen uncontrolled brand palettes must sit on a warm brown ground without colliding with the semantic red/blue/green emblem system.** A blue LGD crest must never read as a "blue emblem" cue. Resolution levers available: desaturate/dim unselected crests (the client already does this in its compact picker), confine crests to a distinct surface treatment, and keep emblem colour always paired with its glyph and stat name. This must be settled explicitly in Phase 4, not discovered during build.

**Known asset defects to normalize at build time:**
- `teams/TeamFalcon.png` is singular; `players/TeamFalcons/` is plural. Reconcile to one canonical team key.
- Several player filenames contain URL- and shell-hostile characters: `Kataomi\`.png`, `y\`.png`, `No[o]ne-.png`, `Save-.png`. Slugify on import; keep display names intact and separate from file keys.
- `IronWings` (folder) vs. `IRON WING` (client bracket label). Pick one display string.

## Data Provenance

This distinction is load-bearing and must be visible in the UI itself.

**Real — taken verbatim from the supplied client glossary. Never invent or adjust these:**

*Base point values (per game):*

| Stat | Value |
| --- | --- |
| Kills | +107.00 per kill |
| Deaths | 1,950.00 starting, −195.00 per death |
| Creep Score | +3.00 per last hit or deny |
| GPM | player's GPM × 2.00 |
| Madstone Collected | +13.00 per madstone |
| Tower Kills | +352.00 per tower last hit |
| Wards Placed | +117.00 per observer ward placed |
| Camps Stacked | +234.00 per camp stacked |
| Runes Grabbed | +141.00 per rune bottled or taken |
| Watchers Taken | +147.00 per captured watcher |
| Lotuses Grabbed | +176.00 per lotus taken |
| Roshan Kills | +1,172.00 per Roshan kill |
| Teamfight Participation | max 2,124.00 |
| Stuns | +10.00 per second of stun |
| Tormentor Kills | +879.00 per Tormentor kill |
| Courier Kills | +703.00 per courier kill |
| First Blood | 1,934.00 |
| Smokes Used | +293.00 per Smoke of Deceit used |

*Emblem quality tiers:* I +10% · II +30% · III +60% · IV +100% · V +150%

*Emblem traits:*
- **Fractal** — +60% to stat bonus if all emblem qualities on the banner are different
- **Benevolent** — provides a 20% bonus to the stat value of adjacent emblems
- **Vampiric** — +50% to this emblem's stat value, −10% to adjacent emblems
- **Unique** — +30% if this is the only Unique emblem on the banner
- **Friendly** — +50% if there are at least 3 Friendly emblems on the banner (on a 3-emblem banner: all three)

*Emblem color groups (fixed; color is never rerollable):*
- **Red** — Kills, Deaths, Creep Score, GPM, Madstone Collected, Tower Kills
- **Blue** — Wards Placed, Camps Stacked, Runes Grabbed, Watchers Taken, Smokes Used, Lotuses Grabbed
- **Green** — Roshan Kills, Teamfight Participation, Stuns, Tormentor Kills, First Blood, Courier Kills

*Banner composition by role:* Core = 2 red + 1 green · Mid = 1 red + 1 blue + 1 green · Support = 2 blue + 1 green

*Display formula (verified against screenshots):* `displayed % = 100 + tier bonus + trait bonus`
Confirmed: `GPM 180% = 100 + Tier II (30) + Vampiric (50)`; `Lotuses 160% = 100 + Tier III (60) + Fractal (0)`

*Coaching title prefixes:* Crimson +6% (red hero) · Cerulean +11% (blue) · Emerald +6% (green) · Royal +10% (purple) · Golden +8% (yellow/brown) · Elemental +8% (Aquatic/Fiery/Icy) · Otherworldly +7% (Undead/Demon/Spirit) · Heroic +9% (Caped/Masked)

*Coaching title suffixes:* the Tormented +23% · the Flayed Twins Acolyte +9% · the Patient +23% · the Underdog +6% · the Decisive +24% · the Clutch +16% · the Lucky +21% · the Cruel +13%

*Scoring resolution:* Roster snapshot taken when the period's matches begin. Each player scored individually per game. **Players receive points only for stats present on their banner.** Title conditions amplify. Scores averaged across all players in a role to produce the role's score for a game. Top two scoring games in a series produce the role's match score. If a role plays more than one series in a period, the best series counts.

*Reward ladder (percentile → points):* 100th 12,000 · 99th 11,400 · 95th 10,000 · 90th 8,400 · 80th 5,800 · 60th 3,300 · 40th 1,700 · 20th 400 · 10th 200

*Roll economy:* 3 unique roll options available at a time, identical across all banners. Each roll costs 1 token, affects only the selected banner, and replaces all available options. Approximately 40 tokens granted per stage. Titles are free to change.

*Teams (16):* Team Yandex, Team Vision, BoomBoys, Team Falcons, LGD Gaming, Team Liquid, Aurora Gaming, Team Spirit, Vici Gaming, Team Resilience, GamerLegion, Huligani, Nigma Galaxy, Xtreme Gaming, Iron Wings, OG

**Modeled — generated, plausible, and explicitly labeled as such in the UI:**

Per-player per-stat averages (GPM, CS, wards, stuns, teamfight %, etc.) for all 80 players. Real per-player TI statistics are not obtainable offline, and the advisor cannot function without them. These will be generated to be **role-coherent** — cores carry high CS and GPM, hard supports carry high ward and stack counts, mids skew rune and smoke — and internally consistent so that recommendations are defensible, but they are fiction.

Consequence: **the recommendation engine's rankings are demonstrations of a working method, not real fantasy advice.** The UI must carry a persistent, non-dismissable marker to that effect on any surface that projects points. This is a correctness requirement, not a disclaimer nicety — a fantasy tool that looks authoritative while running on invented numbers is actively harmful to a user making real roll-token decisions.

*Unresolved:* a sixth trait, "Incorruptible," appears in third-party guides but not in the supplied glossary. Excluded until confirmed.

## Component Inventory

| Component | Status | Notes |
| --- | --- | --- |
| `AppShell` | New | Warm dark ground, ornamental frame, period/stage header, roll-token counter |
| `BannerColumn` | New | The spine. Role title, team logo, CHANGE TEAM button, 3 emblem slots, player portraits at base |
| `EmblemCard` | New | Color-coded (red/blue/green), glyph + stat name + computed %, tier row, trait row. Hover reveals point value |
| `EmblemRollPanel` | New | The 3 roll options, token cost, spend action, before/after projection delta |
| `AdjacencyIndicator` | New | Draws Vampiric drain / Benevolent boost between adjacent emblems on hover |
| `PointBreakdown` | New | The math, expanded: base value × tier × trait × title → projected points |
| `TeamChooserModal` | New | Dark slate surface, 16 logos in 2×8 grid, selected state. Ranked by fit for the active role |
| `TeamFitCard` | New | Inside chooser: team, its players for this role, projected score, one-line reasoning |
| `TitlesModal` | New | Two columns, 8 prefixes / 8 suffixes, gold-fill selected rows, condition text |
| `GlossaryModal` | New | Two-column reference. All real values above. Ornamental gold frame, cartouche title |
| `PlayerCard` | New | 1024px portrait, team, role, per-emblem stat profile, form |
| `AdvisorPanel` | New | Ranked recommendations, keep/change verdicts, projected deltas, runner-up always shown |
| `MatchDayBoard` | New | Live per-role scoring, emblem-by-emblem point attribution, count-up on reveal |
| `GroupStageBracket` | New | 16 teams across 4-0 → 0-4 outcome bands |
| `LeaderboardTable` | New | Percentile ladder → reward points. Dense, tabular figures |
| `EmblemGlyph` | New | Tint + glow primitive wrapping the 18 white PNGs |
| `TeamCrest` | New | Tint + glow primitive wrapping the 16 white logos |
| `GoldButton` | New | Beveled gold gradient, small-caps letterspaced label. Primary action hardware |
| `ModelledDataBadge` | New | Persistent marker on projection surfaces. See Data Provenance |

## Key Interactions

**Rolling an emblem.** Click an emblem slot → the banner dims except the selected emblem, and the roll panel enters from the side with three options. Each option shows its stat, tier, trait, and — critically — the projected point delta against the current emblem, signed and colored. Spending a token: the token counter decrements with weight, the old emblem dissolves, the new one lands with a staggered reveal (glyph, then stat, then tier, then trait), and the banner's projected total counts up or down to its new value. The three options are replaced. This is the product's peak moment and gets the full 600–800ms.

**Reading the math.** Hovering any percentage badge expands a breakdown popover: base stat value → × tier → × trait → × active title conditions → projected points, each step on its own line with its own number. Nothing is asserted without derivation.

**Adjacency.** Hovering a Vampiric emblem dims the two adjacent emblems and overlays their −10%. Hovering Benevolent brightens adjacent emblems and overlays +20%. Fractal highlights all three tier badges when the all-different condition is met, and shows them struck through when it is not. The adjacency rules are the single most-missed mechanic in the real client; making them spatial rather than textual is the fix.

**Choosing a team.** CHANGE TEAM opens the dark slate chooser. Unlike the client's flat grid, teams are **ranked for the active role against the current banner**, with the projected score and a one-line reason on each. Selecting one swaps the portraits at the banner base with a cross-fade and recalculates. The previously selected team stays visible with its delta, so the user can see what they gave up.

**Advisor guidance.** A persistent panel answers "what now?" It surfaces the single highest-value change available, its projected delta, and its token cost; it explicitly marks emblems as *keep* (with the reason — usually a tier that is expensive to beat) versus *change*. Every recommendation shows its runner-up. Nothing auto-applies.

**Match day.** Points accrue per role with emblem-by-emblem attribution — the user sees not just that Core scored 41k but that 22k of it came from Creep Score. Numbers count up on reveal. Stats not on the banner render as visible zeroes rather than being omitted, so the cost of a bad emblem is legible after the fact.

## Responsive Behavior

Design decisions are made at **1280+**, where the three-banner spine is the layout. Implementation still uses `min-width` media queries and mobile-first CSS mechanics — the design priority is desktop; the code is authored bottom-up.

- **1280+** — Three banner columns side by side, advisor panel docked right. Full spine visible at once. The target experience.
- **1024–1279** — Three columns retained but narrowed; advisor collapses to a bottom drawer. Emblem cards drop the trait description text, keeping name and percentage.
- **768–1023** — Banners become a two-up plus one wrap, or a horizontal snap-scroll carousel of three full-width banners. **This is a behavior change, not a resize** — the spine metaphor breaks and role switching becomes navigation rather than layout.
- **375–767** — One banner at a time, role switching via a segmented control fixed below the header. Roll panel becomes a bottom sheet. Portraits crop to head-and-shoulders. Advisor becomes a dismissible card above the banner. Touch targets 44×44 minimum; body text 16px minimum.

The emblem card is the component most at risk. At mobile width it must retain stat name, computed percentage, and color, and may drop tier/trait rows behind a tap.

## Accessibility Requirements

- **Contrast**: 4.5:1 minimum for body text and all numeric values against their actual backgrounds — including cream text on parchment, which is the likeliest failure in this palette and must be checked rather than assumed. 3:1 for large display type and for UI component boundaries. Gold-on-brown is the second risk area; the gold accent may need a lightness fork between "ornament" and "text" use.
- **Color is never the only channel.** Emblem red/blue/green carries real meaning (stat group). Every emblem must also carry its glyph and its stat name in text. A red/green colorblind user must be able to build a banner with no loss of information — this rules out any design where the color chip alone communicates group.
- **Keyboard**: full traversal of banner → emblem slot → roll option → spend. Modals trap focus and restore it to their trigger on close. Escape closes. The roll action must be reachable and confirmable without a pointer.
- **Screen reader**: emblem cards announce as a composite — stat name, computed percentage, tier, trait, and projected points — not as four disconnected nodes. Point-total changes after a roll announce via a polite live region. Adjacency effects, being hover-only visuals, require a text equivalent in the emblem's accessible description.
- **Motion**: `prefers-reduced-motion` disables the roll sequence's staggered reveal, portrait parallax, and count-up animations, replacing them with instant state changes. The information must be identical; only the theatre is removed.
- **Focus**: visible focus rings that survive the gold-on-dark palette — a single ring color will likely fail on either parchment or slate, so two are budgeted.

## Out of Scope

- **Light theme.** Dark only, deliberately. The entire asset kit is white-on-transparent and a light variant would fight every token.
- **Real backend, auth, accounts, persistence.** State lives in memory for the session.
- **Real match data or live scoring.** Match day runs on fixed mock fixtures, not a feed.
- **Real per-player statistics.** See Data Provenance — modeled and labeled.
- **The actual Compendium economy** — buying levels, earning tokens through play, rewards fulfilment. Tokens are a fixed session budget.
- **Multiplayer, friend leagues, or social comparison** beyond the static percentile ladder.
- **Hero-level modeling.** Coaching title prefixes are hero-color conditional; we surface the titles and their stated conditions but do not simulate hero picks. Prefix bonuses are presented as conditional, not resolved.
- **"Incorruptible" trait** — unverified, excluded.
- **Localization.** English only.
- **Crafting economy design** — no roll-odds tuning, no rarity curve balancing. Rolling exists as an interaction, not as a system to be balanced.
