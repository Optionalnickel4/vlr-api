"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
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
  const [active, setActive] = useState(-1);
  const listId = useId();
  const versionRef = useRef(0);
  const requestRef = useRef<AbortController | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Invalidate before aborting: a transport can ignore cancellation or already
  // be decoding a response. Only the current generation may update the UI.
  const cancelPending = useCallback(() => {
    versionRef.current += 1;
    if (timerRef.current !== null) clearTimeout(timerRef.current);
    timerRef.current = null;
    requestRef.current?.abort();
    requestRef.current = null;
  }, []);

  const dismiss = useCallback(() => {
    cancelPending();
    setOpen(false);
    setLoading(false);
    setActive(-1);
  }, [cancelPending]);

  useEffect(() => {
    function onDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        dismiss();
      }
    }
    document.addEventListener("mousedown", onDown);
    return () => {
      document.removeEventListener("mousedown", onDown);
      cancelPending();
    };
  }, [cancelPending, dismiss]);

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const q = e.target.value;
    cancelPending();
    const version = versionRef.current;
    setQuery(q);
    setItems([]);
    setError(null);
    setActive(-1);
    setLoading(q.length >= MIN_QUERY_LEN);
    setOpen(q.length >= MIN_QUERY_LEN);
    if (q.length < MIN_QUERY_LEN) return;

    timerRef.current = setTimeout(async () => {
      timerRef.current = null;
      const controller = new AbortController();
      requestRef.current = controller;
      try {
        const r = await fetch(`/api/players?q=${encodeURIComponent(q)}`, {
          cache: "no-store",
          signal: controller.signal,
        });
        if (!r.ok) throw new Error("Player search is unavailable. Try again.");
        const res = (await r.json()) as ApiResponse<PlayerSearchResult>;
        if (version !== versionRef.current) return;
        if (res.error) throw new Error(res.error);
        if (!Array.isArray(res.data)) throw new Error("Invalid player search response.");
        setItems(res.data);
      } catch (err) {
        if (version !== versionRef.current) return;
        setError(err instanceof Error ? err.message : "Player search is unavailable. Try again.");
        setItems([]);
      } finally {
        if (version === versionRef.current) {
          requestRef.current = null;
          setLoading(false);
        }
      }
    }, DEBOUNCE_MS);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.nativeEvent.isComposing) return;
    if (e.key === "Escape") {
      e.preventDefault();
      dismiss();
      setQuery("");
      setItems([]);
      setError(null);
    }
    if ((e.key === "ArrowDown" || e.key === "ArrowUp") && items.length > 0) {
      e.preventDefault();
      setOpen(true);
      setActive((previous) => e.key === "ArrowDown"
        ? (previous + 1) % items.length
        : (previous <= 0 ? items.length - 1 : previous - 1));
    }
    if (e.key === "Enter" && open && items.length > 0) {
      const item = items[active < 0 ? 0 : active];
      if (item.id) {
        e.preventDefault();
        dismiss();
        window.location.href = `/player/${item.id}`;
      }
    }
  }

  const showDropdown = open;
  const announcement = !open ? "" : loading ? "Searching players…" : error
    ? `Search failed: ${error}` : items.length === 0 ? "No players found"
    : `${items.length} ${items.length === 1 ? "player" : "players"} found. Use arrow keys to choose a player and Enter to open their profile.`;

  return (
    <div ref={containerRef} className="relative" onBlur={(e) => {
      if (!e.currentTarget.contains(e.relatedTarget as Node | null)) dismiss();
    }}>
      <input
        type="search"
        value={query}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder="Search players…"
        role="combobox"
        aria-label="Search players"
        aria-expanded={showDropdown}
        aria-controls={showDropdown ? listId : undefined}
        aria-activedescendant={open && active >= 0 ? `${listId}-${active}` : undefined}
        aria-autocomplete="list"
        className={cn(
          "w-36 rounded border border-line bg-panel px-2.5 py-1",
          "font-body text-[12px] text-ink placeholder:text-dim",
          "focus:border-accent focus:ring-2 focus:ring-accent/60 focus:outline-none transition-colors",
          "sm:w-44",
        )}
      />

      <div role="status" aria-live="polite" aria-atomic="true" className="sr-only">{announcement}</div>

      {showDropdown && (
        <div
          className={cn(
            "absolute right-0 top-full z-50 mt-1 min-w-[200px] rounded border border-line bg-panel shadow-lg",
            "overflow-hidden",
          )}
        >
          {loading && (
            <div className="px-3 py-2 font-body text-[12px] text-mut">Loading…</div>
          )}

          {!loading && error && (
            <div
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

          <div id={listId} role="listbox" aria-label="Player results" aria-busy={loading} className="divide-y divide-line">
            {!loading &&
              !error &&
              items.map((item, index) => (
                <Link
                  key={item.id ?? item.alias}
                  href={`/player/${item.id}`}
                  id={`${listId}-${index}`}
                  role="option"
                  aria-selected={index === active}
                  tabIndex={-1}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={dismiss}
                  className={cn(
                    "flex items-center justify-between px-3 py-2 hover:bg-panel-2 transition-colors",
                    index === active && "bg-panel-2 ring-2 ring-inset ring-accent/60",
                  )}
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
        </div>
      )}
    </div>
  );
}
