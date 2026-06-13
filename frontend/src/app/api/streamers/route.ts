import { getFeaturedStreamers } from "@/lib/twitch";

// Thin route for the featured-streamers bar. getFeaturedStreamers fans out
// server-side — live matches' Twitch channels ∪ TWITCH_FEATURED → Helix
// (live-only) → Valorant-only → one request-time shuffle — and returns the
// { data, stale, error } envelope. It never throws; an empty list hides the bar.
// force-dynamic so each load re-queries Twitch (fresh live set + fresh order).
// Server-side only: the Twitch client secret never reaches the browser.
export const dynamic = "force-dynamic";

export async function GET() {
  return Response.json(await getFeaturedStreamers());
}
