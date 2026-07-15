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
# vlr serves TWO ranking layouts and the parser handles both:
#  - WORLD view (/rankings, ?region=all): a stripped <tr class="wf-card mod-hover">
#    table with only rank / team(+country) / rating (mod-world). NO W/L record —
#    record/wins/losses are legitimately null here (the column was removed).
#  - REGIONAL view (/rankings/<full-region-slug>, e.g. /rankings/north-america):
#    the rich <div class="rank-item wf-card"> rows that DO carry the W/L record,
#    streak, and earnings. The team text nests a #tag + the country div, so the
#    parser strips the country suffix off the team name.
RANK_ROW = "div.rank-item, tr.rank-item, tr.wf-card.mod-hover"
RANK_NUM = "div.rank-item-rank-num, td.rank-item-rank"
RANK_TEAM_NAME = "div.rank-item-team-name, div.ge-text, td.rank-item-team a div"
RANK_COUNTRY = "div.rank-item-team-country"
RANK_RATING = "div.rank-item-rating, td.rank-item-rating"
# The W/L record is "wins–losses" (en-dash) text in div.rank-item-record. There are
# TWO per regional row — the FIRST is the current/rating-window record, the second
# is all-time; css_first() takes the current one. This is the SUMMARY node, distinct
# from the per-match mod-win/mod-loss dots (rank-item-matches-dt) — never read those,
# they'd concatenate into a silently-wrong number.
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
# opponent team link, when the card exposes one (the card itself is an <a> to the
# match, so a nested team <a> is often absent — opponent_id is null in that case).
TEAM_MATCH_OPPONENT_LINK = 'div.m-item-team.mod-right a[href*="/team/"]'
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
# vlr's 2026 stats-page rewrite dropped the `mod-table` container class and
# renamed the table class wf-table -> st-table (confirmed live 2026-07-14).
PLAYER_STATS_TABLE = "div.wf-card.mod-dark table.st-table"
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

# --- match detail page (/{match_id}/...) — scoreboard (Phase 7) ---
# The per-map scoreboards are <table class="wf-table-inset mod-overview"> — there
# are 8 (per-map × per-team + the all-maps aggregate). This is NOT the player-page
# PLAYER_STATS_TABLE. Header row drives the stat columns:
#   ['', '', 'R','ACS','K','D','A','+/–','KAST','ADR','HS%','FK','FD','+/–']
MATCH_SB_TABLE = "table.wf-table-inset.mod-overview"
MATCH_SB_HEADER = "thead th"
MATCH_SB_ROW = "tbody tr"
MATCH_SB_CELL = "td"
# identity: name nests a 700-weight div.text-of (alias) + a div.ge-text-light (team
# tag); a flag <i> carries the country; the <a> carries the player id.
MATCH_SB_PLAYER = "td.mod-player"
MATCH_SB_PLAYER_LINK = 'a[href^="/player/"]'
MATCH_SB_PLAYER_ALIAS = "div.text-of"
MATCH_SB_PLAYER_TEAM = "div.ge-text-light"
MATCH_SB_PLAYER_FLAG = "i.flag"
MATCH_SB_AGENT = "td.mod-agents img"  # agent name = img alt
# CRITICAL: every value cell is td.mod-stat and holds THREE side-split spans —
# mod-both (combined), mod-t (attack), mod-ct (defense). Read mod-both; NEVER
# td.text(), which concatenates all three into a silently-wrong number (e.g. K=13
# renders raw as "1385"). mod-t/mod-ct are real attack/defense data, not artifacts.
MATCH_SB_STAT_CELL = "td.mod-stat"
MATCH_SB_VAL_BOTH = "span.mod-both"
MATCH_SB_VAL_T = "span.mod-t"
MATCH_SB_VAL_CT = "span.mod-ct"
# the two '+/–' headers collide; disambiguate the diff cells by these class markers
MATCH_SB_CLS_KD_DIFF = "mod-kd-diff"
MATCH_SB_CLS_FK_DIFF = "mod-fk-diff"
# the % columns whose values go through parse_percent
MATCH_SB_PCT_KEYS = ("KAST", "HS%")

# --- match detail: header / maps / rounds (the rich page shape) ---
# header: event link wraps a bold event-name div + a series/stage div
MATCH_H_EVENT_LINK = "a.match-header-event"
MATCH_H_EVENT_NAME = 'a.match-header-event div[style*="font-weight: 700"]'
MATCH_H_SERIES = "div.match-header-event-series"
# the two team links carry the team id (href) + mod-1/mod-2 ordering
MATCH_H_TEAM_LINK = "a.match-header-link"
MATCH_H_TEAM_NAME = "div.match-header-link-name div.wf-title-med"
# series score: the spoiler holds "2:1"; vs-note holds status ("final"/"live") + "Bo3"
MATCH_H_SCORE_SPOILER = "div.match-header-vs-score .js-spoiler"
MATCH_H_VS_NOTE = "div.match-header-vs-note"
MATCH_H_VETO = "div.match-header-note"
# per-map game containers (one per map + an aggregate with data-game-id="all")
MATCH_GAME = "div.vm-stats-game"
MATCH_GAME_ALL_ID = "all"  # the aggregate game's data-game-id
MATCH_NAV_ITEM = "div.vm-stats-gamesnav-item"  # data-game-id -> "1Pearl" etc.
MATCH_GAME_MAP = "div.map"  # text like "PearlPICK37:17"; carries the PICK marker
MATCH_GAME_HEADER_SCORE = "div.vm-stats-game-header div.score"
MATCH_GAME_HEADER_TEAM = "div.vm-stats-game-header div.team-name"
MATCH_GAME_PICK_TOKEN = "PICK"  # presence in the .map text => a team-picked map
# round timeline: one row of square-cols per map; each col = a round
MATCH_RND_ROW = "div.vlr-rounds-row"
MATCH_RND_COL = "div.vlr-rounds-row-col"
MATCH_RND_NUM = "div.rnd-num"  # absent on the team-label col -> skip that col
MATCH_RND_SQ = "div.rnd-sq"  # two per col: [team1, team2]; the winner carries mod-win
MATCH_RND_IMG = "img"  # win-condition icon: /round/elim|boom|defuse|time.webp

# --- match detail: Twitch stream channels (rides the same match-page fetch) ---
# The streams strip lists one .match-streams-btn per broadcast. The embeddable
# Twitch entries carry .mod-embed AND a data-site-id on the inner embed div = the
# bare Twitch login (e.g. "valorant_br"). Non-Twitch platforms (YouTube/SOOP/
# CHZZK/Bilibili/...) are plain anchors with NO data-site-id and are skipped. The
# external link (twitch.tv/<handle>) is a redundant clean source used as a fallback
# only if data-site-id is ever absent on a mod-embed entry.
MATCH_STREAM_BTN = "div.match-streams-container div.match-streams-btn.mod-embed"
MATCH_STREAM_EMBED = "div.match-streams-btn-embed[data-site-id]"  # only entries with the attr
MATCH_STREAM_SITE_ID = "data-site-id"  # attribute on the embed div = Twitch login
MATCH_STREAM_EXTERNAL = "a.match-streams-btn-external"  # href fallback: twitch.tv/<handle>
MATCH_STREAM_TWITCH_HOST = "twitch.tv"  # host guard for the external-href fallback

# --- stats leaderboard page (/stats?region={na|eu}&timespan={30d|60d|90d|all}) ---
# (Phase 12) VLR's region-wide player leaderboard — ONE table (table.st-table,
# confirmed live 2026-07-14 post-rewrite). Header titles drive the stat keys
# (like the player-page agent table) so a new vlr column just falls through.
# Confirmed columns (recon): Player, Agents, Maps, Rnd, R, ACS, K:D, KAST, ADR,
# KPR, APR, FK:FD, FKPR, FDPR, HS%, CL%, CL, KMAX, K, D, A, FK, FD. R is VLR's
# own rating at 100% fill — the headline (we never compute a composite).
STATS_TABLE = "table.st-table"
STATS_HEADER = "thead th"
STATS_ROW = "tbody tr"
STATS_CELL = "td"
# the player identity cell carries the /player/{id} link + the alias in a text-of
# div. The team abbreviation ("SEN", "FLCV") lives in a SIBLING div, class
# st-pl-country (a misnomer — it holds the team tag, not a country, on the
# /stats page; confirmed live 2026-07-14). Read alias and team SEPARATELY from
# their own selectors; never read raw cell text (it would concatenate alias+team
# into "slowlyTYL"). Detected by header=="Player" OR the mod-player class as a
# belt-and-suspenders guard.
STATS_PLAYER_CELL_CLASS = "mod-player"
STATS_PLAYER_LINK = 'a[href^="/player/"]'
STATS_PLAYER_ALIAS = "div.text-of"
STATS_PLAYER_TEAM = "div.st-pl-country"
# CRITICAL: stat value cells side-split into spans (mod-both = combined, mod-t =
# attack, mod-ct = defense), exactly like the match scoreboard. Read mod-both;
# NEVER raw td.text() (it concatenates the three spans into a silently-wrong
# number). Cells with no split just hold plain text (the fallback handles both).
STATS_VAL_BOTH = "span.mod-both"

# id is parsed from href like /310/sentinels or /player/4164/...
HREF_ID_INDEX = 1  # path segment index for numeric id
