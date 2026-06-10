import { getTeam } from "@/lib/vlr";

// Thin route handler: exposes the data-layer loader (already returns the
// { data, stale, error } envelope and never throws) for /team/{id}. The loader
// turns the upstream 500 (some ids 500 — see OPEN-ITEM-team-detail-500.md) into
// a graceful-empty envelope. Server-side fetch only — the browser never calls
// vlr-api directly.
export const dynamic = "force-dynamic";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  return Response.json(await getTeam(id));
}
