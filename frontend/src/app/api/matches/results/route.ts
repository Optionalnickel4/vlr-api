import { getResults } from "@/lib/vlr";

// Route handlers are thin: they expose the data-layer loaders (which already
// return the { data, stale, error } envelope and never throw) to client
// components. Server-side fetch only — the browser never calls vlr-api directly.
export const dynamic = "force-dynamic";

export async function GET() {
  return Response.json(await getResults());
}
