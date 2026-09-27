// @vitest-environment happy-dom
import { afterEach, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { act, createElement as h } from "react";
import { createRoot } from "react-dom/client";
import TeamPage from "@/app/team/[id]/page";
import { TeamTrendPanel } from "./TeamTrendPanel";
import { TeamOverview } from "./TeamOverview";
import { normalizeTeam, normalizeTrend } from "@/lib/vlr";
import team from "@/lib/__fixtures__/team.json";
import trend from "@/lib/__fixtures__/trends.json";

const parse = (node: React.ReactNode) => new DOMParser().parseFromString(renderToStaticMarkup(node), "text/html");
afterEach(() => vi.restoreAllMocks());
async function page(detail: unknown = team, history: unknown = trend, historyStatus = 200, detailStatus = 200) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async input => {
    const isHistory = String(input).includes('/trends/');
    return new Response(JSON.stringify(isHistory ? history : detail), { status: isHistory ? historyStatus : detailStatus });
  });
  return parse(await TeamPage({ params: Promise.resolve({ id: '2' }) }));
}
it('orders populated sections and preserves roster, staff, match and source links', async () => {
  const doc = await page();
  expect([...doc.querySelectorAll('h2')].map(e=>e.textContent)).toEqual(['Recent form','Rating movement','Roster','Results in window']);
  expect(doc.querySelector('h1')?.textContent).toBe('Sentinels');
  expect(doc.querySelector('a[href="/player/1265"]')).not.toBeNull();
  expect(doc.body.textContent).toContain('Captain');expect(doc.body.textContent).toContain('Staff');
  expect(doc.querySelector('a[href="/match/681336"]')).not.toBeNull();
  expect(doc.querySelector('a[href="https://www.vlr.gg/681336"]')?.getAttribute('rel')).toBe('noopener noreferrer');
  expect(doc.body.textContent).toContain('90-day lookback');expect(doc.body.textContent).toContain('5 rated snapshots / 5 total captures');
  expect(doc.querySelector('.td-chart')).toBeNull();expect(doc.body.textContent).toContain('Rating held flat');
});
it('distinguishes history failure from a genuine empty window while retaining team data', async () => {
  let doc=await page(team, {}, 503);
  expect(doc.body.textContent).toContain('Rating history unavailable');expect(doc.body.textContent).toContain('Results unavailable');
  expect(doc.body.textContent).not.toContain('No results matched');expect(doc.querySelector('a[href="/player/1265"]')).not.toBeNull();
  doc=await page({...team,roster:[],results:[]}, {...trend,rating_trend:[],results_in_window:[],summary:null,rating_change:null});
  expect(doc.body.textContent).toContain('No results matched');expect(doc.body.textContent).toContain('No rated snapshots');
  expect(doc.body.textContent).toContain('No roster listed');expect(doc.body.textContent).toContain('No recent results listed');
  expect(doc.querySelector('.td-rating-stats')?.textContent).not.toContain('0 / 0');
});
it('keeps whole-page failure navigable', async () => {
  const doc=await page({}, {}, 503, 503);
  expect(doc.querySelector('h1')?.textContent).toBe("Couldn't load this team");expect(doc.querySelector('a[href="/"]')).not.toBeNull();
});
it('does not invent movement for one point or undated data; keeps null values visible', () => {
  const t=normalizeTrend({...trend,rating_trend:[{rating:1700,captured_at:null,rank:null}],rating_change:99,summary:null})[0];
  let doc=parse(h(TeamTrendPanel, {trend:{data:[t],stale:false}}));
  expect(doc.body.textContent).toContain('One rated snapshot');expect(doc.body.textContent).not.toContain('+99');
  expect(doc.body.textContent).toContain('Date unavailable');expect(doc.querySelector('svg')).toBeNull();
  t.ratingTrend.push({rating:1800,capturedAt:null,rank:null});
  doc=parse(h(TeamTrendPanel, {trend:{data:[t],stale:false}}));
  expect(doc.body.textContent).toContain('Capture dates are insufficient');expect(doc.querySelector('svg')).toBeNull();
});
it('charts actual capture intervals, retains exact ranks, and exposes stale data context', () => {
  const t=normalizeTrend({...trend,rating_trend:[{rating:100,captured_at:'2026-09-01',rank:9},{rating:120,captured_at:'2026-09-02',rank:8},{rating:110,captured_at:'2026-09-11',rank:7}],rating_change:10})[0];
  const doc=parse(h(TeamTrendPanel, {trend:{data:[t],stale:true}}));
  expect(doc.querySelector('svg')?.getAttribute('aria-label')).toContain('minimum 100, maximum 120');
  const circles=[...doc.querySelectorAll('circle')];expect(Number(circles[1].getAttribute('cx'))).toBeCloseTo(86.4);
  expect(doc.querySelectorAll('tbody tr')).toHaveLength(3);expect(doc.body.textContent).toContain('showing last available data');
  expect(doc.querySelector('[role="region"]')?.getAttribute('tabindex')).toBe('0');
});
it('does not draw over missing rating captures', () => {
  const t=normalizeTrend({...trend,rating_trend:[{rating:100,captured_at:'2026-09-01'},{rating:null,captured_at:'2026-09-02'},{rating:110,captured_at:'2026-09-03'}]})[0];
  const doc=parse(h(TeamTrendPanel, {trend:{data:[t],stale:false}}));
  expect(doc.querySelector('path')?.getAttribute('d')).not.toContain('L');expect(doc.querySelectorAll('circle')).toHaveLength(2);
});
it('handles partial identity and unknown verdicts without false losses or links', () => {
  const t=normalizeTeam({roster:[],results:[{opponent:null,score:null,result:null}]})[0];
  const doc=parse(h(TeamOverview, {team:{data:[t],stale:false}}));
  expect(doc.body.textContent).toContain('Team name unavailable');expect(doc.body.textContent).toContain('Unknown');
  expect(doc.querySelector('img')).toBeNull();expect(doc.querySelector('a')).toBeNull();
});
it('uses supplied crests, falls back after image failure, and preserves team links', async () => {
  (globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const t=normalizeTeam(team)[0];t.results[0].opponentId='99';
  const container=document.createElement('div');document.body.append(container);const root=createRoot(container);
  try {await act(async()=>root.render(h(TeamOverview, {team:{data:[t],stale:false}})));
    expect(container.querySelector('img')?.getAttribute('src')).toBe(team.logo);
    await act(async()=>container.querySelector('img')!.dispatchEvent(new Event('error')));
    expect(container.querySelector('img')).toBeNull();expect(container.querySelector('a[href="/team/99"]')).not.toBeNull();
  } finally {await act(async()=>root.unmount());container.remove();}
});
