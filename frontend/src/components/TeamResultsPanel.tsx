import type { ApiResponse, TeamTrend } from "@/types/vlr";
import Link from "next/link";
import { captureDate } from "./TeamTrendPanel";
import { TeamCrest } from "./TeamCrest";

export function TeamResultsPanel({ trend }: { trend: ApiResponse<TeamTrend> }) {
  const t = trend.data[0];
  const results = t?.resultsInWindow ?? [];
  return <section aria-labelledby="team-results">
    <div className="td-section-heading"><div><p className="td-kicker">04 / Results archive</p><h2 id="team-results">Results in window</h2></div><p>{t?.windowDays != null ? `${t.windowDays}-day lookback · ` : ""}{t ? `${results.length} matched results` : "History unavailable"}</p></div>
    {trend.stale && t && <p className="td-notice" role="status">Result updates unavailable — showing last available data.</p>}
    {!results.length ? <p className="td-empty">{!t && (trend.stale || trend.error) ? "Results unavailable — couldn't load this team's history." : "No results matched for this window."}</p> : <>
      <p className="td-caption">Banked results in source order. Capture times are not match dates. Scores and verdicts are shown as supplied. Scroll horizontally to see all columns on smaller screens.</p>
      <div className="td-table-scroll" tabIndex={0} role="region" aria-label="Results in window, scroll horizontally"><table className="td-table td-results"><caption className="sr-only">Team results in the history window</caption><thead><tr><th scope="col">Opponent / Event</th><th scope="col">Result</th><th scope="col">Score</th><th scope="col">Captured at (UTC)</th><th scope="col">Source</th></tr></thead><tbody>{results.map((r,i) => <tr key={r.vlrId ?? i}><th scope="row"><span className="td-result-opponent"><TeamCrest name={r.opponent} logo={r.opponentLogo} size="table" />{r.opponentId ? <Link prefetch={false} href={`/team/${r.opponentId}`}>{r.opponent ?? "Opponent unavailable"}</Link> : r.vlrId ? <Link href={`/match/${r.vlrId}`}>{r.opponent ?? "Opponent unavailable"}</Link> : r.opponent ?? "Opponent unavailable"}</span><span className="td-result-event">{r.event ?? "Event unavailable"}</span></th><td><span className="td-verdict" data-result={r.result ?? "unknown"}>{r.result === "win" ? "Win" : r.result === "loss" ? "Loss" : "Unknown"}</span></td><td>{r.score ?? "—"}</td><td>{captureDate(r.capturedAt)}</td><td>{r.vlrId ? <a href={`https://www.vlr.gg/${r.vlrId}`} target="_blank" rel="noopener noreferrer" aria-label={`View ${r.opponent ?? "match"} on VLR.gg (new tab)`}>VLR.gg ↗</a> : "—"}</td></tr>)}</tbody></table></div>
    </>}
  </section>;
}
