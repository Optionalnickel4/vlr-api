import Link from "next/link";
import { TeamCrest } from "./TeamCrest";
import type { MatchPrediction, PredictionAccuracy } from "@/types/predictions";
import type { ApiResponse } from "@/types/vlr";

function utcDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", { timeZone: "UTC", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date(value)) + " UTC";
}

function PredictionCard({ match, archived = false }: { match: MatchPrediction; archived?: boolean }) {
  const pick = match.prediction;
  const winner = match.teams.find(t => t.id !== null && t.id === pick?.winnerId);
  return <article className="prediction-card" data-status={match.status}>
    <div className="prediction-card-top"><span>{match.event ?? "Event to be confirmed"}</span><span>{match.startsAt ? utcDate(match.startsAt) : match.timing ? `Source countdown: ${match.timing}` : "Start time to be confirmed"}</span></div>
    <h3 className="prediction-match"><span className="sr-only">{match.teams[0].name} versus {match.teams[1].name}</span>
      <span className="prediction-side" aria-hidden="true"><TeamCrest name={match.teams[0].name} logo={match.teams[0].logo} size="card" /><span>{match.teams[0].name}</span></span>
      <span className="prediction-vs" aria-hidden="true">VS</span>
      <span className="prediction-side" aria-hidden="true"><TeamCrest name={match.teams[1].name} logo={match.teams[1].logo} size="card" /><span>{match.teams[1].name}</span></span>
    </h3>
    {archived && pick && <div className="prediction-result" data-outcome={match.result?.outcome ?? (match.status === "no_pick" ? "no_pick" : "pending")}>
      <strong>{match.status === "no_pick" ? "NO PICK · NOT SCORED" : match.result?.outcome === "correct" ? "CORRECT PICK" : match.result?.outcome === "incorrect" ? "WRONG PICK" : "AWAITING FINAL RESULT"}</strong>
      {match.result && <p>Final: {match.teams.map(t => `${t.name} ${match.result!.scores[t.id!]}`).join(" — ")}. {match.teams.find(t => t.id === match.result!.winnerId)?.name} won.</p>}
    </div>}
    <div className="prediction-verdict"><p className="prediction-eyebrow">{winner ? "THE PICK" : match.status === "no_pick" ? "NO CLEAR EDGE" : "AWAITING ANALYSIS"}</p>
      <p className="prediction-winner">{winner?.name ?? (match.status === "no_pick" ? "Too close to call." : "No pick yet.")}</p>
      <p className="prediction-explanation">{pick?.explanation ?? "A pick will appear when both teams, the match start, and enough recent form can be confirmed."}</p>
    </div>
    {pick && <details className="prediction-evidence"><summary>Why this pick? <span>Evidence & limitations</span></summary>
      <ul>{match.facts.filter(fact => pick.evidenceIds.includes(fact.id)).map(fact => <li key={fact.id}><p>{fact.text}</p><a href={fact.sourceUrl} target="_blank" rel="noreferrer">Source team history on VLR.gg <span className="sr-only">(opens in a new tab)</span> ↗</a></li>)}</ul>
      <p className="prediction-eyebrow">WHAT COULD CHANGE IT</p>
      <ul>{[...new Set([...pick.caveats, ...match.limitations])].map((caveat,i) => <li key={i}>{caveat}</li>)}</ul>
    </details>}
    <footer className="prediction-card-footer"><span>{match.generatedAt ? `Saved before match · ${utcDate(match.generatedAt)}` : "Waiting for pre-match evidence"}</span><Link prefetch={false} href={`/match/${match.matchId}`}>Match details ↗<span className="sr-only"> {match.teams[0].name} versus {match.teams[1].name}</span></Link></footer>
  </article>;
}

export function PredictionsBoard({ response, now }: { response: ApiResponse<MatchPrediction> & { accuracy?: PredictionAccuracy }; now: Date }) {
  const upcoming = response.data.filter(m => !m.startsAt || Date.parse(m.startsAt) > now.getTime());
  const archive = response.data.filter(m => m.startsAt && Date.parse(m.startsAt) <= now.getTime());
  const accuracy = response.accuracy;
  const scored = accuracy ? accuracy.correct + accuracy.incorrect : 0;
  return <>
    {response.stale && <p role="status" className="prediction-notice">Coverage is temporarily unavailable. Any saved picks below show the evidence available when they were made.</p>}
    {accuracy && <section className="prediction-record" aria-labelledby="prediction-record-heading">
      <h2 id="prediction-record-heading">OPENCLAW’S RECORD.</h2>
      <div className="prediction-record-totals"><strong>{scored ? `${Math.round(100 * accuracy.correct / scored)}%` : "—"}<span>accuracy</span></strong>
        <p><b>{accuracy.correct}</b> correct</p><p><b>{accuracy.incorrect}</b> wrong</p><p><b>{accuracy.noPick}</b> no pick</p><p><b>{accuracy.awaitingResult}</b> awaiting result</p></div>
      <p>All-time saved record. Accuracy is correct picks divided by {scored} settled winner picks. No-picks and unconfirmed results are excluded. Cards below show the latest 50 saved analyses.</p>
    </section>}
    <section aria-labelledby="prediction-upcoming"><div className="prediction-section-heading"><h2 id="prediction-upcoming">BEFORE THE FIRST ROUND.</h2><span>{upcoming.length} fixtures</span></div>
      {upcoming.length ? <div className="prediction-grid">{upcoming.map(match => <PredictionCard key={match.matchId} match={match} />)}</div>
        : <div className="prediction-empty"><h3>{response.stale ? "Coverage will be back." : "The next slate is on its way."}</h3><p>{response.stale ? "We couldn’t load the upcoming prediction coverage right now." : "There are no upcoming matches available for analysis right now."}</p><Link href="/schedule">Explore the schedule ↗</Link></div>}
    </section>
    {archive.length > 0 && <section aria-labelledby="prediction-archive" className="prediction-archive"><div className="prediction-section-heading"><h2 id="prediction-archive">ON THE RECORD.</h2><span>Original pre-match picks</span></div><p className="prediction-archive-note">Original picks, checked against confirmed final results. Unfinished or unconfirmed matches wait for a result; no-picks do not count as wins or losses.</p><div className="prediction-grid">{archive.map(match => <PredictionCard key={match.matchId} match={match} archived />)}</div></section>}
  </>;
}
