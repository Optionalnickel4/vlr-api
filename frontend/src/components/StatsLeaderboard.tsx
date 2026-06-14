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

/**
 * StatsLeaderboard — the HLTV-style region-wide player leaderboard (Phase 12).
 *
 * VLR's OWN R2.0 rating is the headline column (emphasized, accent) — we never
 * compute a composite. Region (NA/EU) + timespan (30d/60d/90d/all) toggles
 * refetch /api/stats client-side; columns are click-to-sort.
 *
 * SORT SAFETY: every numeric column sorts on the COERCED number (sortLeaders in
 * the data layer), never the raw string — so 1024 sorts above 998 (the lexical
 * "998" < "1024" trap can't happen). Default R2.0 descending.
 *
 * HYDRATION: state seeds from `initial` (server-fetched for the initial region/
 * timespan) and the sort is deterministic given (rows, key, dir) — so the SSR
 * render and the first client render are byte-identical. Refetches happen only
 * after a toggle change (post-mount effect, guarded against the initial mount).
 */

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
};

function num(n: number | null, digits = 0): string {
  return n === null ? "—" : n.toFixed(digits);
}
function pct(n: number | null): string {
  return n === null ? "—" : `${Math.round(n)}%`;
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
    render: (r) =>
      r.playerId ? (
        <Link href={`/player/${r.playerId}`} className="text-ink hover:text-accent">
          {r.player ?? "—"}
        </Link>
      ) : (
        (r.player ?? "—")
      ),
  },
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
      className="flex items-center gap-1 rounded border border-line bg-panel-2 p-0.5"
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
    setError(null);
    fetch(`/api/stats?region=${encodeURIComponent(region)}&timespan=${encodeURIComponent(timespan)}`, {
      cache: "no-store",
    })
      .then((r) => r.json() as Promise<ApiResponse<StatLeader>>)
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
    <section>
      {/* header: title + count + controls */}
      <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-2">
        <h2 className="font-display text-lg font-bold uppercase tracking-broadcast text-ink">
          Leaderboard
        </h2>
        <span className="font-mono text-[12px] text-dim tabular-nums">
          {sorted.length}
        </span>
        {stale && (
          <span className="font-display text-[10px] uppercase tracking-broadcast text-warn">
            stale
          </span>
        )}
        {loading && (
          <span className="font-display text-[10px] uppercase tracking-broadcast text-mut">
            loading…
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
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

      {error && (
        <p role="alert" className="mb-3 font-body text-[13px] text-down">
          Couldn’t load the leaderboard: {error}
        </p>
      )}

      {isEmpty ? (
        <p className="rounded border border-line bg-panel px-4 py-8 text-center font-body text-[13px] text-mut">
          No leaderboard data.
        </p>
      ) : (
        <div className="overflow-x-auto rounded border border-line bg-panel">
          <table
            className={cn(
              "w-full border-collapse text-left",
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
                      onClick={() => onSort(col.key)}
                    >
                      {col.label}
                      {active && <span aria-hidden>{sortDir === "desc" ? " ▾" : " ▴"}</span>}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {sorted.map((r, i) => (
                <tr key={r.playerId ?? `${r.player}-${i}`}>
                  {COLUMNS.map((col, ci) => {
                    if (col.key === null) {
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
