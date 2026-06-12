# SPEC: Team trend endpoint (phase 4 — first analytics view)

The first view that reads the accumulated history and does something vlr.gg
structurally cannot: combine a team's ranking-rating trend over time with its
match results over the same window. Pure query + shaping work — NO new scraper,
NO new tables, NO schema changes. Reads ranking_snapshots + match_results.

## Why this exists
ranking_snapshots has been accumulating rating/rank over time; nothing reads it as
a trend yet. vlr.gg only ever shows current rating. This endpoint turns the banked
history into a time series, joined to results, to validate the snapshot data is
clean enough to build dashboards on.

## CRITICAL data-shape note (read before coding)
In the models, rating/rank/scores are stored as STRING (the scraper captures raw
text on purpose — lossless, no parse assumptions). For a trend you MUST coerce to
numeric at READ time, defensively:
- parse rating to float; if it doesn't parse, SKIP that point (don't crash, don't
  guess). Same for rank -> int.
- never string-compare ratings ("998" < "1024" is False as strings — wrong).
- do the coercion in the endpoint/service layer. DO NOT change the table columns;
  the scraper must keep storing raw text.

## Endpoint
GET /api/v1/trends/team/{team_id}?days=90
Returns JSON:
{
  "team_id": "2",
  "team": "Sentinels",          # latest known name from snapshots
  "window_days": 90,
  "rating_trend": [              # chronological, only parseable points
    {"captured_at": "...", "rating": 1024.0, "rank": 3}
  ],
  "rating_change": 26.0,         # last - first in window, null if <2 points
  "results_in_window": [         # from match_results where this team played, in window
    {"vlr_id": "...", "opponent": "...", "result": "win|loss",
     "score": "1:2", "event": "...", "captured_at": "..."}
  ],
  "summary": {                   # cheap derived stats
    "points": 12,                # parseable rating points
    "wins": 4, "losses": 3,      # from results_in_window
    "current_rating": 1024.0,
    "peak_rating": 1031.0
  }
}

## Matching results to a team
match_results stores team_a / team_b as NAMES (not ids), and ranking_snapshots has
both team_id and team (name). Resolve the team's name from the latest ranking
snapshot for that team_id, then match results where team_a OR team_b equals that
name. Derive win/loss for THIS team from which side it was on + the scores
(coerce scores to int defensively; if a score won't parse, result = null, don't crash).
Note this name-matching is fuzzy by nature (name changes, casing) — that's a known
limitation to surface, not solve now. Add a brief note in the response if no name
could be resolved (empty results, not an error).

## Service layer
Put the query/shaping in app/services/ (e.g. trends.py), endpoint in api/v1/routes.py
stays thin. Reads only; no cache needed for v1 (it's a DB query), but you may cache
with a short TTL if trivial.

## Tests (no network — this is pure DB-shape logic)
Refactor the coercion + shaping into pure functions that take rows (or row-like
dicts) and return the response dict, so they test without a live DB:
- rating coercion: "1024" -> 1024.0; "N/A"/"" -> skipped point.
- rating_change: last-first; null when <2 parseable points.
- win/loss derivation: team on side A with score_a>score_b -> win; reversed -> loss;
  unparseable score -> null result, no crash.
- string-sort trap guard: a series like ["998","1024","1003"] must order numerically
  (998,1003,1024), proving we didn't string-compare.
- empty/garbage input: no points, no results -> valid empty response, no exception.

## Verify + ship
- pytest green (report new count). No verify.py change needed (no scraper).
- Hit GET /api/v1/trends/team/2 on the running service; confirm it returns real
  banked history (there should be ranking_snapshots rows by now) and that
  rating_trend is chronologically ordered and numeric.
- If there's only 1 snapshot so far, rating_change is null and that's correct —
  report it so we know cadence is working but history is still young.
- Commit logically (service+tests; route), push, report commit hashes, pytest count,
  and a sample of the real /trends/team/2 output.

## Out of scope
No charting/frontend, no player trends yet (this validates the pattern on teams
first), no new scrapers or tables, no global search.
