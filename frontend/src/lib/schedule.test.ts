// Schedule logic tests. The eta→offset→day derivation is the one correctness-
// sensitive piece (vlr gives no absolute timestamp), so we lock every format
// variant AND the unparseable fallback — an unexpected eta must route to a safe
// "Later" bucket, never crash or misbucket. Grouping/hero-selection contracts
// are asserted against a FIXED `now` so buckets are deterministic across zones.

import { describe, expect, it } from "vitest";

import {
  buildSchedule,
  groupSchedule,
  matchDayDiff,
  parseEtaOffsetMs,
  teamInitials,
} from "@/lib/schedule";
import type { UpcomingMatch } from "@/types/vlr";

const MIN = 60_000;
const HOUR = 60 * MIN;
const DAY = 24 * HOUR;

function match(over: Partial<UpcomingMatch>): UpcomingMatch {
  return {
    id: null,
    team1: "A",
    team2: "B",
    timeUntil: null,
    startTime: null,
    series: null,
    event: null,
    url: null,
    ...over,
  };
}

describe("parseEtaOffsetMs — every vlr format", () => {
  it("minutes only", () => {
    expect(parseEtaOffsetMs("45m")).toBe(45 * MIN);
  });
  it("hours only", () => {
    expect(parseEtaOffsetMs("2h")).toBe(2 * HOUR);
  });
  it("hours + minutes", () => {
    expect(parseEtaOffsetMs("2h 15m")).toBe(2 * HOUR + 15 * MIN);
  });
  it("days + hours", () => {
    expect(parseEtaOffsetMs("1d 4h")).toBe(DAY + 4 * HOUR);
  });
  it("weeks + days", () => {
    expect(parseEtaOffsetMs("1w 2d")).toBe(7 * DAY + 2 * DAY);
  });
  it("months (mo beats the m unit)", () => {
    expect(parseEtaOffsetMs("1mo")).toBe(30 * DAY);
  });
  it("tolerates surrounding whitespace and case", () => {
    expect(parseEtaOffsetMs("  1D 22H  ")).toBe(DAY + 22 * HOUR);
  });
});

describe("parseEtaOffsetMs — unparseable → null (safe fallback)", () => {
  it.each([
    ["LIVE", "LIVE"],
    ["TBD", "TBD"],
    ["empty string", ""],
    ["whitespace", "   "],
    ["word with no number", "soon"],
    ["unknown unit", "5y"],
  ])("%s", (_label, input) => {
    expect(parseEtaOffsetMs(input)).toBeNull();
  });

  it("null / undefined", () => {
    expect(parseEtaOffsetMs(null)).toBeNull();
    expect(parseEtaOffsetMs(undefined)).toBeNull();
  });
});

describe("matchDayDiff — buckets relative to a fixed now", () => {
  // Mon Jul 27 2026, local noon — margins kept away from midnight so the bucket
  // never depends on the runner's timezone.
  const now = new Date(2026, 6, 27, 12, 0, 0);

  it("a few hours out → today (0)", () => {
    expect(matchDayDiff(match({ timeUntil: "2h" }), now)).toBe(0);
  });
  it("into the next day → tomorrow (1)", () => {
    expect(matchDayDiff(match({ timeUntil: "20h" }), now)).toBe(1);
  });
  it("several days out → that day diff", () => {
    expect(matchDayDiff(match({ timeUntil: "3d 2h" }), now)).toBe(3);
  });
  it("unparseable → null", () => {
    expect(matchDayDiff(match({ timeUntil: "TBD" }), now)).toBeNull();
  });
});

describe("groupSchedule — day + event structure, Later catch-all last", () => {
  const now = new Date(2026, 6, 27, 12, 0, 0);

  it("buckets by derived day and keeps unparseable in a trailing Later group", () => {
    const days = groupSchedule(
      [
        match({ timeUntil: "1h", event: "Masters", series: "R1", team1: "T1" }),
        match({ timeUntil: "3d", event: "Masters", series: "R3", team1: "T2" }),
        match({ timeUntil: "TBD", event: "Challengers", team1: "T3" }),
        match({ timeUntil: "2h", event: "Masters", series: "R1", team1: "T4" }),
      ],
      now,
    );

    // today, future (+3), later — later is always last
    expect(days.map((d) => d.kind)).toEqual(["today", "future", "later"]);
    expect(days[0].label).toBe("Today");
    expect(days[days.length - 1].label).toBe("Later");

    // two "Masters · R1" matches on the same day share ONE event group
    const today = days[0];
    expect(today.events).toHaveLength(1);
    expect(today.events[0].event).toBe("Masters");
    expect(today.events[0].matches.map((m) => m.team1)).toEqual(["T1", "T4"]);
  });

  it("empty input yields no days", () => {
    expect(groupSchedule([], now)).toEqual([]);
  });
});

describe("buildSchedule — hero selection", () => {
  const now = new Date(2026, 6, 27, 12, 0, 0);

  it("picks the soonest PARSEABLE match as hero, even behind a leading TBD, and excludes it from days", () => {
    const soon = match({ timeUntil: "30m", team1: "SOON" });
    const board = buildSchedule(
      [
        match({ timeUntil: "TBD", team1: "TBD_ROW" }),
        soon,
        match({ timeUntil: "2h", team1: "LATER" }),
      ],
      now,
    );

    expect(board.hero).toBe(soon);
    // hero not duplicated in the grouped days
    const shown = board.days.flatMap((d) => d.events.flatMap((e) => e.matches));
    expect(shown).not.toContain(soon);
    expect(shown).toHaveLength(2);
  });

  it("falls back to the first match when none are parseable", () => {
    const first = match({ timeUntil: "TBD", team1: "FIRST" });
    const board = buildSchedule([first, match({ timeUntil: "" })], now);
    expect(board.hero).toBe(first);
  });

  it("empty input → null hero", () => {
    expect(buildSchedule([], now)).toEqual({ hero: null, days: [] });
  });
});

describe("teamInitials — deterministic crest label", () => {
  it.each([
    ["Sentinels", "SEN"],
    ["Paper Rex", "PR"],
    ["Natus Vincere", "NV"],
    ["FULL SENSE", "FS"],
    ["TBD", "TBD"],
  ])("%s → %s", (name, expected) => {
    expect(teamInitials(name)).toBe(expected);
  });

  it("null → placeholder", () => {
    expect(teamInitials(null)).toBe("?");
  });
});
