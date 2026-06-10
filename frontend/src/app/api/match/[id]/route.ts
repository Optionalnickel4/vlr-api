import { getMatch } from "@/lib/vlr";

// Thin route handler for the Phase 7 match-detail endpoint. The loader returns
// the { data, stale, error } envelope and never throws; an upstream 404 (id with
// no vlr page) maps to graceful-empty. Server-side fetch only — the browser
// never calls vlr-api directly.
export const dynamic = "force-dynamic";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  return Response.json(await getMatch(id));
}
