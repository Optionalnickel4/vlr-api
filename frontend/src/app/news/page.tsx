import "./news.css";
import type { Metadata } from "next";
import { getNews } from "@/lib/vlr";
import { NewsBoard } from "@/components/NewsBoard";
import { PageContainer } from "@/components/PageContainer";
export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "News — valstats" };
export default async function NewsPage() {
  const news = await getNews();
  return <PageContainer width="home"><NewsBoard news={news}/></PageContainer>;
}
