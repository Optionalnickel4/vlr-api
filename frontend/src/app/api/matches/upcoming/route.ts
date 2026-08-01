import { getUpcoming } from "@/lib/vlr";

// Thin route handler: exposes the data-layer loader (already returns the
// { data, stale, error } envelope and never throws) to client components.
// Server-side fetch only — the browser never calls vlr-api directly.
// NB the full upcoming list is server-rendered by /schedule; this exists for
// client-side consumers, so it is not the schedule page's data path.
export const dynamic = "force-dynamic";

export async function GET() {
  return Response.json(await getUpcoming());
}
