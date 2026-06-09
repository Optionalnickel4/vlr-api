import { cn } from "@/lib/cn";

type Size = "sm" | "md" | "lg";

const SIZES: Record<Size, string> = {
  sm: "text-xl",
  md: "text-3xl",
  lg: "text-5xl",
};

function side(score: number | null, other: number | null, decided: boolean) {
  if (score === null || other === null) return "text-dim"; // no result yet
  if (!decided) return "text-ink"; // in progress — no winner color
  if (score > other) return "text-up"; // winner
  if (score < other) return "text-dim"; // loser recedes
  return "text-ink"; // tie
}

/**
 * ScoreDisplay — the numeric heart of a scorebug: "1 : 2" in big tabular
 * display numerals, the winning side lit green and the losing side receding to
 * dim. Null scores (an upcoming match) render as dim dashes, never 0 or NaN.
 * The score pair only; team names/logos are composed around it by the scorebug.
 */
export function ScoreDisplay({
  score1,
  score2,
  decided = true,
  size = "md",
  className,
}: {
  score1: number | null;
  score2: number | null;
  /** false while a match is in progress: show the scores but no winner color. */
  decided?: boolean;
  size?: Size;
  className?: string;
}) {
  const show = (n: number | null) => (n === null ? "–" : String(n));
  return (
    <div
      className={cn(
        "inline-flex items-baseline gap-2 font-display font-bold leading-none tabular-nums",
        SIZES[size],
        className,
      )}
      aria-label={`Score ${show(score1)} to ${show(score2)}`}
    >
      <span className={side(score1, score2, decided)}>{show(score1)}</span>
      <span className="text-dim/70 text-[0.6em] font-semibold">:</span>
      <span className={side(score2, score1, decided)}>{show(score2)}</span>
    </div>
  );
}
