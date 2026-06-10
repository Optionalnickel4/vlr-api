"use client";

import { useState } from "react";
import type { MatchDetail, MatchMap, MatchMapTeam } from "@/types/vlr";
import { cn } from "@/lib/cn";
import { Panel } from "@/components/Panel";
import { PlayerStatsTable } from "@/components/PlayerStatsTable";
import { RoundTimeline } from "@/components/RoundTimeline";

/**
 * MapTabs — the client island. One tab per map (Pearl/Fracture/Split, the
 * picked/decider marked) plus an "All Maps" aggregate tab; clicking switches the
 * active scoreboard. State is purely local (the data is already in props from the
 * SSR fetch), so this stays a thin interactive shell.
 *
 * NOTE: Next 16 hardens cross-origin dev access and the map tabs hydration broke
 * before when the LAN host wasn't whitelisted. This runs on LXC 289
 * (192.168.1.35) — see allowedDevOrigins in next.config.ts (already set), not the
 * old Crostini IP.
 */
type Tab =
  | { kind: "map"; map: MatchMap }
  | { kind: "all"; teams: MatchMapTeam[] };

function Scoreboards({ teams }: { teams: MatchMapTeam[] }) {
  return (
    <div className="flex flex-col gap-6">
      {teams.map((team, i) => (
        <div key={team.name ?? i} className="overflow-x-auto">
          <PlayerStatsTable team={team} />
        </div>
      ))}
    </div>
  );
}

export function MapTabs({ match }: { match: MatchDetail }) {
  const tabs: Tab[] = [
    ...match.maps.map((map) => ({ kind: "map" as const, map })),
    ...(match.allMaps
      ? [{ kind: "all" as const, teams: match.allMaps.teams }]
      : []),
  ];
  const [active, setActive] = useState(0);
  if (tabs.length === 0) {
    return (
      <Panel className="px-4 py-6 text-center font-body text-sm text-dim">
        No map data available for this match.
      </Panel>
    );
  }
  const current = tabs[Math.min(active, tabs.length - 1)];

  return (
    <div className="flex flex-col gap-4">
      {/* tab strip */}
      <div className="flex flex-wrap gap-2">
        {tabs.map((t, i) => {
          const isMap = t.kind === "map";
          const label = isMap ? (t.map.name ?? "Map") : "All Maps";
          const score =
            isMap && t.map.scores.length === 2
              ? `${t.map.scores[0] ?? "–"}:${t.map.scores[1] ?? "–"}`
              : null;
          const marker = isMap
            ? t.map.decider
              ? "DEC"
              : t.map.picked
                ? "PICK"
                : null
            : null;
          return (
            <button
              key={i}
              type="button"
              onClick={() => setActive(i)}
              className={cn(
                "flex items-center gap-2 rounded-[8px] border px-3 py-1.5 font-display text-[12px] font-semibold uppercase tracking-[0.08em] transition-colors",
                i === active
                  ? "border-accent/50 bg-accent/[0.08] text-ink"
                  : "border-line bg-transparent text-mut hover:text-ink",
              )}
            >
              <span>{label}</span>
              {score && (
                <span className="font-mono text-[11px] text-dim tabular-nums">
                  {score}
                </span>
              )}
              {marker && (
                <span className="text-[9px] tracking-[0.1em] text-accent">
                  {marker}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* active scoreboard + round strip */}
      <Panel className="flex flex-col gap-2 overflow-hidden py-2">
        {current.kind === "map" && current.map.rounds.length > 0 && (
          <RoundTimeline
            rounds={current.map.rounds}
            team1={current.map.teams[0]?.name ?? null}
            team2={current.map.teams[1]?.name ?? null}
          />
        )}
        <div className="px-2 py-2">
          <Scoreboards
            teams={current.kind === "map" ? current.map.teams : current.teams}
          />
        </div>
      </Panel>
    </div>
  );
}
