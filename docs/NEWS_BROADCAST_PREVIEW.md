# News broadcast delivery and content inventory

> Historical news-slice evidence. The September 27 [site-wide predeployment audit](BROADCAST_PREDEPLOYMENT_AUDIT.md) supersedes the preview directory and check counts below, expands the rights inventory, and records remaining launch dependencies. The news implementation described here is unchanged.

This `v2` slice follows `d9e6c2da9ef8ba9bf2cdea4df9e47294494f0627`. It changes `/news`, adds focused regression tests, and records verification and the requested VLR-derived content inventory. No scraping, refresh, cache, API or homepage behavior was changed. No deployment or production restart was performed.

## News presentation

The first supplied story leads a typographic broadcast surface; all subsequent stories remain in source order in a numbered article list. Full supplied titles, parsed authors/dates and original URLs are preserved. No date sorting, editorial ranking, invented summaries, inferred breaking-news state or unsourced image is introduced. The new `/news` surface deliberately omits descriptions and directs readers to the original reporting.

Each story has one source anchor encompassing its headline and “Read original story” action. It opens the unchanged supplied URL in a new tab with an accessible announcement and `noopener noreferrer`. Missing title, byline, date or URL has an explicit fallback. The lead is identified as the first supplied item, not guaranteed current news. Capture time is unavailable. A failed feed is distinct from a successful empty list; retained stale rows have a warning. The shared shell and fixed bottom ticker are unchanged.

## Preview and fresh verification

[News preview](http://10.0.0.21:3100/news) serves the isolated optimized build at `/tmp/vlr-preview/news-final`, using the existing cache-only adapter on 8101. The source/public/config files were hash-compared with the working frontend. Port 3100 has no controlled-data preload. Production `.next` was not built or replaced.

The cache supplied 30 stories. All 30 had titles, descriptions, metadata and source URLs; descriptions ranged from 28 to 140 characters. The only supplied fields were `title`, `description`, `meta` and `url`; there were no image fields. [Inventory measurements and per-story source URLs](verification/news/2026-09-27/news-inventory.json) record the observation without duplicating story text. Cache availability does not establish freshness or permission.

| Check | Final result |
| --- | --- |
| `npm test` | 330 tests passed in 25 files, including seven new news regressions |
| `npm run lint` | Passed |
| `tsc --noEmit --incremental false` | Passed |
| Isolated `npm run build -- --webpack` | Passed |
| Chromium 1440×1000, 768×844, 390×844, 320×844 | Cached and controlled populated/partial data: eight cases passed |
| Controlled empty/error states | Two browser cases passed |
| Native Chromium 200% page zoom | Passed at 1440/768 outer widths, yielding 720/384 CSS pixels |

[Saved verification](verification/news/2026-09-27/) contains final logs with command timestamps/exit codes, browser scripts/results, fixture preload, source parity and production-health evidence. Existing Vite CJS deprecation and React `act(...)` warnings remain in the passing suite. Final visual review made the headline and read action one clickable/focusable source link; checks and screenshots were refreshed after that change.

The temporary loopback-only 3101 instance used the same build and synthetic long headlines, missing metadata/URL/title, and empty/HTTP-error responses. Its fixtures were labeled and never installed on 3100. Retained stale rows are tested at component level because the current loader's failed response has no retained rows. The controlled instance was stopped after inspection.

## Browser observations and selected screenshots

Long and unbroken headlines wrap without truncation or page-level horizontal overflow at all checked widths. Metadata wraps separately from titles. No news images, blank image frames or guessed thumbnails are rendered. Tab advances between source links, focus is visible, and the final article link and page footer scroll clear of the ticker. Exactly one fixed ticker appears; no page errors were observed in the normal-width matrix. Native 200% zoom retains readable hierarchy, focus and ticker clearance.

Screenshots are viewport captures with browser-added labels distinguishing cached from controlled data. Desktop 100% uses a fresh Chromium context at DPR 1. Mobile lead captures scroll to the story; the focus capture shows the end of the feed. No stitched full-page captures are included. These are QA evidence, not permission-cleared promotional assets.

| Capture | Purpose |
| --- | --- |
| [Cached desktop, 1440px / 100%](screenshots/news/cached-news-1440.png) | Masthead, lead story, source metadata and article-list hierarchy |
| [Cached mobile, 390px / 100%](screenshots/news/cached-news-390.png) | Lead and ordered list above the fixed ticker |
| [Cached mobile focus, 390px / 100%](screenshots/news/cached-news-focus-390.png) | Final source-link focus and ticker clearance |
| [Controlled long headline, 320px / 100%](screenshots/news/controlled-news-320.png) | Synthetic unbroken headline and missing fields; not real reporting |
| [Cached native 200% zoom](screenshots/news/cached-news-zoom-200.png) | 1440px outer width / 720 CSS-pixel viewport |

## VLR-derived news inventory

Scope: the committed frontend and its 3100 preview, inspected source paths and current read-only cache. Production was checked for health/process continuity, not crawled to establish its exact rendered release. This is a factual implementation inventory and a promotion handoff, not a finding that any reuse is licensed.

| Surface / files | Material displayed or retained | Source and handoff action |
| --- | --- | --- |
| `/news`: [route](../frontend/src/app/news/page.tsx), [NewsBoard](../frontend/src/components/NewsBoard.tsx) | All supplied titles, authors and dates; 30 cached rows observed. No descriptions, article bodies or news imagery. One lead plus the remaining rows, unchanged order. | [VLR news listing](https://www.vlr.gg/news), with each payload's article URL used directly. Keep those direct destinations and bylines; seek written clearance covering public headline aggregation/promotion rather than treating attribution as authorization. |
| Homepage `/`: [HomeNews](../frontend/src/components/HomeSections.tsx), [NewsPanel leadStory branch](../frontend/src/components/NewsPanel.tsx), [homepage styles](../frontend/src/app/globals.css) | First five supplied titles, dates and authors. The first story's complete supplied `description` is rendered; other four descriptions are not. No editorial photos or thumbnails. | Same listing and original story URLs. Recommend omitting the copied lead excerpt before public promotion, or limiting it to an expressly agreed excerpt scope. This design slice leaves homepage behavior unchanged. |
| Legacy `NewsPanel` non-lead branch / `NewsRow`, in the same component | Can render each supplied description with a two-line CSS clamp. The full string remains in markup; clamping is not content removal. This branch no longer renders the `/news` route, and the homepage uses the separate leadStory branch. | If reused elsewhere, omit or shorten descriptions under a documented permission policy. Do not describe a visual clamp as a rights safeguard. |
| [Frontend news API](../frontend/src/app/api/news/route.ts), [normalizer/loader](../frontend/src/lib/vlr.ts), [NewsArticle type](../frontend/src/types/vlr.ts) | `/api/news` still returns normalized titles, complete listing descriptions, parsed author/date and URL. `normalizeNews` separates bullet-delimited metadata and preserves unrecognized date text. No image field or article-body field exists. | Treat public API redistribution of excerpts separately from the new headline-only UI. Withhold promotion of the bulk excerpt feed until written permission covers that use. No API contract changed here. |
| [News scraper in events.py](../app/scrapers/events.py), [selectors](../app/scrapers/selectors.py), [refresh service](../app/services/refresh.py), [backend route](../app/api/v1/routes.py) | Fetches `/news` listing rows and caches title/description/meta/URL. Does not fetch full news article bodies or news image assets in this path. Production route can refresh on cache miss. | Origin is VLR's listing; relative article links become `https://www.vlr.gg/...`. Scraping behavior is unchanged. This review used cached data, not refresh calls. |
| [Frontend news fixture](../frontend/src/lib/__fixtures__/news.json), [backend HTML fixture](../tests/fixtures/news.html) | Existing source-derived title/excerpt/metadata examples retained for tests; HTML fixture identifies a July 14, 2026 capture. They are not new UI copy. | Original URLs are embedded in the files. Review redistribution scope before using fixtures as public examples; prefer the synthetic news fixtures supplied with this report for demos. These existing files are unchanged. |
| News screenshots in this report; existing [homepage QA captures](screenshots/broadcast/) | Raster captures can reproduce displayed headlines/bylines and, where the homepage news block is visible, its lead excerpt. They are screenshots of this frontend, not VLR article photographs. | Do not assume screenshots eliminate underlying reuse questions. Use clearly labeled synthetic-story captures for promotion pending written clearance for real-story assets. Existing homepage captures were not changed or re-audited individually here. |
| News imagery across the above UI/API/scraper paths | None supplied or rendered. Charcoal gradients, rules and typography are CSS. Shared-shell/game/team assets elsewhere are not news illustrations and are outside this news inventory. | Keep news photos, article screenshots and Open Graph thumbnails absent until their source and an appropriate written reuse license are established with VLR or the relevant rights holder. No unsourced artwork was added. |

### Permission and promotion handoff

VLR's [published terms](https://www.vlr.gg/terms), checked September 27, 2026 and labeled updated September 16, 2025, address content reuse in section 2 and automated/systematic retrieval in sections 3 and 5. They restrict systematic collection without written permission and identify `community@vlr.gg` for requests about uses beyond their stated grant. Attribution is a condition mentioned for authorized reuse, not a standalone grant of reuse rights. The README's commercial-scraping summary is narrower than those published provisions; non-commercial status alone should not be treated as clearance.

No written news-republication permission was found in the inspected repository documentation. [README](../README.md) and [LICENSE](../LICENSE) distinguish repository code licensing from third-party content rights. An agreement may exist outside this repository; its existence and scope remain unverified. No permission request was sent during this task.

Recommended before public promotion: obtain and record written scope for headline aggregation, excerpts, API redistribution, screenshots, images, promotional channels and attribution. Keep supplied titles/author/date intact and link directly to the original article where allowed. Omit or shorten copied descriptions to the agreed scope; no universal character count establishes permission. Until that scope is established, withhold real-story promotional captures, copied excerpts/bulk feeds and any proposed news imagery, and use the labeled controlled-data demo. These are handoff recommendations, not a claim that shortening or linking alone clears rights. The user-authorized repository commit/push is not itself evidence of VLR permission.

## Remaining gaps and operational evidence

- Publication metadata is preserved as supplied, not independently verified. Cache age/capture time is unavailable. Missing news images are handled by an intentional text-only design, not an image-loading fallback.
- The generic news loader normalizes non-array success payloads to an empty list; malformed-success detection remains outside this slice. HTTP failures and explicit stale/error envelopes are distinguished by the UI.
- Native 200% was checked at desktop/tablet outer widths; 390/320 were checked at 100%. No screen-reader or non-Chromium audit was performed.
- Production API `/health` and frontend `/favicon.ico` returned HTTP 200. API PID 61821 (active since September 17, 11:10:09 UTC) and frontend PID 308 (active since September 3, 04:02:56 UTC), both `NRestarts=0`, matched the initial baseline. This supports no production restart; it is not an exhaustive production-route audit.
- The unrelated `.gitignore` change and untracked `docs/SHARED_NAV_HOMEPAGE_REDESIGN_PLAN.md` remain byte-for-byte unchanged and are excluded from this commit.
