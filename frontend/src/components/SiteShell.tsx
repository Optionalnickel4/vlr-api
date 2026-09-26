import type { ReactNode } from "react";
import { SiteHeader } from "./SiteHeader";
import { StatTicker } from "./StatTicker";

/** Persistent shell; no server data fetching and exactly one ticker owner. */
export function SiteShell({ children }: { children: ReactNode }) {
  return (
    <>
      <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded focus:bg-panel focus:px-4 focus:py-3 focus:text-ink">
        Skip to main content
      </a>
      <SiteHeader />
      {children}
      <StatTicker />
    </>
  );
}
