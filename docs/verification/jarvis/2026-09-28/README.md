# Jarvis endpoint deployment — 2026-09-28

Backend revision: `396bc79b0f233f6d6f92ab4a8b89b94bdf81db28`, branch `v2`.
Deployed at 15:05:20 UTC via the established pinned-artifact launcher path.
Contract and Jarvis configuration: [JARVIS_TEAM_MATCH.md](../../../JARVIS_TEAM_MATCH.md).

The existing assistant route and consumers were inspected first: legacy tests,
verification scraper, status metadata, and handoff documentation. No frontend
caller was found. Its first-hit name resolution, refresh-on-miss behavior and
response fields remain untouched. A separate `/api/v1/jarvis/team-match`
contract (`schema_version: "1"`) isolates authentication, ambiguity handling,
cache-only serving, and nullable structured scores.

Validation:

- Full backend suite: 321 passed; existing Starlette/httpx deprecation warning.
- Exact exported artifact: 321 passed from `/tmp`, importing the pinned source.
- Isolated HTTP + real Redis check passed for checkout and artifact: dedicated
  ephemeral Redis, temporary token, loopback API, lifespan off. Verified 401,
  structured response and real atomic quota enforcement at request 31.
- One authenticated production Jarvis request, `team_id=13576&kind=completed`:
  HTTP 200 in 0.004 seconds, `Cache-Control: no-store`, `state: ok`.
  JD Gaming (`13576`) vs FUT Esports (`1184`), match `753445`, completed,
  Valorant Champions 2026, series 0–2, map rounds Ascent 1–13 / Summit 10–13.
  Source display date was `2026/09/277:35 am`; retained verbatim, not interpreted
  as timezone-qualified time. Capture timestamp/age null, freshness unknown.
- Health/status HTTP 200; status reports the exact SHA and artifact import root,
  PostgreSQL and Redis healthy. Service active with PID 178083.

The private token file was created with mode 600 outside Git, under a mode-700
service configuration directory. It is scoped to this one read endpoint. No
credential was printed or included in evidence. Jarvis needs the private base
URL, this endpoint's route/parameters, and a securely transferred Bearer secret.
The Jarvis repository was not modified.

Backup: `/home/builder/vlr-backups/20260928-jarvis` (mode 700). Archive contains
the previous pinned source, complete virtualenv, environment and project metadata;
launcher, environment and systemd unit also have separate copies. Archive members
for launcher/environment/revision were verified. SHA256:
`c1f78fbc676cc8453fa716295949648f50ec090414b2238a64c8341b44e42b01`.

Rollback, if required:

```sh
bash /home/builder/vlr-backups/20260928-jarvis/rollback.sh
```

The script verifies unchanged unit/environment, restores the prior pinned source
and runtime from the archive, retains replaced files, and restarts only vlr-api.
Syntax checked; rollback was not needed or exercised against the healthy service.
The launcher was replaced atomically; unit and environment compared identical
with their backups after cutover. No caches were flushed, no other service was
restarted, no Caddy/public ingress changes, no broad probe or release review.
Unrelated working-tree edits were preserved.

Player date verification passed at 15:23:52 UTC (`player-date-check.json`).
The player 36245 entry had expired naturally: TTL was -2 immediately before the
single normal request. HTTP 200 in 0.169 seconds; all five recent results now
have non-null date text, including `2026/09/25 7:25 am`. The normal request
repopulated the cache with TTL 3600. No flush, deletion, shortened expiry, or
forced refresh was used. These are source display dates, not ISO timestamps.
