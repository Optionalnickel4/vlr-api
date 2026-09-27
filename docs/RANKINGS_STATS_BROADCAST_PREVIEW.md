# Rankings and stats broadcast preview

The rankings/statistics slice extends the broadcast system on `v2`, based on `18a128dfb9e5dce985fec6692274e2662767f61e`. Only these routes, their components/tests, documentation and evidence are included. No deployment or production restart was performed.

## Presentation and preserved behavior

Rankings now use the shared broadcast masthead, regional navigation and side-by-side desktop ladders. Every source row, rank, rating, source country/region label and team-page link is retained in order. Ladder boundaries follow the existing rank-reset interpretation; country changes do not split ladders. The all-regions response does not supply ladder names, so groups are explicitly numbered rather than assigned inferred regions or presented as a global ranking.

The region links use the backend's existing allow-list: all, north-america, europe, brazil, asia-pacific, korea, china, japan, la-s, la-n, oceania, gc, mena and collegiate. Unsupported query values fall back to all; each selected region has `aria-current`. Named views use the existing `getRankings(region)` loader and contract. Links disable prefetch to avoid eagerly requesting uncached regions. No new backend fields, calculations or endpoints were introduced. The homepage rankings treatment is unchanged.

Stats retain NA/EU and 30D/60D/90D/ALL controls, the default R2.0 descending order, all existing sortable columns, numeric sorting, missing-values-last behavior, stable ties, formatting and player links. First-kill sorting still sorts the FK/FD column by FK; the guide makes this explicit. The normalized source values and calculations are unchanged. The newly visible Rounds column uses the existing `rnd` value, including genuine zero, without deriving a sample from player counts.

The former podium is a set of three preview cards labeled by position in the current sort. It no longer claims “Top Rated” after an unrelated sort. Buttons within column headers support Enter/Space, preserve `aria-sort`, and expose the current direction. Selected filter/sort context and a column glossary explain the table. Numeric columns are right-aligned and tabular; the player identity column stays visible during horizontal scrolling. The table region itself accepts keyboard focus and arrow-key scrolling.

Changing filters clears the old rows while the new request loads, preventing another region's data from appearing as the selected region. Late responses cannot replace a newer selection. Failed HTTP or malformed envelopes produce a graceful error. Empty, failed, stale-with-rows and missing-value states remain distinct. Shared shell and fixed bottom ticker are unchanged; focus scroll margins account for ticker height.

## Preview and sources

- [Rankings](http://10.0.0.21:3100/rankings)
- [Stats](http://10.0.0.21:3100/stats)

Port 3100 serves `/tmp/vlr-preview/ladders-final`, an isolated optimized build with source/public/config parity checked against the working frontend. No controlled-data preload is installed on 3100. Production `.next` was not built or replaced.

The existing read-only adapter on port 8101 supplies Redis GET/SELECT-only data. Its preview-only filter validation was corrected to accept the existing API's hyphenated ranking slugs and `30d`/`60d`/`90d` stats values; only that adapter process was restarted. No production service was restarted and no scrape/refresh was triggered.

Real cache inspection found 128 ranking rows and 100 NA/all player rows. Karmine Corp headed the first supplied ladder; Notuud was first under the default stats sort. All eight NA/EU timespan combinations returned cached rows during keyboard testing. Europe and North America named ranking caches were unavailable; Europe navigation was browser-tested and displayed an honest unavailable state. These records establish cached availability, not real-world freshness.

A temporary loopback-only 3101 instance of the same build supplied labeled controlled long names, missing fields, missing links, zero values, empty lists, HTTP errors and stale statistics. The source fixtures/preload are saved with the verification files. Retained stale rankings are covered by component tests: the current rankings loader's error path supplies an empty list, not retained rows. The controlled server was stopped after inspection.

## Fresh verification

| Check | Result |
| --- | --- |
| `npm test` | 323 tests passed across 24 files; nine new focused regressions |
| `npm run lint` | Passed |
| `tsc --noEmit --incremental false` | Passed |
| Isolated `npm run build -- --webpack` | Passed |
| Chromium at 1440×1000, 768×844, 390×844, 320×844 | Both routes with cached and controlled populated/partial data: 16 cases passed |
| Keyboard filter navigation and controlled states | Eight cached stats filter combinations, named ranking cache-miss navigation, and five controlled empty/error/stale cases passed |
| Native Chromium 200% page zoom | Both routes at 1440/768 outer widths (720/384 CSS pixels): four cases passed |

[Saved verification](verification/ladders/2026-09-27/) includes final command logs with UTC timestamps and exit codes, browser scripts/results, fixtures and operational/source-parity evidence. Existing Vite CJS deprecation and React `act(...)` warnings remain in the passing suite.

The initial isolated build rejected an optional page argument; the rankings signature and direct test callers were corrected. Visual review then corrected an overly broad crest selector and constrained the stats identity column so mobile screens show more numeric content. The saved final checks and screenshots reflect those corrections; earlier intermediate captures were excluded.

## Browser observations and selected screenshots

No document-level horizontal overflow occurred in the checked matrix. Rankings use two ladders across on desktop and one on smaller screens. Extreme unbroken team/player names wrap within their cells. Numeric values remain right-aligned. Wide tables scroll inside named focusable regions, with arrow keys reaching additional columns; the far-right column is reachable. Stats sort buttons change direction with Enter, and the column guide opens from the keyboard. Native 200% zoom retains usable scrolling and visible focus. The final team/player link and final table scroll above the fixed ticker. The normal-width matrix had one fixed ticker and no page errors.

All screenshots are viewport captures with browser-added source/zoom labels, not stitched pages. Desktop 100% captures use fresh contexts at DPR 1. Table-focused mobile captures scroll down; stats captures also scroll horizontally to expose sample/rating columns beside the sticky identity column. The ticker may cover intermediate content during scrolling, while the final-link/bottom assertions establish clearance.

| Screenshot | Evidence |
| --- | --- |
| [Cached rankings desktop](screenshots/ladders/cached-rankings-1440.png) | 1440px, 100%; regional controls and adjacent source ladders |
| [Cached stats desktop](screenshots/ladders/cached-stats-1440.png) | 1440px, 100%; active filters, preview cards and numeric headers |
| [Cached rankings mobile](screenshots/ladders/cached-rankings-390.png) | 390px, 100%; readable team/rating rows |
| [Cached stats mobile controls](screenshots/ladders/cached-stats-controls-390.png) | 390px, 100%; wrapping filter groups and visible selected state |
| [Cached stats mobile table](screenshots/ladders/cached-stats-390.png) | 390px, 100%; horizontally scrolled numeric table with sticky player identity |
| [Controlled rankings long names](screenshots/ladders/controlled-rankings-320.png) | 320px, 100%; synthetic names and partial data, not real rankings |
| [Controlled stats long names](screenshots/ladders/controlled-stats-320.png) | 320px, 100%; synthetic player identity and missing sample |
| [Cached rankings at native 200%](screenshots/ladders/cached-rankings-zoom-200.png) | 1440px outer / 720 CSS pixels |
| [Cached stats at native 200%](screenshots/ladders/cached-stats-zoom-200.png) | 1440px outer / 720 CSS pixels |

## Limits and operational evidence

- The rankings contract loses regional heading names from the all-regions source. Rank resets are the available grouping signal; numbered groups avoid inventing those names. Named regional cache misses remain unavailable in this preview.
- No capture timestamp is supplied. Ranking match samples, rank movement and global rank are unavailable; none are inferred. Stats supply per-player rounds but not exact window boundaries. No freshness timestamp or trend claim was added.
- The existing rankings loader does not surface cache-status response headers in its envelope. Consequently the UI cannot identify retained cache data from those headers alone; it does not label such data fresh. Explicit stale/error envelopes are handled and tested.
- Existing numeric display formatting is preserved (for example, whole-number ACS/ADR and two-decimal R2.0); raw API payloads and normalized values were not changed.
- Native 200% checks cover desktop/tablet outer widths; 390/320 checks use 100%. No screen-reader session or non-Chromium audit was performed.
- Production API `/health` and frontend `/favicon.ico` returned HTTP 200. API PID 61821, active since September 17 at 11:10:09 UTC, and frontend PID 308, active since September 3 at 04:02:56 UTC, retained their baseline identities and `NRestarts=0`. This supports no production restart, rather than an exhaustive production-route audit.
- `.gitignore` and the untracked `docs/SHARED_NAV_HOMEPAGE_REDESIGN_PLAN.md` are byte-for-byte preserved and excluded from this commit.
