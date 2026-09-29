import { describe, expect, it } from "vitest";
import { buildMatchWire } from "./matchWire";
import type { LiveMatch, MatchWireSources, ResultMatch, TeamTrend, UpcomingMatch } from "@/types/vlr";

const base = (): MatchWireSources => ({ live: [], upcoming: [], results: [], rankings: [], trends: [], liveDetails: [] });
const live = (id: string): LiveMatch => ({ id, team1: "JD Gaming", team2: "FUT Esports", score1: 0, score2: 1, event: "Champions", series: "Opening", url: null, team1Id: "13576", team2Id: "1184", team1Logo: "https://cdn/jdg.png", team2Logo: "https://cdn/fut.png", team1ShortName: "JDG", team2ShortName: "FUT" });
const upcoming = (id: string): UpcomingMatch => ({ id, team1: "G2 Esports", team2: "Paper Rex", timeUntil: "in 2h", startTime: "7:00 PM", event: "Champions", series: "Group", url: null });
const final = (id: string): ResultMatch => ({ id, team1: "LOUD", team2: "Sentinels", score1: 2, score2: 1, time: "2h ago", event: "Americas", series: "Final", url: null });
const mover = (): TeamTrend => ({ teamId: "2", team: "Sentinels", windowDays: 90, ratingTrend: [{ capturedAt: "a", rating: 1, rank: 7 }, { capturedAt: "b", rating: 2, rank: 3 }], ratingChange: 1, resultsInWindow: [], summary: null, logo: "https://cdn/sen.png" });

describe("Match Wire curation", () => {
  it("orders live, upcoming, finals, then movers and links by stable ids", () => {
    const items = buildMatchWire({ ...base(), live: [live("10")], upcoming: [upcoming("20")], results: [final("30")], trends: [mover()] });
    expect(items.map(item => item.kind)).toEqual(["live", "upcoming", "final", "mover"]);
    expect(items.map(item => item.href)).toEqual(["/match/10", "/match/20", "/match/30", "/team/2"]);
  });

  it("degrades through upcoming, final, ranking-only, and empty states", () => {
    expect(buildMatchWire({ ...base(), upcoming: [upcoming("20")] })[0].kind).toBe("upcoming");
    expect(buildMatchWire({ ...base(), results: [final("30")] })[0].kind).toBe("final");
    expect(buildMatchWire({ ...base(), trends: [mover()] })[0].kind).toBe("mover");
    expect(buildMatchWire(base())).toEqual([]);
  });

  it("caps movers so they cannot dominate active match information", () => {
    const trends = Array.from({ length: 8 }, (_, i) => ({ ...mover(), teamId: String(i + 1), team: `Mover ${i + 1}` }));
    const items = buildMatchWire({ ...base(), live: [live("10")], upcoming: [upcoming("20")], results: [final("30")], trends });
    expect(items.filter(item => item.kind === "mover")).toHaveLength(2);
    expect(items.slice(0, 3).map(item => item.kind)).toEqual(["live", "upcoming", "final"]);
  });

  it("marks the final winner with identity as well as score", () => {
    const item = buildMatchWire({ ...base(), results: [final("30")] })[0];
    expect(item.kind).toBe("final");
    if (item.kind === "final") expect(item.winnerId).toBe(item.teams[0].id ?? "side-1");
  });
});
