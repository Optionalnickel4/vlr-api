# Schedule and results broadcast preview

This slice extends the committed homepage/match/team/player visual system on `v2`, based on `20237af01053fd8a497b05ea09c0df14cb3d441a`. It changes only schedule/results presentation, focused tests and delivery evidence. No deployment or production restart is part of this delivery.

## Implementation

- Schedule: full-width fixture rows with source start clock, state, relative countdown, two team identities, stage and a direct match link.
- Results: two-column desktop cards, single-column below 1000px, with aligned tabular scores and a textual winner indicator. Zero remains zero; missing scores and ties never produce an invented winner.
- Both: broadcast masthead, feed count, date/event context, cross-navigation, shared `TeamCrest` initials, shared shell and existing fixed bottom ticker. Match-list payloads supply no crest URLs or team IDs; no guessed crests/team links were added.
- Only contiguous entries with the same estimated day and event are grouped. Flattening the groups exactly reproduces source order, including unknown dates and repeated events. The old schedule's extracted hero and regrouping are no longer used. There were no existing filters or pagination to retain. API loaders, normalizers, metadata, dynamic routes and `/match/{id}` destinations remain unchanged.
- Complete relative durations yield estimated UTC dates from page-load time (forward for fixtures, backward for results). Clocks, partial strings, LIVE and missing timings remain undated. Source age and clock timezone are unavailable; dates are explicitly estimates, not confirmed calendar dates. Stale/error data with retained rows suppresses estimated dates.
- Successful empty lists and failed requests have distinct messages. Missing team, time, stage, event, score or match ID remains explicit. No source row is dropped.

## Preview and verification

- [Schedule](http://10.0.0.21:3100/schedule)
- [Results](http://10.0.0.21:3100/results)

Port 3100 serves the isolated optimized build in `/tmp/vlr-preview/listings-final`, using the existing read-only cache adapter on 8101. Its source/public/config files were hash-compared with the working frontend. The preview has no controlled-data preload. Production `.next` was not built or replaced.

Real cached feeds contained **30 fixtures and 50 results**. The first fixture was G2 Esports vs Paper Rex (753456); the first result was 100 Thieves 2–0 T1 (753444). These are available cached records, not a claim of current real-world schedule freshness. The adapter reads existing cache without triggering scraper refreshes.

Fresh checks on September 27, 2026:

| Check | Result |
| --- | --- |
| `npm test` | 314 passed across 23 files, including 10 new listing regressions |
| `npm run lint` | Passed |
| `tsc --noEmit --incremental false` | Passed |
| Isolated `npm run build -- --webpack` | Passed |
| Chromium 1440×1000, 768×844, 390×844, 320×844 | Both routes, real cached and controlled populated/partial feeds: 16 layout cases passed |
| Controlled empty/error feeds | Both routes: 4 cases passed |
| Native Chromium 200% page zoom | Both routes at 1440/768 outer widths, 720/384 CSS-pixel content widths: 4 cases passed |

[Saved verification files](verification/match-listings/) include command logs with UTC times/exit codes, browser scripts/results, controlled fixtures and operational/source-parity evidence. Existing Vite CJS deprecation and React `act(...)` warnings remain in the passing test log. A final wording correction changed “countdowns” to “relative source timings” for accuracy on results and explicitly disclosed unknown source age; the saved checks and captures are from the final source.

## Browser observations and selected captures

No page-level horizontal overflow occurred at any checked width. Long unbroken team/event names wrapped at 320px. Scores remained aligned, and winner text avoided reliance on color. Tab advanced between direct match links with visible focus. The last match link and the bottom of each board scrolled above the ticker. Exactly one fixed ticker was present; no page errors occurred in the normal-width matrix. Native 200% zoom retained focus and bottom clearance.

Screenshots are viewport captures, not stitched full-page images. Desktop captures use fresh Chromium contexts at 100% zoom/DPR 1. Mobile captures scroll to the first date/event group. The ticker naturally overlays content passing behind it during scrolling; clearance assertions check focused final links and the page bottom. Browser-added evidence labels are not product UI.

| Evidence | Interpretation |
| --- | --- |
| [Cached schedule desktop](screenshots/match-listings/cached-schedule-1440.png) | 1440px, 100%; masthead, time-first fixtures and event context |
| [Cached results desktop](screenshots/match-listings/cached-results-1440.png) | 1440px, 100%; score cards and source sequence |
| [Cached schedule mobile](screenshots/match-listings/cached-schedule-390.png) | 390px, 100%; stacked team identities and match link |
| [Cached results mobile](screenshots/match-listings/cached-results-390.png) | 390px, 100%; scores, textual winner and stage |
| [Controlled schedule long names](screenshots/match-listings/controlled-schedule-320.png) | 320px, 100%; synthetic extreme names, not real fixtures |
| [Controlled results long names](screenshots/match-listings/controlled-results-320.png) | 320px, 100%; synthetic extreme names, not real results |
| [Cached schedule at native 200%](screenshots/match-listings/cached-schedule-zoom-200.png) | 1440px outer width, 720 CSS px |
| [Cached results at native 200%](screenshots/match-listings/cached-results-zoom-200.png) | 1440px outer width, 720 CSS px |

Controlled tests used a temporary loopback-only 3101 instance of the same build with a fetch preload. Only listing responses were substituted; the shell/ticker remained real. The fixture includes missing identity/time/event/stage/ID/score, a genuine zero and a tie. Empty and HTTP 503 cases were exercised separately. Retained stale-data behavior is covered by unit tests because the current loader returns an empty failed response rather than retained rows. The controlled instance was stopped after inspection. Temporary/redundant captures are excluded.

## Limits and production evidence

- Absolute match dates, source capture age, timezone and logos are absent from these contracts. Relative cached timing can age; estimated headings may drift. The UI exposes this limitation and does not promise live countdown accuracy.
- Repeated day/event headings are intentional when the source interleaves groups; preserving source order takes precedence over merging them.
- Native 200% was inspected at desktop/tablet outer widths; 390/320 were inspected at 100%. No screen-reader session or non-Chromium audit was performed.
- Production API `/health` and frontend `/favicon.ico` returned HTTP 200. API PID 61821 (active since September 17, 11:10:09 UTC) and frontend PID 308 (active since September 3, 04:02:56 UTC), both with `NRestarts=0`, matched the initial baseline. This supports no production restart during this work; it is not an exhaustive production route audit.
- The unrelated `.gitignore` change and untracked `docs/SHARED_NAV_HOMEPAGE_REDESIGN_PLAN.md` are byte-for-byte preserved and excluded from this commit.
