# Team detail broadcast preview — 2026-09-27

Team-only delivery on `v2`, based on the committed homepage (`d71f389`) and match detail (`0fa35c4`). No deployment. Production API/frontend services were not restarted; the preview frontend and its read-only adapter were the only processes restarted.

## Implementation

The page now follows identity/summary → recent form → rating movement → roster → results. The shared navigation and fixed bottom ticker are unchanged.

- Identity uses the supplied crest through the existing `TeamCrest`, with initials for absent or failed images. Team tag, country, listed player/staff counts, and source attribution provide context.
- Recent form shows up to five team-detail results in **source order**, with explicit win/loss/unknown labels, unchanged scores, event/date text, and match/opponent links when IDs exist. It is explicitly separate from the historical lookback.
- Rating history shows the API's current/peak/change/W–L values, requested lookback, actual capture range, rated sample count and total captures. A single point never shows a delta or line; flat history and unusable capture dates have explanatory states. The SVG uses elapsed capture time, labels its non-zero rating range, and breaks at missing ratings. A native disclosure exposes exact UTC captures, ratings and ranks in a labeled keyboard-scrollable table.
- Roster retains player links, external fallbacks, role/country/name fields, captain labels and separate staff rows. Results retain source links and supplied score/verdict semantics, add internal match navigation, and label capture time separately from match date. Source ordering and existing calculations/API contracts are unchanged.
- History request failure does not become “no results.” Successful empty history, partial data, stale retained history, and whole-page failure have distinct messages. Missing summary values render as dashes rather than a fabricated 0–0 record.
- Tables have visible overflow guidance, focusable named scroll regions, aligned numbers, and persistent opponent/player identity columns. The route's focus scroll margins account for the fixed ticker.

## Preview and data provenance

**Review URL:** <http://10.0.0.21:3100/team/controlled-populated>

The running preview uses the isolated production build at `/tmp/vlr-preview/team-final`. Source/build-input parity is recorded in [source-parity.json](verification/team-detail/2026-09-27/source-parity.json). No build ran against the production frontend's `.next` directory.

The review URL is **controlled acceptance data**, not live Sentinels performance. The preview-only Node fetch preloader intercepts only `/team/controlled-*` and `/trends/team/controlled-*` backend requests. It uses existing repository fixtures, changes the identity to `CONTROLLED`, and supplies deliberately varied rating samples to exercise the chart. Ordinary numeric team URLs continue to use the read-only adapter. The preloader is an evidence utility, not imported by application code or enabled by a normal production build.

Other review states: `controlled-partial`, `controlled-empty`, `controlled-history-error`, `controlled-error`, and `controlled-flat` under `/team/`.

At verification time Redis held **no `vlr:team:*` detail keys**. Therefore <http://10.0.0.21:3100/team/2> correctly showed the unavailable state. Banked rating history for team 2 was available through the read-only trend service. No scrape was triggered to fill the missing detail. The adapter now permits that existing SELECT-only trend service; cache refreshes, writes and schedulers remain disabled.

## Fresh checks

Full logs, command lines, UTC timestamps and exit statuses are saved under [verification/team-detail/2026-09-27](verification/team-detail/2026-09-27/).

| Check | Result |
| --- | --- |
| `npm test` | 295 tests passed in 21 files, including 8 focused team tests |
| `npm run lint` | Passed, exit 0 |
| `tsc --noEmit --incremental false` | Passed, exit 0 |
| `npm run build -- --webpack` in isolated copy | Passed, exit 0 |
| Chromium 1440×1000, 768×1024, 390×844, 320×844 | Passed layout, keyboard, independent overflow, ticker clearance and controlled state checks |
| Native Chromium 200% page zoom | Passed at 1440 and 768 outer widths (720 and 384 CSS-pixel viewports) |

The suite still emits the existing Vite CJS deprecation and React `act(...)` warnings; these are preserved in the test log. No new test outcome is inferred from older delivery reports.

Browser checks found no page-wide horizontal overflow at the four normal widths or the two zoomed widths. History disclosure works with Enter; Tab reaches its scroll region. Arrow keys scroll overflowing tables, all rightmost columns are reachable, focus has a visible outline, and the last result link and final table remain above the ticker. Exactly one fixed ticker appeared at every normal width. No page errors occurred in the populated viewport matrix. Supplied-image and broken-image fallbacks were exercised with controlled browser responses.

Visual inspection confirmed the large team identity, five-card desktop form row, two-column mobile form layout, legible chart context and table hierarchy. Mobile tables intentionally require horizontal scrolling; sticky identity columns retain the row context. The actual 200% zoom screenshot shows the disclosure focus ring and fixed ticker at their enlarged sizes.

## Selected screenshots

Every capture below is **controlled data**, with real shared shell/ticker content around the controlled team page. These are viewport captures, not stitched full-page images that could misrepresent the fixed ticker.

| Capture | Evidence |
| --- | --- |
| [Desktop overview](screenshots/team-broadcast/controlled-overview-1440.png) | Identity, summary and recent form at 1440px |
| [Mobile overview](screenshots/team-broadcast/controlled-overview-390.png) | Wrapped identity and shared mobile shell at 390px |
| [Rating history](screenshots/team-broadcast/controlled-history-1440.png) | Range/sample context, chart and expanded exact capture table |
| [320px roster](screenshots/team-broadcast/controlled-roster-320.png) | Narrow roster and overflow affordance |
| [390px results](screenshots/team-broadcast/controlled-results-390.png) | Horizontal scrolling, retained row identity, final focused source link and bottom clearance |
| [Partial history](screenshots/team-broadcast/controlled-partial-390.png) | No invented movement from one undated snapshot |
| [200% native zoom](screenshots/team-broadcast/controlled-zoom-200.png) | Visible keyboard focus, enlarged history and ticker |

Temporary iterations and redundant state screenshots were excluded. The reproducible browser scripts, controlled preloader and machine-readable observations accompany the report.

## Limits and operational evidence

- A populated **live/cached team detail** could not be inspected because the preview cache was empty. Controlled fixtures establish presentation and behavior, not data freshness or real team performance.
- The unchanged normalizers collapse missing nested arrays to empty arrays. A successful partial payload cannot always distinguish an omitted roster/results field from an explicitly empty list. The UI says “listed” or “matched” rather than claiming the team has no players or no history. Endpoint failures are distinguished.
- The existing team-detail date strings can be compact/ambiguous; they are preserved verbatim rather than assigned an invented timezone. Historical timestamps are capture times, not match times. Recent-form order follows the source and makes no inferred streak claim.
- Native 200% zoom was tested at 1440/768 browser widths; 390/320 were tested at 100%. This was Chromium verification, not a screen-reader session or cross-browser audit.
- Production health evidence is limited to API `/health` and frontend `/favicon.ico` HTTP 200 plus unchanged service identities: API PID 61821, active since September 17 11:10:09 UTC; frontend PID 308, active since September 3 04:02:56 UTC; both `NRestarts=0`. This supports no production restart during the work, not an exhaustive audit of every production route.
- The pre-existing `.gitignore` edit and untracked `docs/SHARED_NAV_HOMEPAGE_REDESIGN_PLAN.md` remain byte-for-byte unchanged and excluded from the commit.
