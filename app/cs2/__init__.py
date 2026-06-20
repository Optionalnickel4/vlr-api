"""CS2 (HLTV.org) second-game integration.

Parallel package to app/scrapers/ — owns its own HTTP client, selectors,
parsers, and capture script. The two packages never share code at the
scraper/parser level; they share only infrastructure (app/core/cache.py,
app/core/db.py, app/jobs/run*.py, app/api/v1/*).

Per FEATURES.md: "Architecture should not actively prevent a second game,
but do not abstract for it prematurely. A second game = a new scraper
targeting its source with its own selectors feeding the SAME patterns,
not a rewrite."

v1 scope (locked 2026-06-20):
    results, upcoming, live, rankings, events, news,
    team profile (high-level), player profile (header only),
    match detail (high-level — no per-map scoreboards)

v2 deferred:
    per-player stats tables (needs nodriver cookie-refresh machinery),
    per-map scoreboards, live in-play websocket updates,
    the nodriver+grab_cf.py flow itself
"""