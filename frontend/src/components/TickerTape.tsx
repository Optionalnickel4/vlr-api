"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { TeamCrest } from "./TeamCrest";
import type { MatchWireItem, MatchWireTeam } from "@/types/vlr";

function Team({ team, winner }: { team: MatchWireTeam; winner: boolean }) {
  return <span className="wire-team" data-winner={winner || undefined}>
    <TeamCrest name={team.name} logo={team.logo} size="ticker" />
    <span className="wire-team-name"><span className="wire-short">{team.shortName}</span><span className="wire-full">{team.name}</span></span>
    {winner && <span className="wire-winner">WIN</span>}
  </span>;
}

function matchLabel(item: Extract<MatchWireItem, { kind: "live" | "upcoming" | "final" }>): string {
  const [a, b] = item.teams;
  if (item.kind === "upcoming") return `Upcoming: ${a.name} versus ${b.name}, ${item.time ?? "start time unavailable"}, ${item.event ?? "event unavailable"}`;
  const score = `${a.score ?? "score unavailable"} to ${b.score ?? "score unavailable"}`;
  if (item.kind === "live") return `Live: ${a.name} versus ${b.name}, ${score}, ${item.event ?? "event unavailable"}`;
  const winner = item.winnerId === (a.id ?? "side-1") ? a.name : item.winnerId === (b.id ?? "side-2") ? b.name : "Winner unavailable";
  return `Final: ${a.name} versus ${b.name}, ${score}, winner ${winner}, ${item.event ?? "event unavailable"}`;
}

function EntryContent({ item }: { item: MatchWireItem }) {
  if (item.kind === "mover") {
    return <>
      <span className="wire-status wire-rank">RANK</span>
      <Team team={item.team} winner={false} />
      <span className="wire-move" data-direction={item.direction}><span aria-hidden>{item.direction === "up" ? "▲" : "▼"}</span><span className="sr-only">Moved {item.direction}</span> {item.positions}</span>
      <span className="wire-ranks">#{item.previousRank} → #{item.currentRank}</span>
      <span className="wire-meta">{item.context}</span>
    </>;
  }
  const [a, b] = item.teams;
  const aWinner = item.kind === "final" && item.winnerId === (a.id ?? "side-1");
  const bWinner = item.kind === "final" && item.winnerId === (b.id ?? "side-2");
  return <>
    <span className={`wire-status wire-${item.kind}`}>{item.status}</span>
    <Team team={a} winner={aWinner} />
    {item.kind === "upcoming" ? <span className="wire-versus">VS</span> : <span className="wire-score">{a.score ?? "–"}<span>:</span>{b.score ?? "–"}</span>}
    <Team team={b} winner={bWinner} />
    {item.kind === "upcoming" && <span className="wire-time">{item.time ?? "Time TBA"}</span>}
    <span className="wire-meta">{[item.event, item.context].filter(Boolean).join(" · ") || "Match details unavailable"}</span>
  </>;
}

function TickerEntry({ item, interactive }: { item: MatchWireItem; interactive: boolean }) {
  const content: ReactNode = <EntryContent item={item} />;
  const className = "wire-entry";
  if (!interactive) return <span className={className}>{content}<span className="wire-divider">/</span></span>;
  const label = item.kind === "mover"
    ? `${item.team.name} moved ${item.direction} ${item.positions} positions, rank ${item.previousRank} to ${item.currentRank}`
    : matchLabel(item);
  return <Link prefetch={false} className={className} href={item.href} aria-label={label}>{content}<span className="wire-divider" aria-hidden>/</span></Link>;
}

export function TickerTape({ items, stale = false, showEmpty = false }: {
  items: MatchWireItem[];
  stale?: boolean;
  showEmpty?: boolean;
}) {
  const [manualPaused, setManualPaused] = useState(false);
  const [hoverPaused, setHoverPaused] = useState(false);
  const [focusPaused, setFocusPaused] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setReducedMotion(query.matches);
    sync();
    query.addEventListener?.("change", sync);
    return () => query.removeEventListener?.("change", sync);
  }, []);

  if (!items.length && !showEmpty) return null;
  const paused = manualPaused || hoverPaused || focusPaused || reducedMotion;
  const durationSeconds = Math.max(28, items.length * 7);
  return <section aria-label={stale ? "Match Wire, showing last available data" : "Match Wire"}
    className="vlr-ticker broadcast-ticker"
    data-paused={paused} data-manual-paused={manualPaused} data-reduced-motion={reducedMotion}
    onPointerEnter={() => setHoverPaused(true)} onPointerLeave={() => setHoverPaused(false)}
    onFocusCapture={() => setFocusPaused(true)}
    onBlurCapture={event => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setFocusPaused(false); }}>
    <div className="ticker-label"><span className="ticker-dot" aria-hidden />MATCH WIRE{stale && <span className="ticker-stale">STALE</span>}</div>
    {items.length ? <>
      <div className="ticker-viewport" tabIndex={0} role="region" aria-label="Match Wire items; scroll horizontally while paused">
        <div className="vlr-ticker-track" style={{ animationDuration: `${durationSeconds}s`, animationPlayState: paused ? "paused" : "running" }}>
          <div className="ticker-copy">{items.map(item => <TickerEntry key={item.id} item={item} interactive />)}</div>
          {!reducedMotion && <div className="ticker-copy ticker-duplicate" aria-hidden="true">{items.map(item => <TickerEntry key={item.id} item={item} interactive={false} />)}</div>}
        </div>
      </div>
      <button type="button" className="ticker-pause" aria-pressed={manualPaused}
        onClick={() => setManualPaused(value => !value)}>{manualPaused ? "Resume" : "Pause"}<span className="sr-only"> Match Wire motion</span></button>
    </> : <div className="ticker-empty"><span>{stale ? "Match Wire updates unavailable." : "No match or ranking updates available."}</span><Link href="/schedule">View schedule ↗</Link></div>}
  </section>;
}
