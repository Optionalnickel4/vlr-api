import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

/**
 * Panel — the base broadcast surface: a subtly graded near-black card with a
 * hairline border. Everything (match cards, stat tables, trend strips) sits in
 * one of these so the dashboard reads as a stack of broadcast lower-thirds.
 */
export function Panel({
  children,
  className,
  as: Tag = "div",
}: {
  children: ReactNode;
  className?: string;
  as?: "div" | "section" | "article" | "aside";
}) {
  return (
    <Tag
      className={cn(
        "rounded-[10px] border border-line bg-gradient-to-b from-panel to-panel-2",
        className,
      )}
    >
      {children}
    </Tag>
  );
}

/**
 * SectionHeading — the uppercase, wide-tracked label with a rule that bleeds to
 * the edge. The recurring "module label" of the broadcast layout.
 */
export function SectionHeading({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <h2
      className={cn(
        "flex items-center gap-3 font-display text-[13px] font-semibold uppercase tracking-[0.16em] text-mut",
        "after:h-px after:flex-1 after:bg-line after:content-['']",
        className,
      )}
    >
      {children}
    </h2>
  );
}
