import Link from "next/link";
import { agentRounds, playerOverall, signatureAgent } from "@/lib/vlr";
import type { PlayerDetail } from "@/types/vlr";
import { TeamCrest } from "./TeamCrest";

export function PlayerCard({ player }: { player: PlayerDetail }) {
  const overall = playerOverall(player.agentStats);
  const selected = signatureAgent(player.agentStats);
  const sig = selected && player.agentStats.some(row => row.agent === selected.agent && (agentRounds(row.stats) ?? 0) > 0) ? selected : null;
  const rounds = player.agentStats.map(row => agentRounds(row.stats)).filter((n): n is number => n !== null && n > 0);
  const recent = player.matches.slice(0, 10);
  const team = player.team ?? "Team unavailable";
  return <header className="pd-identity">
    <p className="pd-kicker">Valorant / Player dossier</p>
    <div className="pd-identity-main">
      <span className="pd-avatar" aria-hidden>{player.alias?.slice(0, 2).toUpperCase() ?? "?"}</span>
      <div><p className="pd-meta">{player.realName ?? "Name unavailable"} / {player.country ?? "Country unavailable"}</p><h1>{player.alias ?? "Player name unavailable"}</h1>
        <div className="pd-affiliation"><TeamCrest name={player.team} logo={player.teamLogo} size="table" />{player.teamId ? <Link href={`/team/${player.teamId}`}>{team}</Link> : player.teamUrl ? <a href={player.teamUrl} target="_blank" rel="noopener noreferrer">{team}</a> : <span>{team}</span>}<span>Role unavailable</span></div>
      </div>
    </div>
    <div className="pd-headline">
      <div><span>Rating</span><strong>{overall.rating?.toFixed(2) ?? "—"}</strong></div>
      <div><span>K/D</span><strong>{overall.kd?.toFixed(2) ?? "—"}</strong></div>
      <div><span>ACS</span><strong>{overall.acs == null ? "—" : Math.round(overall.acs)}</strong></div>
      <div className="pd-signature"><span>Main agent · by rounds</span><strong>{sig?.agent ?? "Unavailable"}</strong>{sig?.usage && <span>{sig.usage} source usage</span>}</div>
    </div>
    <p className="pd-caption">{player.agentStats.length} agent rows · {rounds.length ? `${rounds.reduce((a,b)=>a+b,0).toLocaleString("en-US")} known rounds across ${rounds.length} rows` : "Round sample unavailable"} · All-time source stats; capture date unavailable.</p>
    <details className="pd-method"><summary>How headline statistics are calculated</summary><p>Rating and ACS are rounds-weighted across parseable agent rows; missing or non-positive rounds use weight 1. K/D divides summed kills by summed deaths. Coverage can differ by metric. Main agent follows the existing highest-rounds selection; missing rounds count as zero, with source order breaking ties. A main agent is shown only when its round count is available and positive. Role and portrait are not supplied.</p></details>
    {recent.length > 0 && <div className="pd-form"><span>Form · {recent.length} listed matches · newest first</span><ol>{recent.map((m,i)=><li key={m.id ?? i}><span className="pd-verdict" data-result={m.result ?? "unknown"} title={`${m.opponent ?? "Unknown opponent"}: ${m.result ?? "result unavailable"}`}>{m.result === "win" ? "W" : m.result === "loss" ? "L" : "?"}<span className="sr-only"> against {m.opponent ?? "unknown opponent"}</span></span></li>)}</ol></div>}
  </header>;
}
