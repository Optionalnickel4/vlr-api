// Root layout — the app shell: the three broadcast typefaces, page metadata, and
// the persistent lower-third ticker that follows every route.
//
// Fonts come through `next/font`, which downloads and SELF-HOSTS them at build
// time. That matters for this deployment: the container serves the dashboard on
// a LAN with no guarantee of outbound internet at request time, so a runtime
// Google Fonts request would be a hard dependency on something that may not be
// reachable. Nothing here fetches at request time — see the two comments in the
// body below for the only other subtle things in this file.
import type { Metadata } from "next";
import { Saira, Saira_Condensed, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { StatTicker } from "@/components/StatTicker";

// Display: Saira Condensed — the uppercase, wide-tracked broadcast voice.
const sairaCondensed = Saira_Condensed({
  variable: "--font-saira-condensed",
  subsets: ["latin"],
  weight: ["400", "600", "700"],
});

// Body: Saira — the readable companion to the condensed display.
const saira = Saira({
  variable: "--font-saira",
  subsets: ["latin"],
  weight: ["400", "500"],
});

// Mono: JetBrains Mono — tabular numerics for scores and stat columns.
const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "valstats — VLR broadcast",
  description: "Self-hosted VLR.gg broadcast dashboard.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${sairaCondensed.variable} ${saira.variable} ${jetbrainsMono.variable} h-full`}
    >
      {/* suppressHydrationWarning is scoped to <body> ONLY and is one-level-deep:
          it silences mismatches on body's OWN attributes (browser extensions —
          Grammarly, password managers, dark-reader — inject attrs/classes here
          before React hydrates), NOT its descendants. Page content mismatches
          still surface (and are guarded by match-hydration.test.ts). This is the
          one node external code mutates; it is not a wrapper and masks no render
          value of ours — the match island is provably deterministic. */}
      <body suppressHydrationWarning className="min-h-full flex flex-col">
        {children}
        {/* The persistent broadcast lower-third. A self-fetching client island:
            the layout passes NO data and does NO fetching, so every page renders
            at full speed. The island owns its own static/live lifecycle and
            hides itself when empty — `body:has(.vlr-ticker)` (globals.css)
            reserves bottom space only while a tape is actually showing. */}
        <StatTicker />
      </body>
    </html>
  );
}
