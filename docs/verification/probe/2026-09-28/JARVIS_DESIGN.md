# Future Jarvis endpoint — proposal only

Do not implement until Jarvis's actual task is specified. The existing
`/assistant/team-match?name=` already resolves a team and chooses live, next, or
last match. Determine whether Jarvis needs that one answer, a watchlist digest,
notifications, or player analysis before selecting a route and query contract.

Useful data includes schedules/results, explicit series scores and map scores,
team rosters, nullable player identities, recent results, regional rankings,
leaderboard stats, banked trends and cohort dimensions. News currently supplies
links, not article bodies. Keep series scores separate from round scores;
percentile dimensions are cohort-relative, and player history is a series of
capture-time aggregates, not a match-by-match performance log.

A proposed versioned envelope (illustrative empty response, not a live result):

```json
{
  "schema_version": "1",
  "request_id": "opaque-id",
  "state": "empty",
  "data": {"teams": [], "players": [], "matches": []},
  "freshness": {
    "served_at": "2026-09-28T15:00:00Z",
    "captured_at": null,
    "age_seconds": null,
    "status": "unknown"
  },
  "errors": []
}
```

Use `ok|empty|partial|unavailable` for envelope state; reserve
`live|upcoming|completed|unknown` for a match's state. String IDs and canonical VLR
links are stable identifiers; names are labels. Each selected entity should have
its own provenance/freshness when components have different capture times, plus
nullable scores, `starts_at` only when timezone-qualified upstream data exists,
and `display_date` for unqualified source text. Missing values stay null. Freeze
an explicit allowlist of fields and numeric types once the use case is known;
do not pass arbitrary scraper dictionaries through this proposed contract.

Require server-to-server authentication (a scoped, rotatable token stored as a
secret), TLS on its eventual ingress, and a per-client rate/concurrency limit.
A provisional ceiling is 30 requests/minute with burst 5 and one outstanding
request per client; validate it against Jarvis's polling needs before adoption.
Return 401/403 for authentication/authorization failures and 429 with Retry-After
for quota exhaustion. Never log tokens or expose underlying exception strings.
No authentication or ingress changes are part of this pass.

Freshness must come from recorded acquisition metadata or a known cache state,
not latency, HTTP Date, or a scheduler's global last-run timestamp. Existing
`captured_at` describes our snapshot time, not the time upstream last changed.
Where metadata is absent, report `unknown`. Empty live matches are a successful
empty result. Distinguish no history, no query match, ambiguous name, unavailable
cohort, and upstream/cache failure with stable error codes. Preserve usable stale
components with explicit status and component errors; use 503 when none can be
served. A single snapshot can be usable with a null change; do not manufacture
points or missing identities. Retry only according to server backoff guidance.

Reuse `services.search`, `services.assistant`, cache reads, and the pure trend and
dimension functions rather than making loopback HTTP calls or building another
scraper. Review assistant's current name-selection and missing-score fallbacks
before adopting them: Karmine Corp search returned two IDs in this pass, so
ambiguous names need explicit resolution and unknown round data must not become
an invented 0–0. Prefer a bounded cache/DB-only service entrypoint for Jarvis, with
scheduled refresh and coalesced background warming. Current service cold misses
can scrape and current detail deadlines reach 80 seconds; blindly reusing that
path would defeat a short Jarvis response budget. A proposed 5-second total
budget and partial responses should be settled alongside the real use case.
