"use client";

import { useId, useRef, useState } from "react";
import type { MatchDetail, MatchMap, MatchMapTeam } from "@/types/vlr";
import { PlayerStatsTable } from "@/components/PlayerStatsTable";
import { RoundTimeline } from "@/components/RoundTimeline";

type Tab = { key: string } & (
  | { kind: "map"; map: MatchMap }
  | { kind: "all"; teams: MatchMapTeam[] }
);

/** Selection is local, stable across score updates, and usable without a pointer. */
export function MapTabs({ match }: { match: MatchDetail }) {
  const tabs: Tab[] = [
    ...match.maps.map((map, i) => ({ key: `map-${map.gameId ?? i}`, kind: "map" as const, map })),
    ...(match.allMaps ? [{ key: "all", kind: "all" as const, teams: match.allMaps.teams }] : []),
  ];
  const [selected, setSelected] = useState<string | null>(null);
  const id = useId();
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  const active = Math.max(0, tabs.findIndex(tab => tab.key === selected));
  if (!tabs.length) return <section className="md-empty" aria-label="Map coverage">No map data available for this match.</section>;
  const current = tabs[active];
  const teams = current.kind === "map" ? current.map.teams : current.teams;
  const teamName = (i: number) => teams[i]?.name ?? match.teams[i]?.name ?? `Team ${i + 1}`;
  const select = (i: number) => { setSelected(tabs[i].key); buttons.current[i]?.focus(); };

  return <section className="md-maps" aria-label="Maps and player performance">
    <div className="md-section-heading"><div><p className="md-eyebrow">The series / map by map</p><h2>MAP BREAKDOWN.</h2></div><p>Scores follow the team order above.</p></div>
    <div className="md-map-tabs" role="tablist" aria-label="Select a map">
      {tabs.map((tab, i) => <button key={tab.key} type="button" role="tab" id={`${id}-tab-${i}`} aria-controls={`${id}-panel`} aria-selected={i === active} tabIndex={i === active ? 0 : -1}
        ref={el => { buttons.current[i] = el; }} onClick={() => setSelected(tab.key)}
        onKeyDown={event => {
          const next = event.key === "ArrowRight" ? (i + 1) % tabs.length : event.key === "ArrowLeft" ? (i + tabs.length - 1) % tabs.length : event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : null;
          if (next !== null) { event.preventDefault(); select(next); }
        }}>
        <span className="md-tab-kicker">{tab.kind === "map" ? `Map ${i + 1}` : "Series totals"}</span>
        <span className="md-tab-name">{tab.kind === "map" ? tab.map.name ?? "Name unavailable" : "All Maps"}</span>
        {tab.kind === "map" && <span className="md-tab-score">{tab.map.scores[0] ?? "–"} : {tab.map.scores[1] ?? "–"}</span>}
        <span className="md-tab-marker">{tab.kind === "map" ? tab.map.decider ? "Decider" : tab.map.picked ? "Pick" : "Map" : "Combined stats"}</span>
      </button>)}
    </div>
    <div id={`${id}-panel`} role="tabpanel" aria-labelledby={`${id}-tab-${active}`} tabIndex={0} className="md-map-panel">
      <div className="md-map-heading"><h3>{current.kind === "map" ? current.map.name ?? `Map ${active + 1}` : "All Maps"}</h3><p>{current.kind === "map" ? `${teamName(0)} ${current.map.scores[0] ?? "–"} : ${current.map.scores[1] ?? "–"} ${teamName(1)}` : "Combined player performance across the series"}</p></div>
      {current.kind === "map" && (current.map.rounds.length ? <RoundTimeline rounds={current.map.rounds} team1={teamName(0)} team2={teamName(1)} /> : <p className="md-data-note">Round history unavailable for this map.</p>)}
      <div className="md-scoreboards">
        <div className="md-section-heading"><h3>PLAYER SCOREBOARDS</h3><p>Source order · Scroll tables for all statistics</p></div>
        {!teams.length && <p className="md-empty">Player statistics unavailable for this map.</p>}
        {teams.map((team, i) => <PlayerStatsTable key={`${current.key}-${i}`} team={{ ...team, name: teamName(i) }} />)}
      </div>
    </div>
  </section>;
}
