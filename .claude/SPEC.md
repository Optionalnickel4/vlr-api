# valstats (rebuild) — broadcast frontend on LXC 289, targeting vlr-api

Ground-up rebuild of the Valorant broadcast dashboard, built ON the container
(LXC 289, 192.168.1.35) alongside vlr-api, consuming vlr-api directly (NOT the
public vlrggapi). Pushed to GitHub.

## Why a rebuild, not a port
The old valstats-v5 was written against vlrggapi's shapes (flat team1/score1,
{data:{segments}} envelopes, normalizeMatchUrl). vlr-api's shapes are different
(teams[]/scores[] arrays, bare-array responses, absolute URLs, stable ids). We
build the data layer against vlr-api's REAL shapes from the start instead of
adapting the old transforms. The UI design is unchanged and settled.

## Design — LOCKED, do not re-litigate
The broadcast style is the established, final design. Read the `frontend-design`
skill before writing visual code, then implement the broadcast look:
- Dark near-black ground, high contrast.
- Saira Condensed, uppercase, wide tracking for headers/labels/stat columns.
- Scorebug header: TEAM A  score:score  TEAM B, winner score in green.
- Signal colors: red = LIVE, green = winner/win, red = loss/round-loss, dim gray =
  idle/unknown. Tight stat tables, right-aligned numerics, uppercase column heads.
- Restrained chroma — color carries meaning, not decoration.
- NEVER the Neon Ronin / cyberpunk / anime aesthetic. That direction is dropped.
Reference: the established valstats match-page look (scorebug + per-map PLAYER/
AGENT/R/ACS/K/D/A/KAST/ADR/HS% tables + veto line + map tabs).

## Stack
Next.js 16 + React 19 + TypeScript + Tailwind v4 + Framer Motion 12 + Vitest.
(Match the proven valstats-v5 stack; do not downgrade.)

## Placement & runtime (co-located on LXC 289)
- Code at /opt/valstats (separate dir from /opt/vlr-api).
- Next.js dev/build runs on port 3000; vlr-api stays on 8000.
- The frontend talks to the API over http://127.0.0.1:8000/api/v1 (same host).
  Set VLR_API_BASE env; default to that. Server-side fetches only (Next route
  handlers / server components) — do not call the API from the browser, so the
  API never needs CORS or public exposure.
- Own systemd unit `valstats` (next start), independent of `vlr-api`. Node via the
  container's existing node (confirm version; Next 16 needs Node 18.18+/20+).
- Deploy: `git pull && npm ci && npm run build && systemctl restart valstats`.
- Caddy is NOT set up yet — out of scope here. Reachable at
  http://192.168.1.35:3000 directly for now. (A future Caddy block can map
  valstats.jushosting.dev → 3000 and vlr.jushosting.dev → 8000.)

## Data layer — build against vlr-api's real shapes (the contract)
Single network boundary `fetchApi(path)` → base = process.env.VLR_API_BASE ??
"http://127.0.0.1:8000/api/v1". Uniform envelope back to the UI:
`ApiResponse<T> = { data: T[], stale: boolean, error?: string }`. On upstream
failure return `{ data: [], stale: true, error }` — graceful-empty, never throw to
the page. Keep parseNumeric (return null, never NaN) — vlr-api values are strings.

Per-endpoint transforms, mapping vlr-api → domain types:

### results — GET /matches/results
vlr-api item: `{ id, teams:[a,b], scores:[a,b], eta, time, series, event, url, status }`
→ `ResultMatch { id, team1=teams[0], team2=teams[1], score1=parseNumeric(scores[0]),
score2=parseNumeric(scores[1]), time=eta||time, series, event, url }`.
Lost vs old UI: flag1/flag2, tournamentIcon — DROP from the type, do not render.
Win: `id` is provided directly (no url regex needed).

### upcoming — GET /matches/upcoming
`{ id, teams[], scores:["–","–"], eta, series, event, url, status }` →
`UpcomingMatch { id, team1, team2, timeUntil=eta, series, event, url }`.
No flags, no unix timestamp — any countdown/sort must use eta string only, do NOT
build a timestamp-based countdown (no source). Scores are en-dash → parseNumeric
→ null, fine.

### live — GET /matches/live
Same generic card parser as results → `LiveMatch { id, team1, team2, score1,
score2, series, event, url }`. DEGRADED: no currentMap, mapNumber, logos, flags,
round-half scores. The live view shows team/score/series/event only. Render a LIVE
badge (red). Do NOT render current-map UI — no data source.

### rankings — GET /rankings?region=all (verify param)
vlr-api item: `{ team_id, rank:"1", team, country, record:null, earnings:null,
rating:"2000" }` → `RankedTeam { id=team_id, rank=parseNumeric(rank), team,
country, rating=parseNumeric(rating) }`. ADD a rating field to the type (vlr-api
exposes it; old UI didn't). record/earnings are null in live data, lastPlayed*/
logo absent — DROP. VERIFY on the container whether rankings accepts region=na|eu
or only `all` / a /rankings/{region} path; wire the region switcher to whatever it
actually accepts, don't assume.

### news — GET /news
`{ title, description, meta:"•June 8, 2026•by raezeri", url }` →
`NewsArticle { title, description, date, author, url }` by splitting `meta` on "•"
and the "by " prefix. If the split is fragile, fall back to showing meta verbatim.
URL is absolute — use directly.

### player detail — GET /player/{id}
`{ id, alias, real_name, country, team, team_id, team_url, agent_stats:[{agent,
stats:{Use,RND,Rating,ACS,"K:D",ADR,KAST,KPR,APR,FKPR,FDPR,K,D,A,FK,FD}}],
matches:[{id,url,opponent,result,score,event}] }`. Render a player profile page:
identity header, per-agent stat table (keys are display-cased with colons, e.g.
"K:D" — read them verbatim), and recent matches list. TenZ = id 9.

### team detail — GET /team/{id}  ⚠️ CURRENTLY 500s
Known broken on the deployment (separate vlr-api bug, being fixed). Build the team
page against the documented shape but guard for failure (graceful-empty). Mark with
a TODO referencing the /team/{id} 500 fix. Do not block the rest of the build on it.

### team trends — GET /trends/team/{id}
`{ team_id, team, window_days, rating_trend[], rating_change, results_in_window[] }`
→ a form/trend panel: rating delta + a W/L results strip. This is net-new vs the old
UI and showcases vlr-api's history advantage.

## Match detail — EXPLICIT STUB (Phase 7 backs it later)
vlr-api has NO match-detail endpoint yet (no per-map scoreboard, rounds, or vetos).
The broadcast match page (the scorebug + per-map PLAYER tables + veto line) is the
flagship view but has no data source today.
- Build the match-detail PAGE and components (scorebug, MapTabs, PlayerStatsTable,
  veto line) so the UI is ready.
- Feed it from a clearly-marked stub/fixture, NOT live data. Gate it behind an
  obvious "match detail pending API support (vlr-api Phase 7)" notice.
- Document in OPEN-ITEM-match-detail-pending.md and a TODO(phase7) comment, same
  pattern as the parked live-path item in the old build.
- When Phase 7 lands a /matches/{id} (or similar) detail endpoint, this page swaps
  the stub for a real transform — design unchanged.

## Stats leaderboard — OMIT for now
vlr-api has no region-wide stats leaderboard endpoint. Do NOT build a fake one and
do NOT half-build the page. Leave it out of the nav (or a "coming soon" stub).
Decision deferred: later either add a vlr-api leaderboard endpoint or rebuild this
page around /player/{id} profiles.

## Build order (vertical slices, review at each stop)
1. Scaffold + data layer (fetchApi boundary, types, transforms) with Vitest tests
   against SAVED vlr-api JSON fixtures (capture real responses once, commit them;
   tests assert structure/invariants, no network). Stop & review.
2. Broadcast primitives + design tokens (Panel/Badge/LiveBadge/ScoreDisplay/
   TableShell, Saira Condensed, color tokens). Stop & review.
3. Results + upcoming + live (ticker / match center, polling for live). Stop.
4. Rankings + news. Stop.
5. Player detail + team trends (team detail guarded for the 500). Stop.
6. Match-detail page as stub (components real, data stubbed). Stop.
7. Visual polish pass against the broadcast reference.

## Testing
- Vitest on the data transforms using committed real-response fixtures from vlr-api.
- Assert invariants (parseNumeric null-not-NaN, envelope shape, graceful-empty on
  failure, teams[]/scores[] indexing), not volatile values — so tests don't rot.
- No network in tests.

## Git / deploy
- New repo (or new dir pushed to a repo) — recommend github.com/Optionalnickel4/
  valstats (confirm name). Commit per the established phase/slice trunk workflow.
- .env (VLR_API_BASE) not committed; .env.example committed.
- A PROGRESS.md tracking the slices, same as vlr-api Phase 6.

## Hard constraints / lessons carried over
- parseNumeric returns null, never NaN.
- Graceful-empty on upstream failure, never throw to the page.
- vlr-api URLs are absolute — never prepend a domain (old vlrggapi bug).
- Read agent_stats keys verbatim (display-cased, colons) — exact field names, the
  recurring stats-mapping bug.
- Next 16 dev server: if accessed over LAN/Tailscale IP, add the host to
  `allowedDevOrigins` in next.config.ts (the Crostini hydration bug — same class).
- Server-side fetch only; API stays on localhost, no CORS, no public API port.
