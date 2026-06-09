import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export type BadgeTone = "up" | "down" | "warn" | "accent" | "neutral";

const TONES: Record<BadgeTone, string> = {
  // color = meaning: win/loss/idle never share a hue
  up: "text-up border-up/35 bg-up/[0.07]",
  down: "text-down border-down/35 bg-down/[0.07]",
  warn: "text-warn border-warn/35 bg-warn/[0.07]",
  accent: "text-accent border-accent/35 bg-accent/[0.07]",
  neutral: "text-dim border-line bg-transparent",
};

/**
 * Badge — a small uppercase, wide-tracked pill. The broadcast vocabulary for
 * statuses and verdicts (WIN / LOSS / UPCOMING / region tags). Tone carries the
 * meaning; the label is always uppercase display type.
 */
export function Badge({
  children,
  tone = "neutral",
  dot = false,
  className,
}: {
  children: ReactNode;
  tone?: BadgeTone;
  dot?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5",
        "font-display text-[11px] font-semibold uppercase leading-none tracking-[0.12em]",
        TONES[tone],
        className,
      )}
    >
      {dot && (
        <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      )}
      {children}
    </span>
  );
}
