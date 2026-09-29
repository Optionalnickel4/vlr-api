import { fetchUpstream, normalizePlayerSearch } from "@/lib/vlr";

// Thin proxy: forwards q= to the backend /players endpoint which already
// returns the { data, stale, error } envelope. Never throws — upstream errors
// degrade to a graceful-empty. Browser never hits vlr-api directly.
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const q = new URL(request.url).searchParams.get("q") ?? "";
  try {
    const raw = await fetchUpstream(`/players?q=${encodeURIComponent(q)}`);
    const envelope = raw && typeof raw === "object" && !Array.isArray(raw)
      ? raw as Record<string, unknown>
      : {};
    return Response.json({
      data: normalizePlayerSearch(envelope.data),
      stale: envelope.stale === true,
      ...(envelope.error ? { error: String(envelope.error) } : {}),
    });
  } catch (err) {
    return Response.json({ data: [], stale: true, error: String(err) });
  }
}
