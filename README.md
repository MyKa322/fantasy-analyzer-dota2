# Dota 2 Compendium Analyzer — TI15

**Live page: https://myka322.github.io/fantasy-analyzer-dota2/**

_Русская версия README: [README.ru.md](README.ru.md)._

Analytics for the two compendium blocks of The International 2026: **Predictions** (team level —
Swiss buckets and the playoff bracket) and **Fantasy Draft** (player level — how many points a role
will score over a period).

Built to the [development plan](dota2-compendium-analyzer-plan.md), but the numbers and the
mechanics come from the in-game TI15 glossary, not from the plan — see the next section.

---

## How reality differs from the plan

The plan was written against TI2025 data. The TI15 glossary differs both in numbers and in
mechanics:

| | plan (§4.2) | TI15 compendium |
|---|---|---|
| Kills | +121 | **+107** |
| Deaths | 1800 / −180 | **1950 / −195** |
| Roshan | +850 | **+1172** |
| Tormentor / Courier | +850 / +850 | **+879 / +703** |
| Stuns | +128/sec | **+10/sec** |
| Camps stacked | +170 | **+234** |
| Runes | +121 | **+141** |
| Tower kill | +340 | **+352** |
| Wards | +113 | **+117** |
| First blood | +1700 | **+1934** |
| Smoke | +283 | **+293** |
| Teamfight | up to 1895 | **up to 2124** |
| — | — | **Madstone +13, Lotuses +176, Watchers +147** — new stats |

The mechanics changed too:

- **The roster is 5 players, not 3**: core duo, mid, support duo. A role scores the **average** of
  its own players per game.
- **Emblems now have traits** (Fractal, Benevolent, Vampiric, Unique, Friendly), some of which act
  on adjacent emblems — so **the order of emblems on the banner changes the score**.
- Colours were redefined: red — Kills/Deaths/CS/GPM/Madstone/Tower, blue — Wards/Camps/Runes/
  Watchers/Smokes/Lotuses, green — Roshan/Teamfight/Stuns/Tormentor/First Blood/Courier.
- Period scoring: **the best two maps of the best series** (the plan had this right).

### The emblem formula

The War Banner screen shows the final percentage on every card, and that pins the formula down
exactly — **all bonuses add up**:

```
percent = 100% + quality bonus + own trait (if its condition holds) + neighbour effects
```

| card from the game | breakdown | result |
|---|---|---|
| Creep Score, Tier II, Friendly | 100 + 30 + 0 (Friendly did not fire) | 130% |
| Stuns, Tier I, Fractal | 100 + 10 + 0 (qualities not all distinct) − 10 (Vampiric neighbour) | 100% |
| GPM, Tier II, Vampiric | 100 + 30 + 50 | 180% |
| GPM (mid), Tier II, Unique | 100 + 30 + 30 − 10 (Vampiric neighbour) | 150% |

The same cards imply two more facts: there are **exactly three slots**, and **emblems sit in a
column** — on the core banner a Vampiric at the bottom took 10% off the middle slot only, while the
top one kept its 130%. In a ring layout both would have suffered.

### Slot colours are fixed by the role

| role | slots | what it means |
|---|---|---|
| Core | 🔴 🔴 🟢 | GPM and Creep Score are available, wards and smokes never will be |
| Mid | 🔴 🔵 🟢 | the only role with all three colours |
| Support | 🔵 🔵 🟢 | GPM is out of reach entirely |

The colour never rerolls — only the stat inside the colour, the quality and the trait do. That is
why both the emblem search and the per-stat player ranking stay strictly inside the colours the
role can actually get.

Every number lives in [`backend/config/ti15_fantasy.yaml`](backend/config/ti15_fantasy.yaml) — it
can be edited without touching a line of code.

---

## Quick start

```bash
python -m venv .venv && .venv/Scripts/pip install -r backend/requirements.txt
```

Backend:

```bash
.venv/Scripts/python -m uvicorn app.main:app --reload --app-dir backend
```

Frontend:

```bash
npm install --prefix frontend && npm run dev --prefix frontend
```

The dashboard is at http://localhost:5173, the API docs at http://localhost:8000/docs.

Dashboard tabs: **Emblems** — the best War Banner, what each stat is worth, form map by map and the
split of a duo by player; **My emblems** — the inverse problem: enter what your rolls already
produced and get the TI15 duos ranked for that exact set; **Profiles** — a page for any team and
any player in the database: matches, averages, heroes, rating and our analysis on top; **Match** —
any game by its id, pulled live from OpenDota: the scoreboard with items, the ward map with a
timeline, the head-to-head record and compendium points for the map; **Roster** —
candidates per role across the 16 participants and the best combinations; **Predictions** — Swiss
bucket probabilities and a ready prediction layout; **Ratings** — the Glicko-2 table and the trend
with its uncertainty band; **Custom banner** — a manual builder with a point projection; **Data** —
match ingestion.

The interface speaks twelve languages: English, Russian, Ukrainian, Chinese, Spanish, Portuguese,
German, French, Polish, Turkish, Indonesian and Vietnamese. The switcher sits in the top right, and
every language has its own address (`/` for English, `/ru/`, `/uk/`, `/zh/`, `/es/`, `/pt/`, `/de/`,
`/fr/`, `/pl/`, `/tr/`, `/id/`, `/vi/`).

---

## Where the data comes from

Not a single number on the page was typed in by hand — except the ones that were, because there was
no other way to get them. The line runs here:

| what | source | how it is refreshed |
|---|---|---|
| Matches, player statistics, rosters | [OpenDota API](https://docs.opendota.com): `/teams/{id}/matches`, `/matches/{id}`, `/proMatches` | `cli.py ingest-ti` — daily in CI |
| Team rating and form | computed by us from those same matches (Glicko-2 over map outcomes) | `cli.py ratings`, recomputed from scratch |
| Roles inside a team (who is mid, who supports) | derived from matches: share of games in the middle lane and farm priority | together with ingestion |
| Hero reference | [dotaconstants](https://github.com/odota/dotaconstants) → [`heroes.json`](backend/config/heroes.json) | `cli.py ingest-heroes` |
| Who plays TI15 and under what name | [`ti15_predictions.yaml`](backend/config/ti15_predictions.yaml), including `aliases` for teams under a changed brand | by hand |
| Stat prices, quality and trait bonuses, titles | the in-game compendium glossary → [`ti15_fantasy.yaml`](backend/config/ti15_fantasy.yaml) | by hand |
| Rosters when a substitute has not played yet | [`ti15_rosters.yaml`](backend/config/ti15_rosters.yaml) — takes precedence over the automation | by hand |
| Player portraits, logos, hero and emblem icons | the compendium design archive, squeezed into WebP | `tools/optimise_assets.py` |
| Item reference (inventory slots hold ids) | [dotaconstants](https://github.com/odota/dotaconstants) → [`items.json`](backend/config/items.json) | `cli.py ingest-items` |
| The minimap, its markers and item icons | an export of the game's own interface (`panorama/`, `materials/`), squeezed into WebP | `tools/optimise_assets.py` |
| A single match on the **Match** tab | [OpenDota API](https://docs.opendota.com) `/matches/{id}`, requested by the browser itself | on every request, not cached in the repository |

**About players.** There is no "give me this player's statistics" request: everything on a player
page is computed from their team's maps. So a player only shows matches inside the period, and only
for teams whose history we loaded. The nickname, `account_id` and hero all arrive inside the match
body.

**About teams.** We load the history of the sixteen participants — and their qualifier opponents
come along with it, which is why the database holds close to a hundred teams and several hundred
players. Those opponents get their matches incidentally: they have no full history of their own,
and such teams honestly carry a large RD.

**What the data does not have.** OpenDota tracks neither madstones nor watchers, and lotuses are
approximate; death to the Tormentor and a fountain kill are not flagged. All of this is stated
outright — in the API response (`unavailable_stats`) and in the interface — rather than silently
filled with zeros. The `ANALYZER_STRATZ_API_TOKEN` config key is reserved for STRATZ; the mapping
for it has not been written yet.

**The sampling window.** Fantasy analytics looks at 180 days, profile pages at 180 days, ratings
are recomputed over 200 days. Only matches with a parsed replay count towards Fantasy, and the
share of such matches is shown next to the numbers.

---

## How often the data is refreshed

| when | what happens |
|---|---|
| Every day at 04:20 UTC | workflow `refresh-data`: fresh matches for 150 days, rating recomputation, hero reference, snapshot and profile export, commit |
| Right after the data commit | workflow `deploy`: the page is rebuilt and published to Pages |
| On every push touching `frontend/**` | the same — the page is rebuilt |
| Manually | `workflow_dispatch` on `refresh-data` (with a depth option) or `cli.py ingest-ti` locally |

04:20 UTC is not an arbitrary hour: by then yesterday's replays are parsed, and without a parsed
replay a map is useless for Fantasy.

How fresh the data is can be read off the page itself: the header carries "data as of <date>" —
that is the snapshot's `generated_at`, i.e. the moment of export, not the moment you opened the
page.

Between runs the database lives in the Actions cache: without it every run would pull seven hundred
matches again and hit OpenDota's daily limit (2000 requests without a key). Match bodies are cached
locally too, in `backend/data/`, so re-parsing costs nothing. When the match parsing format changes,
`STATS_VERSION` goes up and the next run re-reads the old matches from cache; such a run takes
longer but spends no quota.

---

## How to score more points: what the analyzer computes

**A stat's value is price × volume, not the price from the glossary.** Roshan Kills is worth 1172
points apiece against 117 for a ward, but a support who plants 10 wards a map and finishes Roshan
once in ten games will get far more out of wards. The analyzer computes this from the role's real
matches:

```bash
.venv/Scripts/python backend/tools/cli.py roster
```

**Deaths** deserve a separate look: the stat starts at 1950 points and subtracts 195 per death, so
for a careful player it outscores even GPM — while looking like a penalty box that is easy to skip.

**The trait combination decides as much as the stats do.** Fractal gives +60%, but only if all three
qualities differ; Friendly gives +50%, but only with three Friendly emblems. So three Tier V plus
three Friendly (300% each) usually beats Tier V plus Fractal with distinct qualities. The search
goes over every combination at once rather than greedily slot by slot — a greedy choice is
systematically wrong here.

**Vampiric has to be placed deliberately.** +50% to itself and −10% to each neighbour: on an
expensive emblem it pays for itself, on a cheap one it takes more from the neighbours than it
brings.

**Evaluating a roll.** The `/api/fantasy/evaluate-swap` endpoint shows what swapping a particular
emblem would do — taking into account that a trait changes the neighbours as well.

**Your own emblem set is the inverse problem.** Rolls are finite, and the question is usually not
"what is the best banner in general" but "who should I put what I already have on".
`/api/fantasy/inventory` (the **My emblems** tab) lays the inventory out over each role's slot
colours and ranks every TI15 duo by the points these exact emblems produce. The order is solved by
enumeration: Benevolent pays more in the middle (two neighbours), Vampiric on the edge. Roles that
cannot be assembled from the set are named outright: "Support Duo: 2 blue needed, 0 available" — a
slot colour never rerolls.

**Team and player pages.** `/api/profiles/teams/{id}` and `/api/profiles/players/{id}` (the
**Profiles** tab) collect everything the database knows about a given team or player: the Glicko-2
rating with its history and uncertainty band, the map record, opponents, the roster with roles,
per-map averages, the hero pool with win rates and the match list. Alongside sits our analysis: the
best banner per role, Swiss bucket probabilities, a player's share of their duo.

Regular statistics and Fantasy numbers are deliberately kept in separate tables. A kill in a profile
is a kill; in the analysis it is 107 points. Mixing them gives you a page from which you can neither
judge a player nor build a roster. Averages are computed only over matches with a parsed replay, and
the share of those is shown explicitly: in the rest OpenDota reports neither wards nor stuns, and
including them would drag everything down at once.

**Form and style: the cuts that a single average hides.** Every team and player page carries the
same block — the record over the last 30 days against the previous two months (in percentage
points, not "twice as good"), the current win or loss streak, the split by side (Radiant / Dire) and
by map length (under 30 minutes, 30–40, over 40). A team that wins 76% of its mid-length maps and
59% of the long ones is telling you something the total win rate does not.

A team page adds the price of its wins: the average rating of the opponents faced, the record
against teams rated above itself, and how often the team takes first blood. A player page adds the
Fantasy points per map (median, p90 ceiling and spread over the role's full stat pool — comparable
inside a role), how wide the hero pool is (distinct heroes and the share of the top three), and the
lane split from the OpenDota markup.

**Match breakdown.** The **Match** tab takes any match id and pulls the game straight from the
public OpenDota API in the browser — it is the one place where the page talks to someone else's
data live, because the snapshot only knows the matches of the sixteen participants. On top of the
usual scoreboard (heroes, KDA, last hits, GPM/XPM, net worth, damage, wards, final items) it adds
what a statistics site has no reason to compute: the compendium points this map is worth for each
player on the best neutral banner of their role, and which Coaching Titles would have fired on this
map and on whom. Roles are inferred from the match — mid by lane, the Support Duo as the two lowest
net worths — and the page says so. Any match page is a link: `#/match/8922016200`, and the date in a
profile's match table is that link.

**The map and the timeline.** Per-tick hero positions are not in the open API — only parsing the
replay itself gives those. What the API does give is the thing the map is opened for: every ward
with its coordinates and lifetime, the places players died inside a teamfight, and the objective
events. So the page draws the game's own minimap with two views: the whole match at once — every
ward placed, which is the map of what a team always lights and never does — and a timeline you can
scrub or play, showing what was alive at that minute and where the fight going on was killing
people. Next to it runs the event feed: towers, barracks, Roshan, aegis, first blood, big fights;
clicking an event jumps the timeline to it.

**Items and the build order.** The final inventory sits in the scoreboard, and under it the first
purchases with their timings — consumables left out, or tangoes and TPs would bury the items that
were actually built. The icons and the minimap come from an export of the game's own interface; only
the map, three markers and the item icons are kept, squeezed into WebP.

**Head to head.** Two teams that met before are worth looking at through those meetings, so the
match page shows the whole record between them for the period, and each opponent on a team page
expands into the same list. Every row links to the breakdown of that map. The data is a separate
[`head_to_head.json`](frontend/public/data/head_to_head.json) (~200 KB): the question is asked by
the match page, and it loads neither the profiles nor half the snapshot.

Point-by-point data instead of a single average. For every stat you see not just the average points
but the median with a quartile (one blowout map should not decide anything), the share of maps where
the stat happened at all (0.3 Roshans a map means every third game, not a little bit every game),
and the form over the last 30 days against the previous 60. Separately there is the role split by
player (`/api/fantasy/players`): the score is the average of the duo, so a duo where one player does
everything is worth as much as a duo where both do — and collapses harder. And the point curve map
by map (`/api/fantasy/timeline`) — the two best maps of a series are what counts, so the spread
matters as much as the level.

**Heroes: what a team picks and what it changes.** The hero pool is computed per team, per role and
per player — with win rates and a breakdown of whose hero it is inside a duo. It also drives the
titles: the prefixes ("Crimson", "Cerulean" and the other six) pay a percentage for a hero from
their own list, and the lists sit in [`ti15_fantasy.yaml`](backend/config/ti15_fantasy.yaml) next to
the titles. A test checks every name against the hero reference — a typo would silently drop a hero
out of the estimate.

**Coaching Titles** are scored as percentage × share of maps where the condition held. That makes
the comparison fair: "the Lucky" with its +21% looks like the best of the lot but fires on roughly
one map in ten (the duration has to end in an 8), while "the Underdog" with +6% fires on half of
them. Six of the eight suffixes are computed from data: duration, defeat, the last digit of the
clock, the decider of a series (the third map in a Bo3, the fifth in a Bo5) and the time of first
blood. "the Patient" (+23% if there was no first blood before 10:00) barely ever happens in pro
matches — 0.2% of maps in our sample, and that is an answer too.

Two conditions are not checked: OpenDota flags neither a death to the Tormentor nor a kill at the
fountain. One more — "the Flayed Twins Acolyte" — cannot be told apart from a gap: the first blood
time comes back as zero both before the horn and when the event was missed. All three are marked
"not measurable" with the reason instead of being invented.

The first data run (no keys, public OpenDota):

```bash
.venv/Scripts/python backend/tools/cli.py ingest-ti --days 150
```

```bash
.venv/Scripts/python backend/tools/cli.py ratings
```

```bash
.venv/Scripts/python backend/tools/cli.py group --simulations 20000
```

```bash
.venv/Scripts/python backend/tools/cli.py roster
```

`ingest-ti` loads the history of all 16 participants and assigns their players to roles; `roster`
builds a lineup (core duo / mid / support duo from three different teams). For a wider view of the
scene there is `ingest-feed --days 30` — the general pro match feed.

---

## TI15 participants and their OpenDota profiles

The compendium shows some teams under changed names — the organisations with betting sponsors. The
config carries `aliases` for them, and the lookup covers every variant:

| in the compendium | organisation | team_id |
|---|---|---|
| BoomBoys | BetBoom | 8255888 |
| Huligani | L1ga Team | 10149530 |
| Team Vision | PARIVISION | 9572001 |
| Iron Wing | 1win Team | 10150413 |

The other twelve — Team Liquid, Xtreme Gaming, Team Falcons, Aurora Gaming, Team Yandex, Vici
Gaming, Team Resilience, LGD Gaming, OG, GamerLegion, Nigma Galaxy, Team Spirit — run under their
own names.

**About the old profiles.** Huligani, LGD, Nigma and Team Vision each have an older OpenDota profile
with a long history (L1GA TEAM 9303383, LGD Gaming 15, Nigma Galaxy 7554697). That history is
deliberately **not** mixed in: the rosters there are different (LGD's old profile is the Chinese
2024 lineup, Nigma's has Miracle and rmN instead of GH and SumaiL). Handing a new team a rating that
other players earned is the shortest path to a confidently wrong forecast. A small sample is
represented more honestly by a high RD, and the model will say for itself that the data is thin.

---

## Layout

```
backend/
  config/ti15_fantasy.yaml        compendium numbers: stats, qualities, traits, titles
  config/ti15_predictions.yaml    Swiss format, bracket, point scales, participants
  config/ti15_rosters.yaml        manual roster overrides (they beat the automation)
  app/
    fantasy/rules.py              loading and typing of the rules
    fantasy/scoring.py            the point engine: emblems -> player -> role -> series -> period
    fantasy/projection.py         bootstrap projection of a role's points over a period
    fantasy/advisor.py            the analyzer: stat value, banner search, per-stat ranking
    analytics/glicko2.py          rating with uncertainty
    analytics/rating.py           chronological recomputation (anti-leak)
    analytics/simulate.py         Monte-Carlo Swiss + bracket + prediction layout
    ingest/opendota.py            client with rate limiting and a file cache
    ingest/stat_mapping.py        turning a match into compendium stats
    ingest/pipeline.py            writing to the database
    services/analysis.py          wiring the database to the analytics, role detection
    services/profiles.py          team and player pages, form and style cuts
    api/routes.py                 the HTTP API
  tools/cli.py                    the same without a server
  tools/export_snapshot.py        the static snapshot for GitHub Pages
  tools/build_og_image.py         social preview images, one per language
frontend/                         React + TS + Tailwind + Recharts
  src/engine/scoring.ts           the emblem maths in the browser, ported from the backend
  src/opendota.ts                 the OpenDota client for the match page, map coordinates
  src/headToHead.ts               the head-to-head file: every meeting of a pair of teams
  src/components/MatchPanel.tsx   match breakdown: scoreboard, items, compendium points, titles
  src/components/MatchMap.tsx     the minimap: wards, deaths, the timeline and the event feed
  src/components/TrendPanel.tsx   form and style cuts, shared by both profile pages
  src/i18n/site.ts                languages, version addresses, descriptions for search engines
  src/i18n/messages/en.ts         the reference dictionary — it defines the key set
  src/i18n/messages/<locale>.ts   one file per language, loaded as its own chunk
  scripts/seo.ts                  localized HTML, sitemap and robots at build time
```

---

## What matters when working with the results

**Stat availability.** OpenDota covers 15 of the 18 stats exactly. The rest:

| stat | status | why |
|---|---|---|
| `lotuses_grabbed` | approximate | counted from lotuses used (`item_uses.famango`); one picked up and handed to an ally is invisible |
| `madstone_collected` | no data | OpenDota does not track it |
| `watchers_taken` | no data | OpenDota does not track it |

The projection does not hide this: `unavailable_stats` in the response, a warning in the interface.
The gap can be closed with STRATZ (token in `ANALYZER_STRATZ_API_TOKEN`) — the mapping for it is not
written yet.

**Unparsed matches.** Matches without a parsed replay (`version: null`) have no wards, stuns, stacks
or teamfight participation. They still count towards team ratings (the outcome is known) but are
excluded from the Fantasy sample — otherwise the projection is systematically too low.

**Anti-leak.** Ratings are always recomputed from scratch, chronologically. A team's rating at the
moment of a match knows only about matches before it — otherwise the model would be "predicting" the
past.

**Which matches make up the sample.** A map counts towards a role only if at least three of the
team's current five played in it. Selecting purely by `account_id` would blur two different cases:
a squad that moved to a new brand (Iron Wing used to play as Tundra and 1w, LGD as HEROIC, Huligani
as L1GA — those matches belong in the sample, or the new tag is left with two dozen maps) and a
player who moved from another team (Noticed played 26 maps for Team Yandex — with different partners
there, and "the average across the role's players" would be computed from one person instead of
two). Roster overlap tells them apart without hand-written rename lists.

**How roles are determined.** There is no role field in the data. First the five with the most maps
for the team are selected (this cuts out stand-ins and players who dropped by for a couple of
matches), and only then are roles handed out inside that five: mid by the share of games in the
middle lane, the core duo as the two with the highest farm priority, the remaining two as supports.
The order matters: hand out roles before selecting the five and a visiting core with a high GPM
pushes a real support out of the roster.

Rosters are stored in a separate `team_roster_slots` table rather than as a field on the player:
rosters overlap (a player can play for two teams inside the period), and one row per player would
overwrite the markup of whichever team was processed first.

**Calibration matters more than accuracy.** A realistic pre-match forecast in Dota is nowhere near
90% accurate. What matters is that at a stated 70% the team really does win about 70% of the time,
not the bare share of correct guesses.

---

## Open questions

The War Banner screen settled these: the number of slots (3), the layout (a column), the formula
(additive), the slot colours per role, the list of Coaching Titles with their percentages. What is
left:

1. **Series format in Swiss.** Decided: decisive matches are Bo3, the rest Bo1
   (`regular_best_of` / `decisive_best_of` in `ti15_predictions.yaml`). Round 1 is no longer
   guessed: once the pairings were announced they went into `swiss.first_round`, and the simulation
   starts from them instead of splitting the field by seed. It is all or nothing — half the round
   from the bracket and half from the seeding would be two different tournaments. Later rounds are
   still paired by record, because they depend on results that have not happened yet.
2. **Prefix title conditions.** They depend on a hero's colour and type. The lists are filled in by
   hand from the glossary, and a hero that is not on any list simply does not trigger a prefix.
3. **Substitutions before the tournament.** Rosters are derived from a team's recent matches, but if
   a substitute has not played a single game yet, only a human can see it. `config/ti15_rosters.yaml`
   exists for that case — whatever is written there beats the automation. A player who has never
   played for the team at all is written as a dictionary rather than a nickname, because nicknames
   are not unique in OpenDota:

   ```yaml
   LGD Gaming:
     mid:
       - name: "Topson"
         account_id: 94054712
         replaces: "TaiLung"
   ```

   `replaces` is what makes the role computable. The newcomer has no games in the sample, so the
   projection is built from the maps of the player he replaced — a mid's points are largely set by
   how the team plays, so the slot is the best available prior. It is never passed off as the
   newcomer's own record: the role is flagged as a substitution, and the analyzer says so above the
   emblems ("the projection is built on the slot itself: N maps played by X"). If `replaces` cannot
   be resolved, the whole override is dropped and the role goes back to the automation — better the
   previous line-up than a slot with no history at all.

---

## Publishing and automation

The GitHub Pages page works **without a backend**: everything that needs a database or simulations
is computed ahead of time into `frontend/public/data/snapshot.json` (~760 KB), and the emblem maths
is mirrored in TypeScript in `frontend/src/engine/scoring.ts` — which is why the banner search, the
roll restriction and the per-stat rankings all run right in the browser. Team and player pages read
a separate `profiles.json` (~2 MB) that is only fetched when you open the **Profiles** tab, and the
head-to-head record is a third file (`head_to_head.json`, ~200 KB). The match itself comes from
OpenDota directly. Tabs that require a live server ("Data", "Ratings", the manual builder) are
hidden in this mode.

Refresh the snapshot by hand:

```bash
.venv/Scripts/python backend/tools/export_snapshot.py --simulations 20000
```

Three workflows:

| file | when | what it does |
|---|---|---|
| `.github/workflows/deploy.yml` | push to `main` touching `frontend/**` | builds the static site and publishes it to Pages |
| `.github/workflows/refresh-data.yml` | daily at 04:20 UTC | pulls fresh matches, recomputes ratings and analytics, commits the snapshot and triggers the deploy |
| `.github/workflows/tests.yml` | push and pull request | pytest on the backend, a type-checked build on the frontend |

The match database lives in the Actions cache between runs — otherwise every run would pull seven
hundred matches again and hit OpenDota's daily limit. Putting `OPENDOTA_API_KEY` into the repository
secrets raises the limit, but everything works without a key.

The daily refresh commits the snapshot only. It deliberately does **not** touch code: code changes
come from a human.

### Language versions and search

The app renders in the browser, but a crawler needs ready HTML. So the build
([`frontend/scripts/seo.ts`](frontend/scripts/seo.ts)) writes twelve pages next to the bundle — `/`,
`/ru/`, `/uk/`, `/zh/`, `/es/`, `/pt/`, `/de/`, `/fr/`, `/pl/`, `/tr/`, `/id/`, `/vi/` — and each
already carries its own `<title>`, description, `canonical`, `hreflang` links to its siblings, Open
Graph and Twitter cards, JSON-LD markup and an intro text explaining what the tool is. A human on a
slow connection sees the same text: before the first render the app waits for the portrait and icon
manifests, and that space used to be an empty page.

The dictionary is one file per language ([`src/i18n/messages/`](frontend/src/i18n/messages)), with
English as the reference: `MessageKey` is derived from it, so a missing or extra key in any other
language is a build error rather than an English string in the middle of a Vietnamese page. Only the
language you asked for is fetched — each dictionary is its own chunk of about 25 KB. A test on the
Python side checks the same parity, because new titles and stats are born in the YAML config, and
you want to hear about a missing translation in the same test run.

The search-engine texts sit in the same file as the language list
([`src/i18n/site.ts`](frontend/src/i18n/site.ts)) and are read from that one place by both the build
and the app: otherwise the tab title and the description in the results would drift apart one day.
The list of the sixteen participants is substituted into the intro block from the snapshot — a query
like "Team Falcons TI15 fantasy" should find the page rather than an empty shell.

`sitemap.xml` and `robots.txt` are generated in the same step; in the sitemap every address carries
its alternate language versions and a `lastmod` taken from the snapshot date. The preview images
(1200×630, one per language) are built separately:

```bash
.venv/Scripts/python backend/tools/build_og_image.py
```

Two caveats. First: for a GitHub Pages project site, `robots.txt` ends up at
`/fantasy-analyzer-dota2/robots.txt`, while a crawler only reads it from the domain root — that root
belongs to `myka322.github.io` as a whole and is not ours to control. Indexing here is driven by the
meta tags on the pages themselves, with the sitemap handed to Search Console by link. Second:
without external links it can take a while to appear in results — the site has to be added once to
[Google Search Console](https://search.google.com/search-console) and the sitemap submitted there.
The Search Console property has to be the URL prefix **including the subdirectory**
(`https://myka322.github.io/fantasy-analyzer-dota2/`): a domain-root property looks for the
verification file at the root of `myka322.github.io`, which this repository cannot serve.

### Auto-committing local edits

```bash
pwsh -File tools/autocommit.ps1
```

The script watches the files and commits with a push after a 45-second pause — edits pile up and
leave in a single commit, otherwise every save in the editor would spawn one of its own. Directories
from `.gitignore` (the database, the match cache, `node_modules`, `.venv`) are not watched. Flags:
`-DebounceSeconds` changes the pause, `-NoPush` commits without pushing.

### What stays out of the repository

`backend/data/` — the database and the match cache (about 400 MB, restored by `ingest-ti`), and the
source assets at full resolution: 80 portraits weigh 79 MB, and the interface export (`panorama/`,
`materials/`) is 4600 files and 137 MB, of which the page needs the minimap, three markers and the
item icons. What the repository holds are their WebP copies in `frontend/public/assets` — under
2 MB for the lot, produced by `tools/optimise_assets.py`.

---

## Tests

```bash
.venv/Scripts/python -m pytest
```

355 tests. The substantive ones:

- All nine cards from the War Banner screen are reproduced by the formula exactly (130/100/180,
  150/180/120, 160/130/130) — the most direct check of the scoring that exists.
- Glicko-2 matches the reference example from Glickman's paper (1464.06 / 151.52 / 0.05999).
- Every Swiss run produces exactly the bucket sizes the compendium has: 1 / 2 / 5 / 5 / 2 / 1.
- A volatile player with the same average beats a steady one — a direct consequence of the "best two
  maps of the best series" rule, and the main reason averages are useless here.
- The stat mapping is checked against a real parsed match, not an invented fixture.
- Form cuts are checked on the edge cases: a streak counts only the latest run, the form window does
  not overlap its baseline, and every map lands in exactly one duration bucket.
- The interface dictionary is checked against the config: every title, stat, role and trait must have
  a translation, and every language must cover the same key set as English. The check deliberately
  crosses the language boundary — a new title without a translation would break neither the frontend
  build nor the backend tests on their own, and the page would just quietly show an English string to
  someone who picked Chinese.

Separately, the regressions found on live data are covered:

- a run of 429s from OpenDota no longer kills ingestion (throttling has its own retry budget, one
  failed match does not kill the batch, one failed team does not stop the others);
- the 5xx branch was not incrementing the attempt counter — the client could spin forever;
- a player who spent a couple of maps on someone else's team does not end up in its roster;
- overlapping rosters do not erase the markup of a neighbouring team;
- a replaced player yields the slot to their successor even when they played more maps
  (the Team Vision case: SSS with 55 maps in March–April against Noticed's 50 in May–June).
