# Project review and redesign direction

Reviewed September 26, 2026. Scope: repository architecture, frontend routes and
components, cache/scheduler behavior, existing tests, and the saved match-detail
screenshot. This is a code-based assessment, not a live browser or production
performance audit. No application behavior changed during this review.

## Product direction

The requested direction combines a clean esports dashboard, dense sports
analytics, and editorial coverage. The existing “ESPN for Valorant” vision fits:
lead with matches, explain performance with data, and give news its own presence.

Keep the existing API, historical data, and useful normalization layer. The
strongest differentiators are trends, form, rating dimensions, and curated match
context. Make those easier to discover alongside scores.

## Verified baseline

- Backend: 207 tests passed; one Starlette/httpx deprecation warning.
- Frontend: 202 tests passed across 14 files. Several tests emit React `act`
  warnings; passing results do not establish complete interaction coverage.
- ESLint and TypeScript (`tsc --noEmit`) passed.
- No production build, production service changes, or browser checks performed.

## Engineering priorities

| Priority | Finding and evidence | Proposed improvement |
| --- | --- | --- |
| High | Default rankings TTL is one hour and events TTL is 30 minutes (`app/core/config.py`); both jobs run every six hours (`app/jobs/scheduler.py`). `_cached_or_refresh` in `app/api/v1/routes.py` scrapes on misses. | Separate freshness from retention. Serve the last successful payload with freshness metadata while refreshing in the background; coalesce concurrent refreshes. Test expired data and upstream failure. |
| High | `LiveMatches.tsx` accepts any parsed response without checking HTTP status, response shape, or the error envelope. A loader failure returns an empty array, replacing good scores. | Retain last successful data on failure, mark it stale, and distinguish a successful empty live list from an outage. Bound requests and avoid overlapping polls. |
| High | `fetchUpstream` in `frontend/src/lib/vlr.ts` has no explicit timeout. The homepage awaits all six loaders, including stream discovery and Twitch calls. | Add request deadlines and let secondary sections load independently so optional content does not delay match coverage. |
| Medium | `PlayerSearch.tsx` debounces input but does not cancel in-flight requests or ignore old responses. An older query can overwrite newer results or reopen a cleared dropdown. | Cancel obsolete requests, guard result ordering, and clean up timers. Add delayed-response regression coverage. |
| Medium | Search advertises a combobox/listbox but lacks selectable option semantics and arrow-key navigation. The primary nav and fixed-width search share a non-wrapping inner row. | Complete keyboard behavior and build a deliberate mobile navigation/search layout; validate with a real browser. |
| Medium | Main listing pages use `SiteHeader`, while match/team/player pages implement their own headers. Page widths vary and navigation disappears on detail pages. | Create a consistent site shell, persistent navigation, breadcrumbs, and route-specific content widths. |
| Medium | `globals.css` uses an unlayered global anchor color, which can override Tailwind color utilities. Reduced-motion handling stops the ticker but not the LIVE pulse. | Put base styles in the appropriate layer; verify link states, contrast, focus visibility, and reduced motion across components. |
| Medium | `frontend/FEATURES.md` still calls news, player detail, and player trends unbuilt despite their implementation. Route comments claim lists never scrape, contradicting the cold-cache helper. | Update documentation against the actual behavior and maintain one current backlog. |

These are source-confirmed implementation concerns. Production severity and
visual overflow still need runtime measurement. Changing API envelopes should
preserve existing consumers or use an explicit migration path.

## UI overhaul brief

### Shared visual language

- Deep charcoal surfaces with clear separation and higher-contrast secondary text.
- Restrained teal branding; reserve status colors for meaningful states.
- Bold condensed headings for sporting identity, readable body text, and tabular
  numbers for scores. Avoid tiny uppercase labels for essential information.
- Consistent spacing, borders, controls, loading states, and keyboard focus.
- Team crests and available player imagery for identity; use honest fallbacks.
  Editorial images require a usable source and should not imply fabricated news.

### Homepage: coverage and discovery

1. Consistent navigation and prominent search.
2. Lead match area using actual live matches, with a next-match fallback.
3. Compact upcoming/results coverage with obvious routes to full lists.
4. A distinct news area: lead headline plus secondary stories, using the existing
   feed rather than invented editorial content.
5. Visible performance context: rankings, form, and notable performances with
   links into the existing analysis pages.
6. Secondary watch-live content that loads without delaying the main coverage.

Use a wider desktop main column and supporting rail; deliberately reorder for
mobile. Avoid making every section another equally weighted dark panel.

### Match, team, and player pages: analysis

- Match: stronger team identity and score hierarchy, clear series versus map
  scores, readable map controls, and accessible round history and scoreboards.
- Team: identity, recent form, rating movement, roster, and results in that order.
- Player: identity and headline stats, trend and rating dimensions, then detailed
  agent statistics and match history.
- Dense tables retain aligned numeric columns, meaningful sorting, and usable
  small-screen overflow. Freshness and sample size remain visible where relevant.

## Delivery sequence

1. Repair freshness, polling, timeout, and search-race behavior with focused tests.
2. Build the shared shell and design primitives, then redesign the homepage as
   the first complete desktop/mobile example of the combined direction.
3. Apply the system to match, player, and team pages, preserving analytics.
4. Finish schedule, results, rankings, stats, and news; reconcile the backlog.
5. Verify with a production build and browser checks for mobile, desktop,
   keyboard navigation, reduced motion, slow responses, missing data, and errors.

Success means faster access to live coverage, clearer analytical context,
consistent navigation, legible mobile screens, and graceful handling of stale
data—not simply a new palette.
