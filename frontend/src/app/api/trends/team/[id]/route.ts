import { getTeamTrend } from "@/lib/vlr";

// Thin route handler for the team rating-trend view. The loader returns the
// { data, stale, error } envelope and never throws; a `?days=` query passes
// through to the window (defaults to 90). This endpoint also 500s on certain
// ids upstream — the loader maps that to graceful-empty. Server-side only.
export const dynamic = "force-dynamic";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const daysParam = new URL(request.url).searchParams.get("days");
  const days = daysParam ? Number(daysParam) : undefined;
  return Response.json(
    await getTeamTrend(id, Number.isFinite(days as number) ? days : undefined),
  );
}
