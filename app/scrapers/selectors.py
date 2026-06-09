"""ALL vlr.gg CSS selectors live here.

When vlr.gg changes its markup, this is the ONLY file you should need to edit.
Verify against live pages with: python -m app.scrapers.verify
"""

# --- results / matches list (a.match-item cards) ---
MATCH_CARD = "a.match-item"
MATCH_TIME = "div.match-item-time"
MATCH_TEAMS = "div.match-item-vs-team-name, div.match-item-vs div.text-of"
MATCH_SCORES = "div.match-item-vs-team-score, div.js-spoiler"
MATCH_EVENT = "div.match-item-event"
MATCH_EVENT_SERIES = "div.match-item-event-series"
MATCH_STATUS = "div.ml-status, span.ml-status"
MATCH_ETA = "div.ml-eta"

# --- rankings (team rows) ---
# vlr now renders rankings as <table class="wf-faux-table mod-teams"> with one
# <tr class="wf-card mod-hover"> per team; the team-name <td> wraps the country
# div, so the parser strips the country suffix off the team name.
RANK_ROW = "div.rank-item, tr.rank-item, tr.wf-card.mod-hover"
RANK_NUM = "div.rank-item-rank-num, td.rank-item-rank"
RANK_TEAM_NAME = "div.rank-item-team-name, div.ge-text, td.rank-item-team a div"
RANK_COUNTRY = "div.rank-item-team-country"
RANK_RATING = "div.rank-item-rating, td.rank-item-rating"
RANK_RECORD = "div.rank-item-record"
RANK_EARNINGS = "div.rank-item-earnings"

# --- events list ---
# each desc-item (prize/dates) nests a label div ("Prize Pool", "Dates") that
# the parser strips off so the value text doesn't get the label concatenated.
EVENT_CARD = "a.event-item"
EVENT_TITLE = "div.event-item-title"
EVENT_STATUS = "span.event-item-desc-item-status"
EVENT_PRIZE = "div.event-item-desc-item.mod-prize"
EVENT_DATES = "div.event-item-desc-item.mod-dates"
EVENT_DESC_LABEL = "div.event-item-desc-item-label"
EVENT_REGION = "div.event-item-desc-item.mod-location i"

# --- news ---
# vlr news rows are <a class="wf-module-item"> with inline-styled (class-less)
# title/desc divs; only the meta line keeps a class (ge-text-light).
NEWS_ITEM = "a.wf-module-item, a.news-item"
NEWS_TITLE = 'div.news-item-title, div[style*="font-weight: 700"]'
NEWS_DESC = 'div.news-item-desc, div[style*="font-size: 13px"]'
NEWS_DATE = "div.news-item-meta, div.ge-text-light"

# --- team detail page (/team/{id}/{slug}) ---
# header
TEAM_NAME = "div.team-header-name h1, h1.wf-title"
TEAM_TAG = "div.team-header-name h2.team-header-tag, h2.wf-title.team-header-tag"
TEAM_LOGO = "div.team-header-logo img"
TEAM_COUNTRY = "div.team-header-country"  # text node; the flag <i> is empty so no bleed
TEAM_COUNTRY_FLAG = "div.team-header-country i.flag"
# self-id lives in the active nav tab: /team/2/sentinels/
TEAM_SELF_LINK = "a.wf-nav-item.mod-active"
# roster: items are grouped under "players" / "staff" wf-module-labels inside one
# wf-card; document-order traversal of that card assigns each item to its section.
TEAM_ROSTER_ITEM = "div.team-roster-item"
TEAM_ROSTER_SECTION = "div.wf-module-label"  # "players" | "staff" -> drives is_staff
TEAM_ROSTER_LINK = 'a[href^="/player/"]'
TEAM_ROSTER_ALIAS = "div.team-roster-item-name-alias"
TEAM_ROSTER_REAL = "div.team-roster-item-name-real"
TEAM_ROSTER_ROLE = "div.team-roster-item-name-role"  # absent for active players
TEAM_ROSTER_FLAG = "div.team-roster-item-name-alias i.flag"
TEAM_ROSTER_CAPTAIN = "i.fa-star"  # team-captain marker inside the alias node
# match cards: recent results + upcoming share a.m-item; per-map expandable sub-rows
# carry the extra `m-item-games-item` class and are filtered out by the parser.
TEAM_MATCH_CARD = "a.m-item"
TEAM_MATCH_GAME_ROW_CLASS = "m-item-games-item"
# event name sits in an inner div.text-of; the descendant combinator skips the
# series/stage text that trails it in the same container (label-bleed guard).
TEAM_MATCH_EVENT = "div.m-item-event div.text-of"
TEAM_MATCH_OPPONENT = "div.m-item-team.mod-right span.m-item-team-name"
TEAM_MATCH_RESULT = "div.m-item-result"
TEAM_MATCH_DATE = "div.m-item-date"

# --- player detail page (/player/{id}/{slug}) ---
# header
PLAYER_ALIAS = "h1.wf-title"
PLAYER_REAL = "h2.player-real-name"
PLAYER_COUNTRY_FLAG = "div.player-header i.flag"
# self-id lives in the timespan filter buttons: /player/9/tenz/?timespan=30d
PLAYER_SELF_LINK = "a.player-stats-filter-btn"
# current team = the first team module-item on the page; name sits in a 500-weight div
PLAYER_TEAM = 'a.wf-module-item[href^="/team/"]'
PLAYER_TEAM_NAME = 'div[style*="font-weight: 500"]'
# per-agent stats table (header titles drive the stat keys, agent name = img alt)
PLAYER_STATS_TABLE = "div.wf-card.mod-table table.wf-table"
PLAYER_STATS_HEADER = "thead th"
PLAYER_STATS_ROW = "tbody tr"
PLAYER_STATS_CELL = "td"
PLAYER_AGENT_IMG = "img"
# recent match history cards
PLAYER_MATCH_CARD = "a.m-item"
PLAYER_MATCH_EVENT = "div.m-item-event div.text-of"
PLAYER_MATCH_TEAM_NAME = "span.m-item-team-name"
PLAYER_MATCH_OPPONENT = "div.m-item-team.mod-right span.m-item-team-name"
PLAYER_MATCH_RESULT = "div.m-item-result"

# id is parsed from href like /310/sentinels or /player/4164/...
HREF_ID_INDEX = 1  # path segment index for numeric id
