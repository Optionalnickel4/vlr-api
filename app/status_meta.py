"""Static, committed project metadata for the status dashboard (Phase 6).

This is the versioned source of truth that ships with the code. It is NOT computed
at runtime — bump the constants in the same commit that earns them. PROGRESS.md
mirrors these counts; keep the two in sync.
"""

# Short sha of the release this build corresponds to. Bump per release.
COMMIT = "phase13"

# Committed constant — do NOT compute at runtime. Bump when you add tests.
TESTS_PASSING = 169

# Where this is deployed (already-public LXC ip; no secrets here).
DEPLOY = {"lxc": 289, "host": "192.168.1.35"}

PHASES = [
    {"n": 1, "name": "league listings",  "desc": "results, upcoming/live, rankings, events, news + history", "shipped": True},
    {"n": 2, "name": "player detail",     "desc": "on-demand fetch + PlayerSnapshot history",                 "shipped": True},
    {"n": 3, "name": "team detail",       "desc": "on-demand fetch + TeamSnapshot history",                   "shipped": True},
    {"n": 4, "name": "team trends",       "desc": "rating trend joined with results",                         "shipped": True},
    {"n": 5, "name": "results backfill",  "desc": "team-page results into match_results, id-join",            "shipped": True},
    {"n": 6, "name": "status dashboard",  "desc": "this page",                                                "shipped": True},
    {"n": 7, "name": "match detail",      "desc": "rich /match/{id} endpoint — header/maps/scoreboards/round timeline", "shipped": True},
    {"n": 8, "name": "player trends",     "desc": "rating/ACS trend over PlayerSnapshot history (rounds-weighted)", "shipped": True},
    {"n": 9, "name": "player pre-scrape", "desc": "twice-daily job banks PlayerSnapshots for next-48h match players (cache-gated)", "shipped": True},
    {"n": 10, "name": "player search",    "desc": "GET /players?q= — DB-first over snapshots, VLR autocomplete fallback on a miss (cached)", "shipped": True},
    {"n": 11, "name": "live auto-refresh", "desc": "30s job re-scrapes live match detail + status-aware short TTL; page polls while live", "shipped": True},
    {"n": 12, "name": "stats leaderboard", "desc": "HLTV-style player rankings — VLR R2.0 headline; 6h scheduled scrape of na/eu × 4 windows into cache; GET /stats", "shipped": True},
    {"n": 13, "name": "dimension-split rating", "desc": "Firepower/Entry/Consistency/Clutch as 0-100 cohort percentiles; GET /players/{id}/dimensions; radar + bars on player page", "shipped": True},
]

# History tables surfaced on the status page, in display order.
HISTORY_TABLES = ["match_results", "ranking_snapshots", "player_snapshots", "team_snapshots"]

# Registered APScheduler job ids (must match app/jobs/scheduler.py exactly).
JOBS = ["upcoming", "live_matches", "results", "news", "events", "rankings", "player_prefetch", "stats"]
