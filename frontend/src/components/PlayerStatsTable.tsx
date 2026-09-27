import Link from "next/link";
import type { MatchMapTeam } from "@/types/vlr";

const COLS = [
  { label: "R", key: "R", title: "Rating" },
  { label: "ACS", key: "ACS", title: "Average combat score" },
  { label: "K", key: "K", title: "Kills" },
  { label: "D", key: "D", title: "Deaths" },
  { label: "A", key: "A", title: "Assists" },
  { label: "+/−", key: "KD_+/-", title: "Kill/death difference" },
  { label: "KAST", key: "KAST", title: "Kill, assist, survive or traded rounds", pct: true },
  { label: "ADR", key: "ADR", title: "Average damage per round" },
  { label: "HS%", key: "HS%", title: "Headshot percentage", pct: true },
  { label: "FK", key: "FK", title: "First kills" },
  { label: "FD", key: "FD", title: "First deaths" },
];

function fmt(value: number | null | undefined, pct?: boolean): string {
  if (value === null || value === undefined) return "—";
  const n = Number.isInteger(value) ? String(value) : value.toFixed(2);
  return pct ? `${n}%` : n;
}

/** Preserve upstream row order, every existing column, and numeric formatting. */
export function PlayerStatsTable({ team }: { team: MatchMapTeam }) {
  return <section className="md-scoreboard" aria-label={`${team.name ?? "Team"} player scoreboard`}>
    <div className="md-scoreboard-heading"><h4>{team.name ?? "Team unavailable"}</h4>{team.score !== null && <span>{team.score} <span className="md-eyebrow">rounds</span></span>}</div>
    <div className="md-table-scroll" role="region" aria-label={`${team.name ?? "Team"} statistics, scroll horizontally`} tabIndex={0}>
      <table className="md-table">
        <caption className="sr-only">{team.name ?? "Team"} player statistics in source order</caption>
        <thead><tr><th scope="col">Player / Agent</th>{COLS.map(col => <th scope="col" key={col.key}><abbr title={col.title}>{col.label}</abbr></th>)}</tr></thead>
        <tbody>{team.players.length ? team.players.map((player, i) => <tr key={player.playerId ?? `${player.player}-${i}`}>
          <th scope="row"><div className="md-player">{player.playerId ? <Link href={`/player/${player.playerId}`}>{player.player ?? "Player unavailable"}</Link> : <span>{player.player ?? "Player unavailable"}</span>}<span className="md-agent">{player.agent ?? "Agent unavailable"}</span></div></th>
          {COLS.map(col => <td key={col.key}>{fmt(player.stats[col.key]?.value, col.pct)}</td>)}
        </tr>) : <tr><td colSpan={COLS.length + 1}>Player statistics unavailable.</td></tr>}</tbody>
      </table>
    </div>
  </section>;
}
