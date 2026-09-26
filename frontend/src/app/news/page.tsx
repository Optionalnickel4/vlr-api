import type { Metadata } from "next";
import { getNews } from "@/lib/vlr";
import { NewsPanel } from "@/components/NewsPanel";
import { PageContainer } from "@/components/PageContainer";

// force-dynamic so the feed reflects vlr-api's current cache on each load rather
// than a build-time snapshot. Same loader the home page's news panel uses.
export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "News — valstats" };

/**
 * /news — the full headline feed (the home page carries a short panel of the
 * same data). Narrower column than the match pages: this is prose, so it is
 * capped for line length rather than to fit stat columns.
 */
export default async function NewsPage() {
  const news = await getNews();

  return (
    <PageContainer width="reading" title="News">
      <NewsPanel news={news} />
    </PageContainer>
  );
}
