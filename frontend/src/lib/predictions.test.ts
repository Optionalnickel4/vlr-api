import { describe, expect, it } from "vitest";
import { normalizePredictions } from "./predictions";

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
});
