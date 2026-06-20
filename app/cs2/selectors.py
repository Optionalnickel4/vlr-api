"""ALL hltv.org CSS selectors live here.

When HLTV changes its markup, this is the ONLY file you should need to edit.
Verify against live pages with: python -m app.cs2.verify (added in Phase B's
deferred items; for now, the live-network tests in tests/cs2/test_http.py
plus the integration tests against saved fixtures are the verification path).

Selectors were discovered by probing live HLTV /results on 2026-06-20 with
cloudscraper + the real Chrome UA. The HTML at the time of discovery used
104 <div class="result-con"> blocks per page, each with this shape:

    <div class="result-con" data-zonedgrouping-entry-unix="1781985905000">
      <a href="/matches/2395001/spirit-vs-falcons-iem-cologne-major-2026"
         class="a-reset">
        <div class="result">
          <table>
            <tr>
              <td class="team-cell">
                <div class="line-align team1">
                  <div class="team ">Spirit</div>
                  <img ... class="team-logo day-only" title="Spirit">
                  <img ... class="team-logo night-only" title="Spirit">
                </div>
              </td>
              <td class="result-score">
                <span class="score-lost">1</span> -
                <span class="score-won">2</span>
              </td>
              <td class="team-cell">
                <div class="line-align team2">
                  <img ... class="team-logo" title="Falcons">
                  <div class="team team-won">Falcons</div>
                </div>
              </td>
              <td class="event">
                <img ... class="event-logo day-only" title="IEM Cologne Major 2026">
                <img ... class="event-logo night-only" title="IEM Cologne Major 2026">
                <span class="event-name">IEM Cologne Major 2026</span>
              </td>
              <td class="star-cell">
                <div class="map-and-stars">
                  <div class="stars">
                    <i class="fa fa-star star"></i> x4
                  </div>
                  <div class="map map-text">bo3</div>
                </div>
              </td>
            </tr>
          </table>
        </div>
      </a>
    </div>

Conventions mirror app/scrapers/selectors.py:
- All constants are uppercase module-level strings.
- The selector file owns ONLY the CSS — parsing lives in app/cs2/*.py.
- Comments explain non-obvious quirks (label-bleed guards, sibling-vs-child
  distinctions, what each span score class means).
"""

# --- /results page (results list, 104 blocks at the time of discovery) ---

# Top-level container per result row. data-zonedgrouping-entry-unix is the
# unix-ms timestamp of when the match STARTED (not when the result was
# posted). Some blocks had it missing in early HTML; the parser falls back
# to "no timestamp" rather than guessing.
RESULTS_ROW = "div.result-con"

# The href on the inner anchor gives us the match ID and the slug. The slug
# is informational only (e.g. "spirit-vs-falcons-iem-cologne-major-2026") —
# the integer segment after /matches/ is the canonical ID.
RESULTS_MATCH_LINK = "a.a-reset"

# Team names: td.team-cell .team, first is team1, second is team2.
# `.team-won` marks the winner — we use it to record who won, not just the
# numeric score. NB: the .team element is INSIDE .line-align.team1/.team2;
# don't use `.team ` (with trailing space) on a hypothetical combined
# selector that could match `<div class="team-something">`.
RESULTS_TEAM_CELL = "td.team-cell"
RESULTS_TEAM_NAME = ".team"
RESULTS_WINNER_CLASS = "team-won"

# Score cell: <td class="result-score"><span class="score-lost">1</span> -
# <span class="score-won">2</span>. The two spans are siblings, NOT nested;
# the literal " - " between them is whitespace + hyphen + whitespace. We
# read both spans and treat them as ordered (lost, won). We don't rely on
# the "lost"/"won" classes for the values themselves — those just style the
# span; the numeric text inside is what we want.
RESULTS_SCORE_CELL = "td.result-score"
RESULTS_SCORE_SPAN = "span"  # inside .result-score; use css_first/css_last

# Event name: td.event .event-name. The td also has event-logo <img>s with
# title attributes matching the event name; the .event-name <span> is the
# canonical text node.
RESULTS_EVENT_NAME = "td.event .event-name"

# Format (bo1, bo3, bo5): div.map.map-text. The .map class is overloaded —
# it ALSO appears on per-map <div>s deeper in match detail pages, but on
# /results it always holds the format string. Selector chain pinpoints both
# classes to avoid catching unrelated .map nodes.
RESULTS_FORMAT = "div.map.map-text"

# HLTV user-assigned importance: number of <i class="star"> icons inside
# .stars. 0-5 stars; absent div means 0.
RESULTS_STARS_CONTAINER = "div.stars"
RESULTS_STAR = "i.star"

# --- /matches page (upcoming matches) — DISCOVERED 2026-06-20 ---

# Outer wrapper per day-group (data-zonedgrouping-entry-unix is the day start).
# We don't use this for splitting today/tomorrow; we just read the timestamp
# to backfill matches that lack a per-match unix attribute.
UPCOMING_ZONE = "div.match-zone-wrapper"

# Each individual match. The data-* attributes are HLTV's source of truth:
#   data-match-id  : int, the canonical HLTV match id
#   data-stars     : int 0-5, HLTV importance rating
#   data-event-id  : int, the event this match belongs to (cross-reference to events.py)
#   data-region    : "Europe" | "North America" | "South America" | "Asia" | "Oceania" | etc.
#   data-eventtype : "ranked" | "lan" | "online"
#   live           : "true" | "false" — the only reliable live-marker we found
#                    (per-wrapper; there were 0 with live="true" in the snapshot
#                    because no matches were live at capture time)
#   team1, team2   : HLTV team IDs (string). Useful for cross-referencing the
#                    team profile route.
UPCOMING_MATCH = "div.match-wrapper"
# Live marker is the `live` attribute on the wrapper, NOT a CSS class. The
# parser reads it via attribute lookup, not via this CSS selector. We keep
# the constant as documentation of where the value lives.
UPCOMING_LIVE_ATTR = "live"

# Two anchors per match:
#   - the time/meta anchor (class="match-info a-reset") carries time + format
#   - the teams anchor (class="match-teams a-reset") carries the two team names
# We use a single href selector and read both anchors via position.
UPCOMING_TIME_ANCHOR = "a.match-info"
UPCOMING_TEAMS_ANCHOR = "a.match-teams"
# Fallback selector if the classes change: any anchor whose href starts with /matches/.
# We prefer the class-based selectors above (more specific) and fall back to this.
UPCOMING_MATCH_LINK = "a[href^='/matches/']"

# Inside the time/meta anchor:
UPCOMING_TIME = "div.match-time"  # data-unix (ms), data-time-format ("HH:mm")
UPCOMING_FORMAT = "div.match-meta"  # text content is "bo1" | "bo3" | "bo5"

# Inside the teams anchor:
UPCOMING_TEAM_NAME = "div.match-teamname"
UPCOMING_TEAM_CELL = "div.match-team"

# Event: each match has an event link elsewhere in its zone-group with an
# <img alt="..."> whose alt is the event name. We don't link per-match (the
# HLTV markup doesn't carry it on every match-wrapper), so we expose the
# event_id from data-event-id and let the frontend cross-reference via the
# events cache. v2 can join per-match event names once HLTV exposes them
# on every wrapper.
UPCOMING_STAGE = "div.match-stage"  # "Semifinal", "Group A Winners' Match", etc.

# --- shared (both pages) ---
# /matches/{id} canonical page for a single match — used to build absolute URLs.
# IMPORTANT: HLTV returns 404 for /matches/{id} alone; the slug is REQUIRED.
# See fixtures/match_2395001.html — the working URL was
# /matches/2395001/spirit-vs-falcons-iem-cologne-major-2026
MATCH_PATH_PREFIX = "/matches/"