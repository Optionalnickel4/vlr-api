# Team identities and Match Wire

Team artwork comes from VLR’s source markup. Team pages, match headers, world rankings, player affiliations, and team/player match history expose logo URLs directly. Regional rankings expose stable team IDs without artwork; match-list cards expose names without team links.

`app.services.team_identity` fills those gaps from data already held in Redis. It uses cached match details first for ordered match sides, then cached world rankings and team/player details. All multi-row lookups use one bounded `MGET`; no renderer scrapes a team page or performs one cache request per row. When enrichment is unavailable, routes return the original valid payload and retain their existing stale, timeout, and refresh behavior.

The API adds aligned `team_ids`, `team_logos`, and `team_short_names` fields to match cards and carries identity fields through rankings, stats, search, team/player details, and trends. Stable IDs remain the primary identity. Exact normalized name lookup is limited to source rows, such as match listings, that provide no team ID.

The frontend normalizes these fields into shared types. `TeamCrest` renders source artwork in fixed hero, card, row, table, and ticker boxes with `object-fit: contain`. Missing or failed artwork uses deterministic initials and colors in the same reserved space. Team names remain visible beside artwork.

Logo-enabled surfaces include the homepage, schedule, results, match headers, map headings, round history, player scoreboards, team recent form/history, player affiliation/history, rankings, stats, player search, and Match Wire. News currently has no structured team identity in its API payload.

Match Wire combines existing live, upcoming, result, ranking, trend, and live-detail loaders in this order:

1. Live matches, capped at four
2. Upcoming matches, capped at four
3. Recent finals, capped at three
4. Ranking movers, capped at two

The client runs one serial refresh every 30 seconds. Failed, stale, malformed, late, or out-of-order responses retain the last valid feed. Items link by stable match/team ID, and dense links disable automatic route prefetch. The moving copy has a noninteractive, screen-reader-hidden duplicate; reduced-motion mode renders one static copy. Manual Pause/Resume, pointer hover, and keyboard focus control motion independently.

Verification covers logo parsing and propagation, batched/failing enrichment, cached pre-logo data, source and broken-image rendering, stable links, feed priority and partial/empty states, stale retention, request ordering, keyboard controls, accessible names, reduced motion, responsive layouts, and production builds. The repository live-selector verifier also checks absolute world-ranking and match-header artwork.
