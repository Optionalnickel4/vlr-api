import { getUpcoming } from "@/lib/vlr";

export const dynamic = "force-dynamic";

export async function GET() {
  return Response.json(await getUpcoming());
}
