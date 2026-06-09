import type { Metadata } from "next";
import { Saira, Saira_Condensed, JetBrains_Mono } from "next/font/google";
import "./globals.css";

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
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
