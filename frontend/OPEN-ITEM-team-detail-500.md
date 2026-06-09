# OPEN ITEM — `/team/{id}` 500s for unknown team ids (vlr-api bug)

Banked during frontend slice 1 so we don't have to re-trigger/re-diagnose it in a
later session. **This is an API-side bug (root repo `app/`), not a frontend one.**
The frontend already guards it (graceful-empty), so it does not block the build.

## Symptom
`GET /api/v1/team/{id}` returns **500 Internal Server Error** for team ids that
vlr.gg has no page for, while valid ids work fine.

Observed on the LXC 289 deployment 2026-06-09:

| id | result |
|------|--------|
| `2` (Sentinels) | 200 ✓ |
| `2593`, `9999` | 200 |
| `1`, `120`, `1001` | **500** |

Note: `1001` is a *current rankings* `team_id` (Team Heretics, rank 1 in
`rankings.json`) — so the 500 is reachable from normal navigation (click a ranked
team → its team page), not just hand-typed ids.

> The original frontend spec said `/team/2` itself 500s. On this deployment `2`
> works; it's the *unknown-id* ids that 500. Same underlying bug, different ids.

## Root cause (from journalctl -u vlr-api, captured 2026-06-09 12:48)
Upstream vlr.gg returns **404** for a nonexistent team; the scraper's HTTP client
calls `resp.raise_for_status()`, which raises `httpx.HTTPStatusError`, and nothing
between the scraper and the route handler catches it → FastAPI surfaces a generic
500.

Traceback (trimmed to the project frames):

```
app/api/v1/routes.py", line 93, in team
    data = await R.refresh_team(team_id)
app/services/refresh.py", line 176, in refresh_team
    data = await te.fetch_team(team_id)
app/scrapers/teams.py", line 127, in fetch_team
    html = await get_client().get_html(f"/team/{team_id}")
app/core/http.py", line 48, in get_html
    resp.raise_for_status()
httpx.HTTPStatusError: Client error '404 Not Found' for url 'https://www.vlr.gg/team/1'
```

## Suggested API-side fix (later, in the Python repo — NOT this frontend)
Map an upstream 404 to a clean response instead of letting it 500: catch
`httpx.HTTPStatusError` in `fetch_team`/`refresh_team` (or in `get_html`) and
either raise `HTTPException(404, ...)` from the route or return an empty/None team
the router translates to 404. Whichever the team picks, the frontend guard below
keeps working.

## Frontend handling (already in place — slice 1)
`getTeam(id)` in `src/lib/vlr.ts` goes through `load()`, whose try/catch turns any
non-2xx (incl. this 500) into `{ data: [], stale: true, error }`. The team detail
page (slice 5) renders that as a graceful-empty / unavailable state.
`TODO(api-team-500)` — when the API maps 404 cleanly, the frontend needs no change;
this item can be closed.
