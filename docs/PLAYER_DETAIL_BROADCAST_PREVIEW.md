# Player detail broadcast delivery — 2026-09-27

Player-only redesign on `v2`, based on homepage `d71f389`, match `0fa35c4`, and team `85999ed`. No deployment or production restart. The separate preview frontend was restarted on port 3100 using an isolated production build.

## Implementation and interpretation

The page now reads identity/team/role availability and headline statistics → rating history → rating dimensions → agent statistics → match history. The shared shell and fixed desktop/mobile bottom ticker remain unchanged.

- Identity uses a text monogram. The existing player contract has **no portrait or role field**; the page says “Role unavailable” and does not guess a role from agent usage or construct an image URL. Team IDs retain internal links, with the supplied team URL used when no ID exists.
- Headline Rating, K/D and ACS retain the existing `playerOverall` calculations and rounding. Known positive round counts and row coverage are displayed, alongside the all-time source scope (`fetch_player` requests `?timespan=all`); the missing capture date is labeled. A keyboard-operated explanation describes rounds weighting, weight-1 fallback, metric-specific coverage, total-kills/total-deaths K/D and signature selection. `signatureAgent` is unchanged; the UI only names a main agent when the selected agent has a positive round sample. Recent form retains the first ten source matches, with visible W/L/unknown markers.
- Rating history displays the requested lookback, actual rated-capture range, rated/total capture counts, current/peak rating and ACS, and the API's deltas. One-point series do not claim change; flat or insufficiently dated series do not draw a line. The chart spaces points by capture time, identifies the non-zero y-axis range, and breaks at missing ratings. A native disclosure exposes capture time, rating, ACS and rounds. Overlapping snapshot rounds are explicitly not independent match samples.
- Dimensions retain the source cohort percentiles and ordinal calculation. Region and timespan are visible; unavailable cohort size and round sample are stated. Null scores remain unavailable, real zero scores remain zero, and a partial set does not produce a fabricated radar polygon. Low-confidence warnings are visible, not only tooltips. Lookup failure and confirmed NA/EU non-membership are distinct states.
- Agent statistics retain every raw upstream key/value, including `Rating`, `R`, `K:D`, and unknown added keys. Column order remains the ordered union of source keys; rows retain source order. No sort controls existed here, and no new ordering or calculation was introduced. Numeric cells are right-aligned with tabular figures. The agent column remains visible during horizontal scrolling.
- Match history retains supplied verdict/score semantics and original external URLs, and adds internal match links when IDs exist. Missing dates and coverage period are stated. Opponent identity remains visible during scrolling.
- Existing parallel loaders, API contracts, force-dynamic behavior and the navigable page-level failure remain intact. No backend or shared-shell source was changed.

## Preview and provenance

**Review URL:** <http://10.0.0.21:3100/player/controlled-populated>

This is **controlled acceptance data**, not current TenZ performance. A preview-only fetch preloader uses the committed player fixture and deliberately constructed trend/dimension responses for deterministic layout checks. It labels the player identity and trend source note as controlled. Only backend requests for player IDs beginning `controlled-` are intercepted; normal IDs still use the read-only preview adapter. The hook is not application code and is not enabled by a normal production build.

Other controlled states: `/player/controlled-partial`, `/player/controlled-empty`, `/player/controlled-history-error`, `/player/controlled-error`, and `/player/controlled-flat`.

Redis inspection found **no `vlr:player:*` detail entries**. The normal route <http://10.0.0.21:3100/player/9> showed the expected unavailable state. No production scrape was triggered to populate it. Consequently, a populated real cached player page could not be verified in this delivery.

The running build is `/tmp/vlr-preview/player-final`; all **120 source/build-input files** matched the working source in [source-parity.json](verification/player-detail/2026-09-27/source-parity.json). The production frontend's `.next` was not rebuilt.

## Fresh verification

Full commands, UTC timestamps, exit codes, logs and browser scripts are saved in [verification/player-detail/2026-09-27](verification/player-detail/2026-09-27/).

| Check | Verified result |
| --- | --- |
| `npm test` | 304 tests passed in 22 files; includes 9 new player tests and the existing player tests |
| `npm run lint` | Passed, exit 0 |
| `tsc --noEmit --incremental false` | Passed, exit 0 |
| `npm run build -- --webpack`, isolated copy | Passed, exit 0 |
| Chromium 1440×1000, 768×1024, 390×844, 320×844 at 100% | Passed layout, disclosure keyboard, numeric alignment, scrolling, focus and ticker-clearance assertions |
| Native Chromium 200% zoom | Passed at 1440 and 768 outer widths, yielding 720 and 384 CSS-pixel content widths |

The initial standalone TypeScript run caught an inferred union type in the new test fixture; its explicit `AgentStat[]` annotation corrected it. A final backend-source review also confirmed the all-time agent-stat scope, and that label was corrected before the final verification. The saved logs are the fresh final passing runs. Existing Vite CJS deprecation and React `act(...)` warnings remain visible in the suite log.

Browser observations:

- No document-level horizontal overflow at any checked width or zoom. Wide agent tables intentionally scroll inside their own region, including on desktop.
- Numeric cells were right-aligned. Arrow keys scrolled the named focusable regions; the far-right columns were reachable, with agent/opponent identities retained.
- Headline-method and rating-history disclosures opened with Enter; Tab reached the history table region. A visible 2px focus outline appeared at normal widths.
- The final match source link and final table remained above the ticker. Exactly one fixed ticker appeared across the normal-width matrix.
- No page errors occurred during the populated viewport matrix. Controlled partial, empty, secondary-error, whole-page-error and flat states passed.
- Visual inspection confirmed the large condensed identity, compact headline figures, mobile two-column headline grid, explicit chart context, visible dimension confidence note and aligned raw-stat rows.

## Selected screenshots

All captures below show **controlled player data** within the real shared shell/ticker. Each screenshot carries a browser-added evidence label identifying controlled data and zoom. This annotation is not part of the product UI. Viewport captures preserve the ticker's true fixed position; no stitched full-page images are included.

| Screenshot | What it establishes |
| --- | --- |
| [Desktop overview, 1440px, 100%](screenshots/player-broadcast/controlled-overview-1440.png) | Normal desktop scale, shared navigation, identity, headline statistics and form; fresh browser context, DPR 1 |
| [Mobile overview, 390px, 100%](screenshots/player-broadcast/controlled-overview-390.png) | Identity and compact headline layout, scrolled to the player header |
| [Rating history, 1440px, 100%](screenshots/player-broadcast/controlled-history-1440.png) | Sample/range context, chart and disclosure |
| [Dimensions and agent stats, 1440px, 100%](screenshots/player-broadcast/controlled-dimensions-1440.png) | Percentile hierarchy, sample limitation and raw numeric table |
| [Agent table, 320px, 100%](screenshots/player-broadcast/controlled-agents-320.png) | Narrow-width identity column, sample columns and overflow guidance |
| [Match history, 390px, 100%](screenshots/player-broadcast/controlled-matches-390.png) | Scrolled table, retained opponent identity, focused final source link and ticker clearance |
| [Partial history, 390px, 100%](screenshots/player-broadcast/controlled-partial-390.png) | Sparse history without a fabricated line or delta |
| [Native 200% zoom](screenshots/player-broadcast/controlled-zoom-200.png) | Enlarged disclosure focus, history and fixed ticker at a 1440px outer browser width |

Unlabeled intermediate captures were overwritten and excluded. Native zoom used Chromium's page-zoom setting, not CSS zoom or pinch emulation.

## Remaining gaps and operational evidence

- Populated real cached player data was unavailable. Controlled evidence validates presentation/behavior, not data freshness or actual player performance. Player trend/dimension paths for ordinary IDs are also outside the current cache-only adapter's supported routes; the controlled hook exercises their UI contracts without invoking production refresh behavior.
- No portrait, role, exact agent-stat date boundaries/capture date, match dates or dimension cohort sample counts are supplied by the current contract. These remain explicitly unavailable; no new data or inferred role was introduced.
- Normalizers still collapse omitted nested arrays to empty arrays. A successful partial detail payload cannot distinguish omitted agent/match lists from explicitly empty lists; messages describe what is supplied/listed. Endpoint failures remain distinct.
- The aggregate helper intentionally reads `Rating` rather than aliasing a raw `R` key. Such rows remain visible verbatim in the table and may leave the headline rating unavailable. This existing calculation was preserved.
- Native 200% zoom was checked at 1440/768 outer widths; 390/320 were checked at 100%. No screen-reader session or non-Chromium browser audit was performed.
- Production API `/health` and frontend `/favicon.ico` returned HTTP 200. API PID 61821 (active since September 17 11:10:09 UTC), frontend PID 308 (active since September 3 04:02:56 UTC), and both `NRestarts=0` remained unchanged. This supports no production restart during this work; it is not an exhaustive audit of every production route.
- The pre-existing `.gitignore` change and untracked `docs/SHARED_NAV_HOMEPAGE_REDESIGN_PLAN.md` are byte-for-byte preserved and excluded from the player commit.
