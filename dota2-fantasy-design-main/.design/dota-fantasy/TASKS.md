# Build Tasks: Dota 2 Fantasy — Banner Builder & Advisor

Generated from: `.design/dota-fantasy/DESIGN_BRIEF.md`
Also reads: `INFORMATION_ARCHITECTURE.md`, `DESIGN_TOKENS.css`, `tailwind.config.js`
Date: 2026-08-01

**Codebase state**: greenfield. No components, no tokens installed, no router, no `package.json`. Every component below is new; nothing is reused or modified. Project scaffolding is folded into Task 1 rather than being its own task — a scaffold is not a vertical slice.

**Ordering logic**: risk first (the emblem card and the scoring engine are where this either works or doesn't), then visual priority (the banner spine early, so the aesthetic can be judged before detail work), then dependency.

---

## Foundation

- [x] **1. App shell & token installation** — Scaffold Vite + React + Tailwind, wire `DESIGN_TOKENS.css` and `tailwind.config.js`, load Cinzel / Alegreya Sans / Barlow Semi Condensed. Build `AppShell`: ornamental gold outer frame, header with period selector + roll-token counter + glossary link, 4-item primary nav, bottom tab bar at ≤767. **Establishes the Heraldic Deco philosophy** — grain texture, bevel hardware, letterspaced small-caps labels. Done when the shell renders correctly at 375 / 768 / 1024 / 1280 with no content inside it. _New. Blocks everything._

- [x] **2. Asset primitives & normalization** — `EmblemGlyph` (white PNG → group tint + glow via `[data-emblem]` scope), `TeamCrest` (neutral plate, idle/hover/selected/disabled filter states), `PlayerPortrait` (crop framing, parallax-ready transform). Includes the asset normalization the brief flagged: reconcile `TeamFalcon`/`TeamFalcons` and `IronWings`/`IRON WING`, and slugify the four hostile filenames (`` Kataomi`.png ``, `` y`.png ``, `No[o]ne-.png`, `Save-.png`) with display names kept separate from file keys. Done when all 18 emblems render in all 3 tints, all 16 crests in all 4 states, and all 80 portraits load. _New. Depends on: 1._

- [x] **3. Scoring engine & glossary** — _Engine self-verifies against all 9 reference cards on boot. Glossary renders directly from the engine's constants, so it cannot drift from the math._ — Implement the real 2025 math: 18 base stat values, tier multipliers (I +10 → V +150), the five traits including adjacency resolution, title condition multipliers, and the `100 + tier + trait` display formula. Render it as `/glossary` — the engine's constants in human-readable form, two columns, ornamental frame. Done when the glossary displays every real value from the brief and the engine reproduces the verified case `GPM 180% = 100 + Tier II 30 + Vampiric 50`. _New. Depends on: 1. Highest-value task to get right — everything downstream trusts this._

- [x] **4. Modelled dataset & provenance badge** — Generate role-coherent per-player averages across all 18 stat categories for all 80 players, from a fixed seed so results are reproducible. Cores carry CS and GPM, hard supports carry wards and stacks, mids skew runes and smokes. Build `ModelledDataBadge` — persistent, non-dismissable. Done when supports out-ward cores, cores out-farm supports, and the badge appears on every projecting surface. _New. Depends on: 3. **The badge is a correctness requirement, not decoration** — see brief, Data Provenance._

- [x] **5. Routed overlay primitive** — `RouteOverlay`: focus trap, Escape to close, focus restoration to trigger, underlying route stays mounted, cold deep-link falls back to `/build` beneath. Set up React Router with all routes from the IA. Done when `/glossary` deep-links cold with `/build` behind it and the back button closes rather than exiting. _New. Depends on: 1, 3. Blocks every modal task._

---

## Core UI

- [x] **6. EmblemCard** — **Build this before anything else visual.** The atom of the entire product and the riskiest component: it carries the semantic colour system, the bevel treatment, tinted glyphs, and the computed percentage. All three groups, header strip + inset well, tier row, trait row. Done when a red, blue, and green card sit side by side and read as Dota hardware rather than dark web cards. _New. Depends on: 2, 3._

- [x] **7. BannerColumn** — The spine. Parchment surface (`data-surface="parchment"`, umber text ramp), role title in Cinzel at widest tracking, team crest, three emblem slots, portraits at the foot on the decorative gradient. Core/Support show a duo, Mid shows one. Done when three banners render with correct role composition — Core 2 red + 1 green, Mid one of each, Support 2 blue + 1 green. _New. Depends on: 6. This is the screenshot that proves the aesthetic._

- [~] **8. Builder page** — _Three banners, live projections, and the responsive segmented control are DONE. Period lock state still outstanding._ — `/build` assembling three banners with per-role and combined projected totals, always visible without scrolling. Period-aware lock state. Done when changing any emblem or team moves the projection. _New. Depends on: 7, 4._

- [ ] **9. Full-grid team picker & setup sequence** — `/setup/core|mid|support`, 16 cards each with crest, name, and that team's duo (or solo mid), SUBMIT gated on a changed selection, chrome-free shell. Seed-ordered with the advisor silent — there is no banner to rank against yet. Includes the skip path to a sample lineup. Done when all three steps complete into a populated `/build`, and skip reaches `/build` in one click. _New. Depends on: 2, 8._

- [x] **10. Compact ranked team picker** — `/build/:role/team` on the slate surface (`data-surface="slate"` — the one cool surface in the product). 16 crests ranked by projected fit against the current banner, each with its projected score and a one-line reason. Current pick stays visible with its delta. Done when reordering demonstrably follows the banner's emblems, not a fixed order. _New. Depends on: 5, 9, 4._

- [x] **11. Advisor panel** — Ranked recommendations with keep/change verdicts, projected deltas, token costs, and the runner-up always shown. Docked right at ≥1280, bottom drawer at 1024–1279, dismissible card below. Done when it names the single highest-value change with auditable reasoning and never auto-applies anything. _New. Depends on: 10. **Principle 2 lives or dies here** — advise, never decide._

---

## Interactions & States

- [x] **12. Roll interaction** — The ceremony, and the peak moment of the product. `/build/:role/emblem/:slot`: banner dims except the selected emblem, three options enter with signed coloured deltas, token spend decrements with weight, old emblem dissolves, new one lands in a 4-step stagger (glyph → stat → tier → trait), totals count up. Options replace after every roll. Covers: default, hover, focus, spending, zero-token (options shown read-only with the reason stated, never hidden), reduced-motion. Done when the full sequence runs at ~800ms and feels like a game, not a form submit. _New. Depends on: 6, 8, 5._

- [ ] **13. Point breakdown popover** — `PointBreakdown` on every percentage anywhere in the product: base → × tier → × trait → × title → projected, one line per step. Popover at ≥768, bottom sheet below. Sits above routed overlays in the z-stack. Done when no percentage anywhere is more than one hover or tap from its derivation. _New. Depends on: 3, 6. **Principle 1 lives or dies here.**_

- [ ] **14. Adjacency visualization** — Hovering a Vampiric emblem dims its neighbours and overlays −10%; Benevolent brightens them and overlays +20%; Fractal highlights all three tier badges when satisfied and strikes them through when not. Text equivalents in accessible descriptions, since the visual is hover-only. Done when the most-missed mechanic in the real client is legible without reading the glossary. _New. Depends on: 7, 3._

- [ ] **15. Titles modal** — `/titles`, two columns of 8 prefixes and 8 suffixes with condition text, gold-fill on selected rows. Free to change per the real rules, so selections apply immediately with live projection updates rather than a commit step. Done when switching a title visibly moves the projected total. _New. Depends on: 5, 3._

---

## Secondary Screens

- [ ] **16. Match day** — `/matches` with per-role scores and emblem-by-emblem attribution, plus `/matches/:seriesId` for game detail and which two games counted. **Stats not on the banner render as visible zeroes**, never omitted — the cost of a bad emblem is only legible if the miss is shown. Count-up on reveal. Done when a user can see which emblems produced their score and which produced nothing. _New. Depends on: 4, 7._

- [ ] **17. Standings** — `/standings` with the real percentile ladder (100th → 10th, 12,000 → 200 points), the user's position marked, and distance to the next tier. Dense table, tabular figures throughout. Done when the ladder matches the brief's values exactly. _New. Depends on: 4._

- [ ] **18. Group stage bracket** — `/bracket`, 16 teams across the 4-0 → 0-4 outcome bands from the client, with the user's three teams highlighted in the field. Done when all 16 crests render at once without scrolling at ≥1280. _New. Depends on: 2._

- [ ] **19. Player detail** — `/players/:playerSlug`, the 1024px portrait finally at full strength, per-stat averages across all 18 categories, and a relevance filter showing which of the user's emblems this player actually scores in. Done when the portrait asset justifies its file size. _New. Depends on: 4, 5._

---

## Responsive & Polish

- [ ] **20. Responsive pass** — Breakpoints 375 / 768 / 1024 / 1280 / 1536. The behaviour changes, not just resizes: three-column spine → carousel at 768–1023 → single banner with segmented control at ≤767, where `/build/:role` stops meaning focus and starts meaning navigation. Roll panel becomes a bottom sheet. Advisor demotes twice. EmblemCard keeps stat name, percentage, and colour at every size, dropping tier/trait behind a tap at mobile. Touch targets ≥44×44, body ≥16px. _Depends on: 8–19._

- [ ] **21. Accessibility pass** — Keyboard traversal banner → slot → roll option → spend, fully pointer-free. Emblem cards announce as one composite node, not four. Polite live region for post-roll total changes. Text equivalents for hover-only adjacency. Verify the two focus rings survive parchment, dark, and slate. **Re-verify the 40 token contrast pairs against real rendered output** — they pass as values, but gradients and texture overlays can push a pairing under. Confirm no information is colour-only: every emblem shows glyph + stat name alongside its group colour. _Depends on: 20._

- [ ] **22. Motion pass** — Card hover lift with portrait parallax, gold sheen on primary hardware, staggered reveals, count-ups. Verify the motion budget actually landed where the brief said: heavy on the roll, restrained everywhere else. Confirm `prefers-reduced-motion` removes all theatre while preserving every piece of information. _Depends on: 20._

---

## Review

- [ ] **23. Design review** — Run `/design-review` against the brief. Screenshots at all breakpoints into `.design/dota-fantasy/screenshots/`.

---

## Risk Notes

**Task 6 is the make-or-break.** If the EmblemCard doesn't read as Source 2 hardware, nothing built on top of it will either. Build it, look at it against the screenshots, and fix it before starting Task 7 — a wrong bevel treatment propagates into nineteen components.

**Task 3 before Task 4, always.** The engine defines what the modelled data has to satisfy. Generating stats first would mean tuning fiction against nothing.

**Task 11 is where the product's reason to exist gets tested.** An advisor that can't explain itself is a slot machine. If the reasoning strings come out vague ("Team Spirit is good"), the ranking model needs work, not the copy.

**The parchment/dark text inversion is the likeliest bug in the build.** Both ramps are warm browns and creams; a wrong pairing looks entirely plausible in code and is unreadable on screen. Use `[data-surface]` scoping rather than picking ramps by hand, and check any new surface against the forbidden-pairings block in the token file.
