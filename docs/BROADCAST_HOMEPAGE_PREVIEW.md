# Broadcast homepage delivery

Broadcast visual pass on `v2`, based on `071c627a898721aa39380c91e946366685bce333`. Final verification: September 27, 2026, 10:54–10:56 UTC. This report accompanies the delivery commit; no deployment or production restart was performed. Resolve the containing commit with `git log -1 --format=%H -- docs/BROADCAST_HOMEPAGE_PREVIEW.md`.

**Owner decision, September 27:** the ticker stays fixed at the viewport bottom on both desktop and mobile. This supersedes the earlier in-page mobile ticker proposal. The local `SHARED_NAV_HOMEPAGE_REDESIGN_PLAN.md` was corrected accordingly. That plan was entirely untracked and also contains earlier shared-shell planning, so no isolated correction against HEAD was possible; it remains outside this commit. The pre-existing `.gitignore` change is preserved and excluded.

## Preview and isolation

**http://10.0.0.21:3100/** — private-interface binding, running Next.js production build in `/tmp/vlr-preview/pass4`, also targeted by `/tmp/vlr-preview/current`. Preview PID: **121609**. This is a temporary preview, not a boot-persistent service.

```sh
python3 /tmp/vlr-preview/manage.py status
tail -n 60 /tmp/vlr-preview/preview.log
```

The preview uses a read-only adapter on `127.0.0.1:8101`, PID **117463**. It performs Redis GETs and read-only database search without upstream scraping, scheduler activity, migrations, cache flushes, or refresh commands. Cache misses remain unavailable until normal production data flow replenishes them. Twitch is disabled in this preview. Upcoming countdowns are upstream display strings, not a client-side clock.

The final build was created separately in `/tmp/vlr-broadcast-delivery-20260927/build`; `.env*`, `.next`, `node_modules`, and TypeScript incremental artifacts were excluded from the source copy. Its `node_modules` links to the existing installation. Build environment selected the preview adapter and blank Twitch settings. Production's `.next` was not rebuilt. The existing 3100 process was neither replaced nor restarted.

[Runtime evidence](verification/broadcast/2026-09-27/runtime-results.json) confirms all **112 source, public asset, and build configuration/package files** match byte-for-byte across the working tree, running preview directory, and fresh build directory. [SHA-256 manifest](verification/broadcast/2026-09-27/source-sha256.json) identifies those inputs.

## Implementation and review

The full working-tree visual diff and new implementation/tests were reviewed before staging. No blocking implementation issue was identified. Backend code, API routes/response bodies, search behavior, and detail-page content are unchanged; the shared ticker, crest component, and global canvas styling also affect other routes.

- `frontend/src/app/page.tsx` and `globals.css`: broadcast masthead, full-width featured match, responsive fixture/result/news layout, regional leaders and stats destination, dark canvas correction, and ticker clearance.
- `BroadcastMatch.tsx`: actual scores or scheduled timing, team initials, event/series context, and explicit match destination. Missing information remains visibly unavailable.
- `HomeSections.tsx` and `LiveMatches.tsx`: independently streamed sections remain intact. Failed live updates retain scores and a stale notice. Cold live failure shows an unavailable state. Only confirmed empty live data activates the next-match fallback. The shared upcoming promise feeds both hero and snapshot; CSS hides the featured duplicate, preserving up to five upcoming fixtures across both areas.
- `NewsPanel.tsx` and `RankingsPanel.tsx`: ivory lead-story treatment and regional leader cards using existing data. Full-page variants remain available. The red stats panel links to existing analytics without invented editorial analysis.
- `TeamCrest.tsx`: supplied image URLs with initials fallback on missing/broken images. Match lists still supply names only; no additional crest-fetch fan-out.
- `StatTicker.tsx` and `TickerTape.tsx`: one persistent ticker owner with one serial polling loop, abort cleanup, a 15-second cycle deadline, five-minute static refreshes, and live cycles 30 seconds after settlement. Failed reads retain the last tape. Desktop and mobile use a fixed bottom ticker with pause/resume, horizontal access, reduced motion, an assistive-technology-hidden duplicate, safe-area padding, and content clearance. Empty tape links to results.
- `broadcast.test.ts`: six focused regressions covering ticker non-overlap/cleanup, retained tape, pause semantics, image fallback, stale scores, and unavailable coverage.

## Fresh verification

All four commands below completed with **exit code 0** on September 27, beginning at 10:54:02 UTC. Logs include command, working directory, UTC timestamps, and exit status. Checked-in text logs remove terminal color escapes only.

| Check | Result | Fresh log |
|---|---|---|
| `npm test` in `frontend/` | **275 tests passed across 19 files**, including six broadcast tests; Vitest duration 23.46s | [Tests](verification/broadcast/2026-09-27/tests.txt) |
| `npm run lint` in `frontend/` | Passed, no diagnostics | [Lint](verification/broadcast/2026-09-27/lint.txt) |
| `./node_modules/.bin/tsc --noEmit --incremental false` in `frontend/` | Passed, no diagnostics | [TypeScript](verification/broadcast/2026-09-27/typescript.txt) |
| `npm run build -- --webpack` in the isolated build directory | Passed: compilation, TypeScript, static generation, optimization, and build traces completed | [Build](verification/broadcast/2026-09-27/build.txt) |

[Machine-readable command results](verification/broadcast/2026-09-27/check-results.json) are included. Existing Vite CJS deprecation and older React test `act` warnings remain in the passing test log. These fresh results supersede the earlier handoff's lint/TypeScript/build claims, whose standalone logs were unavailable. Whitespace validation with `git diff --check` also passed.

## Browser evidence

Fresh Chromium checks used the existing temporary Playwright/Chromium installation under `/tmp/vlr-browser-tools`; no repository dependencies or system packages were installed. Scripts and raw browser logs for this run are in `/tmp/vlr-broadcast-delivery-20260927/`.

[Real cached-data results](verification/broadcast/2026-09-27/browser-results.json), captured at 10:54:59 UTC:

- **1440×1000, 768×1024, 390×844, and 320×844:** document width equals viewport width, no main-content overflow detected, exactly one ticker fixed flush to the viewport bottom, and no page errors captured.
- Ticker height/content clearance: **64/84px** at 1440 and 768px; **92/112px** at 390 and 320px. Last page content clears the ticker at every tested width.
- Cached content showed 100 Thieves–T1 at 1:0 with live ticker data. Screenshots are snapshots of preview cache contents, not independent validation of upstream sports data.

[Fresh controlled acceptance results](verification/broadcast/2026-09-27/acceptance-results.json):

- At 1440, 390, and 320px: skip link, Tab access to search, visible focus, ArrowDown/ArrowUp selection, Enter destination, Escape dismissal, clearing, and dropdown bounds passed. No page errors recorded in those search runs.
- Browser-only live fixture → HTTP failure retained the 3:2 score and stale notice → successful empty response displayed the upcoming fallback without a visible duplicate → a subsequent live response restored scores.
- Keyboard ticker pause and reduced-motion checks passed. Search results, navigation destinations, live poll responses, and ticker fixtures were intercepted only inside the test browser.

**Earlier evidence, not rerun in this delivery:** [preserved streaming results](verification/broadcast/2026-09-27/prior-streaming-results.json) from the 04:28 UTC acceptance run record match visibility in 359ms while news/rankings were delayed 6.5 seconds and Twitch responses 9 seconds. The available `/tmp/vlr-preview/slow-sections.cjs`, `delay-fetch.cjs`, and `acceptance-server.log` corroborate the setup, including interception of external Twitch requests. That loopback 3101 acceptance process is stopped. This historical result is not presented as a fresh timing measurement.

## Selected screenshots

Only five fresh viewport captures are included. Full-page composites, duplicate widths, and superseded captures were excluded; earlier images are preserved locally under `/tmp/vlr-broadcast-delivery-20260927/prior-screenshots/`.

| Screenshot | Data and purpose |
|---|---|
| [Desktop, 1440px](screenshots/broadcast/cached-viewport-1440.png) | Real cached preview data: masthead, live stage, section hierarchy, fixed populated ticker |
| [Mobile, 390px](screenshots/broadcast/cached-viewport-390.png) | Real cached preview data: responsive header, match stage, and fixed mobile ticker; further content is reached by scrolling |
| [Mobile bottom, 390px](screenshots/broadcast/cached-bottom-390.png) | Real cached preview data: rankings/stats area and final content clearance above the ticker |
| [CONTROLLED search, 390px](screenshots/broadcast/search-controlled-390.png) | Browser test results “Test One/Two”; verifies focused search and contained dropdown. Other page content uses the preview cache. |
| [CONTROLLED stale score, 390px](screenshots/broadcast/stale-controlled-390.png) | Fabricated browser-only “Test Alpha/Beta” 3:2 response and controlled ticker fixture after an HTTP failure; demonstrates retained scores and stale messaging, not real match coverage. |

## Production health and remaining gaps

At 10:55:53 UTC, preview `/` returned HTTP 200, production API `/health` returned HTTP 200 with `{"status":"ok"}`, and production frontend `/favicon.ico` returned HTTP 200. Both production services remained active:

- API PID **61821**, activation/start **2026-09-17 11:10:09 UTC**, `NRestarts=0`.
- Frontend PID **308**, activation/start **2026-09-03 04:02:56 UTC**, `NRestarts=0`.

Those unchanged PIDs and original start times support that production was not restarted during the redesign or final verification. No deployment command was run. Health checks are limited probes, not a full production end-to-end test.

Remaining gaps: physical iOS/Android, Safari/Firefox, manual screen-reader testing, 200% zoom, and a complete browser route matrix. Modern CSS `:has()` remains a browser dependency. Rankings cache-header propagation remains a separate reliability follow-up. Preview cache gaps can legitimately show unavailable live/rankings/ticker states; Twitch content cannot be reviewed here. The isolated preview and temporary tooling/log paths are not persistent deployment infrastructure. No detail-page redesign was performed.
