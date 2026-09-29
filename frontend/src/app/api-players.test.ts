import { beforeEach, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  fetchUpstream: vi.fn(),
  normalizePlayerSearch: vi.fn(),
}));

vi.mock("@/lib/vlr", () => api);

import { GET } from "@/app/api/players/route";

beforeEach(() => vi.clearAllMocks());

it("normalizes backend player-search team identity before returning it to the client", async () => {
  const raw = [{ id: "1265", team_id: "2", team_logo: "https://cdn/sen.png" }];
  const normalized = [{ id: "1265", teamId: "2", teamLogo: "https://cdn/sen.png" }];
  api.fetchUpstream.mockResolvedValue({ data: raw, stale: false });
  api.normalizePlayerSearch.mockReturnValue(normalized);

  const response = await GET(new Request("http://local/api/players?q=john"));

  expect(api.fetchUpstream).toHaveBeenCalledWith("/players?q=john");
  expect(api.normalizePlayerSearch).toHaveBeenCalledWith(raw);
  expect(await response.json()).toEqual({ data: normalized, stale: false });
});

it("keeps the graceful empty search contract when upstream fails", async () => {
  api.fetchUpstream.mockRejectedValue(new Error("offline"));
  const response = await GET(new Request("http://local/api/players?q=john"));
  expect(await response.json()).toEqual({ data: [], stale: true, error: "Error: offline" });
});
