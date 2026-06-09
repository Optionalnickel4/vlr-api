"""Static, committed project metadata for the status dashboard (Phase 6).

This is the versioned source of truth that ships with the code. It is NOT computed
at runtime — bump the constants in the same commit that earns them. PROGRESS.md
mirrors these counts; keep the two in sync.
"""

# Short sha of the release this build corresponds to. Bump per release.
COMMIT = "1d22037"

# Committed constant — do NOT compute at runtime. Bump when you add tests.
TESTS_PASSING = 58

# Where this is deployed (already-public LXC ip; no secrets here).
DEPLOY = {"lxc": 289, "host": "192.168.1.35"}

PHASES = [
    {"n": 1, "name": "league listings",  "desc": "results, upcoming/live, rankings, events, news + history", "shipped": True},
    {"n": 2, "name": "player detail",     "desc": "on-demand fetch + PlayerSnapshot history",                 "shipped": True},
    {"n": 3, "name": "team detail",       "desc": "on-demand fetch + TeamSnapshot history",                   "shipped": True},
    {"n": 4, "name": "team trends",       "desc": "rating trend joined with results",                         "shipped": True},
    {"n": 5, "name": "results backfill",  "desc": "team-page results into match_results, id-join",            "shipped": True},
    {"n": 6, "name": "status dashboard",  "desc": "this page",                                                "shipped": True},
]

# History tables surfaced on the status page, in display order.
HISTORY_TABLES = ["match_results", "ranking_snapshots", "player_snapshots", "team_snapshots"]

# Registered APScheduler job ids (must match app/jobs/scheduler.py exactly).
JOBS = ["upcoming", "results", "news", "events", "rankings"]
