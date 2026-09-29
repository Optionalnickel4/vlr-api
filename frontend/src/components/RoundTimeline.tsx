import type { MatchRound } from "@/types/vlr";
import { TeamCrest } from "@/components/TeamCrest";

function description(round: MatchRound, index: number, names: string[]) {
  const winner = round.winner === null ? "Result unavailable" : `${names[round.winner - 1]} won`;
  return [`Round ${round.round ?? index + 1}`, winner, round.side === "t" ? "Attack" : round.side === "ct" ? "Defense" : null, round.outcome, round.score].filter(Boolean).join(" · ");
}

/** Real round results only. Text and a disclosure complement the color matrix. */
export function RoundTimeline({ rounds, team1, team2, team1Logo, team2Logo }: {
  rounds: MatchRound[];
  team1: string | null;
  team2: string | null;
  team1Logo?: string | null;
  team2Logo?: string | null;
}) {
  if (!rounds.length) return null;
  const names = [team1 ?? "Team 1", team2 ?? "Team 2"];
  return <section className="md-rounds" aria-label="Round history">
    <div className="md-section-heading"><h3>ROUND HISTORY</h3><p>W = win · L = loss · – = unavailable</p></div>
    <div className="md-round-scroll" role="region" tabIndex={0} aria-label="Round results, scroll horizontally">
      <div className="md-round-labels" aria-hidden><span>Round</span><span><TeamCrest name={team1} logo={team1Logo} size="ticker" />{names[0]}</span><span><TeamCrest name={team2} logo={team2Logo} size="ticker" />{names[1]}</span></div>
      <ol className="md-round-grid">{rounds.map((round, i) => <li key={round.round ?? i} title={description(round, i, names)}>
        <span className="sr-only">{description(round, i, names)}</span>
        <span aria-hidden className="md-round-number">{round.round ?? i + 1}</span>
        {[1, 2].map(team => <span aria-hidden key={team} className="md-round-result" data-result={round.winner === null ? "unknown" : round.winner === team ? "win" : "loss"}>{round.winner === null ? "–" : round.winner === team ? "W" : "L"}</span>)}
      </li>)}</ol>
    </div>
    <details className="md-round-details"><summary>Round-by-round details</summary><ol>{rounds.map((round, i) => <li key={round.round ?? i}>{description(round, i, names)}</li>)}</ol></details>
  </section>;
}
