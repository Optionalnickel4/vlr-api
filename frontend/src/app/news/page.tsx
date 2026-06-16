import { getNews } from "@/lib/vlr";
import { NewsPanel } from "@/components/NewsPanel";
import { SiteHeader } from "@/components/SiteHeader";

export const dynamic = "force-dynamic";

export default async function NewsPage() {
  const news = await getNews();

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6 sm:py-10">
      <SiteHeader label="news" active="news" />
      <NewsPanel news={news} />
    </main>
  );
}
