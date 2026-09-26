import Link from "next/link";
import { PageContainer } from "@/components/PageContainer";

export default function NotFound() {
  return <PageContainer title="Page not found" width="reading">
    <p className="mb-4 text-mut">This page does not exist.</p>
    <Link href="/">Back to match center</Link>
  </PageContainer>;
}
