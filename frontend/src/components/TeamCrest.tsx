import { cn } from "@/lib/cn";
import { teamHue, teamInitials } from "@/lib/schedule";

// TYPOGRAPHIC crest — vlr's match-list payload carries no team logos (only
// names), so the schedule anchors each side with a deterministic initials disc,
// accent-tinted by a hue hashed from the team name. Muted S/L keeps it a
// broadcast chip, never neon. Purely decorative: the team name always sits
// beside it, so it's aria-hidden.
const SIZES = {
  sm: { box: 34, text: "text-[13px]" },
  md: { box: 46, text: "text-[17px]" },
  lg: { box: 88, text: "text-[30px]" },
} as const;

export function TeamCrest({
  name,
  size = "sm",
  className,
}: {
  name: string | null;
  size?: keyof typeof SIZES;
  className?: string;
}) {
  const s = SIZES[size];
  const hue = teamHue(name);
  return (
    <span
      aria-hidden
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full border",
        "font-display font-semibold uppercase leading-none tracking-[0.02em]",
        s.text,
        className,
      )}
      style={{
        width: s.box,
        height: s.box,
        color: `hsl(${hue} 60% 66%)`,
        borderColor: `hsl(${hue} 40% 50% / 0.45)`,
        backgroundColor: `hsl(${hue} 45% 48% / 0.12)`,
      }}
    >
      {teamInitials(name)}
    </span>
  );
}
