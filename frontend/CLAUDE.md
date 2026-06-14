# vlr-api frontend — broadcast dashboard in /opt/vlr-api/frontend/

Add a Next.js broadcast-style Valorant dashboard INTO the existing vlr-api repo as
a subdirectory. Same git repo (github.com/Optionalnickel4/vlr-api), same container
(LXC 289, 192.168.1.35). Fresh scaffold, built against vlr-api's real response
shapes. The Python API stays untouched at the repo root.

## Repo layout (monorepo — one .git at /opt/vlr-api)
```
/opt/vlr-api/                 # existing Python API repo root — DO NOT disturb
├── app/                      # Python API (untouched)
├── tests/                    # Python tests (untouched)
├── pyproject.toml, .venv/    # Python (untouched)
├── CLAUDE.md                 # drives the API build (untouched)
├── PROGRESS.md               # existing project tracker (append a frontend section)
└── frontend/                 # ← NEW: the entire Next.js project lives here
    ├── CLAUDE.md             # ← separate spec, frontend-only conventions
    ├── package.json, node_modules/
    ├── next.config.ts, tsconfig.json
    ├── .next/                # build output (gitignored)
    └── src/
        ├── app/              # Next app router + route handlers
        │   └── api/          # /api/matches, /api/rankings, /api/news, etc.
        ├── lib/vlr.ts        # data layer + fetchUpstream boundary
        ├── types/vlr.ts      # domain types
        └── components/       # broadcast UI
```
Rules:
- The Next.js project is ENTIRELY inside `frontend/`. Nothing Node touches the root.
- One `.git` at `/opt/vlr-api`. Add to root `.gitignore`: `frontend/node_modules/`,
  `frontend/.next/`, `frontend/.env*` (keep `frontend/.env.example`).
- Scaffold with `src/` dir + `@/*` import alias (matches the established v5 layout).
- A SEPARATE `frontend/CLAUDE.md` holds all frontend conventions; the root
  `CLAUDE.md` stays API-only. Do not merge the two stacks' guidance.

## Internal structure — mirror the established valstats-v5 layout EXACTLY
Use the same skeleton and names the project already uses — only the transforms
change (to target vlr-api instead of vlrggapi):
- `src/lib/vlr.ts` — the data layer. The single network boundary is
  **`fetchUpstream(path)`** (keep this name), base = `process.env.VLR_API_BASE ??
  "http://127.0.0.1:8000/api/v1"`. All transforms (`normalizeResult`,
  `normalizeUpcoming`, `normalizeLive`, `normalizeRankings`, `normalizeNews`, etc.)
  live here.
- `src/types/vlr.ts` — domain types (`ResultMatch`, `UpcomingMatch`, `LiveMatch`,
  `RankedTeam`, `NewsArticle`, player/team types).
- `src/app/api/*` — Next route handlers returning `ApiResponse<T> = { data: T[],
  stale: boolean, error?: string }`. Same route surface as v5 (`/api/matches?q=`,
  `/api/rankings`, `/api/news`, player/team), minus the ones with no API source.
- UI components consume ONLY the domain types via `{data, stale, error}` — they
  never see raw vlr-api JSON. All mapping stays in `lib/vlr.ts` + `types/vlr.ts`.

## Design — LOCKED, established, do not re-litigate
Broadcast style is final. Read the `frontend-design` skill before visual code, then
implement: dark near-black ground; Saira Condensed uppercase wide-tracked headers/
labels/stat columns; scorebug header (TEAM A score:score TEAM B, winner green); red
= LIVE / loss, green = win/winner, dim gray = idle; tight right-aligned stat tables
with uppercase column heads; restrained chroma (color = meaning). NEVER Neon Ronin /
cyberpunk / anime — that direction is dropped. Reference: the established valstats
match-page look (scorebug + per-map PLAYER/AGENT/R/ACS/K/D/A/KAST/ADR/HS% tables +
veto line + map tabs).

## Stack
Next.js 16 + React 19 + TypeScript + Tailwind v4 + Framer Motion 12 + Vitest.
Match the proven v5 stack; do not downgrade.

## Runtime (co-located on LXC 289)
- Next on port 3000; vlr-api stays on 8000.
- Server-side fetch only, to `http://127.0.0.1:8000/api/v1` — API never needs CORS
  or public exposure; the browser never calls it directly.
- Own systemd unit `valstats` (or `vlr-frontend`): `next start` in
  `/opt/vlr-api/frontend`, WorkingDirectory set there. Confirm container Node ≥
  18.18/20 for Next 16.
- Deploy: `cd /opt/vlr-api/frontend && git pull && npm ci && npm run build &&
  systemctl restart valstats`.
- Caddy NOT set up — out of scope. Reach directly at http://192.168.1.35:3000.
- Next 16: if accessed over a LAN/Tailscale IP, add that host to
  `allowedDevOrigins` in next.config.ts (the known hydration bug class).

## Data layer — vlr-api's real shapes (the contract, from the shape-diff)
Keep parseNumeric (return null, never NaN). Graceful-empty on failure: return
`{data:[], stale:true, error}`, never throw to the page. vlr-api URLs are absolute —
never prepend a domain.

- **results** `GET /matches/results`: item `{id, teams:[a,b], scores:[a,b], eta,
  time, series, event, url, status}` → `ResultMatch{id, team1=teams[0],
  team2=teams[1], score1=parseNumeric(scores[0]), score2=parseNumeric(scores[1]),
  time=eta||time, series, event, url}`. Drop flags + tournamentIcon (no source).
  `id` provided directly — no url regex.
- **upcoming** `GET /matches/upcoming`: `{id, teams[], scores:["–","–"], eta,
  series, event, url}` → `UpcomingMatch{id, team1, team2, timeUntil=eta, series,
  event, url}`. No flags, no unix timestamp — countdown uses eta string only.
- **live** `GET /matches/live`: same card parser → `LiveMatch{id, team1, team2,
  score1, score2, series, event, url}` + red LIVE badge. DEGRADED: no currentMap/
  mapNumber/logos/flags. Do not render current-map UI (no source).
- **rankings** `GET /rankings?region=all` (VERIFY accepted param on container):
  `{team_id, rank, team, country, record:null, earnings:null, rating}` →
  `RankedTeam{id=team_id, rank=parseNumeric, team, country, rating=parseNumeric}`.
  ADD rating to the type. Drop record/earnings/logo/lastPlayed* (null/absent).
- **news** `GET /news`: `{title, description, meta:"•June 8, 2026•by raezeri",
  url}` → split meta on "•" / "by " into `{title, description, date, author, url}`;
  fallback to showing meta verbatim if the split is fragile. URL absolute.
- **player detail** `GET /player/{id}`: render profile (identity, per-agent stat
  table, recent matches). agent_stats keys are display-cased with colons ("K:D") —
  read VERBATIM. TenZ = id 9.
- **team detail** `GET /team/{id}` ⚠️ CURRENTLY 500s on deployment (separate API
  bug). Build the page to the documented shape but guard for failure
  (graceful-empty) + TODO referencing the 500. Don't block the build on it.
- **team trends** `GET /trends/team/{id}`: `{rating_trend[], rating_change,
  results_in_window[]}` → form/trend panel (rating delta + W/L strip). Net-new vs
  v5; showcases the history advantage.

## Match detail — EXPLICIT STUB (vlr-api Phase 7 backs it later)
No match-detail endpoint exists yet (no per-map scoreboard/rounds/vetos). Build the
PAGE + components (scorebug, MapTabs, PlayerStatsTable, veto line) real, fed from a
clearly-marked stub/fixture, gated behind a "match detail pending API support
(Phase 7)" notice. Document in `frontend/OPEN-ITEM-match-detail-pending.md` + a
`TODO(phase7)` comment. When Phase 7 ships a detail endpoint, swap stub → real
transform, design unchanged.

## Stats leaderboard — BUILT (Phase 12)
Originally deferred (no region-wide stats endpoint). vlr-api Phase 12 added
`GET /stats?region={na|eu}&timespan={30d|60d|90d|all}` (VLR's own R2.0 rating as the
headline — no composite). Frontend: `/stats` route + `StatsLeaderboard` island
(region/timespan toggles, click-to-sort columns) + `/stats` nav slot. CRITICAL: sort
on the COERCED numeric (`sortLeaders`), never the raw string (the "998" < "1024" trap).

## Build order (vertical slices — stop & review at each)
1. Scaffold Next into `frontend/` + `frontend/CLAUDE.md` + data layer
   (`lib/vlr.ts` fetchUpstream, `types/vlr.ts`, transforms) with Vitest tests vs
   SAVED vlr-api JSON fixtures (capture real responses once, commit under
   `frontend/src/lib/__fixtures__/`; assert structure/invariants, no network). Stop.
2. Broadcast primitives + design tokens (Panel/Badge/LiveBadge/ScoreDisplay/
   TableShell, Saira Condensed, color tokens). Stop.
3. Results + upcoming + live (ticker / match center, polling for live). Stop.
4. Rankings + news. Stop.
5. Player detail + team trends (team detail guarded for the 500). Stop.
6. Match-detail page as stub (components real, data stubbed). Stop.
7. Visual polish pass against the broadcast reference.

## Testing
Vitest on transforms using committed real-response fixtures. Assert invariants
(parseNumeric null-not-NaN, envelope shape, graceful-empty, teams[]/scores[]
indexing) not volatile values. No network in tests.

## Git / deploy
- Same repo. Commit per the established slice-by-slice trunk workflow, prefixing
  frontend commits clearly (e.g. "frontend: data layer").
- Root `.gitignore` gets the frontend Node ignores (above).
- Append a frontend section to the existing root `PROGRESS.md` (or a
  `frontend/PROGRESS.md` — keep one source of truth, your call but be consistent).
- `frontend/.env.example` committed with `VLR_API_BASE`; real `.env` ignored.

## Hard constraints / carried lessons
- Do NOT modify anything outside `frontend/` except root `.gitignore` and
  `PROGRESS.md`. The Python API, its CLAUDE.md, app/, tests/ stay untouched.
- parseNumeric null-not-NaN; graceful-empty; absolute URLs (never prepend domain);
  agent_stats keys verbatim; server-side fetch only; allowedDevOrigins for LAN/TS
  access.
