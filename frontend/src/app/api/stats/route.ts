import { getStats } from "@/lib/vlr";

// Thin route handler: exposes the stats-leaderboard loader (already returns the
// { data, stale, error } envelope and never throws) to the client island.
// Server-side fetch only — the browser never calls vlr-api directly. region +
// timespan pass through to the loader; default na / all.
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const sp = new URL(request.url).searchParams;
  const region = sp.get("region") ?? "na";
  const timespan = sp.get("timespan") ?? "all";
  return Response.json(await getStats(region, timespan));
}
