# Predictions: first release

The v2 implementation adds `/predictions` to the existing valstats frontend and
`GET /api/v1/predictions` to the existing API. It shows a winner lean, a short
explanation, links to team evidence, caveats, pending fixtures, and original
pre-match picks after their scheduled start. No probabilities or score forecasts.

## Generation and records

Past cards show correct/wrong picks, the final score and winning team, or an
awaiting-result label. No-picks remain explicitly unscored. A separate
`prediction_results` table retains final results without rewriting prediction
snapshots. The opt-in scheduler checks three outstanding results every five
minutes, verifying final status, match/team IDs, consistent non-tied series
scores and pre-start generation. Unknown, live, cancelled or inconsistent
results are not graded. Public reads never fetch match pages or call OpenClaw.

The API's `accuracy` counters cover all saved pre-start predictions whose match
start has passed, not only the latest 50 displayed cards. Accuracy is correct
divided by correct plus incorrect; no-picks and awaiting results are excluded.
Final results can appear after the next successful background check. Past
predictions, including abstentions and wrong picks, remain unchanged.

Generation is opt-in (`VLR_PREDICTIONS_ENABLED=false` by default). The existing
scheduler processes at most three candidates every ten minutes. Requests from
the public never trigger a model call. Each failed candidate has a thirty-minute
cooldown so it cannot indefinitely block later fixtures.

Only confirmed team IDs and absolute UTC starts between fifteen minutes and
seven days ahead qualify. Both teams need at least three recorded results
within ninety days. At most five per team are supplied; same-day, future, duplicate
and target-match results are excluded. Completed recent scoreboards supply
verified head-to-head meetings, map results and listed-player ACS, ADR and rating.
Coverage is explicit; results are not opponent-adjusted and do not establish
player availability, the upcoming veto or current patch suitability. The frontend
hides any fixture with a TBD or unknown team.

OpenClaw returns structured JSON. Unknown winners, unsupported evidence references,
missing caveats, probability/score text and malformed output are rejected. The
fixture is fetched again after inference; changed participants, changed starts,
live/started fixtures and expired worker ownership prevent publication.

PostgreSQL `match_predictions` stores the original evidence, answer, UTC start,
generation timestamp, evidence hash, agent ID and prompt version. A unique match
key with `ON CONFLICT DO NOTHING` preserves the first publication. Existing
`init_db` creates the new table during an authorized backend rollout. No production
database changes are additive: the new prediction table only.

## OpenClaw and Access prerequisites

Inspection found OpenClaw 2026.9.8 in Proxmox LXC 152, running its existing gateway.
Its HTTP chat-completions endpoint was initially disabled. Existing agents, including Jarvis,
must remain intact. The dedicated agent ID is `val-predictions`; its workspace
instructions are in `deploy/openclaw/val-predictions/AGENTS.md`.

The proposed additive settings are in
`deploy/openclaw/val-predictions.patch.json`. Merged with a temporary copy of the
existing LXC 152 configuration, they passed the installed OpenClaw validator.
After explicit user approval, these settings were installed with a restricted
rollback copy at `/root/.openclaw/openclaw.pre-vlr-20261008T120825Z.json`.

The agent is now active under canonical `agents.entries`, inherits the configured
provider/model, and denies all tools (`tools.deny: ["*"]`). Its workspace is
`/srv/vlr-predictions/workspace`. It has no messaging-channel binding.

`gateway.http.endpoints.chatCompletions.enabled=true` is active. A dedicated
`vlr-api-predictions` Access service token and application-scoped Service Auth
policy were created on the existing OpenClaw application. The token expires
2027-10-08 at 08:06 EDT. The owner and Jarvis policies remain unchanged.
OpenClaw hot-reloaded the settings; its gateway process remained running without
a restart. An authenticated HTTPS synthetic-evidence request returned HTTP 200
with a valid winner, explanation, references for both teams, and caveats.
Unauthenticated requests returned 401 locally and 403 through Access.

Credentials are stored only in `/srv/vlr-predictions/credentials.json`, root-owned
mode 600 inside a mode-700 directory in LXC 152. No credentials were put in the
repository or displayed. The integration test is synthetic and was not published
as a real match prediction.

The backend sends `Authorization: Bearer <gateway token>` plus the two Access
service-token headers to the HTTPS `/v1/chat/completions` endpoint, with
`model: openclaw/val-predictions`. It does not send a stable user/session ID.
All three credentials remain backend-only, never in `NEXT_PUBLIC_*`, browser code,
API responses, logs or this repository. The gateway token has broad gateway
authority; keep its transport behind Access and its storage restricted.

Environment variables are listed in `.env.example`. Enable predictions only once
the dedicated agent, HTTPS endpoint, Access credentials and backend database are
verified. Authentication failures, redirects, timeouts and invalid responses
leave fixtures pending. Previously saved picks remain available if the schedule
is temporarily unavailable.

## Rollout status

Production rollout preserves the existing pinned backend based on
`c6ba79d21d8d673f8d2b2e2676f9695fbf821550`: apply only this feature's backend
diff over that source, rather than replacing unrelated live stats/Jarvis code
with the older v2 baseline. The release manifest records both the feature commit
and preserved base, plus file hashes. The frontend is built from the feature
commit. Keep rollback copies of the previous launcher, frontend build and env
files outside Git. Reuse the existing secured OpenClaw connection server-side.
Saved preview analyses may be copied into the new production prediction table
without overwriting existing records; their original timestamps remain intact.

The preview now uses `winner-explanation-v3`, with a seven-day pre-match window.
The dedicated OpenClaw agent writes short, natural match previews: a direct pick,
two or three concrete reasons, and a useful counterpoint. Detailed metric counts
remain in the evidence section. Upcoming test analyses can be regenerated only
on explicit request, with original records backed up before replacement; past
records remain unchanged. New analyses supplement recent form
with completed match details from up to five recent series per team (90-day
window). Head-to-head evidence requires matching participant IDs and consistent
results. Named-map records include sample sizes; player ACS, ADR and rating are
unweighted per-map averages for currently listed non-staff, non-inactive players.
All-map aggregates are excluded to avoid double counting. Optional history loads
are capped at ten requests and sixty seconds; missing data is explicitly stated.
Historical maps do not establish the upcoming veto or current patch suitability.

43 focused Linux tests and the preview frontend build passed. A real BBL–Misa
request included twelve BBL maps and seven Misa maps, with player evidence for two
BBL players and five Misa players. No head-to-head meeting was verified in that
sample. Secured OpenClaw returned a validated abstention, citing all six supplied
facts and explaining the conflicting signals and unequal roster coverage. This
diagnostic did not replace the existing immutable published pick; future new
analyses use the richer evidence. Production service processes remained unchanged.

An isolated test build was deployed to LXC 221 with explicit user approval.
The preview is `http://10.0.0.21:3200/predictions`; source and dependencies are
under `/opt/vlr-predictions-preview`. No Git commits or pushes were created.
The production services on ports 3000/8000 retain their original processes.

The preview backend listens only on 127.0.0.1:8200, uses PostgreSQL database
`vlr_predictions_preview` owned by the separate `vlr_preview` role, and a separate
Redis service on 127.0.0.1:6381. Server credentials are in the root-owned mode-600
`/etc/vlr-predictions-preview.env`. They were transferred between LXCs through
Proxmox without displaying them or copying the SSH private key off the desktop.

Services: `vlr-preview-api`, `vlr-preview-frontend`, `vlr-preview-redis`, plus
`vlr-preview-refresh.timer`. The timer requests the live API upcoming endpoint
each minute, with inference bounded to every ten minutes. Match and team evidence
come directly from live `/match/{id}` and `/team/{id}` API endpoints, bypassing
the preview detail caches. The live match API lacks absolute UTC starts, so the
original VLR page supplies only that missing timestamp after identity/status
verification. Stale API evidence is rejected. The preview frontend uses the live
API on port 8000 for all ordinary data and the isolated API on port 8200 only for
saved prediction records. The preview's general scraping scheduler is disabled. Its isolated-only
runner is `scripts/predictions_preview_refresh.py`.

The first end-to-end run saved two actual match analyses, for NRG–LOUD and
G2 Esports–Team Vitality. Both correctly abstained because the supplied recent
records were even; the browser displays their explanations and evidence.

To stop the test build, stop `vlr-preview-refresh.timer`,
`vlr-preview-refresh.service`, `vlr-preview-frontend.service`,
`vlr-preview-api.service`, and `vlr-preview-redis.service`. This leaves test
storage intact and does not affect production. Proxmox access uses
`codex-proxmox` with passwordless `sudo -n pct exec 221`.
