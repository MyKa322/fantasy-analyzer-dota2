# Information Architecture: Dota 2 Fantasy — Banner Builder & Advisor

**Feature slug**: `dota-fantasy`
**Date**: 2026-08-01
**Reads from**: [DESIGN_BRIEF.md](./DESIGN_BRIEF.md)
**Stack**: React + Vite + Tailwind, client-side routing (React Router)

---

## Structural Premises

Settled from the brief without needing debate, recorded so the build doesn't relitigate them:

- **The 80% view is `/build`.** Everything else is a destination the user visits and leaves. If a decision is close, it resolves in favour of the builder.
- **One user type, one entry point.** No roles, no auth, no alternate onboarding. A visitor and a returning user differ only by whether a lineup exists in session state.
- **Two levels of navigation depth, maximum.** Anything needing a third level is a modal over a level-two page, not a level-three page.
- **Almost nothing grows.** 16 teams, 80 players, 18 emblems, 8 prefixes, 8 suffixes — all fixed and small enough to render without pagination, search, or filtering. Only match results accumulate, and only within a bounded tournament.

---

## Site Map

```
Setup (first-run, skippable)          /setup           → redirects to /setup/core
  Choose Your Core Duo                /setup/core
  Choose Your Mid Player              /setup/mid
  Choose Your Support Duo             /setup/support

Builder ★ the 80% view                /build
  Role focus                          /build/:role                    role = core | mid | support
    Team picker (full grid)           /build/:role/team
    Emblem roll                       /build/:role/emblem/:slot       slot = 1 | 2 | 3

Coaching Titles                       /titles

Match Day                             /matches
  Series detail                       /matches/:seriesId

Standings                             /standings

Group Stage Bracket                   /bracket

Player detail                         /players/:playerSlug

Glossary                              /glossary
```

**Routing notes.** Every modal is a real route, per the routing decision — back closes the overlay, deep links work, and the Phase 7 review can screenshot any state by URL. `/build/:role/team` and `/build/:role/emblem/:slot` render as overlays **on top of** `/build`, which stays mounted behind them. `/glossary`, `/titles`, and `/players/:slug` render as overlays over whatever the user was on, falling back to `/build` underneath on a cold deep-link.

**Deliberately absent:** no `/settings`, no `/account`, no `/teams/:slug` index. Team identity is expressed through the picker and the banner, and a team page would be a destination with nothing to do on it.

---

## Navigation Model

- **Primary navigation** — 4 items, hard cap: **Builder · Match Day · Standings · Bracket**. Four is enough to fit a mobile tab bar without compression, and no fifth candidate earns a permanent slot.

- **Secondary navigation** — Role selection within the builder. At ≥1280 the three banners are all visible, so "selection" means focus, not navigation, and `/build/:role` only marks which banner owns the roll panel and advisor. Below 1024 the same route becomes true navigation via a segmented control, since only one banner is on screen. **Same URL, different meaning by breakpoint** — this is intentional and is the one place the IA bends.

- **Utility navigation** — Lives in the app shell header, outside the content hierarchy: **period selector**, **roll-token counter**, **glossary**. The token counter is utility by placement but is functionally a resource meter, so it sits adjacent to the period selector rather than in a menu, and it animates on spend.

- **Mobile navigation** — Bottom tab bar with the 4 primary items. Not a hamburger: with only four destinations, hiding them behind a menu costs a tap for no gain, and the builder needs to be one thumb-reach away from match day. Utility items collapse into the header; the period selector becomes a compact pill, and the glossary moves to an icon.

---

## Content Hierarchy

### Builder `/build` ★

1. **The three banners** — The product. Role title, team crest, the three emblems with computed percentages, and the duo's portraits at the base. Nothing outranks this; if space is contested, everything else yields.
2. **Projected total, per role and combined** — The number the user is trying to move. Must be visible without scrolling at every breakpoint, because it is the feedback signal for every action taken on this page.
3. **Advisor panel** — The single highest-value change available, its delta, its token cost, and its runner-up. Docked right at ≥1280, bottom drawer at 1024–1279, dismissible card at ≤1023.
4. **Roll-token balance** — A constraint, not content. Prominent enough to inform decisions, quiet enough not to compete with projections.
5. **Adjacency state** — Revealed on hover/focus, not persistently drawn. Always-on adjacency lines would turn the banner into a diagram.
6. **Coaching titles summary** — One line showing the active prefix/suffix and their combined conditional bonus, linking to `/titles`.

### Team Picker `/build/:role/team`

1. **Ranked team cards** — 16 cards, ordered by projected fit against the current banner. Rank is the entire reason this differs from the client's arbitrary grid.
2. **Projected score per team** — On every card, so the ranking is auditable rather than asserted.
3. **The duo (or mid) portraits** — Confirms exactly who is being committed. This is the "CHOOSE YOUR CORE DUO" promise: you pick a team, you get these specific people.
4. **One-line reasoning** — Why this team ranks where it does, tied to the banner's actual emblems.
5. **Team crest and name** — Identity and scannability. Crests stay full-colour for the selected card and desaturate when unselected, keeping brand colour from competing with emblem semantics.
6. **SUBMIT** — Explicit commit. Disabled until a selection differs from current.

### Emblem Roll `/build/:role/emblem/:slot`

1. **The three roll options** — With signed, coloured point deltas against the current emblem. The delta is the decision.
2. **Current emblem** — Held in view for comparison. Never replaced until the token is spent.
3. **Token cost and remaining balance** — The price of the decision, adjacent to it.
4. **Full point breakdown for each option** — base → tier → trait → title → projected.
5. **Adjacency consequences** — If an option is Vampiric or Benevolent, its effect on the two neighbouring emblems is shown before committing, not after.

### Match Day `/matches`

1. **Per-role score with emblem-by-emblem attribution** — Not "Core scored 41k" but which emblems produced it.
2. **Zeroes for stats not on the banner** — Rendered visibly, not omitted. The cost of a bad emblem is only legible if the miss is shown.
3. **Series and game structure** — Which two games counted, which was dropped.
4. **Title condition resolution** — Which conditional bonuses fired, which didn't.
5. **Comparison to period average** — Context for whether a score was good.

### Standings `/standings`

1. **Your percentile and its reward tier** — The user's own position first.
2. **The percentile ladder** — All nine tiers, real values, with the user's position marked.
3. **Distance to the next tier** — The actionable number.

### Bracket `/bracket`

1. **Outcome bands, 4-0 through 0-4** — The structure the client uses.
2. **Team crests and names** — All 16 visible at once, no scroll at desktop.
3. **Which of your three teams are where** — Your lineup highlighted within the field. This is what makes the bracket yours rather than generic tournament furniture.

### Player Detail `/players/:playerSlug`

1. **Portrait at full scale** — The 1024px asset finally used at strength.
2. **Per-stat averages against the 18 emblem categories** — The data the advisor reasons over, exposed.
3. **Which of your emblems this player actually scores in** — The relevance filter.
4. **Team, role, and modelled-data marker.**

### Glossary `/glossary`

1. **Scoring values** — All 18, verbatim.
2. **Tiers and traits** — With adjacency explained spatially, not only in prose.
3. **Emblem colour groups** — The 6/6/6 mapping.
4. **Scoring resolution rules** — Snapshot, averaging, best-two-games, best-series.
5. **Reward ladder.**

---

## User Flows

### First-run setup (skippable)

1. User lands on `/` with no lineup in session → redirected to `/setup/core`.
2. Sees the full-grid picker: 16 team cards, each showing that team's **core duo**, title "CHOOSE YOUR CORE DUO".
   - Ranking is unavailable here — no banner exists yet to rank against — so cards are ordered by group-stage seed, and the advisor stays silent rather than fabricating a reason.
3. User selects a team → SUBMIT enables → advances to `/setup/mid`.
4. Repeats for mid (`CHOOSE YOUR MID PLAYER`, single portrait), then support (`CHOOSE YOUR SUPPORT DUO`).
5. On final submit → `/build` with three banners populated with starting emblems and a full token balance.

**Skip path**: a persistent "Skip — use a sample lineup" affordance on all three steps loads a pre-set lineup and goes straight to `/build`. Anyone evaluating the prototype reaches the interesting screen in one click.

### Roll an emblem — the core loop

1. User is on `/build`, banners visible.
2. Clicks an emblem → `/build/core/emblem/2`, roll panel enters, banner dims except the selected emblem.
3. Three options render, each with a signed point delta and full breakdown.
   - If token balance is 0 → options render read-only with the spend action disabled and the reason stated. Options are never hidden.
   - If an option carries Vampiric or Benevolent → its adjacency effect previews on the neighbouring emblems before commit.
4. User spends a token → counter decrements, old emblem dissolves, new one lands in staggered reveal, projected totals count to new values.
5. Roll options are replaced with three new ones (client behaviour: rolling replaces the whole option set).
6. Advisor recalculates and may now recommend something different.
7. User closes → back to `/build`. Back button also closes.

### Act on advisor guidance

1. Advisor on `/build` reads: "Support — Xtreme Gaming projects +8.4k over your current pick. Their duo averages 12.4 observer wards; your banner is wards-weighted."
2. User clicks through → `/build/support/team` with Xtreme Gaming ranked first and the reasoning restated on its card.
3. Current team stays visible with its delta, so the user can see what they'd give up.
4. Submit → banner base cross-fades to the new duo, projections recalculate, advisor moves to the next-highest-value change.
   - If the user disagrees and picks the runner-up instead → accepted without objection, advisor re-ranks from the new state.

### Read the math

1. User hovers or focuses any percentage badge anywhere in the product.
2. Breakdown popover expands: base stat value → × tier → × trait → × active title conditions → projected points, one line per step.
3. "Full rules" link → `/glossary`, deep-linked to the relevant stat.

### Review match day

1. User opens Match Day, period-scoped by the header selector.
2. Sees per-role scores with emblem attribution, including visible zeroes for banner stats that produced nothing.
3. Drills into a series → `/matches/:seriesId` for game-level detail and which two games counted.

### Change coaching titles

1. From the builder's titles summary → `/titles`.
2. Two columns, 8 prefixes and 8 suffixes, each with its condition text.
3. Selection is free — no token cost, per the real rules — so changes apply immediately with live projection updates rather than requiring a commit.
4. Close → `/build`.

---

## Naming Conventions

Pick one word, use it everywhere. Where the client's term is good, keep it; where it's ambiguous, improve it and note why.

| Concept | Label in UI | Notes |
| --- | --- | --- |
| The per-role emblem carrier | **Banner** | Client says "War Banner". Shortened for repetition in a UI where it appears constantly; full term used once in the glossary. |
| One of three slots on a banner | **Emblem** | Client term. Unambiguous. Keep. |
| Emblem quality level | **Tier** | Client uses "Quality" in prose and "TIER I–V" on the card. The card wins — it's what users read. Never "level", never "rarity". |
| Emblem modifier | **Trait** | Client term. Keep. |
| Adjacency effect | **Neighbouring emblems** | Never "adjacent" in UI copy — it's the more abstract word and this mechanic is already the most-missed one. |
| Roll currency | **Token** | Client says "roll token". Shortened; the counter is labelled "Tokens". |
| Rerolling an emblem | **Roll** (verb), **Roll options** (noun) | Never "reroll", never "craft", never "mutate" — one verb only. |
| Coach prefix/suffix | **Title** | Client term. The pair is "your titles". |
| Core / Mid / Support | **Role** | Three roles, never "position", never "slot" (slot is reserved for emblem positions). |
| The two players in a role | **Duo** | Directly from the client's "CORE DUO" / "SUPPORT DUO". Mid is a **Player**, never a duo. |
| Tournament segment | **Period** | Client term, and it's what scoring keys off. Not "stage" — the bracket uses "Group Stage" as a proper noun and the collision would confuse. |
| Estimated future points | **Projected** | Always "projected", never "estimated", "expected", or "predicted". One word so the modelled-data caveat attaches to exactly one term. |
| The recommendation system | **Advisor** | Not "AI", not "optimizer", not "assistant". |
| Change in projected points | **Delta**, shown as signed value | Label is the signed number itself (`+8.4k`); the word "delta" appears only in internal naming. |
| Emblem colour groups | **Red / Blue / Green** | Never renamed to thematic labels. The client's colours are the shared vocabulary among players. |
| Modelled statistics | **Modelled** | One spelling, used on every marker. Never "simulated", "mock", "sample", or "fake". |

---

## Component Reuse Map

| Component | Used on | Behaviour differences |
| --- | --- | --- |
| `AppShell` | All routes except `/setup/*` | Setup runs chrome-free — no primary nav, no period selector — to keep the sequence linear. Token counter appears only after setup completes. |
| `BannerColumn` | `/build`, `/build/:role` | Three side by side at ≥1280; one at a time with segmented control at ≤1023. Read-only variant on `/matches` where it shows what scored rather than what's editable. |
| `EmblemCard` | `/build`, roll panel, `/matches`, `/glossary` | Interactive on build; comparison variant (with delta) in roll options; attribution variant (with points earned) on match day; static reference variant in glossary. |
| `TeamPickerGrid` | `/setup/*`, `/build/:role/team` | Unranked and seed-ordered during setup (no banner to rank against); ranked with reasoning in the builder. Portrait count varies by role: 2 for core/support, 1 for mid. |
| `TeamCrest` | Picker, banner, bracket, standings, match day | Full colour when selected or primary; desaturated when unselected or secondary. Never tinted. |
| `EmblemGlyph` | Everywhere emblems appear | Tinted to its colour group + glow. The one asset class that gets tinted. |
| `PointBreakdown` | Any percentage, anywhere | Popover on desktop, bottom sheet at ≤767. Identical content. |
| `ModelledDataBadge` | `/build`, `/matches`, `/standings`, `/players/:slug`, team picker | Every surface that projects or reports points. Persistent, non-dismissable. Absent only on `/glossary` and `/bracket`, which carry no modelled figures. |
| `GoldButton` | Primary actions across all routes | SUBMIT, spend token, confirm. One hardware treatment, no variants beyond size and disabled state. |
| `RouteOverlay` | Team picker, roll, titles, glossary, player detail | Shared focus trap, escape handling, focus restoration, and underlying-route preservation. Written once. |

---

## Content Growth Plan

This product is bounded by design, which is a structural advantage worth stating explicitly so nobody builds infrastructure for growth that will never arrive.

**Fixed forever** — 16 teams, 80 players, 18 emblems, 5 traits, 5 tiers, 8 prefixes, 8 suffixes, 9 reward tiers. All render fully with no pagination, no search, no filtering, no lazy loading. A 16-card grid and an 18-row glossary are just lists.

**Grows within bounds** — Match results accumulate across a tournament, but a Major group stage plus playoffs is on the order of tens of series. `/matches` groups by period and renders the current period fully; earlier periods collapse to summary rows. No infinite scroll, no archive pattern.

**Grows per session, discarded** — Roll history and projection changes exist while the session lives. Not persisted, not paginated.

**The one real pressure point**: `/matches/:seriesId` at game level is the densest surface in the product — five players × up to 18 stats × up to 3 games. It handles this by showing only the stats **on that role's banner** (which is also the real scoring rule), reducing 18 columns to 3. The rule and the layout constraint happen to agree, which is the sign it's the right structure.

---

## URL Strategy

**Pattern**: `/section/:entity/:sub-entity` — never deeper than three segments.

**Dynamic segments**:
- `:role` — `core` | `mid` | `support`. Closed set, validated; unknown values redirect to `/build`.
- `:slot` — `1` | `2` | `3`. Emblem position within a banner, left to right, matching visual order.
- `:playerSlug` — slugified player name. **Derived from the display name, never from the filename** — the assets include `Kataomi\`.png`, `y\`.png`, `No[o]ne-.png`, and `Save-.png`, which are not URL-safe. Mapping lives in the data layer with display names preserved separately.
- `:seriesId` — opaque identifier from the mock fixture set.

**Query parameters**:
- `?period=group|playoffs` — Cross-cutting, applies to `/build`, `/matches`, `/standings`, `/bracket`. Persists across navigation within a session. Omitted means current period. Chosen over a path segment precisely because it cuts across sections rather than nesting under one.
- `?stat=<emblem-stat>` — On `/glossary` only, for deep-linking from a point breakdown to the relevant entry.
- `?compare=<teamSlug>` — On `/build/:role/team`, optional, pins a specific team alongside the current pick for comparison.

**Rules**:
- Lowercase, hyphenated, no trailing slashes.
- Every modal state is addressable. If a user can see it, it has a URL.
- Overlay routes preserve the underlying route's scroll position and state on close.
- A cold deep-link to an overlay route renders `/build` beneath it, so back always lands somewhere real rather than exiting the app.
