// @vitest-environment happy-dom
import { act, createElement as h } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { MatchHeader } from "./MatchHeader";
import { MapTabs } from "./MapTabs";
import { PlayerStatsTable } from "./PlayerStatsTable";
import { RoundTimeline } from "./RoundTimeline";
import { normalizeMatch } from "@/lib/vlr";
import type { MatchDetail } from "@/types/vlr";
import fixture from "@/lib/__fixtures__/match.json";
import partialFixture from "@/lib/__fixtures__/match_live_partial.json";

(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let root: Root | undefined;
let container: HTMLDivElement;
const match = () => normalizeMatch(structuredClone(fixture))[0];
async function mount(element: React.ReactNode) {
  container = document.createElement("div"); document.body.append(container);
  root = createRoot(container);
  await act(async () => root!.render(element));
}
afterEach(async () => { if (root) await act(async () => root!.unmount()); container?.remove(); root = undefined; vi.restoreAllMocks(); });

it.each(["final", "live", "upcoming", null])("labels %s match state and preserves team/source links", async status => {
  const data = match(); data.status = status;
  await mount(h(MatchHeader, { match: data }));
  expect(container.querySelector('.md-status')?.textContent).toBe(status === "final" ? "Final result" : status === "live" ? "Live coverage" : status === "upcoming" ? "Upcoming match" : "Status unavailable");
  expect(container.querySelector('a[href="/team/2359"]')).not.toBeNull();
  expect(container.querySelector('a[href="https://www.vlr.gg/684612"]')?.getAttribute('rel')).toBe('noopener noreferrer');
  expect(container.textContent).toContain(data.event);
});
it("distinguishes live-map rounds from the still-level series", async () => {
  await mount(h(MatchHeader, { match: normalizeMatch(partialFixture)[0] }));
  expect(container.querySelector('[aria-label="Score 1 to 0"]')).not.toBeNull();
  expect(container.querySelector('[aria-label="Series score 0 to 0"]')).not.toBeNull();
  expect(container.textContent).toContain('Map 1 · Haven');
});
it("keeps absent crest fields null, uses a supplied crest, and falls back after failure", async () => {
  const data = match(); expect(data.teams[0].logo).toBeNull();
  const withLogo = normalizeMatch({ ...fixture, teams: [{ ...fixture.teams[0], logo: '//example.test/crest.png' }, fixture.teams[1]] })[0];
  await mount(h(MatchHeader, { match: withLogo }));
  const image = container.querySelector('img')!;
  expect(image.getAttribute('src')).toBe('https://example.test/crest.png');
  await act(async () => image.dispatchEvent(new Event('error')));
  expect(container.querySelector('img')).toBeNull();
  expect(container.querySelector('.md-team-identity')?.textContent).toContain('LEVIATÁN');
});
it("shows honest missing identity, scores, context and maps without fabricated links", async () => {
  const data: MatchDetail = { ...match(), teams: [], maps: [], allMaps: null, event: null, status: null, format: null, url: null, veto: null };
  await mount(h('div', null, h(MatchHeader, { match: data }), h(MapTabs, { match: data })));
  expect(container.textContent).toContain('Team 1 TBD');
  expect(container.textContent).toContain('Event unavailable');
  expect(container.querySelector('[aria-label="Score – to –"]')).not.toBeNull();
  expect(container.querySelector('a')).toBeNull();
  expect(container.textContent).toContain('No map data available');
});
it("selects maps and aggregates using arrows/Home/End with linked tab semantics", async () => {
  await mount(h(MapTabs, { match: match() }));
  const tabs = [...container.querySelectorAll<HTMLButtonElement>('[role="tab"]')];
  await act(async () => { tabs[0].focus(); tabs[0].dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true })); });
  expect(document.activeElement).toBe(tabs[1]); expect(tabs[1].getAttribute('aria-selected')).toBe('true');
  expect(container.querySelector('.md-map-heading h3')?.textContent).toBe('Fracture');
  expect(container.querySelector('[role="tabpanel"]')?.getAttribute('aria-labelledby')).toBe(tabs[1].id);
  await act(async () => tabs[1].dispatchEvent(new KeyboardEvent('keydown', { key: 'End', bubbles: true })));
  expect(container.querySelector('.md-map-heading h3')?.textContent).toBe('All Maps');
  expect(container.querySelector('.md-rounds')).toBeNull();
  await act(async () => tabs[3].dispatchEvent(new KeyboardEvent('keydown', { key: 'Home', bubbles: true })));
  expect(tabs[0].getAttribute('tabindex')).toBe('0'); expect(tabs[1].getAttribute('tabindex')).toBe('-1');
});
it("retains selected map across refreshed scores and falls back safely if it disappears", async () => {
  const data = match(); await mount(h(MapTabs, { match: data }));
  await act(async () => container.querySelectorAll<HTMLButtonElement>('[role="tab"]')[1].click());
  const refreshed = match(); refreshed.maps[1].scores = [12, 10];
  await act(async () => root!.render(h(MapTabs, { match: refreshed })));
  expect(container.querySelector('.md-map-heading')?.textContent).toContain('12 : 10');
  await act(async () => root!.render(h(MapTabs, { match: { ...refreshed, maps: [], allMaps: refreshed.allMaps } })));
  expect(container.querySelector('[aria-selected="true"]')?.textContent).toContain('All Maps');
});
it("preserves all 11 stat columns, source order, player links, percentages, zero and null", async () => {
  const team = match().maps[0].teams[0];
  team.players[0].stats.R.value = null; team.players[0].stats.K.value = 0; team.players[0].stats['HS%'].value = 25;
  await mount(h(PlayerStatsTable, { team }));
  expect(container.querySelectorAll('thead th')).toHaveLength(12);
  const rows = [...container.querySelectorAll('tbody tr')];
  expect(rows.map(row => row.querySelector('.md-player > :first-child')?.textContent)).toEqual(team.players.map(p => p.player));
  expect(rows[0].querySelector('a')?.getAttribute('href')).toBe(`/player/${team.players[0].playerId}`);
  expect(rows[0].querySelectorAll('td')[0].textContent).toBe('—');
  expect(rows[0].querySelectorAll('td')[2].textContent).toBe('0');
  expect(rows[0].querySelectorAll('td')[8].textContent).toBe('25%');
  expect(container.querySelector('[role="region"]')?.getAttribute('tabindex')).toBe('0');
});
it("reports unavailable players and rounds instead of empty unexplained panels", async () => {
  const data = match(); data.maps = [{ ...data.maps[0], teams: [{ name: null, score: null, players: [] }], rounds: [] }]; data.allMaps = null;
  await mount(h(MapTabs, { match: data }));
  expect(container.textContent).toContain('Player statistics unavailable.');
  expect(container.textContent).toContain('Round history unavailable');
  expect(container.querySelector('caption')?.textContent).toContain('LEVIATÁN');
});
it("exposes round winner, side, outcome and cumulative score without color-only meaning", async () => {
  await mount(h(RoundTimeline, { team1: 'Alpha', team2: 'Beta', rounds: [{ round: 1, winner: 1, side: 'ct', outcome: 'defuse', score: '1-0' }, { round: 2, winner: null, side: null, outcome: null, score: null }] }));
  expect(container.querySelector('.md-round-details')?.textContent).toContain('Round 1 · Alpha won · Defense · defuse · 1-0');
  expect(container.querySelector('.md-round-details')?.textContent).toContain('Round 2 · Result unavailable');
  expect(container.querySelector('[data-result="win"]')?.textContent).toBe('W');
  expect(container.querySelector('[data-result="loss"]')?.textContent).toBe('L');
});
