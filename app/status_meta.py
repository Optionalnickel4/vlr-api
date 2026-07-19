"""Project metadata for the status dashboard (Phase 6).

Phase/test counts are the versioned source of truth that ships with the code —
bump them in the same commit that earns them (PROGRESS.md mirrors these counts;
keep the two in sync). COMMIT and DEPLOY are resolved once at process start so
they always report the machine and checkout actually serving the page.
"""
import socket
import subprocess
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _git_short_commit() -> str:
    """Short sha of the running checkout; never raises (the status page must not 500)."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        sha = out.stdout.strip()
        if out.returncode == 0 and sha:
            return sha
    except Exception:
        pass
    return "unknown"


# Resolved once at import — no per-request shell-outs.
COMMIT = _git_short_commit()

# Committed constant — do NOT compute at runtime. Bump when you add tests.
TESTS_PASSING = 178

# Where this is running (hostname of the serving machine; no secrets here).
DEPLOY = {"hostname": socket.gethostname()}

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
