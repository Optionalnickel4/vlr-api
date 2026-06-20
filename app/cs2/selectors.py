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

# --- /matches page (upcoming matches) — DISCOVERED BUT NOT YET PARSED ---

# Discovered structure (Phase B only parses /results; /matches parser is
# Phase B-2):
#   div.match-zone-wrapper[data-zonedgrouping-entry-unix="..."]
#     div.match-wrapper[data-match-id][data-stars][data-match-link]
#       a[href^="/matches/"] containing:
#         div.team (two, ordered)
#         div.match-time[data-unix][data-time-format]
#         div.match-meta (format like "bo3")
#         span.event-name (from a sibling plausible-event-name anchor)
UPCOMING_ZONE = "div.match-zone-wrapper"
UPCOMING_MATCH = "div.match-wrapper"
UPCOMING_MATCH_LINK = "a[href^='/matches/']"
UPCOMING_TIME = "div.match-time"
UPCOMING_FORMAT = "div.match-meta"

# --- shared (both pages) ---
# /matches/{id} canonical page for a single match — used to build absolute URLs.
MATCH_PATH_PREFIX = "/matches/"