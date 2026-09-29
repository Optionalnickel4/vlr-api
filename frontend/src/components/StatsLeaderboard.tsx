"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import Link from "next/link";
import { cn } from "@/lib/cn";
import {
  DEFAULT_STAT_DIR,
  DEFAULT_STAT_SORT,
  STAT_REGIONS,
  STAT_TIMESPANS,
  sortLeaders,
  type SortDir,
  type StatSortKey,
} from "@/lib/vlr";
import type { ApiResponse, StatLeader } from "@/types/vlr";
import { TeamCrest } from "./TeamCrest";

/** Region/window controls retain the existing API and stable numeric sorting.
 * Preview cards follow the current sort. They are not global rank claims.
 * Filter changes clear old rows until the selected request settles; cancelled
 * requests cannot replace a newer selection. */

const REGION_LABELS: Record<string, string> = { na: "NA", eu: "EU" };
const TIMESPAN_LABELS: Record<string, string> = {
  "30d": "30D",
  "60d": "60D",
  "90d": "90D",
  all: "ALL",
};

type Col = {
  key: StatSortKey | null; // null = unsortable (the derived rank column)
  label: string;
  align: "left" | "right";
  render: (r: StatLeader) => ReactNode;
  emphasize?: boolean; // the R2.0 headline column
  className?: string;
  sample?: boolean;
};

function num(n: number | null, digits = 0): string {
  return n === null ? "—" : n.toFixed(digits);
}
function pct(n: number | null): string {
  return n === null ? "—" : `${Math.round(n)}%`;
}

// First rows of the current sort, not an independent ranking or performance claim.
const PODIUM_SLOTS = [{rank:1},{rank:2},{rank:3}] as const;
function PodiumBlock({player,slot}: {player:StatLeader|undefined;slot:(typeof PODIUM_SLOTS)[number]}) {
 if(!player)return null;
 return <div className="ld-sort-card" data-podium-rank={slot.rank}>
  <span className="ld-kicker">View position {slot.rank}</span>
  {player.playerId?<Link href={`/player/${player.playerId}`}>{player.player??'Player unavailable'}</Link>:<strong>{player.player??'Player unavailable'}</strong>}
  <span className="inline-flex items-center gap-1"><TeamCrest name={player.team} logo={player.teamLogo} size="ticker" />{player.team??'Team unavailable'}</span>
  <div><strong>{num(player.r2,2)}</strong> R2.0 <span> / {player.rnd??'—'} rounds</span></div>
 </div>;
}

const COLUMNS: Col[] = [
  // rank is derived from the current sort order, so it's unsortable
  {
    key: null,
    label: "#",
    align: "right",
    className: "w-8 text-dim",
    render: () => null, // filled with the row index by the renderer
  },
  {
    key: "player",
    label: "Player",
    align: "left",
    render: (r) => (
      <>
        {r.playerId ? (
          <Link href={`/player/${r.playerId}`} className="text-ink hover:text-accent">
            {r.player ?? "—"}
          </Link>
        ) : (
          (r.player ?? "—")
        )}
        {r.team && (
          <span className="flex items-center gap-1 font-display text-[10px] font-semibold uppercase tracking-broadcast text-dim">
            <TeamCrest name={r.team} logo={r.teamLogo} size="ticker" />{r.team}
          </span>
        )}
      </>
    ),
  },
  { key: null, label: "Rounds", align: "right", sample: true, render: r => r.rnd === null ? "—" : String(r.rnd) },
  { key: "r2", label: "R2.0", align: "right", emphasize: true, render: (r) => num(r.r2, 2) },
  { key: "acs", label: "ACS", align: "right", render: (r) => num(r.acs, 0) },
  { key: "kd", label: "K:D", align: "right", render: (r) => num(r.kd, 2) },
  { key: "kast", label: "KAST", align: "right", render: (r) => pct(r.kast) },
  { key: "adr", label: "ADR", align: "right", render: (r) => num(r.adr, 0) },
  { key: "kpr", label: "KPR", align: "right", render: (r) => num(r.kpr, 2) },
  {
    key: "fk",
    label: "FK/FD",
    align: "right",
    render: (r) => `${num(r.fk, 0)} / ${num(r.fd, 0)}`,
  },
  { key: "hs", label: "HS%", align: "right", render: (r) => pct(r.hs) },
];

function Toggle<T extends string>({
  options,
  labels,
  value,
  onChange,
  ariaLabel,
}: {
  options: readonly T[];
  labels: Record<string, string>;
  value: T;
  onChange: (v: T) => void;
  ariaLabel: string;
}) {
  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className="ld-toggle"
    >
      {options.map((opt) => (
        <button
          key={opt}
          type="button"
          aria-pressed={value === opt}
          onClick={() => onChange(opt)}
          className={cn(
            "rounded px-2.5 py-1 font-display text-[11px] font-semibold uppercase tracking-broadcast transition-colors",
            value === opt ? "bg-accent/15 text-accent" : "text-mut hover:text-ink",
          )}
        >
          {labels[opt] ?? opt}
        </button>
      ))}
    </div>
  );
}

export function StatsLeaderboard({
  initial,
  initialRegion = "na",
  initialTimespan = "all",
}: {
  initial: ApiResponse<StatLeader>;
  initialRegion?: string;
  initialTimespan?: string;
}) {
  const [region, setRegion] = useState(initialRegion);
  const [timespan, setTimespan] = useState(initialTimespan);
  const [rows, setRows] = useState<StatLeader[]>(initial.data);
  const [stale, setStale] = useState(initial.stale);
  const [error, setError] = useState<string | null>(initial.error ?? null);
  const [loading, setLoading] = useState(false);
  const [sortKey, setSortKey] = useState<StatSortKey>(DEFAULT_STAT_SORT);
  const [sortDir, setSortDir] = useState<SortDir>(DEFAULT_STAT_DIR);

  // Refetch on a toggle change only — never on the initial mount (the server
  // already seeded `initial` for the initial region/timespan).
  const isFirst = useRef(true);
  useEffect(() => {
    if (isFirst.current) {
      isFirst.current = false;
      return;
    }
    let cancelled = false;
    setLoading(true);
    setRows([]);
    setStale(false);
    setError(null);
    fetch(`/api/stats?region=${encodeURIComponent(region)}&timespan=${encodeURIComponent(timespan)}`, {
      cache: "no-store",
    })
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const body = await r.json() as ApiResponse<StatLeader>;
        if (!Array.isArray(body.data)) throw new Error("Invalid leaderboard response");
        return body;
      })
      .then((res) => {
        if (cancelled) return;
        setRows(res.data);
        setStale(res.stale);
        setError(res.error ?? null);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(String(err));
          setRows([]);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [region, timespan]);

  const sorted = useMemo(() => sortLeaders(rows, sortKey, sortDir), [rows, sortKey, sortDir]);

  function onSort(key: StatSortKey | null) {
    if (key === null) return;
    if (key === sortKey) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortKey(key);
      // numbers default high→low (best first); the name column defaults A→Z
      setSortDir(key === "player" ? "asc" : "desc");
    }
  }

  const isEmpty = !loading && sorted.length === 0;

  return (
    <section className="ladder-page ld-stats" aria-busy={loading}>
      {/* header: title + count + controls */}
      <div className="ld-controls">
        <h2 className="font-display text-lg font-bold uppercase tracking-broadcast text-ink">
          Leaderboard
        </h2>
        <span className="font-mono text-[12px] text-dim tabular-nums">
          {sorted.length}
        </span>
        {stale && (
          <span className="font-display text-[10px] uppercase tracking-broadcast text-warn">
            Updates unavailable — last available data
          </span>
        )}
        {loading && (
          <span className="font-display text-[10px] uppercase tracking-broadcast text-mut">
            loading…
          </span>
        )}
        <div className="ld-filter-groups">
          <Toggle
            options={STAT_REGIONS}
            labels={REGION_LABELS}
            value={region as (typeof STAT_REGIONS)[number]}
            onChange={(v) => setRegion(v)}
            ariaLabel="Region"
          />
          <Toggle
            options={STAT_TIMESPANS}
            labels={TIMESPAN_LABELS}
            value={timespan as (typeof STAT_TIMESPANS)[number]}
            onChange={(v) => setTimespan(v)}
            ariaLabel="Timespan"
          />
        </div>
      </div>

      <p className="ld-context" role="status">{REGION_LABELS[region] ?? region} / {timespan === "all" ? "All time" : `${timespan.slice(0,-1)} days`} · {loading ? "Loading selected filters" : `${sorted.length} listed players`} · Sorted by {COLUMNS.find(c=>c.key===sortKey)?.label} {sortDir === "desc" ? "descending" : "ascending"}</p>
      <p className="ld-note">Positions reflect this sort within the selected region and time window, not a global rank. Rounds are the supplied per-player sample; — means unavailable. Capture time and exact window boundaries are not supplied. Scroll the table horizontally for all columns.</p>
      <details className="ld-glossary"><summary>Column guide and sorting</summary><p>R2.0: source rating. ACS: average combat score. K:D: kill/death ratio. KAST: rounds with a kill, assist, survival or trade (%). ADR: average damage per round. KPR: kills per round. FK/FD: first kills / first deaths, sorted by first kills. HS%: headshot percentage. Click a column to sort; click again to reverse. Missing values stay last. Equal values retain source order.</p></details>
      {error && (
        <p role="alert" className="mb-3 font-body text-[13px] text-down">
          Couldn’t load the leaderboard: {error}
        </p>
      )}

      {/* Preview cards follow the current table order. */}
      {!isEmpty && !loading && (
        <div
          className="ld-sort-cards"
          aria-label="First three rows in the current sort"
          role="region"
        >
          {PODIUM_SLOTS.map((slot) => {
            // sorted[0]=rank1, sorted[1]=rank2, sorted[2]=rank3
            const idx = slot.rank - 1;
            return (
              <PodiumBlock key={slot.rank} player={sorted[idx]} slot={slot} />
            );
          })}
        </div>
      )}

      {loading ? <p className="ld-notice" role="status">Loading leaderboard…</p> : isEmpty ? (
        <p className="rounded border border-line bg-panel px-4 py-8 text-center font-body text-[13px] text-mut">
          {error || stale ? "Leaderboard unavailable for these filters." : "No leaderboard data."}
        </p>
      ) : (
        <div className="ld-scroll ld-stat-scroll" role="region" aria-label="Player statistics table; scroll horizontally for all columns" tabIndex={0}>
          <table
            className={cn(
              "ld-table ld-stat-table w-full border-collapse text-left",
              "[&_tbody_td]:border-t [&_tbody_td]:border-line/60 [&_tbody_td]:px-3 [&_tbody_td]:py-2",
              "[&_tbody_tr:hover]:bg-ink/[0.03]",
            )}
          >
            <thead>
              <tr>
                {COLUMNS.map((col, i) => {
                  const active = col.key !== null && col.key === sortKey;
                  return (
                    <th
                      key={`${col.label}-${i}`}
                      scope="col"
                      aria-sort={
                        active ? (sortDir === "desc" ? "descending" : "ascending") : undefined
                      }
                      className={cn(
                        "px-3 pb-2 pt-2 font-display text-[11px] font-semibold uppercase tracking-[0.1em]",
                        col.align === "right" ? "text-right" : "text-left",
                        col.key === null ? "text-dim" : "cursor-pointer select-none",
                        active ? "text-accent" : "text-dim hover:text-mut",
                        col.className,
                      )}
                    >
                      {col.key ? <button type="button" onClick={() => onSort(col.key)} aria-label={`Sort by ${col.label}`}>{col.label}{active && <span aria-hidden>{sortDir === "desc" ? " ▾" : " ▴"}</span>}</button> : col.label}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {sorted.map((r, i) => (
                <tr key={r.playerId ?? `${r.player}-${i}`}>
                  {COLUMNS.map((col, ci) => {
                    if (col.key === null && !col.sample) {
                      // derived rank = position in the current sort order
                      return (
                        <td
                          key={ci}
                          className="text-right font-mono text-dim tabular-nums"
                        >
                          {i + 1}
                        </td>
                      );
                    }
                    if (col.key === "player") {
                      return (
                        <td
                          key={ci}
                          className="font-display text-sm font-semibold uppercase tracking-[0.03em] text-ink"
                        >
                          {col.render(r)}
                        </td>
                      );
                    }
                    return (
                      <td
                        key={ci}
                        className={cn(
                          "text-right font-mono tabular-nums",
                          col.emphasize
                            ? "text-sm font-bold text-accent"
                            : "text-sm text-ink",
                        )}
                      >
                        {col.render(r)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
