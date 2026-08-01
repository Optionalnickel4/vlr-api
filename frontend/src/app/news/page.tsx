import { getNews } from "@/lib/vlr";
import { NewsPanel } from "@/components/NewsPanel";
import { SiteHeader } from "@/components/SiteHeader";

// force-dynamic so the feed reflects vlr-api's current cache on each load rather
// than a build-time snapshot. Same loader the home page's news panel uses.
export const dynamic = "force-dynamic";

/**
 * /news — the full headline feed (the home page carries a short panel of the
 * same data). Narrower column than the match pages: this is prose, so it is
 * capped for line length rather than to fit stat columns.
 */
export default async function NewsPage() {
  const news = await getNews();

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6 sm:py-10">
      <SiteHeader label="news" active="news" />
      <NewsPanel news={news} />
    </main>
  );
}
