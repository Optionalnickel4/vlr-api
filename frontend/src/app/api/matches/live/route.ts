import { getLive } from "@/lib/vlr";

// Polled by the client every 30s (matches the upstream live TTL). Never cached.
export const dynamic = "force-dynamic";

export async function GET() {
  return Response.json(await getLive());
}
