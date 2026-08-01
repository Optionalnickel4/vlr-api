// Schedule grouping + crest logic (PURE, unit-tested in schedule.test.ts).
//
// ⚠️ DERIVED DATE — READ THIS. vlr's upcoming feed carries NO absolute kickoff
// timestamp, only a relative countdown string (`timeUntil`, e.g. "2h 15m",
// "1d 4h"). To bucket matches into TODAY / TOMORROW / weekday we parse that
// countdown into a millisecond offset and add it to "now" (the server render
// time). The resulting calendar day is an APPROXIMATION, good enough to group
// by day but NOT an exact start time — never treat it as authoritative. Any
// countdown we cannot parse (LIVE / TBD / empty / unknown format) routes to a
// safe trailing "Later" bucket so the render can never crash or misbucket.
//
// ⚠️ THE DAY BOUNDARIES ARE THE SERVER'S, NOT THE VIEWER'S. Bucketing runs in a
// server component (app/schedule/page.tsx is force-dynamic), and startOfDayMs
// uses LOCAL midnight — local to the Node process. So "Today" means today in the
// container's timezone, and a viewer in a different zone can see a match labelled
// "Tomorrow" that is still this evening for them. Deliberate: computing it
// server-side is what keeps SSR and hydration identical (a client-side "now"
// would diverge from the server's markup and produce a hydration mismatch).
// Doing this per-viewer would mean bucketing on the client after mount, and
// accepting a flash of unbucketed content.

import type { UpcomingMatch } from "@/types/vlr";

const SECOND = 1_000;
const MINUTE = 60 * SECOND;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

// Unit → ms. `mo` (month, ~30d) and `w` (week) are included because vlr emits
// them for far-out matches; the spec's core cases (m/h/d) are the common ones.
const UNIT_MS: Record<string, number> = {
  mo: 30 * DAY,
  w: 7 * DAY,
  d: DAY,
  h: HOUR,
  m: MINUTE,
  s: SECOND,
};

// One "<number><unit>" token. ORDER MATTERS: `mo` must precede `m` in the
// alternation so "1mo" parses as one month, not "1m" + a stray "o".
const ETA_TOKEN = /(\d+)\s*(mo|w|d|h|m|s)\b/gi;

/**
 * Parse a vlr countdown string into a millisecond offset from now.
 *
 * Handles every format vlr emits — "45m", "2h", "2h 15m", "1d 4h", "1w 2d",
 * "1mo" (and surrounding whitespace / mixed case). Returns `null` for LIVE /
 * TBD / empty / null / anything containing no numeric token, so callers can
 * route those to the catch-all bucket instead of fabricating a day.
 */
export function parseEtaOffsetMs(eta: string | null | undefined): number | null {
  if (!eta) return null;
  const s = eta.trim().toLowerCase();
  if (!s || s.includes("live")) return null;

  let total = 0;
  let matched = false;
  for (const tok of s.matchAll(ETA_TOKEN)) {
    const n = Number(tok[1]);
    const unit = tok[2];
    if (!Number.isFinite(n) || !(unit in UNIT_MS)) continue;
    total += n * UNIT_MS[unit];
    matched = true;
  }
  return matched ? total : null;
}

// ---- day bucketing ----------------------------------------------------------

export type DayKind = "today" | "tomorrow" | "future" | "later";

// Title-case abbreviations (uppercased at render via font-display). Fixed arrays
// keep labels deterministic across locales/CI — no Intl locale surprises.
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function startOfDayMs(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

// Whole-calendar-day difference between two dates, using LOCAL midnights. Diffing
// midnights then rounding absorbs DST (23h/25h days) cleanly.
function calendarDayDiff(now: Date, target: Date): number {
  return Math.round((startOfDayMs(target) - startOfDayMs(now)) / DAY);
}

function dayMeta(diff: number, now: Date): { key: string; label: string; kind: DayKind } {
  if (diff === 0) return { key: "d0", label: "Today", kind: "today" };
  if (diff === 1) return { key: "d1", label: "Tomorrow", kind: "tomorrow" };
  const d = new Date(startOfDayMs(now) + diff * DAY);
  return {
    key: `d${diff}`,
    label: `${WEEKDAYS[d.getDay()]} · ${MONTHS[d.getMonth()]} ${d.getDate()}`,
    kind: "future",
  };
}

/** Derived calendar-day offset for a match (0 = today, 1 = tomorrow, …), or
 *  `null` when the countdown is unparseable (→ "Later" bucket). A tiny negative
 *  offset (clock skew) is clamped to today rather than leaking a past day. */
export function matchDayDiff(m: UpcomingMatch, now: Date): number | null {
  const offset = parseEtaOffsetMs(m.timeUntil);
  if (offset === null) return null;
  const diff = calendarDayDiff(now, new Date(now.getTime() + offset));
  return diff < 0 ? 0 : diff;
}

// ---- grouped shape ----------------------------------------------------------

export interface ScheduleEventGroup {
  key: string;
  event: string | null;
  series: string | null;
  matches: UpcomingMatch[];
}

export interface ScheduleDay {
  key: string;
  label: string;
  kind: DayKind;
  events: ScheduleEventGroup[];
}

export interface ScheduleBoardData {
  hero: UpcomingMatch | null;
  days: ScheduleDay[];
}

/**
 * Group matches into ordered day sections, each sub-grouped by event+series.
 * Input order is preserved (vlr returns soonest-first); the "Later" catch-all
 * (unparseable etas) always sorts last so a surprise format can never break the
 * ordering or crash the render.
 */
export function groupSchedule(matches: UpcomingMatch[], now: Date): ScheduleDay[] {
  const order: (number | "later")[] = [];
  const byDay = new Map<number | "later", ScheduleDay>();

  for (const m of matches) {
    const diff = matchDayDiff(m, now);
    const dkey: number | "later" = diff === null ? "later" : diff;

    let day = byDay.get(dkey);
    if (!day) {
      const meta =
        dkey === "later"
          ? { key: "later", label: "Later", kind: "later" as DayKind }
          : dayMeta(dkey, now);
      day = { key: meta.key, label: meta.label, kind: meta.kind, events: [] };
      byDay.set(dkey, day);
      order.push(dkey);
    }

    // Sub-group by event + series so the tournament label is stated once. The
    // list is short (~50), so a linear find per match is fine and preserves
    // first-appearance order within the day.
    const ekey = `${m.event ?? ""}|${m.series ?? ""}`;
    let grp = day.events.find((e) => e.key === ekey);
    if (!grp) {
      grp = { key: ekey, event: m.event, series: m.series, matches: [] };
      day.events.push(grp);
    }
    grp.matches.push(m);
  }

  order.sort((a, b) => {
    if (a === "later") return 1;
    if (b === "later") return -1;
    return a - b;
  });
  return order.map((k) => byDay.get(k)!);
}

/**
 * Build the full schedule board: pull the soonest match out as the hero, group
 * the rest by day. The hero is the smallest PARSEABLE offset (a leading TBD row
 * shouldn't become the showpiece); it falls back to the first match, and is
 * excluded from the day groups so it is never shown twice.
 */
export function buildSchedule(matches: UpcomingMatch[], now: Date): ScheduleBoardData {
  if (matches.length === 0) return { hero: null, days: [] };

  let hero: UpcomingMatch | null = null;
  let best = Infinity;
  for (const m of matches) {
    const off = parseEtaOffsetMs(m.timeUntil);
    if (off !== null && off < best) {
      best = off;
      hero = m;
    }
  }
  if (!hero) hero = matches[0];

  const rest = matches.filter((m) => m !== hero);
  return { hero, days: groupSchedule(rest, now) };
}

// ---- crest helpers (typographic fallback — vlr's match list has no logos) ----

/** Deterministic 1–3 char abbreviation from a team name, for the crest disc. */
export function teamInitials(name: string | null | undefined): string {
  if (!name) return "?";
  const words = name.trim().split(/[\s/·._-]+/).filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0].slice(0, 3).toUpperCase();
  return words.slice(0, 3).map((w) => w[0]).join("").toUpperCase();
}

/** Deterministic hue (0–359) from a team name. Saturation/lightness are applied
 *  at render (muted, never neon) so crests read as broadcast chips while staying
 *  distinguishable per team. Empty/TBD gets a teal-ish default.
 *
 *  "Deterministic" is a hydration requirement, not a preference: the same name
 *  must hash to the same hue on the server and on the client, or the crest
 *  changes colour on hydration. Rules out Math.random() and any time/locale
 *  input if you ever rework the palette. */
export function teamHue(name: string | null | undefined): number {
  if (!name) return 190;
  let h = 0;
  for (let i = 0; i < name.length; i++) {
    h = (h * 31 + name.charCodeAt(i)) >>> 0;
  }
  return h % 360;
}
