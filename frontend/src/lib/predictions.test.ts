import { describe, expect, it } from "vitest";
import { normalizePredictions, normalizePredictionAccuracy } from "./predictions";

const fixture = () => ({ match_id: "123", teams: [{ id: "1", name: "Alpha" }, { id: "2", name: "Beta" }],
  status: "published", starts_at: "2026-10-09T12:00:00Z", generated_at: "2026-10-08T12:00:00Z",
  prediction: { winner_id: "1", explanation: "Alpha has stronger recent results.", evidence_ids: ["form:1", "form:2"], caveats: ["Unequal opponents."] },
  facts: [{ id: "form:1", team_id: "1", text: "Four wins.", source_url: "javascript:alert(1)" }, { id: "form:2", team_id: "2", text: "Two wins." }] });

describe("prediction boundary", () => {
  it("keeps a valid pick and derives source links from verified IDs", () => {
    const [pick] = normalizePredictions([fixture()]);
    expect(pick.status).toBe("published");
    expect(pick.facts[0].sourceUrl).toBe("https://www.vlr.gg/team/1");
  });
  it.each([
    { winner_id: "3" }, { evidence_ids: ["form:1", "unknown"] },
    { evidence_ids: ["form:1", "form:1"] }, { caveats: [] },
  ])("withholds invalid picks: %j", change => {
    const row = fixture();
    const [pick] = normalizePredictions([{ ...row, prediction: { ...row.prediction, ...change } }]);
    expect(pick.status).toBe("pending");
    expect(pick.prediction).toBeNull();
    expect(pick.facts).toEqual([]);
  });
  it("withholds predictions generated after the start", () => {
    expect(normalizePredictions([{ ...fixture(), generated_at: "2026-10-10T12:00:00Z" }])[0].status).toBe("pending");
  });
  it("preserves explicit abstention", () => {
    const row = fixture();
    expect(normalizePredictions([{ ...row, status: "no_pick", prediction: { ...row.prediction, winner_id: null } }])[0].status).toBe("no_pick");
  });
  it("grades winner picks against the confirmed result and keeps abstentions unscored", () => {
    const row = { ...fixture(), result: { winner_id: "2", scores: { "1": 1, "2": 2 } } };
    expect(normalizePredictions([row])[0].result?.outcome).toBe("incorrect");
    expect(normalizePredictions([{ ...row, prediction: { ...row.prediction, winner_id: "2" } }])[0].result?.outcome).toBe("correct");
    expect(normalizePredictions([{ ...row, status: "no_pick", prediction: { ...row.prediction, winner_id: null } }])[0].result?.outcome).toBe("no_pick");
  });
  it.each([{ winner_id: "3", scores: { "1": 1, "2": 2 } },
    { winner_id: "1", scores: { "1": 1, "2": 2 } },
    { winner_id: "2", scores: { "1": 2, "2": 2 } },
    { winner_id: "2", scores: { "1": null, "2": 2 } }])("withholds inconsistent results: %j", result => {
    expect(normalizePredictions([{ ...fixture(), result }])[0].result).toBeNull();
  });
  it("validates all-time counters without deriving accuracy from a limited card list", () => {
    expect(normalizePredictionAccuracy({ correct: 8, incorrect: 2, no_pick: 4, awaiting_result: 1 }))
      .toEqual({ correct: 8, incorrect: 2, noPick: 4, awaitingResult: 1 });
    expect(normalizePredictionAccuracy({ correct: -1, incorrect: 2, no_pick: 4, awaiting_result: 1 })).toBeUndefined();
  });
});
