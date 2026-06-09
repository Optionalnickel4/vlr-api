import { getNews } from "@/lib/vlr";

// Thin route handler: exposes the data-layer loader (already returns the
// { data, stale, error } envelope and never throws) to client components.
// Server-side fetch only — the browser never calls vlr-api directly.
export const dynamic = "force-dynamic";

export async function GET() {
  return Response.json(await getNews());
}
