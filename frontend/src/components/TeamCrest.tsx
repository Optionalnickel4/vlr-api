"use client";

import Image from "next/image";
import { useState } from "react";
import { cn } from "@/lib/cn";
import { teamHue, teamInitials } from "@/lib/schedule";

// Source-provided crests use an image; missing or failed images use initials.
// Decorative by default because adjacent text usually identifies each team.
const SIZES = {
  ticker: { box: 24, text: "text-[9px]" },
  table: { box: 28, text: "text-[10px]" },
  row: { box: 34, text: "text-[13px]" },
  card: { box: 46, text: "text-[17px]" },
  hero: { box: 88, text: "text-[30px]" },
  // Backward-compatible names while call sites migrate to semantic contexts.
  sm: { box: 34, text: "text-[13px]" },
  md: { box: 46, text: "text-[17px]" },
  lg: { box: 88, text: "text-[30px]" },
} as const;

export function TeamCrest({
  name,
  size = "sm",
  className,
  logo,
  labelMode = "decorative",
}: {
  name: string | null;
  size?: keyof typeof SIZES;
  className?: string;
  /** Use only an actual source-provided URL; no guessed asset paths. */
  logo?: string | null;
  labelMode?: "decorative" | "informative";
}) {
  const [failedSource, setFailedSource] = useState<string | null>(null);
  const source = logo?.startsWith("//") ? `https:${logo}` : logo;
  const s = SIZES[size];
  if (source && /^https?:\/\//.test(source) && failedSource !== source) {
    return <span data-team-logo="true" aria-label={labelMode === "informative" ? `${name ?? "Unknown"} team identity` : undefined}
      aria-hidden={labelMode === "decorative" ? true : undefined}
      className={cn("relative inline-flex shrink-0 items-center justify-center", className)}
      style={{ width: s.box, height: s.box }}>
      <Image src={source} width={s.box} height={s.box} alt="" unoptimized
        className="block h-full w-full object-contain" onError={() => setFailedSource(source)} />
    </span>;
  }
  const hue = teamHue(name);
  return (
    <span
      data-team-fallback="true"
      aria-hidden={labelMode === "decorative" ? true : undefined}
      aria-label={labelMode === "informative" ? `${name ?? "Unknown"} team identity` : undefined}
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
