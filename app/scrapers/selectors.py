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

# --- team page ---
TEAM_NAME = "div.team-header-name h1, h1.wf-title"
TEAM_TAG = "div.team-header-name h2, h2.wf-title.team-header-tag"
TEAM_ROSTER = "div.team-roster-item"
TEAM_ROSTER_ALIAS = "div.team-roster-item-name-alias"
TEAM_ROSTER_REAL = "div.team-roster-item-name-real"

# --- player page ---
PLAYER_NAME = "h1.wf-title"
PLAYER_REAL = "h2.player-real-name"
PLAYER_TEAM = "div.wf-card a.wf-module-item"

# id is parsed from href like /310/sentinels or /player/4164/...
HREF_ID_INDEX = 1  # path segment index for numeric id
