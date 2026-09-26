"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/cn";
import { PlayerSearch } from "@/components/PlayerSearch";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/schedule", label: "Schedule" },
  { href: "/results", label: "Results" },
  { href: "/stats", label: "Stats" },
  { href: "/rankings", label: "Rankings" },
  { href: "/news", label: "News" },
];

/** One shared header. Search follows DOM order on both mobile and desktop. */
export function SiteHeader() {
  const pathname = usePathname();
  return (
    <header className="border-b border-line">
      <div className="mx-auto grid w-full max-w-5xl min-w-0 gap-3 px-4 py-4 sm:px-6 lg:grid-cols-[auto_minmax(0,1fr)_auto] lg:items-center lg:gap-6">
        <Link href="/" aria-label="valstats home" className="w-fit rounded py-2 font-display text-2xl font-bold uppercase leading-none tracking-[0.04em] text-ink">
          valstats<span className="text-accent">.</span>
        </Link>
        <div className="min-w-0 lg:w-52">
          {/* A new route unmounts the old search, cancelling requests/timers.
              There is still exactly one search instance at any viewport width. */}
          <PlayerSearch key={pathname} />
        </div>
        <nav aria-label="Primary" className="grid min-w-0 grid-cols-3 gap-1 lg:flex lg:flex-wrap">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={pathname === item.href ? "page" : undefined}
              className={cn(
                "flex min-h-11 items-center justify-center rounded px-2 py-2 font-body text-sm font-medium transition-colors",
                pathname === item.href ? "bg-panel text-accent underline decoration-2 underline-offset-4" : "text-mut hover:bg-panel hover:text-ink",
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
