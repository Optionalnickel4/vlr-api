/** Minimal className joiner — drops falsy values, joins with spaces. Keeps the
 *  primitives dependency-free (no clsx/tailwind-merge needed at this scale). */
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}
