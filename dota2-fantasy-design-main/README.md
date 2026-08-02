# Dota 2 Fantasy Analytics — UI Design

A front-end design for a Dota 2 fantasy analytics tool, built around the
scoring system used by The International 2025 Compendium fantasy.

This is a **design deliverable**, not a finished product: it defines the visual
system, the component vocabulary, and the interaction model, running on a real
scoring engine with generated player statistics. It is intended to be adapted
onto a real analytics backend.

---

## Design direction

**Modern minimalist, dark.** The organising rule the whole system rests on:

> **The interface is greyscale. Colour means something.**

The only saturated colour anywhere is the emblem group colour (red / blue /
green) and each team's own crest. Nothing decorative is ever coloured. That is
what makes this read as an analytics tool rather than a game skin — and it
keeps real data legible once it replaces the generated numbers.

Everything follows from that:

- Flat surfaces, hairline borders, no gradients on chrome, no shadows except overlays
- Elevation is expressed with surface value + 1px, not drop shadows
- **Space Grotesk** headings · **Manrope** body · **JetBrains Mono** for every figure
- A mono numeric face is deliberate: perfect column alignment, and numbers read
  as data rather than prose

### Asset handling

Two asset classes, handled oppositely:

| Asset | Treatment |
| --- | --- |
| `fantasy_craft/` — 18 emblem icons | Opaque 128px greyscale artwork. Rendered as images at full fidelity. **Never tinted or masked.** |
| `teams/` — 16 crests | Full brand colour. **Never tinted.** |
| `players/` — 80 portraits | 1024px transparent cutouts, bled off the card edge |

Emblem group colour lives on the *chip around* the icon — a ring and a 2px
rule — never on the artwork. This is what lets any icon sit in any slot while
the slot's colour stays fixed.

---

## Structure

```
src/
├── data/
│   ├── scoring.js     Real TI 2025 values — point values, tiers, traits, titles, rewards
│   ├── teams.js       16 teams, 80 players, rosters by role, group-stage bands
│   ├── players.js     Generated per-player statistics (fiction — see below)
│   └── assets.js      Asset resolution + normalisation
├── engine/
│   └── scoring.js     The maths. Self-verifies against reference screenshots on boot.
├── components/        AppShell, BannerColumn, EmblemCard, EmblemIcon, TeamCrest,
│                      PlayerPortrait, RouteOverlay, CountUp, Button, ModelledDataBadge
├── routes/            Builder, TeamPicker, EmblemPicker, Bracket, Glossary
└── styles/
    ├── tokens.css     The design system. Start here.
    └── globals.css
```

`.design/` holds the design brief, information architecture, and task list.

---

## Data provenance

This distinction is load-bearing and is surfaced in the UI itself.

**Real** — every scoring figure, taken verbatim from the in-client glossary:
point values for all 18 stats, tier bonuses (I +10% → V +150%), the five
traits and their adjacency rules, coach titles, and the reward ladder.

The engine reproduces the reference banner exactly, including compound cases
like `GPM 180% = 100 + Tier II (30) + Vampiric (50)` and
`Unique +20% = self 30 − 10 from an adjacent Vampiric`. It checks itself on
every boot and fails loudly rather than producing plausible wrong numbers.

**Generated** — per-player statistics (GPM, creep score, wards, stuns, …) for
all 80 players. Real per-player match data is not bundled here. The figures are
role-coherent and deterministic from a fixed seed, but they are invented.

Any surface that reports points carries a persistent, non-dismissable marker
saying so. **Replace `src/data/players.js` with real data and every projection
in the app becomes real** — nothing else needs to change.

---

## Scoring model

Three roles, each with a banner of three emblems:

| Role | Players | Emblem colours |
| --- | --- | --- |
| Core | 2 | 2 red + 1 green |
| Mid | 1 | 1 red + 1 blue + 1 green |
| Support | 2 | 2 blue + 1 green |

`displayed % = 100 + tier bonus + net trait bonus`, where the net trait bonus
is the emblem's own trait plus the adjacency effects of its neighbours.
A player scores **only** for the stats present on their banner.

---

## Running it

```bash
npm install
npm run dev
```

Requires Node 18+. Opens on `http://localhost:5173`.

---

## Accessibility

Every text/background pairing is verified against WCAG AA with alpha
compositing accounted for — measured in the rendered DOM, not assumed from
token values. Colour is never the only channel: every emblem carries its stat
name in text alongside its group colour. Touch targets are ≥44px, and
`prefers-reduced-motion` is honoured.

---

## Assets

Dota 2, team crests, player likenesses, and emblem artwork are the property of
Valve Corporation and the respective organisations. Included here for design
purposes only. This project is not affiliated with or endorsed by Valve.
