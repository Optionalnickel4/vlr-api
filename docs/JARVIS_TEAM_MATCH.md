# Jarvis team match contract v1

Private backend: `GET http://10.0.0.21:8000/api/v1/jarvis/team-match`.
The repository branch is `v2`; the deployed API prefix remains `/api/v1`.
No public ingress or frontend proxy is added. Do not put the credential in a
browser, URL, logs, or source control.

Send `Authorization: Bearer <secret>` from the Jarvis server. The dedicated
opaque token grants only this read endpoint. Backend reads it from
`VLR_JARVIS_TOKEN_FILE` (default `/home/builder/.config/vlr-api/jarvis.token`),
a private file outside Git. Transfer its contents to the Jarvis host's secret
store using the existing private administration channel. Suggested Jarvis
configuration: base URL `http://10.0.0.21:8000/api/v1`, token secret, HTTP timeout
4 seconds, no automatic retry loop. Rotate by atomically replacing the token
file and updating Jarvis's secret; the backend rereads it per request.

Query parameters:

| Parameter | Meaning |
| --- | --- |
| `team_id` | Preferred numeric VLR team ID, 1–16 digits. Takes precedence over `name`. |
| `name` | Alternative, 2–64 characters after trimming (raw maximum 64). DB substring search plus existing cached autocomplete; no upstream lookup. Multiple distinct IDs produce ambiguity even if one name is an exact match. Candidate lists are bounded by existing search caps (12 per source), not exhaustive. |
| `kind` | `auto` (default: live → upcoming → completed), `live`, `upcoming` (next), or `completed` (most recent in source order). |

Examples: `?team_id=2&kind=live`, `?team_id=2&kind=upcoming`,
`?team_id=2&kind=completed`, `?name=Karmine%20Corp`.

Response fields are allowlisted structured facts, with `schema_version: "1"`.
`state` is `ok`, `partial`, `empty`, `ambiguous`, or `unavailable`.
`match.state` is `live`, `upcoming`, or `completed`. Scores are nonnegative
integers or null, always oriented to the selected team. `series_score` counts
maps won; each `maps[].round_score` counts rounds. A round placeholder does not
count as a played round. Unplayed or unknown scores remain null. Map order is
source order; no claim is made that the final listed map is currently active.
IDs are strings or null; names are labels and unknown identities stay null.
Canonical match URLs are `https://www.vlr.gg/<match_id>`.

Example completed result with no cached map detail (illustrative):

```json
{
  "schema_version": "1",
  "state": "partial",
  "team": {"id": "2", "name": "Sentinels"},
  "match": {
    "id": "500", "state": "completed",
    "opponent": {"id": null, "name": "NRG"},
    "event": "VCT", "url": "https://www.vlr.gg/500",
    "series_score": {"team": 2, "opponent": 1}, "maps": [],
    "source_date": {"display_date": "Sep 28, 2026", "display_time": null, "starts_at": null},
    "freshness": {"status": "unknown", "captured_at": null, "age_seconds": null}
  },
  "candidates": [], "error": "partial_data",
  "freshness": {"served_at": "2026-09-28T15:00:00+00:00", "status": "unknown", "captured_at": null, "age_seconds": null}
}
```

For live, the same match object has `state: "live"`, available series scores,
and e.g. `maps: [{"name":"Ascent","round_score":{"team":4,"opponent":2}}]`.
For upcoming, series scores are null. Dates are raw source display values;
`starts_at` remains null because these sources do not establish a timezone.
Global listings may supply only a display time; neither relative labels nor
snapshot times are converted into a calendar match date.

Empty response (all relevant cache reads succeeded and contain no match):

```json
{"schema_version":"1","state":"empty","team":{"id":"2","name":"Sentinels"},"match":null,"candidates":[],"error":"no_match","freshness":{"served_at":"2026-09-28T15:00:00+00:00","status":"unknown","captured_at":null,"age_seconds":null}}
```

Ambiguity response (HTTP 409; illustrative IDs):

```json
{"schema_version":"1","state":"ambiguous","team":null,"match":null,"candidates":[{"id":"2","name":"Example"},{"id":"3","name":"Example Academy"}],"error":"ambiguous_team","freshness":{"served_at":"2026-09-28T15:00:00+00:00","status":"unknown","captured_at":null,"age_seconds":null}}
```

Jarvis should ask the user to choose a candidate and save its stable ID. It must
not turn `empty` into certainty that a team has no real-world scheduled games,
or describe an unknown-freshness live observation as verified current. `partial`
means usable facts exist, but detail or higher-priority coverage is missing.
`unavailable` has `match: null`, a nullable selected team, and one of the errors
below. No scrape or background warming is initiated by this endpoint.

| HTTP | `error` / handling |
| --- | --- |
| 200 | null, `partial_data`, or `no_match` |
| 401 | `unauthorized`; Bearer challenge; missing/wrong credential |
| 409 | `ambiguous_team`; choose an ID |
| 422 | `invalid_query` if lookup absent/blank; FastAPI `detail` validation array for invalid parameter syntax/enum |
| 429 | `rate_limited`; obey `Retry-After` seconds |
| 503 | `auth_unconfigured`, `team_not_cached`, `cache_miss`, `identity_conflict`, `state_conflict`, or `storage_unavailable`; do not infer team nonexistence |
| 504 | `timeout`; storage/service deadline exceeded |

The total async storage/service budget is 3 seconds, including rate limiting.
Redis implements an atomic 30 requests per 60-second window per credential,
shared across workers. Only authenticated calls consume quota. This deployment
has one dedicated Jarvis client credential; do not share it with other clients.
All endpoint-generated responses use `Cache-Control: no-store`.

Freshness is deliberately `unknown`: existing match/team/list cache values have
no acquisition timestamps. Their TTLs and scheduler heartbeat do not establish
capture time. `served_at` is response generation time only. Cached observations
may be stale; missing/expired entries yield partial/unavailable without a
scrape. DB is used for identity, not to pretend historical capture ordering is
match-date ordering. No synthetic capture timestamp or zero score is invented.

The legacy `/api/v1/assistant/team-match?name=` route, its envelope, priority,
search fallback, and consumers remain unchanged. It is exercised by
`tests/test_assistant.py` and `app/scrapers/verify.py`; repository search found no
frontend caller. Separate routing avoids changing its cold-cache behavior,
authentication, name resolution, and established response shape.
