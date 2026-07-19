# vlr-api — self-hosted VLR.gg REST API + broadcast dashboard

A self-hosted REST API that mirrors [vlr.gg](https://www.vlr.gg) Valorant esports data as clean JSON, plus a broadcast-style Next.js dashboard ("valstats") that reads it. The API scrapes vlr.gg's HTML, normalizes it, caches it in Redis, banks history in Postgres, and serves it through FastAPI.

vlr.gg has **no official API**. This project exists to turn its HTML into a stable, versioned, historically-aware JSON surface you can build on — a live match/results/rankings feed *plus* the analysis layer (rating trends, form, notable-performance curation, upset detection) that a raw data mirror structurally can't provide. It is a personal, non-commercial portfolio project; see [Legal & usage notice](#legal--usage-notice) before deploying it.

---

## Screenshots

<!-- TODO(screenshots): add real captures. Suggested sizes ~1400px wide, PNG. -->

<!-- TODO: match detail — scorebug + veto + map tabs + per-map scoreboard + round timeline -->
![Match detail](docs/screenshots/match-detail.png)

<!-- TODO: team page — identity header + rating-trend sparkline + results join + roster -->
![Team page](docs/screenshots/team-page.png)

<!-- TODO: player page — player card (weighted headline) + per-agent table + dimension radar -->
![Player page](docs/screenshots/player-page.png)

<!-- TODO: status dashboard — /status self-describing health page -->
![Status dashboard](docs/screenshots/status-dashboard.png)

---

## Features

Everything below is shipped and tested (13 backend phases, 6+ frontend slices). Nothing here is aspirational — the roadmap lives further down.

**Listings**
- Results, upcoming, and live match lists
- World and regional team rankings
- Events, and a news feed

**Player**
- Player detail: identity, per-agent stat table (values read verbatim from vlr), recent matches
- An ESPN-style player card with **rounds-weighted** headline aggregates (rating / K:D / ACS computed across agents, weighting by rounds played — a 5,000-round main agent isn't averaged flat against a 15-round off-pick), signature-agent chip, and recent-form dots
- Player rating/ACS **trend** over banked snapshot history
- **Dimension-split rating** — Firepower / Entry / Consistency / Clutch as 0–100 cohort percentiles, shown as a radar + labeled bars, with low-confidence flags on thin samples

**Team**
- Team detail: name, region, roster (players + staff), recent results
- Rating **trend** joined to results over the same window — the combined view vlr.gg itself never shows (it only exposes *current* rating)

**Match detail**
- Rich `/match/{id}`: header (event, series, status, format, teams + series score), veto strip, per-map list (pick/decider + map score), per-map and aggregate per-player scoreboards, and a per-round **timeline** (winner, side, outcome, cumulative score)
- Twitch stream channels scraped off the match page

**Stats & analysis**
- HLTV-style **stats leaderboard** led by vlr's own R2.0 rating (na/eu × 30d/60d/90d/all)
- **Live auto-refresh**: a scheduler job re-scrapes each in-progress match every 30s and the match page polls while live, so scores/stats/timeline update without a reload
- **Player search** (`/players?q=`): DB-first over banked snapshots, vlr autocomplete only on a miss — self-healing as history accumulates
- Broadcast **stat ticker** (curated notable performances, upsets, movers) and a **featured-streamers** bar (Twitch Helix live status)

**Ops**
- Self-describing `/status` dashboard: DB checks, per-table history counts, cache TTLs, scheduler last/next run — degrades gracefully when a dependency is down

---

## Architecture

The interesting part. Several deliberate engineering choices define this project — each is here because it solved a real problem, not for style points.

### The API never scrapes; the scheduler does

```
vlr.gg ──scrape──▶ scrapers ──normalize──▶ services ──┬──▶ Redis (cache)
                                                       └──▶ Postgres (history)
                                                              │
  browser / client ◀── FastAPI routers ◀── read cache, then DB
```

`app/api/v1/` routers **read from cache and DB only** — they never scrape inline. All scraping happens in a background APScheduler process (`app/jobs/`) on fixed cadences. A cold cache miss on a detail endpoint may trigger a single scrape-and-cache in the service layer, but the request path never does bulk scraping and never blocks on vlr under load. This keeps the public surface fast and predictable, and it means a vlr outage degrades to stale-but-served rather than a wall of 500s.

The layers are strict and one-directional (`app/api` → `app/services` → `app/scrapers`), and you don't cross them:

| Layer | Responsibility |
|---|---|
| `app/api/v1/` | Routers — read cache/DB only, never scrape |
| `app/services/` | Orchestrate scrape → cache → DB |
| `app/scrapers/` | One module per entity; **all** CSS selectors in `selectors.py` |
| `app/schemas/` | Pydantic response models |
| `app/models/` | SQLAlchemy ORM (history tables) |
| `app/core/` | config, db, cache, shared throttled HTTP client |
| `app/jobs/` | scheduler |

### Every CSS selector lives in one file

All vlr.gg selectors live in `app/scrapers/selectors.py` and **nowhere else**. This is the single most load-bearing rule in the codebase.

vlr.gg is a moving target — it has no API contract and rewrites its markup without notice. This project has already weathered several 2026 rewrites (the stats table, the match-scoreboard `<table>` → div-grid rewrite, the rankings world/regional split). Because every selector is one `grep` away in one file, a markup break is a **one-file diff**, not an archaeological dig through parsers. When vlr changes, you fix `selectors.py` and re-run the verifier — that's the whole loop.

### Scrapers store raw text; coercion happens at read time

Scrapers capture cell text as strings. Numeric coercion (`parseNumeric` → `null`, never `NaN`; `parse_percent`, `parse_fraction`) happens when data is read/served, not when scraped. This keeps the scrape layer dumb and lossless, isolates every number-parsing decision to one boundary, and means a surprising cell (an empty live stat, a `–` placeholder) becomes an honest `null` instead of a `NaN` landmine downstream.

### Redis cache + Postgres history

- **Redis** holds the live read surface with per-entity TTLs (`app/core/config.py`): live matches 30s, results/matches 10m, events 30m, rankings 1h, players/teams 1h, news 15m, stats 6h.
- **Postgres** banks history the live site throws away: `match_results`, `ranking_snapshots`, `player_snapshots`, `team_snapshots`. These snapshots are what make **trends** possible — vlr only ever shows *now*; the historical delta is net-new signal this project generates by banking captures over time.

### `verify.py` — a live-markup checker

The sandbox can't reach vlr.gg, so selectors can't be trusted until they're checked against real pages. `python -m app.scrapers.verify` fetches live vlr pages and asserts every selector still matches **with sane data**, covering every scraper surface: results/upcoming/live lists, world *and* regional rankings, events, news, player detail (with a non-null current-team probe *and* a null control), team detail, the match-detail scoreboard + round timeline, the stats leaderboard, and the `/search/auto` JSON shape.

Crucially, its checks are **semantic**, not just "did anything match": completed cards must carry two *numeric* scores (but upcoming cards legitimately render a `–` placeholder, so they're exempt); regional ranking team names must be `#`-tag-free (a `#` means a child span bled into the read — the exact bug it guards); a scoreboard `K` value must be under 100 and `ACS` under 1000 (a concatenated `K=13`→`"1385"` cell would still parse to a valid float, so magnitude is checked too). The `_check_*` helpers are pure, so their logic is exercised offline against saved captures; only `main()` touches the network.

### Tests assert structure and invariants — never volatile live values

Tests parse **saved HTML fixtures** and never touch the network. But the deeper rule is *what* they assert: structure and invariants, never live values. This avoids two failure modes that make a green suite lie:

- **The pinned-value fixture.** A test that asserts "TenZ's rating is 1.15" passes forever while reality drifts — the assertion is about a captured moment, not the code. So tests assert *relationships*: a rounds-weighted aggregate exceeds a naive mean, nulls sink in a sort, a scrambled series comes back chronologically ordered.
- **The "a team is present" test.** Asserting *a* team parsed — without checking *which* — stays green while the parser serves the wrong team. So identity checks pin the actual expected entity (Sentinels for team 2, a specific player id from search).

This is why `verify.py` exists alongside the unit suite: fixtures prove the parser is *internally* correct against known markup; `verify.py` proves the markup itself hasn't moved out from under the fixtures.

### Documented bug classes

`selectors.py` documents the recurring traps inline, so the next markup change doesn't re-learn them the hard way:

- **Side-split spans.** Scoreboard/stats cells hold three spans — `mod-both` (combined), `mod-t` (attack), `mod-ct` (defense). You read `span.mod-both`, **never** the cell's raw text, which concatenates all three: `K=13` renders raw as `"1385"` — coerces to a valid float, silently wrong.
- **Label-bleed.** Value nodes nest a label child ("Prize Pool", a date/author meta line); read the direct text or the label concatenates into the value.
- **String-sort traps.** Anything sortable sorts on the *coerced number*, never the raw string — otherwise `"998"` sorts above `"1024"`.
- **Double-matching selectors.** Comma-fallback selectors that *also* match live nodes return too many elements and rely on document-order luck; the primaries are kept deliberately single.

---

## Tech stack

**Backend** (`pyproject.toml`)
- Python 3.11+ (developed on 3.13)
- FastAPI ≥0.115, uvicorn ≥0.32
- httpx ≥0.27 (async client, throttled) + selectolax ≥0.3.21 (fast HTML parsing)
- Redis ≥5.2 (cache + live read source)
- Postgres via SQLAlchemy ≥2.0 (async) + asyncpg ≥0.30 (history)
- APScheduler ≥3.10 (cron cadences)
- pydantic ≥2.9 / pydantic-settings ≥2.6
- pytest / pytest-asyncio (fixture-based, no network)

**Frontend** (`frontend/package.json`)
- Next.js 16.2.7 (App Router) + React 19.2.4
- TypeScript 5, Tailwind CSS v4
- Framer Motion 12
- Vitest 2 (transforms vs committed real fixtures)

---

## Setup / Quick start

**Prerequisites:** Python 3.11+, Node 20+, PostgreSQL, Redis.

### ⚠️ Postgres MUST be UTF-8 — read this first

This is the single trap most likely to cost you hours. **The Postgres cluster must be UTF-8 encoded.**

A `SQL_ASCII` cluster throws `asyncpg.exceptions.UntranslatableCharacterError` the moment it tries to persist an accented name — `Ričardas Lukaševičius`, `LEVIATÁN`, `Türkiye` — and **silently fails to bank those records**. Worse, because a refresh writes the cache *before* the DB, the affected records appear to work on read and seem to "self-heal" on retry (the cache is warm) — so the corruption hides until you inspect the history tables and find accented entities missing.

A per-*database* `ENCODING 'UTF8'` is **not enough**: `template1` inherits the cluster encoding, so every new database it mints is broken the same way. You must fix the cluster (or `template1`).

Verify:

```bash
sudo -u postgres psql -c "SHOW server_encoding;"     # must be UTF8, not SQL_ASCII
sudo -u postgres psql -c "\l"                          # check template1's Encoding column too
```

Fix a `SQL_ASCII` cluster (Debian/Ubuntu; adjust the version):

```bash
sudo systemctl stop postgresql
sudo pg_dropcluster 16 main --stop
sudo pg_createcluster 16 main --locale=en_US.UTF-8 --start
```

Confirm `en_US.UTF-8` exists first with `locale -a | grep -i utf`; generate it (`sudo locale-gen en_US.UTF-8`) if it doesn't. Then recreate the role/database below into the now-UTF-8 cluster.

### 1. Database + role

```bash
sudo -u postgres psql <<'SQL'
CREATE USER vlr WITH PASSWORD 'change-me';
CREATE DATABASE vlr OWNER vlr ENCODING 'UTF8';
SQL
```

### 2. Environment

Copy the example and fill it in. All backend env vars are **`VLR_`-prefixed** (see `app/core/config.py`):

```bash
cp .env.example .env
chmod 600 .env
```

| Variable | Default | What it does |
|---|---|---|
| `VLR_DATABASE_URL` | `postgresql+asyncpg://vlr:vlr@localhost:5432/vlr` | Async Postgres DSN (history store) |
| `VLR_REDIS_URL` | `redis://localhost:6379/0` | Redis for cache + live read source |
| `VLR_USER_AGENT` | `vlr-api/0.1 (self-hosted; …)` | Sent to vlr.gg — keep it a real, identifying UA |
| `VLR_MIN_REQUEST_INTERVAL` | `1.5` | Minimum seconds between vlr requests (politeness throttle) |
| `VLR_ENABLE_SCHEDULER` | `true` | Run the scraping scheduler in-process (set `false` for a separate scheduler unit) |

Also configurable (sensible defaults in `config.py`): `VLR_REQUEST_TIMEOUT`, `VLR_MAX_RETRIES`, and the per-entity cache TTL knobs — `VLR_TTL_LIVE` (30), `VLR_TTL_RESULTS`/`VLR_TTL_MATCHES` (600), `VLR_TTL_EVENTS` (1800), `VLR_TTL_RANKINGS`/`VLR_TTL_PLAYERS`/`VLR_TTL_TEAMS` (3600), `VLR_TTL_NEWS` (900), `VLR_TTL_SEARCH` (600), `VLR_TTL_STATS` (21600).

### 3. Install

```bash
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -e ".[dev]"
```

### 4. Verify selectors FIRST

Before trusting a single byte of data, confirm the selectors match live vlr.gg markup:

```bash
.venv/bin/python -m app.scrapers.verify
```

Expect **`ALL SELECTORS MATCHED`**. If any entity reports 0 rows (or a semantic check fails), vlr changed its markup — fix `app/scrapers/selectors.py` and re-run until green *before* running the app. (The sandbox/CI can't reach vlr; this step must run somewhere with internet.)

### 5. Run the API

```bash
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- Health: `curl -s localhost:8000/health`
- Interactive docs: `http://localhost:8000/docs`
- A first request warms cold caches; the scheduler backfills the rest on its cadences.

### 6. Frontend

The frontend fetches vlr-api **server-side only** — the browser never calls the API directly, so vlr-api needs no CORS or public exposure.

```bash
cd frontend
cp .env.example .env          # set VLR_API_BASE (defaults to http://127.0.0.1:8000/api/v1)
npm ci
npm run build
npm run start                 # serves the production build on :3000
```

**Optional — Twitch** (the featured-streamers bar). Add to `frontend/.env`:

```
TWITCH_CLIENT_ID=<from dev.twitch.tv app>
TWITCH_CLIENT_SECRET=<from dev.twitch.tv app>
TWITCH_FEATURED=handle1,handle2      # optional comma-sep custom channels
```

The client secret is used server-side only (client-credentials grant) and never ships to the browser. Without these vars the streamer bar simply renders empty — that's a valid state, not an error.

---

## Development

- **Backend tests:** `.venv/bin/pytest -q` — parse saved fixtures, no network.
- **Frontend tests:** `cd frontend && npm test` — Vitest over committed real-response fixtures.
- **When to run `verify.py`:** any time you touch `selectors.py` or suspect a vlr markup change, run it on a machine with internet. Unit tests prove the parser is correct against *known* markup; `verify.py` proves the markup hasn't moved.
- **The selectors rule for contributors:** a new or changed vlr selector goes in `app/scrapers/selectors.py` and nowhere else. If you find a selector string inline in a scraper, that's a bug.
- **Frontend gotcha:** `next start` serves the compiled `.next/` output. A source change is **not** live until you `npm run build` again — always rebuild before restarting the web service, or you'll be staring at stale UI wondering why your change vanished.

---

## Deployment

Systemd unit templates live in `deploy/`:

- **`deploy/vlr-api.service`** — the uvicorn API. The scheduler runs in-process by default (`VLR_ENABLE_SCHEDULER=true`), so this one unit is usually all you need.
- **`deploy/vlr-scheduler.service`** — a *separate* scheduler process, only for multi-worker setups where you set `VLR_ENABLE_SCHEDULER=false` on the API so scraping isn't duplicated per worker.

The frontend runs as its own unit (`next start` on the production build — never `next dev`), ordered after the API. Both units, plus the UTF-8 and Twitch specifics, are documented in **[DEPLOY.md](DEPLOY.md)**, which is written to be environment-agnostic (parameterized user/paths/host — set them once at the top and paste).

**A thin wrapper around `systemctl` is a convenient operator pattern.** A small script that maps `start` / `stop` / `restart` / `rebuild` / `status` / `logs` onto the two (or three) units saves a lot of typing during a deploy — with one caveat baked in: **the frontend must be rebuilt (`npm run build`) before its service restarts**, so the "rebuild" verb should build *then* restart the web unit, not restart alone. (This repo carries such a wrapper for its own machine; it's gitignored because it's environment-specific, and it's intentionally not part of the project surface.)

**WSL2:** the whole stack runs fine on WSL2 with systemd enabled — add the following to `/etc/wsl.conf` and restart the distro:

```ini
[boot]
systemd=true
```

---

## Project status & roadmap

**Shipped:** 13 backend phases, **173 backend tests + 171 frontend tests** passing. Core listings, player/team detail + trends, rich match detail, stats leaderboard, dimension ratings, live auto-refresh, search, and the status dashboard are all live and verified against real vlr markup.

Honest caveats — things that are *correctly* limited rather than broken:

- **CS2 / HLTV support exists on a branch, not master.** The `feat/cs2-second-game` branch adds a second game (Counter-Strike via HLTV.org). HLTV is far more aggressive about anti-scraping than vlr — it requires Chromium for a `nodriver`-based Cloudflare bypass — so it's kept off master until it's solid.
- **Dimension breakdowns cover only vlr's NA/EU stats cohorts.** A player outside those leaderboard pools (a recent signing, or someone below vlr's rounds threshold) correctly shows *"rating breakdown unavailable"* rather than a fabricated percentile. Honest-null beats a made-up number.
- **Trends need history to accumulate.** Snapshots are banked over time by the scheduler (and on player-page views). A fresh install shows empty/young trends until enough data points bank — the trend panels say so honestly instead of drawing a fake flat line.

The forward-looking backlog (news page, player directory, live-mode ticker) lives in `frontend/FEATURES.md`; the per-phase build journal is in `PROGRESS.md`.

---

## Legal & usage notice

**Please read this before deploying.**

- vlr.gg's Terms of Service prohibit scraping for **commercial** purposes.
- Riot Games' IP policy limits use of its intellectual property to **non-commercial fan** projects.

This is a **self-hosted, non-commercial, personal/portfolio project**. It is **not affiliated with, endorsed by, or sponsored by Riot Games or vlr.gg**. VALORANT is a trademark of Riot Games, Inc. All Valorant data and imagery belong to their respective owners.

The project defaults to a **1.5-second minimum request interval** and identifies itself with a real User-Agent. If you deploy it, you are responsible for respecting vlr.gg's rate limits and Terms, keeping usage non-commercial, and staying within Riot's fan-content guidelines. Don't point it at vlr at high frequency, and don't resell or commercialize the data.

---

## License

This project's **code** is licensed under the [MIT License](LICENSE) © 2026 Nickel (GitHub: [Optionalnickel4](https://github.com/Optionalnickel4)).

The MIT license covers **this repository's source code only.** It grants **no rights** to vlr.gg's data or to Riot Games' intellectual property — those are governed entirely by the [Legal & usage notice](#legal--usage-notice) above. "MIT-licensed" is **not** permission to commercially redeploy a vlr.gg scraper or to redistribute vlr's data; the code is open, the data and IP are not.
