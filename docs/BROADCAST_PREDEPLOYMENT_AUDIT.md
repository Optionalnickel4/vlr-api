# Broadcast predeployment audit — September 27, 2026

**Recommendation: not ready for public deployment or promotion.** The visual implementation and automated checks pass, but cold-cache detail coverage and refresh latency remain release dependencies. Written permission for VLR collection, display and redistribution is a separate public-launch dependency. No deployment, production restart, cache flush, upstream scrape, or external message was performed by this audit.

Reviewed `v2` from `5131fd1d10552824d4b788df87f01d8b2b05852c`, including `frontend/AGENTS.md`, the route/component implementations, tests, `PROJECT_REVIEW.md`, and `NEWS_BROADCAST_PREVIEW.md`. Earlier delivery reports are historical evidence; the logs linked below are fresh runs. The four implementation commits and the evidence commit remain local on `v2`; no push was performed. The local `origin/v2` tracking ref remains at the baseline above.

## Changes and compatibility

| Commit | Defect and correction | Focused evidence |
| --- | --- | --- |
| `7343960` | Generic frontend loaders discarded `X-VLR-Cache: stale`. Propagate it into the existing `stale` field; keep the raw `fetchUpstream` return shape. | Upstream deadline/header tests: 12 passed. |
| `5b5355b` | Match polling could accept failed/stale payloads and silently retain old scores. Check HTTP/envelope/identity, retain last good scores with a status notice, serialize polls, abort at 15 seconds, clean up and stop on final. | Match polling tests: 8 passed, including failure, recovery, timeout and cleanup. |
| `c48b91f` | Failed live ticker polls continued claiming “LIVE WIRE”. Retain statistics with “STALE WIRE”, an accessible warning label, and no live pulse; clear after recovery. | Ticker hydration/polling tests: 6 passed. |
| `cac586a` | Public ticker compared ranks from the combined regional feed to declare “upsets”, although no common ladder identity is supplied. Withhold those entries; retain supported ACS/trend items and existing sampling. | Ticker curation/aggregation tests: 19 passed, including cross-region regression. |

No backend JSON contracts, scraping behavior, route names, sorting calculations, or shared layout changed. The ticker remains fixed on desktop and mobile. Existing source-derived fixtures are controlled test inputs, not new live performance claims.

## Fresh checks and operational boundary

| Check | Result |
| --- | --- |
| Backend `.venv/bin/pytest -q` | 241 passed; one Starlette/httpx deprecation warning |
| Frontend `npm test` | 338 passed in 25 files; existing React `act` and Vite CJS warnings remain |
| `npm run lint` | Passed; this is the configured frontend lint command, not an unconfigured Python linter |
| `tsc --noEmit --incremental false` | Passed |
| Isolated `npm run build -- --webpack` | Passed in `/tmp/vlr-preview/audit-delivery`; production `.next` untouched |
| Backend freshness suite, verbose | 34 passed using an isolated Redis Unix socket and mocked scrapers; no production scheduler lifespan |

[Logs, commands, timestamps and result JSON](verification/audit/2026-09-27/) are retained. [Preview](http://10.0.0.21:3100/) uses the final isolated build and the GET/SELECT-only adapter on 8101. Its source/public/config files are hash-compared with the working frontend. There is no fixture preload on 3100. Controlled checks use a separate loopback-only 3101 instance with the same build; it is stopped after verification.

Production API PID **61821**, frontend PID **308**, both active with **NRestarts=0**, retain their original active timestamps (September 17 and September 3 respectively). `/health` on 8000 and the frontend favicon on 3000 return 200. This supports process continuity and basic health, not a full production application or load test. `.gitignore` and the untracked saved redesign plan are byte-compared with their starting copies and left untouched.

## Route and browser coverage

Chromium at **1440, 768, 390 and 320 CSS pixels** (1000px height): 72 route/viewport cases. All fit the page width, have exactly one fixed ticker, keep the final focused control and page bottom above it, and have no uncaught page errors. Reduced-motion emulation showed no running CSS animations. Native browser **200% zoom**, at 1440/768 outer widths (720/384 CSS pixels), passed 18 route cases without overflow or bottom obstruction.

| Route | Real/cache evidence | Controlled evidence |
| --- | --- | --- |
| `/` | Cached upcoming/results/rankings/news; live availability varied. Honest “waiting for live data” observed. | Live feed and keyboard player search; fixture ticker discovery |
| `/schedule`, `/results` | 30 fixtures / 50 results, source order, direct match links, estimate disclaimers | Long names/events, missing fields/links, valid empty and HTTP failure |
| `/rankings` | 128 entries; combined regional ladders explicitly not a global ranking | Long/missing teams, empty/error; retained rows with stale header visibly warn |
| `/stats` | 100 players, supported round samples, sorting and filter labels | Long/missing values, empty/error/stale envelope; numeric sort regression suite |
| `/news` | 30 titles/bylines/dates/direct source links, no news images | Long/missing titles and metadata, empty/error |
| `/match/[id]` | Cached IDs found during inventory, but requested detail expired/missed in the browser matrix and link journeys | Populated/final/live/upcoming, broken imagery, missing/error; map keyboard controls and table scrolling; live failure retains scores and labels ticker stale |
| `/team/[id]` | No detail keys available; honest unavailable UI. Read-only team trend API returned data. | Populated/partial/empty/error/history-error, chart/table and crest fallback |
| `/player/[id]` | No detail keys available; honest unavailable UI. Search used real DB rows. Player analytics paths are unsupported by this preview adapter. | Populated/partial/empty/error/history-error, agent raw-key tables, trend/dimension context and fallback identity |
| Unknown route | 404 and shared-shell return link | Not needed |

All **14 frontend API route patterns** were read through 3100, including ticker, search, trends and streamers. JSON envelopes distinguish failure from success; individual observations are in `api-coverage.json`. Streamers are unavailable with deliberately blank preview Twitch credentials. There is no frontend events page/API proxy; events header behavior is covered by backend tests, not invented browser coverage.

Real link journeys: Home → Schedule → match `753456`; Home → Results → match `753444`; Home → Rankings → team `8877`; Home → Stats → player `3799`. Back and forward restore the correct routes. These details were unavailable: route correctness is not successful real-detail rendering. DB search returned nine choices for “Ten”; ArrowDown/Enter opened player `26809`. Controlled search reached a populated fixture profile. Stats header Enter changes `aria-sort`; ArrowRight moves the table horizontally. Keyboard EU/30D filter selection updates `aria-pressed`, and the Europe ranking link updates its URL/current state. Match ArrowRight/End changes selected map; both scoreboards scroll by keyboard. Ticker pause/resume works by keyboard. Accessible snapshots inspected names for navigation, search combobox/options, table columns, scroll regions and selected/sorted states. No actual screen-reader session or complete accessibility conformance assessment was performed.

Firefox and Safari/WebKit were not installed, so they were not tested. Browser scripts initially needed explicit waits for client-side history changes, a locator update after “Pause” became “Resume”, and the exact “30D” button label; reruns passed. These were test-harness corrections, not claimed application fixes.

## Freshness and remaining technical dependencies

- **Estimated dates:** `frontend/src/lib/matchListings.ts` derives UTC grouping from relative durations at page load. `MatchListingParts.tsx` labels headings “Estimated date · UTC” and explicitly says they are not confirmed dates; source age/timezone are unavailable. Stale rows withhold estimated dates. Contiguous grouping preserves source ordering. Cached relative times can still drift as a cache ages; obtain source timestamps before offering confirmed calendar dates/calendar export.
- **Rankings/events:** `app/core/cache.py`, `app/services/refresh.py` and `_retained_or_refresh` in `app/api/v1/routes.py` preserve last-successful data and send `X-VLR-Cache: stale` with no-store. Fresh payloads, stale failure/backoff, coalesced cold requests, real empty lists, cold 503s, cancellation/timeouts, and response-before-background-refresh are freshly tested. Rankings now propagate stale status into the UI. Events cache was absent in the read-only adapter; no production cold scrape was triggered to manufacture evidence.
- **Release blocker — cold coverage/latency:** results/upcoming/live/news/details still use expiring caches and inline refresh on miss; they do not share rankings/events retention/coalescing. Live-list TTL is 30 seconds, scheduled upcoming refresh is 60 seconds, and the 30-second live-detail job can refill the list on a miss. Scrape latency/failure leaves gaps despite that fallback. Team/player caches were absent and all tested real-detail journeys failed gracefully. Validate a bounded refresh/retention or prewarming strategy in a staging backend before releasing; do not interpret controlled detail renders as proof of real-source availability.
- **10-second deadline:** frontend requests include headers and body in the deadline. Backend retained refresh can wait up to 120 seconds; underlying HTTP attempts have a 20-second timeout plus throttling/retries. A simulated 12-second rankings refresh produces an unavailable UI and then recovers on reload. Waiting for browser network-idle can take about 21 seconds because ticker requests begin after the initial page request; this is not a 10-second whole-page SLA. A direct frontend API request timed out at 10050ms with the existing stale/error envelope. Unit tests verify abort at 10 seconds for both headers and body. No production slow-refresh test or sustained concurrency/load test was run.
- Live UI islands now retain last-good scores on failure and disclose staleness. This retention lasts only within the mounted client; a cold visitor still depends on backend availability. Static ticker entries have no capture timestamp, and retained static content does not gain a stale notice on a failed refresh. Freshness remains incomplete beyond the fixed live path.
- Complete Firefox/WebKit and assistive-technology checks before claiming broad accessibility/browser support. Preview-only player analytics and disabled Twitch remain explicit coverage gaps.

## VLR-derived material and public-launch dependencies

The earlier [news inventory](NEWS_BROADCAST_PREVIEW.md#vlr-derived-news-inventory) remains applicable. This expands it to the whole site; it does not establish that any reuse is licensed.

| Material | Implementation and source | Public-launch action |
| --- | --- | --- |
| News titles/bylines/dates/excerpts | `app/scrapers/events.py` reads [VLR news](https://www.vlr.gg/news); `frontend/src/lib/vlr.ts` normalizes it. `NewsBoard.tsx` renders titles/metadata, no descriptions. `HomeSections.tsx` → `NewsPanel.tsx` renders the first five titles and the **complete first description**. Legacy `NewsRow` can clamp descriptions visually while retaining full text. | Keep original article links; omit or shorten the homepage excerpt only within an agreed reuse policy. Headline aggregation itself still needs clearance for the intended public use. |
| Bulk news text | `frontend/src/app/api/news/route.ts`, `app/api/v1/routes.py` `/news` preserve full listing descriptions; no article-body extraction in this scraper. Source-derived examples also remain in `frontend/src/lib/__fixtures__/news.json` and `tests/fixtures/news.html`. | Withhold promotion of excerpt redistribution, fixtures and real-story screenshots pending written scope; a headline-only page does not remove the API feed. |
| News/editorial images | None in the current news payload/parser/components. No article photos, thumbnails or Open Graph images are fetched by that news path. | Keep absent unless supplied with suitable reuse rights. |
| Team crests/logos | `app/scrapers/teams.py` extracts VLR team-page logo URLs (including `owcdn.net`); `TeamCrest.tsx` renders supplied HTTP(S) URLs with `next/image` unoptimized. Used in `TeamOverview.tsx` and `MatchHeader.tsx`; match UI accepts a logo if supplied, while the current match scraper does not extract one. | Obtain written display/hotlink/promotional scope from VLR and any relevant mark/asset owners. Initials are honest fallbacks, not VLR image assets. No VLR logo graphic is bundled. |
| Player/agent/round imagery | `PlayerCard.tsx` uses initials; role/portrait unavailable. Player and match scrapers read agent image **alt text**, and match round image filenames become outcome labels. Charts/round UI are rendered components/SVG, not copies of those images. `frontend/public` contains unused starter SVGs, not VLR media. | Do not substitute scraped portraits or agent/game assets without permission. Riot/team/player rights are not granted by the code license. |
| Other remote imagery | `StreamersSection.tsx`/streamer cards and `frontend/src/lib/twitch.ts` use Twitch data when configured; preview disables credentials. | Separate provider dependency, not evidence of VLR-owned news imagery or permission. |
| Match/team/player/statistical text and derived analytics | `app/scrapers/{matches,match_detail,rankings,stats,teams,players}.py`; VLR matches, team/player pages, rankings and stats. Redis/Postgres snapshots feed frontend detail/listing tables, histories, charts and ticker. | Written scope should cover collection, storage/history, public display, derived analytics and promotion. Do not represent regional ranks as global; unsupported public upset comparisons are now withheld. |
| Public JSON redistribution | All `frontend/src/app/api/**/route.ts` endpoints are callable without app authentication: matches/live/results/upcoming, match, team, player, rankings, stats, news, players search, team/player trends, ticker, streamers. Backend `app/api/v1/routes.py` additionally defines events, dimensions, team search, assistant team-match, history/results/rankings/player/team and status. `app/main.py` has no auth layer. Backend external exposure was not established; frontend proxy exposure is enough to constitute redistribution functionality. | Decide authorized datasets, history/bulk access, caching, rate limits and downstream rights before promotion. Attribution and the repository MIT license do not authorize redistribution. |
| Screenshots and fixtures | `docs/screenshots/`, `docs/verification/`, frontend JSON/backend HTML fixtures can reproduce VLR-derived text, names and logos. Controlled captures can still contain names/statistics from saved source fixtures. | QA evidence is not permission-cleared advertising. Use wholly synthetic content or obtain appropriate clearance for public promotional assets. |

**Written-permission dependencies:** VLR's [published terms](https://www.vlr.gg/terms), checked September 27, 2026 (updated September 16, 2025), limit content reuse and address systematic collection and automated extraction. Obtain written authorization covering this service's collection, storage, display, API redistribution and promotion, plus relevant third-party asset rights. Attribution is a condition of some authorized uses, not permission by itself. No written authorization was found in the reviewed repository documents; that does not establish whether the owner holds permission elsewhere. No message was sent. Shortening an excerpt alone does not settle the broader collection/redistribution dependency.

**Technical launch dependencies:** resolve/validate cold-cache availability and bounded refresh behavior, confirm real detail/analytics journeys, and establish operating/load expectations. Browser/accessibility gaps and incomplete capture-time metadata also remain. These are separate from obtaining permission: passing a build neither grants rights nor proves production data availability.

## Selected visual evidence

All captures are labeled viewport screenshots, not stitched pages; only final-build evidence is included. Real/cache screenshots can include periods of unavailable data. Controlled captures are QA fixtures, not current matches or licensed promotional material.

- [Cached homepage, desktop 100%](screenshots/audit/cached-home-1440.png)
- [Cached stats, desktop 100%](screenshots/audit/cached-stats-1440.png)
- [Cached schedule, mobile](screenshots/audit/cached-schedule-390.png)
- [Controlled match, desktop](screenshots/audit/controlled-match-1440.png)
- [Controlled player, 320px](screenshots/audit/controlled-player-320.png)
- [Controlled live outage and stale ticker, 320px](screenshots/audit/controlled-live-outage-320.png)
- [Cached stats at native 200% zoom](screenshots/audit/cached-stats-200-percent.png)
