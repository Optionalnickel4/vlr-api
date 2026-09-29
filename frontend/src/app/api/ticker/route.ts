import { getTicker } from "@/lib/vlr";

// Thin aggregation route for Match Wire. The bounded curator uses the existing
// live/upcoming/results/rankings loaders plus cached live details and team trends.
export const dynamic = "force-dynamic";

export async function GET() {
  return Response.json(await getTicker());
}
