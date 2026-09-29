import Link from "next/link";
import type { PlayerMatch } from "@/types/vlr";
import { TeamCrest } from "./TeamCrest";

export function PlayerMatchesPanel({ matches }: { matches: PlayerMatch[] }) {
  return <section aria-labelledby="player-matches">
    <div className="pd-section-heading"><div><p className="pd-kicker">04 / Match history</p><h2 id="player-matches">Recent Matches</h2></div><p>{matches.length} listed matches · newest first</p></div>
    <p className="pd-caption">Match dates and coverage period are not supplied. Scores and verdicts retain source order and meaning. Scroll horizontally to see all columns.</p>
    {matches.length === 0 ? <p className="pd-empty">No recent matches listed.</p> : <div className="pd-table-scroll" tabIndex={0} role="region" aria-label="Player match history, scroll horizontally"><table className="pd-table pd-matches"><caption className="sr-only">Recent player matches</caption><thead><tr><th scope="col">Opponent / Event</th><th scope="col">Result</th><th scope="col">Score</th><th scope="col">Source</th></tr></thead><tbody>{matches.map((m,i)=><tr key={m.id ?? i}><th scope="row"><span className="pd-opponent"><TeamCrest name={m.opponent} logo={m.opponentLogo} size="table" />{m.opponentId ? <Link prefetch={false} href={`/team/${m.opponentId}`}>{m.opponent ?? "Opponent unavailable"}</Link> : m.id ? <Link href={`/match/${m.id}`}>{m.opponent ?? "Opponent unavailable"}</Link> : m.opponent ?? "Opponent unavailable"}</span><span className="pd-match-event">{m.event ?? "Event unavailable"}</span></th><td><span className="pd-verdict" data-result={m.result ?? "unknown"}>{m.result === "win" ? "Win" : m.result === "loss" ? "Loss" : "Unknown"}</span></td><td>{m.score ?? "—"}</td><td>{m.url ? <a href={m.url} target="_blank" rel="noopener noreferrer" aria-label={`View match against ${m.opponent ?? "unknown opponent"} on VLR.gg (new tab)`}>VLR.gg ↗</a> : "—"}</td></tr>)}</tbody></table></div>}
  </section>;
}
