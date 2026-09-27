// @vitest-environment happy-dom
import { afterEach, expect, it, vi } from "vitest";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import PlayerPage from "@/app/player/[id]/page";
import { PlayerCard } from "./PlayerCard";
import { PlayerTrendPanel } from "./PlayerTrendPanel";
import { PlayerStatsPanel } from "./PlayerStatsPanel";
import { RatingBreakdown } from "./RatingBreakdown";
import { normalizePlayer, normalizePlayerTrend, normalizePlayerDimensions, playerOverall } from "@/lib/vlr";
import type { AgentStat } from "@/types/vlr";
import fixture from "@/lib/__fixtures__/player.json";
const parse = (node: React.ReactNode) => new DOMParser().parseFromString(renderToStaticMarkup(node), "text/html");
const history = { window_days:90, rating_trend:[{captured_at:'2026-09-01',rating:1,acs:200,rounds:100},{captured_at:'2026-09-02',rating:1.2,acs:250,rounds:200},{captured_at:'2026-09-11',rating:1.1,acs:225,rounds:300}],rating_change:.1,acs_change:25,summary:{current_rating:1.1,peak_rating:1.2,current_acs:225,peak_acs:250} };
afterEach(()=>vi.restoreAllMocks());
async function page(player: unknown=fixture, trend: unknown=history, status=200, detailStatus=200) {
 vi.spyOn(globalThis,'fetch').mockImplementation(async input=>{
  const url=String(input);if(url.includes('/dimensions'))return new Response('{}',{status:404});
  const isTrend=url.includes('/trends/');return new Response(JSON.stringify(isTrend?trend:player),{status:isTrend?status:detailStatus});
 });return parse(await PlayerPage({params:Promise.resolve({id:'9'})}));
}
it('orders the player dossier and retains existing aggregate values and links',async()=>{
 const doc=await page();expect([...doc.querySelectorAll('h2')].map(e=>e.textContent)).toEqual(['Rating movement','Rating Breakdown','Agent Stats','Recent Matches']);
 const overall=playerOverall(normalizePlayer(fixture)[0].agentStats);expect(doc.querySelector('.pd-headline')?.textContent).toContain(overall.rating!.toFixed(2));
 expect(doc.querySelector('a[href="/team/16899"]')).not.toBeNull();expect(doc.querySelector('a[href="/match/586655"]')).not.toBeNull();expect(doc.querySelector(`a[href="${fixture.matches[0].url}"]`)?.getAttribute('rel')).toBe('noopener noreferrer');
 expect(doc.body.textContent).toContain('Role unavailable');expect(doc.body.textContent).toContain('All-time source stats');expect(doc.querySelector('img')).toBeNull();
});
it('preserves verbatim agent keys, values, missing cells and source row order',()=>{
 const rows: AgentStat[]=[{agent:'omen',stats:{'K:D':'1.20','R':'1.01'}},{agent:'jett',stats:{'ACS':'200','New:key':'raw'}}];
 const doc=parse(h(PlayerStatsPanel,{agentStats:rows}));expect([...doc.querySelectorAll('thead th')].map(e=>e.textContent)).toEqual(['Agent','K:D','R','ACS','New:key']);
 expect([...doc.querySelectorAll('tbody tr')].map(e=>e.firstElementChild?.textContent)).toEqual(['omen','jett']);expect(doc.querySelector('tbody tr')?.textContent).toContain('1.201.01——');
 expect(doc.querySelector('[role="region"]')?.getAttribute('tabindex')).toBe('0');
});
it('keeps empty successful histories distinct from unavailable secondary sources',async()=>{
 let doc=await page({...fixture,agent_stats:[],matches:[]},{window_days:90,rating_trend:[]});expect(doc.body.textContent).toContain('No rated snapshots');expect(doc.body.textContent).toContain('No agent stats available');expect(doc.body.textContent).toContain('No recent matches listed');
 doc=await page(fixture,{},503);expect(doc.body.textContent).toContain('Rating history unavailable');expect(doc.body.textContent).not.toContain('No rated snapshots');expect(doc.querySelector('.pd-agents')).not.toBeNull();
});
it('preserves the page-level failure and return link',async()=>{
 const doc=await page({}, {},503,503);expect(doc.querySelector('h1')?.textContent).toBe("Couldn't load this player");expect(doc.querySelector('a[href="/"]')).not.toBeNull();
});
it('uses honest partial identity, team URL fallback and unknown match verdicts',()=>{
 const player=normalizePlayer({team:'Example',team_url:'https://example.test/team',matches:[{result:null}],agent_stats:[{agent:'omen',stats:{RND:'—'}}]})[0];const doc=parse(h(PlayerCard,{player}));expect(doc.body.textContent).toContain('Player name unavailable');expect(doc.body.textContent).toContain('Round sample unavailable');expect(doc.querySelector('a')?.getAttribute('href')).toBe('https://example.test/team');expect(doc.querySelector('[data-result="unknown"]')).not.toBeNull();expect(doc.querySelector('.pd-headline')?.textContent).toContain('—');expect(doc.querySelector('.pd-signature')?.textContent).toContain('Unavailable');
});
it('does not invent zero percentiles or a default region for missing dimensions',()=>{
 const d=normalizePlayerDimensions({firepower:null,entry:0,consistency:50,clutch:null,low_confidence:['all']})[0];const doc=parse(h(RatingBreakdown,{dims:{data:[d],stale:false}}));
 expect(doc.querySelector('svg')).toBeNull();expect(doc.body.textContent).toContain('Unavailable');expect(doc.body.textContent).toContain('region unavailable');expect(doc.querySelectorAll('.pd-bar')).toHaveLength(2);expect(doc.querySelector('.pd-bar span')?.getAttribute('style')).toBe('width:0%');expect(doc.body.textContent).toContain('Limited sample');
});
it('distinguishes dimension outage from a confirmed non-cohort player',()=>{
 let doc=parse(h(RatingBreakdown,{dims:{data:[],stale:true}}));expect(doc.body.textContent).toContain('lookup failed');expect(doc.body.textContent).not.toContain("isn't in");
 doc=parse(h(RatingBreakdown,{dims:{data:[],stale:false}}));expect(doc.body.textContent).toContain('NA or EU leaderboard');
});
it('shows dated samples and exact round/ACS history with time-proportional chart spacing',()=>{
 const trend=normalizePlayerTrend(history)[0];const doc=parse(h(PlayerTrendPanel,{trend:{data:[trend],stale:true}}));expect(doc.body.textContent).toContain('90-day lookback');expect(doc.body.textContent).toContain('3 rated snapshots / 3 total captures');expect(doc.body.textContent).toContain('overlapping rounds');expect(doc.body.textContent).toContain('showing last available data');expect(Number(doc.querySelectorAll('circle')[1].getAttribute('cx'))).toBeCloseTo(86.4);expect(doc.querySelectorAll('tbody tr')).toHaveLength(3);
});
it('suppresses unsupported movement for thin, flat and undated history',()=>{
 const t=normalizePlayerTrend({...history,rating_trend:[history.rating_trend[0]],rating_change:99,acs_change:99})[0];let doc=parse(h(PlayerTrendPanel,{trend:{data:[t],stale:false}}));expect(doc.querySelector('svg')).toBeNull();expect(doc.body.textContent).not.toContain('+99');expect(doc.body.textContent).toContain('History is still young');
 t.ratingTrend.push({...t.ratingTrend[0],capturedAt:'2026-09-02'});doc=parse(h(PlayerTrendPanel,{trend:{data:[t],stale:false}}));expect(doc.body.textContent).toContain('Rating held flat');
 t.ratingTrend[1].rating=2;t.ratingTrend[1].capturedAt=null;doc=parse(h(PlayerTrendPanel,{trend:{data:[t],stale:false}}));expect(doc.body.textContent).toContain('Capture dates are insufficient');expect(doc.querySelector('svg')).toBeNull();
});

it('uses current R/Rnd labels for headline weighting, round coverage and main agent while keeping table keys',()=>{
 const rows = [
  {agent:'jett',stats:{R:'1.0',Rnd:'10',ACS:'100',Use:'10%'}},
  {agent:'sova',stats:{R:'2.0',Rnd:'90',ACS:'300',Use:'90%'}},
 ];
 const before=JSON.stringify(rows);
 const player=normalizePlayer({id:'42',alias:'Fixture',agent_stats:rows})[0];
 expect(playerOverall(player.agentStats)).toEqual({rating:1.9,acs:280,kd:null});
 const doc=parse(h(PlayerCard,{player}));
 expect(doc.body.textContent).toContain('100 known rounds across 2 rows');
 expect(doc.querySelector('.pd-signature')?.textContent).toContain('sova');
 expect(doc.body.textContent).toContain('1.90');
 expect(Object.keys(player.agentStats[0].stats)).toEqual(['R','Rnd','ACS','Use']);
 expect(JSON.stringify(rows)).toBe(before);
});

it('prefers historical labels when both are present, including explicitly missing ratings',()=>{
 const rows=[{agent:'sova',stats:{Rating:'1.5',R:'9',RND:'20',Rnd:'999',ACS:'200'}}];
 expect(playerOverall(rows).rating).toBe(1.5);
 const player=normalizePlayer({id:'42',agent_stats:rows})[0];
 expect(parse(h(PlayerCard,{player})).body.textContent).toContain('20 known rounds');
 rows[0].stats.Rating='–';
 expect(playerOverall(rows).rating).toBeNull();
});
