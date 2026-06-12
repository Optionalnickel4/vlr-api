import { getTicker } from "@/lib/vlr";

// Thin aggregation route for the broadcast stat ticker. getTicker fans out
// (bounded) over the SAME loaders the match center already uses — results +
// rankings, plus a few match details (top ACS) and team trends (movers) — and
// curates the notable-stats tape. It returns the { data, stale, error } envelope
// and never throws; an empty tape simply hides the ticker. Server-side fetch
// only — the browser never calls vlr-api directly. No new scraping surface.
export const dynamic = "force-dynamic";

export async function GET() {
  return Response.json(await getTicker());
}
