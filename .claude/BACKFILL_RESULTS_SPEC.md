# SPEC: Backfill match_results from team pages + ID-based trend join (phase 5)

Fixes the gap found in phase 4: GET /api/v1/trends/team/2 returns a rating trend
but results_in_window is empty. Diagnosis confirmed via DB: match_results contains
ZERO Sentinels rows. Cause is structural, NOT a name mismatch:

  /matches/results is a ROLLING global feed of recently-finished matches across all
  of vlr, dominated by high-volume academy/tier-2/3 teams. The 10-min scheduler grabs
  whatever's at the top at that instant, so a specific tier-1 team's matches almost
  never land in the table. The team's OWN page, however, lists its real completed
  results reliably — and we already scrape & parse them on /team/{id}, we just don't
  persist them.

## What to build
1. On a team fetch (GET /api/v1/team/{id}), persist that team's parsed completed
   results into match_results, deduped on the existing unique vlr_id column
   (on_conflict_do_nothing, same idempotent upsert pattern used by refresh_results).
   This backfills real results for exactly the teams people look up.
2. Capture team IDs on match records. Add nullable columns team_a_id / team_b_id to
   match_results (String(32), indexed). Populate them wherever we have the ids:
   - team page results: we know the page's own team_id; the OPPONENT's id comes from
     the opponent href if the parser captures it (add it to the team-results parser
     if missing — opponent_id from the opponent link href, same id_from_href helper).
   - existing /matches/results path: populate ids if present in the card href/markup,
     else leave null. Do NOT block on backfilling old rows; nullable is fine.
3. Rewire the trend join to prefer IDs. In app/services/trends.py, match a team's
   results by team_a_id/team_b_id == team_id FIRST; fall back to the existing fuzzy
   NAME match only when ids are null (older rows). Derive win/loss from which side
   the team was on. Keep numeric coercion of scores defensive (unparseable -> null
   result, no crash) exactly as phase 4 does.

## Schema note
This is an additive migration: two new nullable columns, indexed. init_db /
create_all handles new columns on a fresh table, but the table already exists with
data — so add a tiny idempotent migration step (ALTER TABLE ... ADD COLUMN IF NOT
EXISTS for team_a_id, team_b_id) run at startup or as a one-off, so existing rows
get the columns as null. Do NOT drop/recreate the table (would lose banked history).

## Keep the rules
- Selectors stay in selectors.py. If the team-results parser needs the opponent id,
  derive it from the opponent href via id_from_href — no hardcoding.
- Scraper still stores raw text for scores; coercion stays at read time in trends.
- Dedup on vlr_id so re-fetching a team doesn't duplicate its matches.
- Tests assert structure/invariants, no volatile values.

## Tests
- team-results persistence shaping: given parsed team-page results + the page team_id,
  produce match_results rows with vlr_id, team names, scores, event, AND team ids
  populated (page team on its side, opponent id from href). Pure function, no DB.
- id-preferred join: a results row WITH team_a_id matching is selected by id even if
  the name differs (proves id join works and beats fuzzy name). A row with null ids
  still matches by name (fallback preserved).
- win/loss derivation unchanged from phase 4 (reuse/extend those tests).
- migration idempotency: running the ADD COLUMN IF NOT EXISTS step twice is safe.

## Verify + ship
- pytest green (report count).
- On the running service: GET /api/v1/team/2 (triggers backfill), then
  GET /api/v1/trends/team/2 and confirm results_in_window is now NON-EMPTY with real
  Sentinels matches (the EWC qualifier games etc.), each with a win/loss and the
  match joined by id. Confirm wins/losses in summary are now populated.
- Confirm no duplicate match rows after a second /team/2 fetch (vlr_id dedup).
- Commit logically (model+migration; scraper/parser id capture; service join rewire;
  tests) and push. Report commit hashes, pytest count, and a sample /trends/team/2
  output showing populated results_in_window.

## Out of scope
No new entities, no global search, no events detail, no frontend. Just: persist team
results, capture ids, prefer-id join. Player trends come later, once this proves out.
