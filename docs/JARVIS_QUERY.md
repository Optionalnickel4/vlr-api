# Jarvis general query contract v1

`POST /api/v1/jarvis/query` is an authenticated, read-only, cache/DB-only
endpoint. The repository branch is `v2`; the deployed HTTP prefix remains
`/api/v1`. It shares the existing Jarvis Bearer credential, 30-request/60-second
Redis quota, three-second total service budget, and `Cache-Control: no-store`
response policy with `/api/v1/jarvis/team-match`. Never place the credential in
a URL, browser, log, source file, example, or evidence artifact.

The request is a closed, typed operation object. Unknown operations, extra
parameters, URLs, SQL, arbitrary instructions, unsupported filters, and limits
outside an operation's bound return HTTP 422 with `error: "invalid_request"`.
No operation invokes a refresher, scraper, VLR search fallback, or upstream HTTP.

## Supported operations

| Operation | Parameters | Bound and coverage |
| --- | --- | --- |
| `capabilities` | empty `params` (optional) | Returns the static supported/unavailable operation declaration. |
| `matches.list` | required `state`: `live`, `upcoming`, or `completed`; optional `limit` 1–25 (default 10); optional `team` 2–64 characters; optional `event` 2–128 characters | Preserves source order. Team is an exact normalized name match. Event is a normalized substring match. Region and time-window filters are unsupported because list cards store neither region nor a timezone-qualified start. |
| `matches.get` | numeric `match_id`, 1–16 digits | Cached detail, then bounded listing caches, then sampled completed-result DB row. Absence is unavailable, not proof of nonexistence. |
| `teams.search` | `query` 2–64 characters; optional `limit` 1–12 (default 8) | Searches banked team snapshots plus the already-cached result for that exact autocomplete term. It never calls upstream autocomplete on a miss. |
| `teams.get` | numeric `team_id`, 1–16 digits | Cached team identity summary, then the latest banked snapshot. It does not claim roster currency. |

`matches.list` source-order semantics are the order stored by the existing VLR
list services: the live and upcoming partitions of `/matches`, and the recent
results feed for completed matches. The API does not sort on display strings.
Completed coverage is a rolling recent sample rather than complete history.

Every response uses this envelope:

```json
{
  "schema_version": "1",
  "operation": "matches.list",
  "state": "ok",
  "items": [],
  "candidates": [],
  "error": null,
  "coverage": {
    "status": "partial",
    "source": "cache",
    "cache_status": "present",
    "observed_items": 0,
    "matched_items": 0,
    "returned_items": 0,
    "truncated": false,
    "limitations": []
  },
  "freshness": {
    "served_at": "2026-09-29T05:00:00+00:00",
    "status": "unknown",
    "captured_at": null,
    "age_seconds": null
  }
}
```

Top-level `state` is `ok`, `empty`, `unavailable`, `ambiguous`, or `error`.
The current operations do not produce ambiguity, but the field and state are
reserved consistently with the existing Jarvis contract. `empty` means the
required cache payload was present and no cached rows matched. Because coverage
and freshness are still partial/unknown, it must be spoken as “no matching games
in the cached listing,” never “there are no games.” A missing required cache is
`unavailable` with HTTP 503. The explicit coverage object always distinguishes
those cases.

Existing list payloads have no acquisition timestamp. Cache TTL and scheduler
heartbeat are not capture time, so `captured_at` and `age_seconds` remain null.
Match-card time strings are rendered source values with an unknown viewer
timezone. `starts_at` therefore remains null instead of inventing UTC. All
API-generated timestamps, including `served_at`, are UTC ISO 8601 values.
Unknown IDs, start times, regions, states, and scores remain null. Upcoming
score placeholders are never converted to zero. Canonical links are generated
only from validated numeric IDs: `https://www.vlr.gg/<match_id>` and
`https://www.vlr.gg/team/<team_id>`.

## Exact requests and representative responses

Use a secret-injected header; `<secret>` below is a placeholder, not a token:

```sh
curl --fail-with-body --max-time 4 \
  -H 'Authorization: Bearer <secret>' \
  -H 'Content-Type: application/json' \
  --data '{"operation":"matches.list","params":{"state":"upcoming","limit":5}}' \
  http://10.0.0.21:8000/api/v1/jarvis/query
```

Representative successful item (values illustrate the exact shape):

```json
{
  "schema_version": "1",
  "operation": "matches.list",
  "state": "ok",
  "items": [{
    "id": "753456",
    "state": "upcoming",
    "teams": [
      {"id": null, "name": "G2 Esports", "score": null},
      {"id": null, "name": "Paper Rex", "score": null}
    ],
    "event": "Valorant Champions 2026",
    "series": "Group Stage–Winner's (C)",
    "region": null,
    "starts_at": null,
    "source_time": {"display_time": "5:00 AM", "relative_eta": "4h 22m"},
    "url": "https://www.vlr.gg/753456",
    "freshness": {"status": "unknown", "captured_at": null, "age_seconds": null}
  }],
  "candidates": [],
  "error": null,
  "coverage": {
    "status": "partial",
    "source": "cache",
    "cache_status": "present",
    "observed_items": 30,
    "matched_items": 30,
    "returned_items": 5,
    "truncated": true,
    "limitations": [
      "Only the current cached VLR /matches upcoming partition is covered.",
      "The cache payload has no acquisition timestamp or region field.",
      "Source display times are not converted because their timezone is unknown."
    ],
    "ordering": "source_order",
    "supported_filters": ["team", "event"],
    "unsupported_filters": ["region", "time_window"]
  },
  "freshness": {
    "served_at": "2026-09-29T05:00:00+00:00",
    "status": "unknown",
    "captured_at": null,
    "age_seconds": null
  }
}
```

Filtered example:

```json
{"operation":"matches.list","params":{"state":"upcoming","team":"NRG","event":"Champions","limit":10}}
```

Capabilities example:

```json
{"operation":"capabilities","params":{}}
```

The capabilities response reports these desired operations as unavailable:

- `rankings.list`: only world rankings are scheduler-warmed; regional caches are
  traffic-dependent, and cache acquisition time is absent.
- `players.summary`: player snapshots are on-demand or limited prefetch samples,
  not a complete or uniformly current player directory.
- `news.list`: cached news has no per-item capture timestamp; the normalized
  Jarvis operation has not yet been implemented and verified.
- `matches.head_to_head`: completed history is sampled and many older rows lack
  stable team IDs, making a historical result incomplete and name-ambiguous.

## HTTP behavior

| HTTP | Meaning |
| --- | --- |
| 200 | `ok` or honest cache-present `empty` |
| 401 | missing/wrong Bearer credential; includes Bearer challenge |
| 409 | reserved for an `ambiguous` operation result |
| 422 | closed-schema validation failure; request does not consume quota |
| 429 | shared Jarvis quota exceeded; obey `Retry-After` |
| 503 | auth unconfigured, required data unavailable, or storage failure |
| 504 | three-second storage/service budget exceeded |

The deployed `/api/v1/jarvis/team-match` method, parameters, envelope, behavior,
and callers remain unchanged. Both paths use the same private server credential;
the new route does not modify Jarvis or its routing in this pass.
