import type { ReactNode } from "react";
import Link from "next/link";
import { Panel, SectionHeading } from "@/components/Panel";

/**
 * MatchSection — a titled broadcast module: heading (with optional right-side
 * slot for a count or live indicator), a Panel holding the rows, and graceful
 * empty / stale states. Empty is a valid state (no live matches out of season),
 * not an error.
 *
 * When `viewAllHref` is set (the home-page snapshots), a "View all →" footer row
 * links to the dedicated full-list page. The dedicated pages omit it (they ARE
 * the full list).
 */
export function MatchSection({
  title,
  children,
  count,
  stale = false,
  isEmpty = false,
  emptyLabel = "Nothing here right now.",
  aside,
  viewAllHref,
  viewAllLabel = "View all",
}: {
  title: string;
  children?: ReactNode;
  count?: number;
  stale?: boolean;
  isEmpty?: boolean;
  emptyLabel?: string;
  aside?: ReactNode;
  viewAllHref?: string;
  viewAllLabel?: string;
}) {
  return (
    <section className="flex flex-col gap-3">
      <SectionHeading>
        {title}
        {typeof count === "number" && (
          <span className="font-mono text-[11px] font-normal tracking-normal text-dim">
            {count}
          </span>
        )}
        {aside && <span className="ml-1">{aside}</span>}
      </SectionHeading>
      <Panel className="overflow-hidden">
        {isEmpty ? (
          <p className="px-4 py-6 text-center font-body text-sm text-dim">
            {stale ? "Source unavailable — showing nothing." : emptyLabel}
          </p>
        ) : (
          <>
            {children}
            {viewAllHref && (
              <Link
                href={viewAllHref}
                className="flex items-center justify-center gap-1.5 border-t border-line/60 px-4 py-2.5 font-display text-[12px] font-semibold uppercase tracking-broadcast text-accent transition-colors hover:bg-ink/[0.03]"
              >
                {viewAllLabel}
                <span aria-hidden>→</span>
              </Link>
            )}
          </>
        )}
      </Panel>
    </section>
  );
}
