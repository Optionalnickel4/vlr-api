# Broadcast match-detail delivery

Match-detail slice on `v2`, based on the committed broadcast homepage `d71f3891adc656c75d81309651026bbc1c18c4a4`. Verified September 27, 2026. This report accompanies the delivery commit; resolve it with `git log -1 --format=%H -- docs/MATCH_DETAIL_BROADCAST_PREVIEW.md`.

Read before implementation: `frontend/AGENTS.md`, local Next.js CSS/client-component guidance, the match route and components, existing match/header/hydration/polling tests, `docs/screenshots/match-detail.png`, and `docs/PROJECT_REVIEW.md`.

## Delivered behavior

- The match page adopts the homepage's charcoal surfaces, red top rule, ivory actions, condensed headings, teal section accents, and tabular scores. Styles live in the match route's `match.css`, using match-specific selectors. The homepage and fixed ticker implementation are unchanged.
- A large team-versus-team header shows identities and team links, event/stage, format, explicit state, veto, and the original external VLR link. Final scores are labeled **Series score / Maps won**. Existing live-map scorebug behavior is retained when the series is still 0:0, with a separate, clearly labeled series score below it. Unknown scores remain dashes.
- `TeamCrest` uses supplied URLs and falls back to initials for missing, invalid, or failed images. Match normalization conditionally retains an optional supplied `logo`; absent-logo payloads retain their existing shape. Current real match feeds do not supply crests. No guessed logo paths or extra team fetches were added.
- Map cards show map number/name, round scores, pick/decider markers, and All Maps totals. A labeled selected-map summary identifies score order by team. Proper tab/panel associations, roving focus, ArrowLeft/ArrowRight and Home/End navigation were added. Selected map identity survives score refreshes; disappearing selections fall back safely.
- Round history has numbered columns, explicit W/L/unavailable text as well as color, horizontal keyboard/touch access, and an expandable textual record of winner, side, outcome, and cumulative score. No round results are fabricated.
- Team scoreboards retain all 11 existing statistical columns, numeric/percentage formatting, null dashes, zero values, agent names, player links, and upstream player order. The previous scoreboard had no interactive sorting; no sort order was introduced or changed. Team names in aggregate data fall back to the supplied series team names.
- Numeric columns align right; player identity stays visible in a sticky first column while the table scrolls horizontally. Tables and round strips have named, keyboard-focusable scroll regions. Empty player/map/round data is explained explicitly.
- Existing API paths, envelope, existing response fields, live polling, stop-on-final behavior, SSR/hydration, metadata, breadcrumbs, and page-level unavailable/return-link behavior remain. Backend code and API route handlers were not changed. Fixed ticker placement and safe-area/page clearance are retained.

## Verification on final source

All four checks completed with exit code **0**, from **11:18:59 to 11:19:31 UTC**. Logs include commands, directories, timestamps, and exit codes; terminal color escapes were removed from the checked-in text copies.

| Check | Result | Evidence |
|---|---|---|
| `npm test` in `frontend/` | **287 tests across 20 files passed**, 25.46s Vitest duration | [Tests](verification/match-detail/2026-09-27/tests.txt) |
| `npm run lint` | Passed, no diagnostics | [Lint](verification/match-detail/2026-09-27/lint.txt) |
| `./node_modules/.bin/tsc --noEmit --incremental false` | Passed, no diagnostics | [TypeScript](verification/match-detail/2026-09-27/typescript.txt) |
| `npm run build -- --webpack` in `/tmp/vlr-preview/match-final` | Passed compilation, TypeScript, static generation, optimization and traces | [Build](verification/match-detail/2026-09-27/build.txt) |

[Command results](verification/match-detail/2026-09-27/check-results.json) are included. Twelve new tests in `match-broadcast.test.ts` cover final/live/upcoming/unknown states, live versus series scores, optional and failed crests, absent data, map/aggregate keyboard selection, refresh/removal behavior, preserved scoreboard columns/order/links/formatting, empty players, and textual round results. Existing match hydration and polling regressions continue to pass. Existing Vite CJS deprecation and React `act` warnings remain visible in the passing test log. `git diff --check` passed.

## Chromium observations

[Final browser results](verification/match-detail/2026-09-27/browser-results.json) cover **1440×1000, 768×1024, 390×844, and 320×844**:

- Document width equals viewport width; the page does not scroll horizontally. Tables and the round strip scroll inside their own regions. Keyboard horizontal scrolling works, the player-name column stays fixed, and the final numeric column is reachable at every width.
- Map selection with arrows/Home/End and Tab into the panel works. Focus outlines are visible. The round-detail disclosure opens with Enter.
- Exactly one fixed ticker is present. The final scoreboard and the last focused player link clear the ticker at each tested width. Tables intentionally require horizontal scrolling on smaller screens; no columns are removed.
- Controlled final, live, upcoming, missing-match, and supplied/broken-crest cases passed. A failed live update retained the displayed match and selected map; a successful update preserved selection; a final response stopped polling.
- No page errors were recorded during the four viewport interaction runs. The existing cache-backed route was also inspected and captured.

[Native 200% Chromium page-zoom results](verification/match-detail/2026-09-27/zoom-results.json) cover browser windows **1440px and 768px** wide, producing **720px and 384px CSS layout widths**. Zoom was set through Chromium's actual page-zoom setting, not CSS zoom or pinch emulation. Page width, map keyboard navigation, table keyboard scrolling, focused-link visibility, and bottom clearance passed with no recorded page errors. The 390/320px matrix above was checked at normal zoom, not as a physical mobile browser pinch-zoom test.

Browser review found and fixed a tablet-width overflow caused by absolutely positioned screen-reader-only labels escaping the round strip's clipping context. It also caught and corrected a wrapped secondary series score on mobile. Final browser runs used the built source with those fixes, without injected CSS overrides.

Temporary tooling is under `/tmp/vlr-browser-tools`. Full Chromium's extra CUPS/Avahi shared libraries were downloaded and unpacked under that temporary sysroot; no system packages were installed and no repository dependencies were added. Acceptance scripts/raw browser logs are under `/tmp/vlr-match-delivery/`. A loopback-only server on 3101 intercepted server-side requests for `controlled-*` match IDs with existing repository fixtures. That server was stopped after acceptance; production and the real preview never served those fixtures.

## Selected screenshots

These are viewport captures, not full-page composites. Only the following eight final-build captures are included; drafts and redundant captures remain outside the repository.

| Capture | What it shows |
|---|---|
| [Real cached match, 1440px](screenshots/match-broadcast/cached-match-1440.png) | LOUD–EDward Gaming, including honest dashes where the current detail payload lacks series scores |
| [CONTROLLED final header, 1440px](screenshots/match-broadcast/controlled-header-1440.png) | Complete series score, winner identity, event/stage and veto from a repository fixture |
| [CONTROLLED final header, 390px](screenshots/match-broadcast/controlled-header-390.png) | Scrolled mobile view of the header and fixed ticker |
| [CONTROLLED maps and rounds, 1440px](screenshots/match-broadcast/controlled-maps-1440.png) | Map selection, scores, pick/decider markers, round matrix, and scoreboard hierarchy |
| [CONTROLLED table scrolled right, 320px](screenshots/match-broadcast/controlled-table-scroll-320.png) | Sticky player identities and reachable final numeric columns within a narrow viewport |
| [CONTROLLED bottom clearance, 390px](screenshots/match-broadcast/controlled-bottom-390.png) | Last scoreboard and focused player link above the fixed ticker |
| [CONTROLLED live header, 390px](screenshots/match-broadcast/controlled-live-390.png) | Live map score and separate series score using the partial-live fixture |
| [CONTROLLED native 200% zoom](screenshots/match-broadcast/controlled-zoom-200.png) | Enlarged scoreboard and fixed ticker in a 1440px browser window |

**Controlled** captures contain repository test match data, not current coverage. Their match events are explicitly prefixed `CONTROLLED ACCEPTANCE`; the persistent ticker can still contain real preview cache data. Real cached captures document what the preview supplied at capture time, not independent verification of upstream sports results.

## Preview and production isolation

Preview: **http://10.0.0.21:3100/match/753450**. Match availability depends on the preview cache; other cached match IDs use the same route.

- Preview PID **129299**, directory `/tmp/vlr-preview/match-final`; `/tmp/vlr-preview/current` points there. Only preview/acceptance processes were restarted during iteration.
- The isolated build excluded `.env*`, `.next`, `node_modules`, and incremental TypeScript artifacts; its dependencies link to the existing installation. Build and preview use the read-only adapter on `127.0.0.1:8101`, with Twitch disabled. Production's `.next` was not rebuilt.
- [Runtime evidence](verification/match-detail/2026-09-27/runtime-results.json) confirms **114 source/assets/configuration files** match the final preview byte-for-byte. [SHA-256 input manifest](verification/match-detail/2026-09-27/source-sha256.json) is included.
- At **11:21:14 UTC**, the preview match route returned HTTP 200, production API `/health` returned HTTP 200 with `{"status":"ok"}`, and production frontend `/favicon.ico` returned HTTP 200.
- Production service state exactly matched the pre-work snapshot: API PID **61821**, active since **2026-09-17 11:10:09 UTC**; frontend PID **308**, active since **2026-09-03 04:02:56 UTC**; both `NRestarts=0`. **No production restart or deployment was performed.** These probes are not a complete production end-to-end test.
- The unrelated `.gitignore` change and untracked saved redesign plan are byte-for-byte unchanged and excluded from this delivery.

## Remaining gaps

Physical iOS/Android, Safari/Firefox, manual screen-reader use, and native mobile pinch zoom were not tested. Modern CSS `:has()` remains a dependency of the existing shared ticker. Cached match details can have absent series scores, crests, or statistics; these are shown honestly and were not repaired by changing upstream contracts or inferring results. The preview is temporary, cache-only infrastructure and can show unavailable data after expiry. No backend, team/player detail, or shared ticker redesign is included in this slice.
