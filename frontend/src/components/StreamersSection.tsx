import { FeaturedStreamers } from "./FeaturedStreamers";
import { getFeaturedStreamers } from "@/lib/twitch";

/** Optional server-rendered content; its Suspense boundary keeps match coverage
 * independent of match-detail fan-out and external Twitch requests. */
export async function StreamersSection() {
  const streams = await getFeaturedStreamers();
  return <FeaturedStreamers streams={streams.data} />;
}
