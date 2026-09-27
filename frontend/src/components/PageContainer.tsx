import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

const WIDTHS = { home: "max-w-7xl", reading: "max-w-3xl", schedule: "max-w-4xl", analysis: "max-w-5xl" };

/** Pages own the main landmark; the persistent shell supplies navigation. */
export function PageContainer({ children, width = "analysis", title }: {
  children: ReactNode;
  width?: keyof typeof WIDTHS;
  title?: string;
}) {
  return (
    <main id="main-content" tabIndex={-1} className={cn("mx-auto w-full min-w-0 px-4 py-8 sm:px-6 sm:py-10", WIDTHS[width])}>
      {title && <h1 className="mb-6 font-display text-2xl font-bold uppercase tracking-[0.04em] text-ink">{title}</h1>}
      {children}
    </main>
  );
}
