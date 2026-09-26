# VLR-API project handoff

Prepared September 26, 2026 from repository code and `docs/PROJECT_REVIEW.md`.
This is a source-based assessment, not a fresh production audit. Status labels
mean implemented in the inspected checkout, not guaranteed defect-free.

## 1. Purpose and audience

VLR-API is **both a REST API and a website**, branded **valstats**. It provides
Valorant esports scores, schedules, rankings, news, player/team profiles, and
historical analysis. The website serves esports viewers; the API supports
dashboards and integrations, including a team-match lookup intended for a
Command Central / Jarvis assistant.

The repository describes a personal, self-hosted, non-commercial portfolio
project. Actual user numbers or an established public audience are not documented.

Sources: [README](../../README.md), [assistant service](../../app/services/assistant.py).

## 2. Stack, structure, deployment, and data flow

| Area | Implementation |
| --- | --- |
| Backend | Python 3.11+, FastAPI/Uvicorn, httpx, selectolax, Pydantic |
| Storage/jobs | Redis, PostgreSQL, SQLAlchemy/asyncpg, APScheduler |
| Frontend | Next.js 16.2.7, React 19.2.4, TypeScript, Tailwind 4, Framer Motion |
| Verification | pytest, Vitest/happy-dom, ESLint, TypeScript |

Sources: [Python dependencies](../../pyproject.toml), [frontend package](../../frontend/package.json).

- [app/](../../app): API routers, scrapers, refresh/search/analytics services,
  schemas, database models, infrastructure, and scheduled jobs.
- [frontend/src/](../../frontend/src): pages and API proxies in `app/`, reusable
  `components/`, transformations in `lib/`, and domain `types/`.
- [tests/](../../tests): backend tests and saved HTML fixtures.
- [deploy/](../../deploy), [docs/](..): service templates and project documentation.

```text
VLR.gg HTML -> scrapers -> refresh services -> Redis cached payloads
                                          -> PostgreSQL selected history/snapshots

Redis -> FastAPI -> Next.js server loaders/proxy routes -> normalized UI data
PostgreSQL -> history/trend endpoints -> Next.js -> analysis panels
```

Cache misses can trigger scraping during API requests, despite older documentation
claiming otherwise. There is no universal database fallback for list responses.
Match detail is cached without a historical match-detail snapshot.
Sources: [routes](../../app/api/v1/routes.py), [refresh](../../app/services/refresh.py),
[frontend data layer](../../frontend/src/lib/vlr.ts).

External sources are VLR.gg HTML/autocomplete and Twitch Helix for stream status.
Fonts are downloaded at build time through `next/font`.
Sources: [Twitch integration](../../frontend/src/lib/twitch.ts),
[layout](../../frontend/src/app/layout.tsx).

Documented deployment is Debian/LXC with local PostgreSQL and Redis, Uvicorn on
port 8000, and production Next.js on port 3000 under systemd. The scheduler runs
inside the API by default; an optional separate scheduler must not duplicate it.
The frontend service is documented outside the repository. Reverse proxy setup
is optional. Running infrastructure was not inspected for this handoff.
Sources: [deployment guide](../../DEPLOY.md), [API service](../../deploy/vlr-api.service),
[operator script](../../start-services.sh).

## 3. Routes and features

| Status | Surface |
| --- | --- |
| Complete | Website `/`, `/schedule`, `/results`, `/rankings`, `/stats`, `/news` |
| Complete | `/match/[id]`: scores, vetoes, map tabs, scoreboards, rounds, live refresh |
| Complete | `/team/[id]`, `/player/[id]`: profiles, roster/agent statistics, results, trends; player rating dimensions |
| Complete | Player search, Twitch streams, curated ticker including live mode |
| Complete, API-only | Events, team search, assistant team-match lookup, historical data |
| Partial | Dimensions limited to NA/EU cohorts; trends require accumulated history; richer team records and ranking streak/win-rate displays remain limited |
| Planned/unimplemented | Player directory, redesign, review reliability fixes; clutch/ace event reporting needs additional source data |

Sources: [website routes](../../frontend/src/app),
[ticker](../../frontend/src/components/StatTicker.tsx).

Backend routes under `/api/v1`:

- `/matches/{results,upcoming,live}`, `/rankings`, `/stats`, `/events`, `/news`
- `/players`, `/teams`, `/players/{player_id}/dimensions`
- `/player/{player_id}`, `/team/{team_id}`, `/match/{match_id}`
- `/trends/team/{team_id}`, `/trends/player/{player_id}`
- `/history/results`, `/history/rankings/{team_id}`, `/history/player/{player_id}`,
  `/history/team/{team_id}`
- `/assistant/team-match`, `/status`

FastAPI also exposes `/health`, interactive documentation, and its own HTML `/`
and `/status`. The frontend has `/api/*` proxies plus `/api/ticker` and
`/api/streamers`. Sources: [backend routes](../../app/api/v1/routes.py),
[application wiring](../../app/main.py), [frontend handlers](../../frontend/src/app/api).

The [feature backlog](../../frontend/FEATURES.md) is stale: news, player trends,
and live ticker features are implemented despite being listed as planned.
The root README describes CS2 work on a separate branch; it is not part of the
inspected Valorant implementation and was not audited here.

## 4. Reliability issues

| Verified code issue | Observable failure case |
| --- | --- |
| Rankings TTL defaults to one hour; events TTL to 30 minutes. Both scheduled refreshes run every six hours. | Requests after expiry wait for scraping. Concurrent misses repeat refresh work; upstream failure can produce a backend error and unavailable frontend panel. |
| Homepage live polling does not check HTTP status, response shape, or error envelope. | An upstream failure returned as `{data: [], stale: true, ...}` clears previously visible scores. Network/JSON exceptions preserve scores, so behavior differs by failure type. |
| Search debounces input but does not cancel or sequence requests. | An older response arriving last replaces newer results; pending responses can reopen the dropdown after clearing or Escape. |

Evidence: [cache defaults](../../app/core/config.py),
[scheduler](../../app/jobs/scheduler.py), [cache-miss helper](../../app/api/v1/routes.py),
[LiveMatches](../../frontend/src/components/LiveMatches.tsx),
[PlayerSearch](../../frontend/src/components/PlayerSearch.tsx).

Recommendations, not implemented: retain stale data on refresh failures,
coalesce refreshes, validate polling responses, and cancel/ignore obsolete search
requests. The frontend upstream fetch also lacks an explicit timeout. Production
frequency and impact remain unmeasured.

## 5. Homepage, navigation, and reuse

The homepage contains streamers, live matches, five upcoming matches, five
results, then rankings/news. Paired sections use two columns on large screens
and stack on smaller screens. All six initial loaders are awaited together.
Source: [homepage](../../frontend/src/app/page.tsx).

The shared header links to Schedule, Results, Stats, Rankings, and News, alongside
player search; the wordmark links home. Its outer container wraps, but the inner
navigation/search row does not. There is no dedicated mobile menu; overflow needs
browser verification. Match/team/player pages use separate headers with a home
link instead of full navigation. Sources: [SiteHeader](../../frontend/src/components/SiteHeader.tsx),
[team page](../../frontend/src/app/team/[id]/page.tsx).

Reusable components include `Panel`, `SectionHeading`, `MatchSection`,
`MatchCard`, badges, score displays, tables, crests, sparklines, and analytical
panels. The root layout supplies a persistent bottom ticker.
Sources: [components](../../frontend/src/components), [layout](../../frontend/src/app/layout.tsx).

## 6. Design rules and assets

Existing rules specify dark broadcast styling, condensed uppercase headings,
restrained teal accents, green wins, red live/loss states, and no neon/cyberpunk
styling. Fonts are Saira Condensed, Saira, and JetBrains Mono.
Sources: [tokens/styles](../../frontend/src/app/globals.css),
[frontend guidance](../../frontend/CLAUDE.md).

The owner's newer direction combines dashboard, analytics, and editorial design;
the old “LOCKED” aesthetic should not be treated as immutable. The review is a
written brief, not a completed redesign.

Saved screenshots: [match](../screenshots/match-detail.png),
[team](../screenshots/team-page.png), [player](../screenshots/player-page.png),
[status](../screenshots/status-dashboard.png).

Branding is primarily a text wordmark. `TeamCrest` generates initials rather than
official logos. Public SVGs are scaffold assets. No dedicated redesign mockup
or brand pack was found. Sources: [TeamCrest](../../frontend/src/components/TeamCrest.tsx),
[public assets](../../frontend/public).

## 7. Verification and gaps

Recorded September 26 review baseline: **207 backend tests and 202 frontend tests
pass**, with clean lint and TypeScript checks. Tests were not rerun for the
read-only handoff.

```bash
# Repository root
.venv/bin/pytest -q

# Run these from frontend/
npm test
npm run lint
npx tsc --noEmit
npm run build
```

`.venv/bin/python -m app.scrapers.verify` checks live VLR markup and requires
network access. Routine tests use fixtures/mocks. Sources: [README](../../README.md),
[selector verifier](../../app/scrapers/verify.py).

No production build or browser/performance audit was performed in the review.
Mobile, keyboard, contrast, and failure scenarios need runtime checks. Existing
tests emit React `act` and Starlette/httpx warnings. The reliability cases above
need focused regression coverage.

## 8. Open decisions and constraints

Preserve normalization contracts, server-side backend access, scrape throttling,
and honest missing-data states. API compatibility matters because consumers
extend beyond the website. The repository documents non-commercial use and
distinguishes code licensing from data/image rights.
Sources: [README](../../README.md), [backend guidance](../../CLAUDE.md).

Historical frontend guidance restricts backend edits, although cache fixes require
backend work; implementation scope should explicitly cover that. Next.js changes
require consulting the bundled documentation specified in
[frontend/AGENTS.md](../../frontend/AGENTS.md).

The configured GitHub origin is **Optionalnickel4/vlr-api**. No ownership transfer
or deployment migration has been specified. The review proposes improvements
within the existing architecture, not a hosting change.

## Five questions for the owner

1. Who is the primary audience, and should the first release remain private/self-hosted or become publicly accessible?
2. Should the first implementation include backend reliability fixes and the shared shell/homepage, or redesign every existing page?
3. Which existing brand elements should remain, and what approved team, player, and editorial imagery is available?
4. Which API consumers must remain compatible, and how should stale scores and data freshness be presented?
5. Will GitHub ownership, repository location, hosting, domain, or deployment responsibility change—and who approves releases?
