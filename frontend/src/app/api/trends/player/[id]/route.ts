import { getPlayerTrend } from "@/lib/vlr";

// Thin route handler for the Phase 8 player rating/ACS-trend view. The loader
// returns the { data, stale, error } envelope and never throws; a `?days=` query
// passes through to the window (defaults to 90). A player with no banked
// snapshots 404s upstream → load() maps it to graceful-empty. Server-side only.
export const dynamic = "force-dynamic";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const daysParam = new URL(request.url).searchParams.get("days");
  const days = daysParam ? Number(daysParam) : undefined;
  return Response.json(
    await getPlayerTrend(id, Number.isFinite(days as number) ? days : undefined),
  );
}
