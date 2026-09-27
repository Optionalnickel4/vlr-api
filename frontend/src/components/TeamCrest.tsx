"use client";

import Image from "next/image";
import { useState } from "react";
import { cn } from "@/lib/cn";
import { teamHue, teamInitials } from "@/lib/schedule";

// Source-provided crests use an image; missing or failed images use initials.
// Match-list payloads currently supply names only. Decorative because the
// adjacent text already identifies each team.
const SIZES = {
  sm: { box: 34, text: "text-[13px]" },
  md: { box: 46, text: "text-[17px]" },
  lg: { box: 88, text: "text-[30px]" },
} as const;

export function TeamCrest({
  name,
  size = "sm",
  className,
  logo,
}: {
  name: string | null;
  size?: keyof typeof SIZES;
  className?: string;
  /** Use only an actual source-provided URL; no guessed asset paths. */
  logo?: string | null;
}) {
  const [failedSource, setFailedSource] = useState<string | null>(null);
  const source = logo?.startsWith("//") ? `https:${logo}` : logo;
  const s = SIZES[size];
  if (source && /^https?:\/\//.test(source) && failedSource !== source) {
    return <Image src={source} width={s.box} height={s.box} alt="" aria-hidden unoptimized
      className={cn("shrink-0 object-contain", className)} onError={() => setFailedSource(source)} />;
  }
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
