# `/team/{id}` 500s — TWO distinct API-side bugs (Bug B FIXED 2026-06-09)

Banked during frontend slices 1–2 so we don't re-trigger/re-diagnose in a later
session. **Both are API-side bugs (root repo `app/` + the Postgres cluster), not
frontend bugs.** The frontend guards both (graceful-empty) regardless.

Status: **Bug B (SQL_ASCII) is FIXED** (see "Bug B — RESOLVED" below). **Bug A
(404 → raise_for_status) is still open** — a small, separate code fix.

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

A 404-to-HTTPException handler (Bug A's fix) does **nothing** for Bug B.

### Bug B — RESOLVED 2026-06-09 (DB re-encoded UTF8)
Scope confirmed first: the **whole cluster** was SQL_ASCII (`template0`,
`template1`, `postgres`, `vlr`, all `C`/`C`), so `template1` would keep minting
SQL_ASCII DBs. Only `C.utf8` locale is installed (not `en_US.UTF-8` despite `LANG`)
— that's why the original `initdb` fell back to SQL_ASCII.

History was worth keeping (`ranking_snapshots`=650 — the banked trend series —
plus `match_results`=76), so a **dump → re-encode → restore** migration, not a
clean wipe. Crucially, the existing non-ASCII VARCHAR data was already **valid
UTF-8 bytes** (`LEVIATÁN` = `0xC3 0x81`, `KRÜ` = `0xC3 0x9C`): plain-text inserts
had succeeded because SQL_ASCII stores bytes unvalidated, while only the JSONB
(`team_snapshots.roster`) path failed on asyncpg's `\uXXXX` escapes. So the dump
round-tripped cleanly.

What was done (as root on LXC 289, `vlr-api` stopped for the duration):
1. `systemctl stop vlr-api` (the scheduler runs in-process — one service halts all writers).
2. `pg_dump --encoding=UTF8 --no-owner --no-privileges` of `vlr`; **validated the dump is
   valid UTF-8 with `iconv -f UTF-8 -t UTF-8`** (your mojibake guard) — passed.
3. `CREATE DATABASE vlr_utf8 TEMPLATE template0 ENCODING 'UTF8' LC_COLLATE 'C.utf8'
   LC_CTYPE 'C.utf8' OWNER vlr;` then restored the dump with `psql -v ON_ERROR_STOP=1`
   (exit 0). Verified row counts matched (650/76/4/3) and accented names round-tripped
   (`KRÜ BLAZE`, `LEVIATÁN`, `XØ IND`) **before** touching the original.
4. Atomic swap: terminated `vlr` connections, `DROP DATABASE vlr;`, `ALTER DATABASE
   vlr_utf8 RENAME TO vlr;`.
5. Fixed the cluster: dropped + recreated `template1` from `template0` as UTF8/C.utf8
   (`datistemplate=true`), so it no longer mints SQL_ASCII DBs.
6. `systemctl start vlr-api`.

End-to-end proof (cache cleared between, per the ask): `redis-cli DEL vlr:team:1001`
→ `GET /api/v1/team/1001` → **200**, and `team_snapshots` for id `1001` went
**0 → 1 rows** — i.e. the INSERT that used to 500 now **succeeds** (not a cache
self-heal). The stored roster reads back `Ričardas Lukaševičius` (bytes
`\304\215`=č, `\305\241`=š — clean UTF-8, no mojibake). `SHOW server_encoding` →
`UTF8`. All prior history intact (`ranking_snapshots` still 650; `/trends/team/2`
still returns banked history).

Remaining (intentionally left, harmless): `postgres` (maintenance DB, not a
template) and `template0` (immutable pristine template) are still SQL_ASCII. The
default `CREATE DATABASE` path uses `template1`, now UTF8. A dump backup is at
`/tmp/vlr_dump.sql` (ephemeral).

---

## Frontend handling (already in place — slice 1)
`getTeam(id)` in `src/lib/vlr.ts` goes through `load()`, whose try/catch turns any
non-2xx (both bugs) into `{ data: [], stale: true, error }`. The team detail page
(slice 5) renders that as a graceful-empty / unavailable state. The guard stays
regardless — it still covers Bug A and any future upstream hiccup.
`TODO(api-team-500-A)` — remaining work is Bug A only: catch the upstream 404 in
`fetch_team`/`get_html` and raise `HTTPException(404)` instead of 500. Bug B (the
SQL_ASCII encoding) is resolved; the frontend needs no change for either.
