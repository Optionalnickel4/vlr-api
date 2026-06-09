import { getRankings } from "@/lib/vlr";

// Thin route handler: exposes the data-layer loader (already returns the
// { data, stale, error } envelope and never throws) to client components.
// Server-side fetch only — the browser never calls vlr-api directly.
// ?region= passes through to the loader; defaults to "all".
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const region = new URL(request.url).searchParams.get("region") ?? "all";
  return Response.json(await getRankings(region));
}
