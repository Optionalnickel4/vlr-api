// @vitest-environment happy-dom
import { afterEach, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import RootLayout from "./layout";
import Home from "./page";
import Schedule from "./schedule/page";
import Results from "./results/page";
import Stats from "./stats/page";
import Rankings from "./rankings/page";
import News from "./news/page";
import Match, { generateMetadata as matchMetadata } from "./match/[id]/page";
import Team, { generateMetadata as teamMetadata } from "./team/[id]/page";
import Player, { generateMetadata as playerMetadata } from "./player/[id]/page";
import NotFound from "./not-found";
import matchFixture from "@/lib/__fixtures__/match.json";
import teamFixture from "@/lib/__fixtures__/team.json";
import playerFixture from "@/lib/__fixtures__/player.json";

vi.mock("next/navigation", () => ({ usePathname: () => "/" }));
vi.mock("next/font/google", () => ({
  Saira: () => ({ variable: "body-font" }),
  Saira_Condensed: () => ({ variable: "display-font" }),
  JetBrains_Mono: () => ({ variable: "mono-font" }),
}));
vi.mock("@/components/StreamersSection", () => ({ StreamersSection: () => null }));

afterEach(() => vi.restoreAllMocks());

function assertShell(page: React.ReactNode) {
  const doc = new DOMParser().parseFromString(renderToStaticMarkup(RootLayout({ children: page })), "text/html");
  expect(doc.querySelectorAll('nav[aria-label="Primary"]')).toHaveLength(1);
  expect(doc.querySelectorAll('[role="combobox"]')).toHaveLength(1);
  expect(doc.querySelectorAll("main")).toHaveLength(1);
  expect(doc.querySelector("main")?.id).toBe("main-content");
  expect(doc.querySelectorAll("h1")).toHaveLength(1);
  expect(doc.querySelector('main nav[aria-label="Primary"]')).toBeNull();
  return doc;
}

it.each([
  ["home", Home], ["schedule", Schedule], ["results", Results],
  ["stats", Stats], ["rankings", Rankings], ["news", News],
] as const)("shares landmarks on the %s route even when its source fails", async (_, Page) => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("unavailable", { status: 503 }));
  assertShell(await Page());
});

it.each([
  ["match", Match, matchFixture], ["team", Team, teamFixture], ["player", Player, playerFixture],
] as const)("preserves %s identity and breadcrumbs on success and failure", async (kind, Page, fixture) => {
  const fetcher = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const isDetail = new URL(String(input)).pathname.endsWith(`/${kind}/9`);
    return new Response(JSON.stringify(isDetail ? fixture : {}), { status: isDetail ? 200 : 404 });
  });
  const props = { params: Promise.resolve({ id: "9" }) };
  const success = assertShell(await Page(props));
  expect(success.querySelector('nav[aria-label="Breadcrumb"]')).not.toBeNull();
  expect(success.querySelector("h1")?.textContent).not.toContain("Couldn't load");
  fetcher.mockImplementation(async () => new Response("unavailable", { status: 503 }));
  const failure = assertShell(await Page(props));
  expect(failure.querySelector('nav[aria-label="Breadcrumb"] [aria-current]')?.textContent).toContain("9");
  expect(failure.querySelector("h1")?.textContent).toContain("Couldn't load");
});

it("provides a skip target on the not-found page", () => {
  expect(assertShell(NotFound()).querySelector("h1")?.textContent).toBe("Page not found");
});

it("generates distinct detail titles without extra upstream requests", async () => {
  const fetcher = vi.spyOn(globalThis, "fetch");
  const titles = await Promise.all([matchMetadata, teamMetadata, playerMetadata].map(fn => fn({ params: Promise.resolve({ id: "9" }) })));
  expect(titles.map(meta => meta.title)).toEqual(["Match 9 — valstats", "Team 9 — valstats", "Player 9 — valstats"]);
  expect(fetcher).not.toHaveBeenCalled();
});
