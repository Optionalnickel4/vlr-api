"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { cn } from "@/lib/cn";
import type { ApiResponse, PlayerSearchResult } from "@/types/vlr";

export const MIN_QUERY_LEN = 2;
export const DEBOUNCE_MS = 250;

/**
 * PlayerSearch — a self-fetching client island that drops into SiteHeader.
 *
 * HYDRATION: all state seeds empty (query="", items=[], …) so the SSR render
 * and the first client render are identical — no hydration mismatch. Results
 * only appear after user input + a debounced fetch, which is post-mount only.
 *
 * DEBOUNCE: 250 ms — prevents per-keystroke hammering of the VLR autocomplete
 * fallback on DB misses (see Phase 10 / backend search.py notes).
 */
export function PlayerSearch() {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<PlayerSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Click-outside closes the dropdown.
  useEffect(() => {
    function onDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const q = e.target.value;
    setQuery(q);
    if (timerRef.current) clearTimeout(timerRef.current);

    if (q.length < MIN_QUERY_LEN) {
      setItems([]);
      setError(null);
      setOpen(false);
      return;
    }

    timerRef.current = setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const r = await fetch(`/api/players?q=${encodeURIComponent(q)}`, {
          cache: "no-store",
        });
        const res = (await r.json()) as ApiResponse<PlayerSearchResult>;
        if (res.error) setError(res.error);
        setItems(res.data);
        setOpen(true);
      } catch (err) {
        setError(String(err));
        setItems([]);
        setOpen(true);
      } finally {
        setLoading(false);
      }
    }, DEBOUNCE_MS);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Escape") {
      setOpen(false);
      setQuery("");
      setItems([]);
      setError(null);
    }
    if (e.key === "Enter" && items.length > 0 && items[0].id) {
      window.location.href = `/player/${items[0].id}`;
    }
  }

  const showDropdown = open;

  return (
    <div ref={containerRef} className="relative">
      <input
        type="search"
        value={query}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder="Search players…"
        aria-label="Search players"
        aria-expanded={showDropdown}
        aria-haspopup="listbox"
        className={cn(
          "w-36 rounded border border-line bg-panel px-2.5 py-1",
          "font-body text-[12px] text-ink placeholder:text-dim",
          "focus:border-accent/60 focus:outline-none transition-colors",
          "sm:w-44",
        )}
      />

      {showDropdown && (
        <div
          role="listbox"
          aria-label="Player results"
          className={cn(
            "absolute right-0 top-full z-50 mt-1 min-w-[200px] rounded border border-line bg-panel shadow-lg",
            "divide-y divide-line overflow-hidden",
          )}
        >
          {loading && (
            <div className="px-3 py-2 font-body text-[12px] text-mut">Loading…</div>
          )}

          {!loading && error && (
            <div
              role="alert"
              className="px-3 py-2 font-body text-[12px] text-down"
            >
              {error}
            </div>
          )}

          {!loading && !error && items.length === 0 && (
            <div className="px-3 py-2 font-body text-[12px] text-mut">
              No players found
            </div>
          )}

          {!loading &&
            !error &&
            items.map((item) => (
              <Link
                key={item.id ?? item.alias}
                href={`/player/${item.id}`}
                onClick={() => setOpen(false)}
                className="flex items-center justify-between px-3 py-2 hover:bg-panel-2 transition-colors"
              >
                <span className="font-display text-[13px] font-semibold uppercase tracking-[0.04em] text-ink">
                  {item.alias}
                </span>
                <span className="ml-3 flex items-center gap-1.5">
                  {item.team && (
                    <span className="font-body text-[11px] text-mut">
                      {item.team}
                    </span>
                  )}
                  {item.source === "vlr" && (
                    <span className="font-display text-[10px] uppercase tracking-[0.1em] text-dim">
                      vlr
                    </span>
                  )}
                </span>
              </Link>
            ))}
        </div>
      )}
    </div>
  );
}
