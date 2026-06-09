# OPEN ITEM — `/team/{id}` 500s (TWO distinct API-side bugs)

Banked during frontend slices 1–2 so we don't re-trigger/re-diagnose in a later
session. **Both are API-side bugs (root repo `app/` + the Postgres cluster), not
frontend bugs.** The frontend already guards both (graceful-empty), so neither
blocks the build.

Investigating which bug hits a *real* rank-1 team (`1001` = Team Heretics) revealed
that "the team endpoint 500s" is actually **two different failures with two
different fixes** — exactly the distinction worth recording.

## Observed on the LXC 289 deployment 2026-06-09

| id | vlr.gg returns | API result (1st hit) | which bug |
|------|------|------|------|
| `2` (Sentinels), `2593`, `9999` | 200 | 200 ✓ | none (ASCII rosters) |
| `1`, `120`* (*old behaviour) | **404** | **500** | **Bug A** — raise_for_status |
| `120`, `1001` (Team Heretics) | **200** | **500**, then **200** on retry | **Bug B** — SQL_ASCII persist |

`1001` is rank 1 in `rankings.json`, so both bugs are reachable from normal nav
(click a ranked team → its page), not just hand-typed ids.

---

## Bug A — nonexistent id → upstream 404 → unhandled `raise_for_status` → 500
For an id vlr.gg has no page for (e.g. `1`), vlr returns **404**; the scraper's HTTP
client calls `resp.raise_for_status()`, raising `httpx.HTTPStatusError`, uncaught
all the way to FastAPI → generic 500.

```
app/api/v1/routes.py:93  team -> R.refresh_team(team_id)
app/services/refresh.py:176  refresh_team -> te.fetch_team(team_id)
app/scrapers/teams.py:127  fetch_team -> get_client().get_html(f"/team/{team_id}")
app/core/http.py:48  get_html -> resp.raise_for_status()
httpx.HTTPStatusError: Client error '404 Not Found' for url 'https://www.vlr.gg/team/1'
```

**Fix (API repo):** catch `httpx.HTTPStatusError` (404) in `fetch_team`/`get_html`
and raise `HTTPException(404, ...)` instead of letting it 500.

---

## Bug B — real team, vlr 200, scrape OK, **DB persist fails (SQL_ASCII cluster)**
For a real team whose roster has **non-ASCII names** (e.g. Team Heretics' analyst
"Ričardas Lukaševičius"), vlr returns **200** and the scrape + parse **succeed**
(`refresh_team` even `cache_set`s the correct data at `refresh.py:177`). The 500
comes later, at the `team_snapshots` INSERT:

```
sqlalchemy.exc.DBAPIError: asyncpg.exceptions.UntranslatableCharacterError:
  unsupported Unicode escape sequence
DETAIL: Unicode escape value could not be translated to the server's encoding SQL_ASCII.
[SQL: INSERT INTO team_snapshots (team_id, name, region, roster, captured_at) ...]
[parameters: ('1001', 'Team Heretics', 'Europe',
  '[{"alias":"Boo","real_name":"Ričardas Lukaševičius",...}]', ...)]
```

Confirmed cluster encoding (read-only query, 2026-06-09):
```
SHOW server_encoding;                          -> SQL_ASCII
SELECT pg_encoding_to_char(encoding) ...        -> SQL_ASCII
```

So the Postgres cluster/database was initialized with **SQL_ASCII** encoding and
cannot store the Unicode escape in the roster JSONB.

Because `cache_set` runs **before** the DB writes in `refresh_team`
(`refresh.py:177` vs the snapshot INSERT at `refresh.py:189+`), the *first* request
500s but populates the cache with valid data, so the *retry* returns 200 from
cache — which is why `120`/`1001` "fixed themselves" on the second hit (until the
teams TTL expires and the snapshot persist is re-attempted and 500s again).

**Scope is wider than team detail.** Any non-ASCII text headed for Postgres hits
this: player snapshots, and `match_results` rows carrying accented names (e.g.
"LEVIATÁN", which already appears in `results.json`). History accumulation for
anything non-ASCII is silently dropping rows behind 500s.

**Fix (deployment, NOT the same as Bug A):** the database encoding must be UTF8.
Options, in order of correctness:
1. Recreate the cluster/db with `ENCODING 'UTF8'` (initdb/createdb) and reload — the
   real fix; SQL_ASCII is the wrong choice for scraped international esports data.
2. Interim only: stop persisting non-ASCII (lossy) — not recommended.

A 404-to-HTTPException handler (Bug A's fix) does **nothing** for Bug B.

---

## Frontend handling (already in place — slice 1)
`getTeam(id)` in `src/lib/vlr.ts` goes through `load()`, whose try/catch turns any
non-2xx (both bugs) into `{ data: [], stale: true, error }`. The team detail page
(slice 5) renders that as a graceful-empty / unavailable state.
`TODO(api-team-500)` — when the API maps 404 cleanly (Bug A) **and** the cluster is
re-encoded UTF8 (Bug B), the frontend needs no change; this item can close.
