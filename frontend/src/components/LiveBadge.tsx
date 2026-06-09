import { cn } from "@/lib/cn";

/**
 * LiveBadge — the red, pulsing LIVE flag. Red is reserved for LIVE / loss /
 * stale; the pulse is the one piece of motion on an otherwise still surface, so
 * a live match is the thing your eye goes to. CSS-only animation (keyframes in
 * globals.css) keeps this a server component.
 */
export function LiveBadge({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-down/40 bg-down/[0.08] px-2 py-0.5",
        "font-display text-[11px] font-bold uppercase leading-none tracking-[0.18em] text-down",
        className,
      )}
    >
      <span
        className="h-1.5 w-1.5 rounded-full bg-down [animation:vlr-pulse_2s_infinite]"
        aria-hidden
      />
      Live
    </span>
  );
}
