# Phase 1 backend cache freshness and retention handoff

Updated September 26, 2026. Scope: rankings and events only, on branch `v2`.

## Outcome

Rankings and events now keep their last successful payload independently of the
freshness TTL. Request-triggered and scheduled refreshes share a Redis lease per
dataset. All retained-data responses are sent before refresh work, including the
request whose background task wins the lease. Failed refreshes preserve retained
data; genuinely cold failures return an explicit HTTP 503. Successful response
bodies remain bare lists with their existing fields and values. Additive response
headers identify fresh versus stale payloads.

Implemented and tested locally. **No deployment, production restart, production
Redis operation, live VLR request, or database migration occurred.**
This stops at the requested backend slice; frontend polling/search/design work
is not included.

## Branch safety and follow-up finding

The follow-up began on `master` at `9f4b8cbf22a38bed15163dc353634ad241dbd9ea`.
`git status`, local branches, remote-tracking branches, and `git ls-remote --heads
origin v2` were inspected first. Neither local nor remote `v2` existed, so `v2`
was created from that base with all existing working-tree changes preserved.
No history was discarded, merged, reset, or force-pushed.

Review confirmed the first uncommitted version's limitation: `_retained_or_refresh`
awaited `refresher()` before checking retained data. The stale owner could therefore
block its response for the 120-second scrape timeout, plus a subsequent ranking
DB write. The new regression test failed on that version because no response
body was sent while the simulated upstream was blocked.

The follow-up fixes that ordering using FastAPI's `BackgroundTasks`. It adds no
untracked `asyncio.create_task` jobs, new scheduler, or in-memory coordination
protocol. The existing Redis lease remains the cross-process authority.

## Instructions and baseline

- Read `docs/PROJECT_REVIEW.md`, backend cache/configuration, refresh services,
  scheduler, routes, HTTP client, scrapers, and relevant existing tests before
  editing implementation code.
- No `AGENTS.md` was found at the repository root, its checked parent locations,
  or within the backend/test/documentation paths. The repository's only discovered
  `AGENTS.md` is frontend-specific; no frontend files were changed.
- Read root `CLAUDE.md`; followed its test-first workflow and kept VLR selectors,
  upstream throttling, and response normalization unchanged.
- Tests mock the scraper and database boundaries. New Redis tests use a separate
  temporary Redis process over a private Unix socket, with TCP and persistence
  disabled. They never use the application's configured Redis connection.

## Trace: keys, freshness, and refresh paths

| Existing Redis key | Default TTL | Refresh path / cadence | This slice |
| --- | --- | --- | --- |
| `vlr:rankings:{region}` | 3,600 seconds | `refresh_rankings(region)`; scheduler refreshes `all` every 6h; other regions refresh on request | Original key remains freshness-limited; retained copy and shared lease added |
| `vlr:events` | 1,800 seconds | `refresh_events()` every 6h and on request | Original key remains freshness-limited; retained copy and shared lease added |
| `vlr:results` | 600 seconds | Results job every 10m and request miss | Unchanged |
| `vlr:upcoming` | 600 seconds (`ttl_results`) | Upcoming job every 60s and request miss | Unchanged |
| `vlr:live` | 30 seconds | Upcoming scrape populates it; live-detail job can rewarm it every 30s | Unchanged |
| `vlr:news` | 900 seconds | News job every 15m and request miss | Unchanged |
| `vlr:match:{id}` | 30 seconds live; otherwise 600 | On demand; live-detail job every 30s | Unchanged |
| `vlr:player:{id}`, `vlr:team:{id}` | 3,600 seconds | On demand; player prefetch also runs twice daily | Unchanged |
| `vlr:stats:{region}:{timespan}` | 21,600 seconds | Six-hour job and request miss | Unchanged |
| `vlr:lastrun:{job}` | No expiry | Successful scheduler job wrapper | Shape and writing mechanism unchanged |

Sources: [config](../app/core/config.py), [refresh](../app/services/refresh.py),
[scheduler](../app/jobs/scheduler.py), [routes](../app/api/v1/routes.py).

Before this change, `cache_set` stored only the original JSON payload with its
expiry. `_cached_or_refresh` awaited a refresh after a miss, then reread Redis.
Exceptions propagated; a refresher returning without a payload could become
`[]`. Rankings expired five hours before their scheduled refresh; events expired
5.5 hours before theirs. Concurrent misses independently scraped. The HTTP
throttle spaced upstream requests but did not coalesce them. Rankings also
banked a PostgreSQL snapshot after publishing cache data; events have no DB
history fallback.

## New cache protocol

For each affected existing key `K`:

| Key | Contents | Expiration |
| --- | --- | --- |
| `K` | Unchanged bare JSON list | Existing configured freshness TTL |
| `K:retained` | Same last-successful JSON list | None; overwritten only on successful publication |
| `K:refresh` | Unique owner token, or literal `failed` during backoff | 125-second lease; 30-second failure backoff |

Examples: `vlr:events:retained`, `vlr:events:refresh`,
`vlr:rankings:europe:retained`, `vlr:rankings:europe:refresh`.

Retention is intentionally independent of freshness and does not renew on reads
or failed scrapes. There is no new setting, payload wrapper, frontend body contract,
or database table. The number of retained datasets is bounded by the rankings
region allow-list plus events.

### Read/refresh behavior

| Condition | Before | After |
| --- | --- | --- |
| Fresh original key | Return cached list | Same; service-level callers also skip unnecessary scraping |
| Expired original key, retained payload, upstream healthy | Each miss can scrape before responding | Send retained data first; one post-response lease owner scrapes and atomically publishes both copies |
| Expired key, retained payload, upstream fails | Request errors after old data was deleted | Return retained list, HTTP 200; freshness key stays absent |
| Concurrent callers with retained data | Repeated queued scrapes | All responses send retained data first; their background callbacks share the Redis lease |
| Cold cache, upstream healthy | Concurrent requests can duplicate scrapes | Followers wait for the shared publication; one scrape |
| Cold cache, upstream fails or publishes nothing | Usually 500; missing publication could look like `[]` | HTTP 503 with `{"detail":"Data temporarily unavailable"}` |
| Actual successful empty list | Return `[]` | Return and retain `[]`; not confused with cache absence |
| Repeated requests after refresh failure | Can repeatedly scrape | Shared 30-second retry backoff; stale data or explicit 503 |

The route reads the fresh key, then the retained key. A fresh hit returns directly.
A retained hit returns the retained list with `X-VLR-Cache: stale` and attaches an
async refresh callback. Starlette sends the response start and complete body
before awaiting that callback; both success and failure are regression-tested at
the ASGI send boundary. Callback exceptions are handled and cannot alter the
already-sent response. The server owns this work through the request lifecycle.

Only a truly cold request awaits refresh inline. The scrape owner has a 120-second
async operation timeout. Cold followers poll Redis every 50ms with the same maximum
wait, but never take over that attempt. Service functions remain awaitable for
scheduler use. No response with available retained data waits for upstream work.

`SET NX EX` elects the owner across processes using the same Redis. Lua publication
checks the owner token, writes the fresh and retained payloads, and releases the
lease atomically. An expired owner cannot overwrite a newer owner's publication.
Failure/cancellation installs backoff only if the caller still owns the lease;
crashed processes recover through lease expiry.

Both scheduler and routes use the same service functions. Only a rankings caller
that actually scraped writes a history snapshot. Cache publication still precedes
the DB write, so a DB failure does not erase successfully scraped data. Cadences
and scheduler job names are unchanged. A scheduler run that finds already-fresh
data can complete without adding a duplicate snapshot; its heartbeat records
job completion, not necessarily a new scrape.

## Files changed and concise diff summary

| File | Change |
| --- | --- |
| [app/core/cache.py](../app/core/cache.py) | Add retained-refresh helper, bounded Redis lease, retry backoff, ownership-checked atomic publication, and explicit refresh exception; clarify cache documentation |
| [app/services/refresh.py](../app/services/refresh.py) | Route rankings/events through retained refresh; only the scraping rankings owner banks history |
| [app/api/v1/routes.py](../app/api/v1/routes.py) | Return retained data before post-response refresh; add safe background wrapper and freshness headers; keep bare-list bodies and explicit cold-cache 503 |
| [app/core/config.py](../app/core/config.py) | Documentation only: rankings/events TTLs now govern freshness, not retention; values unchanged |
| [app/jobs/scheduler.py](../app/jobs/scheduler.py) | Documentation only: explain retained datasets and shared refresh coordination; cadence unchanged |
| [tests/test_cache_freshness.py](../tests/test_cache_freshness.py) | Add 34 focused cases using private Redis, mocked scrapers/DB, ASGI response timing, and a separate scheduler process |
| [docs/PHASE1_CACHE_HANDOFF.md](PHASE1_CACHE_HANDOFF.md) | This report |
| [docs/PROJECT_REVIEW.md](PROJECT_REVIEW.md), [docs/IMPLEMENTATION_HANDOFF.md](IMPLEMENTATION_HANDOFF.md) | Include the previously prepared review and implementation plan as historical context; this report supersedes their cache-behavior descriptions |

The existing `.gitignore` modification is unrelated and remains uncommitted.
The two earlier handoff documents are included without rewriting their contents.

## Test commands and results

1. Test-first run:

   ```bash
   .venv/bin/pytest -q tests/test_cache_freshness.py -x
   ```

   Initial sandbox execution could not open the temporary Unix socket. Repeated
   with approved sandbox escalation: **1 failed, 2 passed**, demonstrating that
   the old implementation did not create a retained copy.

2. Follow-up test-first run:

   ```bash
   .venv/bin/pytest -q tests/test_cache_freshness.py -k stale_owner_sends -x
   ```

   **1 failed, 28 deselected** before the follow-up implementation: the blocked
   stale owner had not sent its response body. The same tests now pass for both
   events and rankings, on success and failure.

3. Final focused backend run:

   ```bash
   .venv/bin/pytest -q tests/test_cache_freshness.py tests/test_rankings_region.py tests/test_status.py tests/test_live_refresh.py
   ```

   **51 passed, 1 warning**, 3.49 seconds.

4. Full backend suite:

   ```bash
   .venv/bin/pytest -q
   ```

   **241 passed, 1 warning**, 4.09 seconds; no skips in this environment.

5. `git diff --check`: passed.

The existing warning is Starlette's deprecation of its httpx TestClient integration.
No frontend tests/build were needed because this slice changes no frontend files.

Coverage includes fresh/legacy cache reads, atomic publication and indefinite
retention, expiration, stale refresh success/failure, real empty lists, cold
success/failure, concurrent cold/stale requests, scheduler/request overlap,
independent ranking regions, retry after cooldown, lease ownership loss,
cancellation, owner/follower timeout, invalid return values, missing publication,
exactly one ranking-history write for coalesced calls, DB failure after publication,
and explicit Redis connection failure. Actual Lua scripts and Redis expiry/locking
are exercised rather than mocked.

Follow-up coverage proves full stale response delivery while upstream is blocked,
fresh/stale headers, legacy payload handling, background success/failure, fresh
publication visible on the next request, safe handling of unexpected background
errors, and a separate scheduler process sharing the lease with eight API requests.
httpx's in-process ASGI transport waits for background completion, so the timing
test observes ASGI response messages directly rather than conflating client
transport completion with response delivery.

The new test module requires `redis-server` and skips if it is unavailable. It
starts its own disposable instance with `--port 0`, a private Unix socket, and no
disk persistence, and terminates it afterward. Sandbox escalation was needed only
because this environment blocks socket creation. No production service was used.

## API-visible differences and compatibility

- Successful `/api/v1/rankings` and `/api/v1/events` responses are still HTTP 200
  bare lists, including retained stale responses. Existing fields, raw values,
  URLs, region validation, and defaults are unchanged.
- Successful responses add `X-VLR-Cache: fresh` when read from the freshness key,
  or `X-VLR-Cache: stale` when read from the retained copy. This describes the
  payload at read time, not the outcome of subsequent background work.
- These responses, and explicit cold-cache 503 responses, use
  `Cache-Control: no-store` so intermediaries do not reuse a stale freshness label.
  Cold failures do not claim a fresh/stale payload via `X-VLR-Cache`.
- No last-success timestamp is introduced: legacy retained payloads have no
  capture timestamp and one must not be invented. Consumers can use the additive
  freshness header without changing their body decoders.
- Next.js proxy routes/data loaders are unchanged and do not forward or consume
  these new headers yet. The signal is currently exposed on the FastAPI endpoints.
- A genuinely cold upstream failure now returns HTTP 503 and a stable FastAPI
  `detail` object instead of an unhandled refresh exception or fabricated empty
  result. Internal exception messages are not included in that response.
- Other endpoint response shapes and cold-cache behavior are unchanged.
- `/api/v1/status` retains its exact key-list/TTL shape. Its existing fresh key
  can report null TTL while a retained payload is still available; the new
  retained/lease keys are not added to that API response.
- Redis outages still propagate as failures. The implementation does not pretend
  unavailable Redis is an empty or stale cache and adds no database fallback.

## Remaining risks and follow-up boundaries

1. Retention depends on Redis. Eviction, flushes, or restart without persistence
   can remove retained data. Redis persistence/eviction configuration was not
   inspected or changed.
2. Retained data can be indefinitely old. The fresh/stale header makes its state
   visible to direct API consumers but does not report age. An age indicator or
   maximum stale policy needs a future consumer-compatible decision.
3. Existing pre-change fresh keys remain readable, but do not acquire a retained
   copy until their first successful refresh through the new code. No production
   cache migration or warm-up was performed.
4. Background work is not a durable queue. Graceful server shutdown can wait for
   it; forced shutdown/cancellation can interrupt it. The existing lease expiry
   and failure backoff allow later requests/scheduler runs to retry. Ranking DB
   snapshot writes follow publication and remain outside the scrape timeout.
   Cold requests still wait for refresh; retained-data reads still require Redis
   and are not a latency guarantee during Redis outages.
5. Coordination requires all refresh writers to use the new helper. Mixed old/new
   deployment processes can still duplicate scrapes. Redis failover/eviction or a
   worker paused beyond the lease can permit a replacement scrape; ownership
   fencing prevents obsolete publication, not exactly-once execution under every
   infrastructure failure. Separate-process API/scheduler coordination is tested;
   production load, Redis failover, and rolling deployment were not tested.
6. Lua operations assume the documented standalone Redis deployment. Redis Cluster
   would require colocating related keys in a hash slot. ACLs must allow the
   used Redis commands, including EVAL. Production ACLs were not inspected.
7. Successful scraper output `[]` remains valid. A changed upstream page that
   silently parses as empty is not distinguishable from genuine empty data here;
   HTML validation is outside this cache slice.
8. Only rankings/events gain retention/coalescing. Other cache gaps, frontend
   score polling, search races, request deadlines, and UI redesign remain open.

## Commit state

Delivery branch: **`v2`**, based on
`9f4b8cbf22a38bed15163dc353634ad241dbd9ea`. Implementation commit:
**`93ea25ed105b2349a96e262a176241a44cc36906`**. It contains the implementation,
tests, this report, and the two relevant earlier handoff documents. A subsequent
documentation-only commit records that implementation hash here. The normal push
target and intended upstream are `origin/v2` only. No commits, pushes, or merges
target `main` or `master`. The unrelated `.gitignore` change remains uncommitted.
