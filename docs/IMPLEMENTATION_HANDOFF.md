# VLR-API implementation handoff

Prepared September 26, 2026 from repository code and [PROJECT_REVIEW.md](PROJECT_REVIEW.md).
This is a source-based review, not a fresh production audit. Phase 1 below means
the review's reliability phase, followed by the homepage/navigation overhaul.

## Entry points and deployment

| Area | Entry point / method |
| --- | --- |
| Backend | [app/main.py](../app/main.py): `uvicorn app.main:app`; initializes database, mounts routers, optionally starts scheduler |
| Separate scheduler | [app/jobs/run.py](../app/jobs/run.py): `python -m app.jobs.run`; disable the API's scheduler when using this |
| Frontend | [layout.tsx](../frontend/src/app/layout.tsx): fonts and persistent ticker; [page.tsx](../frontend/src/app/page.tsx): homepage |
| Deployment | systemd: Uvicorn on 8000, production Next.js on 3000, local PostgreSQL/Redis. [DEPLOY.md](../DEPLOY.md), [service template](../deploy/vlr-api.service) |
| Operator commands | [start-services.sh](../start-services.sh): start/stop/status; `restart` builds and restarts both services; `build` builds and restarts frontend |

The frontend unit is documented as living outside the repository. Actual service
configuration, public exposure, and reverse proxy were **not verified**.

## Sources and storage

VLR.gg HTML/autocomplete supplies esports data; Twitch Helix supplies stream
status. Scrapers feed refresh services, which write Redis JSON payloads and
selected PostgreSQL history: match results and ranking/player/team snapshots.

FastAPI serves cached data; history/trends query PostgreSQL. **Cache misses can
scrape inline**, despite older documentation claiming otherwise. There is no
universal database fallback. Next.js fetches FastAPI server-side, normalizes
responses, and supplies pages/browser polling routes.

Relevant files: [scrapers/](../app/scrapers), [refresh.py](../app/services/refresh.py),
[cache.py](../app/core/cache.py), [models](../app/models/__init__.py),
[vlr.ts](../frontend/src/lib/vlr.ts), [twitch.ts](../frontend/src/lib/twitch.ts).

## Current routes

- **Website:** `/`, `/schedule`, `/results`, `/rankings`, `/stats`, `/news`,
  `/match/[id]`, `/team/[id]`, `/player/[id]`.
- **Backend `/api/v1`:** `/matches/{results,upcoming,live}`, `/rankings`, `/stats`,
  `/events`, `/news`, `/players`, `/teams`, `/players/{player_id}/dimensions`,
  `/player/{player_id}`, `/team/{team_id}`, `/match/{match_id}`,
  `/trends/{team,player}/{id}`, `/history/results`,
  `/history/{rankings,player,team}/{id}`, `/assistant/team-match`, `/status`.
- **Backend utility routes:** `/health`, HTML `/` and `/status`, FastAPI documentation.
- **Next.js `/api`:** match listings/detail, player search/detail, team detail,
  stats, rankings, news, team/player trends, ticker, streamers.

Sources: [backend routes](../app/api/v1/routes.py),
[frontend routes](../frontend/src/app). Brace groups above abbreviate related
routes; identifier parameter names vary by entity.

## Homepage and shared navigation

[page.tsx](../frontend/src/app/page.tsx) awaits six loaders and renders streamers
→ live → five upcoming/five results → rankings/news. Paired panels stack on
smaller screens.

[SiteHeader.tsx](../frontend/src/components/SiteHeader.tsx) contains the wordmark,
five navigation links, and [PlayerSearch.tsx](../frontend/src/components/PlayerSearch.tsx).
Its outer container wraps; its inner navigation row does not. Mobile overflow
remains unverified. Detail pages implement separate headers.

Reusable homepage pieces are in [components/](../frontend/src/components):
`MatchSection`, `MatchCard`, `LiveMatches`, `RankingsPanel`, `NewsPanel`,
`FeaturedStreamers`, `Panel`, badges and scores. Shared styling lives in
[globals.css](../frontend/src/app/globals.css); the root layout mounts `StatTicker`.

## Consumers and compatibility requirements

- **Verified consumer:** the included Next.js website, through its loaders and proxy routes.
- **Documented integration:** Command Central/Jarvis, targeted by
  [assistant.py](../app/services/assistant.py). Its external client and actual
  usage cannot be verified here.
- Other external API consumers are unknown.

Preserve these contracts:

- Backend listings/detail commonly return **bare arrays/objects**;
  stats/search/assistant use envelopes. Do not globally wrap existing responses
  without migration.
- Frontend `ApiResponse<T>` is `{ data: T[], stale: boolean, error?: string }`,
  including single-detail responses wrapped as arrays.
- Preserve raw backend score/stat strings, absolute URLs, and verbatim agent-stat
  keys. Frontend numeric normalization returns numbers or `null`, never `NaN`.
- Preserve assistant states `live | upcoming | completed | none`, route
  parameters, and existing status/error behavior unless explicitly changed.

Sources: [routes.py](../app/api/v1/routes.py),
[types/vlr.ts](../frontend/src/types/vlr.ts), [vlr.ts](../frontend/src/lib/vlr.ts).

## Phase 1: likely implementation files

These are proposed changes, not completed work.

| Work | Exact existing files likely to change |
| --- | --- |
| Cache retention/freshness: rankings expire after 1h and events after 30m, versus 6h refreshes | [config.py](../app/core/config.py), [cache.py](../app/core/cache.py), [scheduler.py](../app/jobs/scheduler.py), [refresh.py](../app/services/refresh.py), [routes.py](../app/api/v1/routes.py) |
| Preserve scores on error envelopes; prevent overlapping polls; display stale state | [LiveMatches.tsx](../frontend/src/components/LiveMatches.tsx), [MatchSection.tsx](../frontend/src/components/MatchSection.tsx) |
| Cancel/ignore outdated search responses | [PlayerSearch.tsx](../frontend/src/components/PlayerSearch.tsx), [player-search.test.ts](../frontend/src/components/player-search.test.ts) |
| Bound upstream requests | [vlr.ts](../frontend/src/lib/vlr.ts), [vlr.test.ts](../frontend/src/lib/vlr.test.ts) |
| Regression coverage | [test_live_refresh.py](../tests/test_live_refresh.py), [test_status.py](../tests/test_status.py); proposed new `tests/test_cache_freshness.py` and `frontend/src/components/live-matches.test.ts` |

The subsequent homepage/navigation delivery would principally touch `page.tsx`,
`layout.tsx`, `globals.css`, `SiteHeader.tsx`, homepage components, and
`frontend/src/app/landing.test.ts`. Final scope depends on whether navigation
becomes global.

## Verification commands

```bash
# Repository root
.venv/bin/pytest -q

# Frontend
cd frontend
npm test
npm run lint
npx tsc --noEmit
npm run build
```

Add browser checks for slow/out-of-order responses, stale scores, empty live
lists, mobile navigation, and keyboard search. Consult bundled Next.js
documentation before implementation, as required by
[AGENTS.md](../frontend/AGENTS.md).

The [review](PROJECT_REVIEW.md) records 207 backend and 202 frontend passing tests,
plus clean lint/types. **Tests, production build, and browser checks were not
rerun for this handoff.**
