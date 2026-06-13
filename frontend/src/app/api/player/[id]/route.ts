import { getPlayer } from "@/lib/vlr";

// Thin route handler: exposes the data-layer loader (already returns the
// { data, stale, error } envelope and never throws) for /player/{id}. An
// upstream 404/500 is caught in load() → graceful-empty. Server-side fetch only
// — the browser never calls vlr-api directly.
export const dynamic = "force-dynamic";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  return Response.json(await getPlayer(id));
}
