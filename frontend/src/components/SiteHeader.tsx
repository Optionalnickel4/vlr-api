import Link from "next/link";
import { cn } from "@/lib/cn";
import { PlayerSearch } from "@/components/PlayerSearch";

/**
 * SiteHeader — the VALSTATS broadcast header + primary nav. The wordmark links
 * home (the match center); the nav links the dedicated full-list pages. It reads
 * as part of the broadcast header, not a generic menu: same Saira-condensed
 * uppercase wide-tracked voice, accent only on the active item.
 *
 * Extensible by design — a new top-level page slots in with ONE entry in NAV.
 *
 * Responsive: wordmark + page label on the left, nav + search on the right; the
 * row wraps cleanly on a phone.
 */
const NAV: { href: string; label: string; key: string }[] = [
  { href: "/schedule", label: "Schedule", key: "schedule" },
  { href: "/results", label: "Results", key: "results" },
  { href: "/stats", label: "Stats", key: "stats" },
];

export function SiteHeader({
  label,
  active,
}: {
  /** short page label shown next to the wordmark (e.g. "match center"). */
  label?: string;
  /** nav key of the current page — lit accent in the nav, others stay muted. */
  active?: string;
}) {
  return (
    <header className="mb-8 flex flex-wrap items-center gap-x-5 gap-y-3 border-b border-line pb-4 md:mb-10">
      <Link
        href="/"
        className="font-display text-2xl font-bold uppercase leading-none tracking-[0.04em] text-ink"
      >
        valstats<span className="text-accent">.</span>
      </Link>
      {label && (
        <span className="font-display text-[13px] font-semibold uppercase tracking-broadcast text-mut">
          {label}
        </span>
      )}
      <nav aria-label="Primary" className="ml-auto flex items-center gap-1 sm:gap-2">
        {NAV.map((item) => (
          <Link
            key={item.key}
            href={item.href}
            aria-current={active === item.key ? "page" : undefined}
            className={cn(
              "rounded px-2.5 py-1 font-display text-[12px] font-semibold uppercase tracking-broadcast transition-colors",
              active === item.key ? "text-accent" : "text-mut hover:text-ink",
            )}
          >
            {item.label}
          </Link>
        ))}
        <PlayerSearch />
      </nav>
    </header>
  );
}
