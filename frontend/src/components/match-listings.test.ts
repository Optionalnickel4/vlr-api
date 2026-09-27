// @vitest-environment happy-dom
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, expect, it, vi } from "vitest";
import { ScheduleBoard } from "./ScheduleBoard";
import { ResultsBoard } from "./ResultsBoard";
import SchedulePage from "@/app/schedule/page";
import ResultsPage from "@/app/results/page";
import { groupListing, listingDay } from "@/lib/matchListings";
import type { UpcomingMatch, ResultMatch } from "@/types/vlr";
const now = new Date('2026-09-27T23:30:00Z');
const fixture: UpcomingMatch = { id:'1', team1:'Alpha', team2:'Beta', timeUntil:'2h', startTime:'5:00 AM', event:'Championship', series:'Final', url:null };
const result: ResultMatch = { id:'2', team1:'Alpha', team2:'Beta', score1:2, score2:0, time:'1d', event:'Championship', series:'Final', url:null };
const parse = (node: React.ReactNode) => new DOMParser().parseFromString(renderToStaticMarkup(node), 'text/html');
afterEach(()=>vi.restoreAllMocks());
it('estimates UTC days in the correct direction and rejects ambiguous dates',()=>{
 expect(listingDay('2h',1,now).key).toBe('2026-09-28');
 expect(listingDay('1d',-1,now).key).toBe('2026-09-26');
 expect(listingDay('0s',1,now).label).toContain('Today');
 for(const value of [null,'LIVE','5:00 AM','in 2h maybe','2h ago','9999999999999999999999999d']) expect(listingDay(value,1,now).key).toBe('unknown');
 expect(listingDay('2h',1,now,true).key).toBe('unknown');
});
it('groups only adjacent event/day pairs, retaining unknown dates and interleaved source order',()=>{
 const matches=[{...fixture,id:'unknown',timeUntil:null},{...fixture,id:'a'}, {...fixture,id:'b',event:'Other'}, {...fixture,id:'c'}, {...fixture,id:'d'}];
 const groups=groupListing(matches,m=>m.timeUntil,1,now);
 expect(groups.map(g=>g.matches.map(m=>m.id))).toEqual([['unknown'],['a'],['b'],['c','d']]);
 const doc=parse(h(ScheduleBoard,{response:{data:matches,stale:false},now}));
 expect([...doc.querySelectorAll('.ml-match-link')].map(a=>a.getAttribute('href'))).toEqual(matches.map(m=>`/match/${m.id}`));
 expect(doc.body.textContent).toContain('5:00 AM');expect(doc.body.textContent).toContain('Estimated date · UTC');
});
it('renders zero scores, text winners and direct links without inventing crests',()=>{
 const doc=parse(h(ResultsBoard,{response:{data:[result],stale:false},now}));
 expect(doc.querySelector('[aria-label="Beta score 0"]')?.textContent).toBe('0');
 expect(doc.querySelectorAll('[data-winner="true"]').length).toBe(1);
 expect(doc.querySelector('[data-winner="true"]')?.textContent).toContain('Alpha');
 expect(doc.querySelector('a')?.getAttribute('href')).toBe('/match/2');expect(doc.querySelector('img')).toBeNull();
});
it('retains result ordering and does not announce a winner for incomplete or tied scores',()=>{
 const data=[{...result,id:'partial',score1:null},{...result,id:'tie',score1:0},{...result,id:'last',event:'Other'}];
 const doc=parse(h(ResultsBoard,{response:{data,stale:false},now}));
 expect([...doc.querySelectorAll('.ml-match-link')].map(a=>a.getAttribute('href'))).toEqual(['/match/partial','/match/tie','/match/last']);
 expect(doc.querySelectorAll('[data-winner="true"]').length).toBe(1);
 expect(doc.body.textContent).toContain('Score incomplete');expect(doc.body.textContent).toContain('Level score reported');
});
it('keeps missing identity, stage, time and link explicit',()=>{
 const doc=parse(h(ScheduleBoard,{response:{data:[{...fixture,id:null,team1:null,team2:null,event:null,series:null,startTime:null,timeUntil:null}],stale:false},now}));
 for(const text of ['Team TBD','Event unavailable','Stage unavailable','Time TBA','Countdown unavailable','Match link unavailable']) expect(doc.body.textContent).toContain(text);
 expect(doc.querySelector('a')).toBeNull();
});
it('preserves long names verbatim and reports live source timing without inventing a date',()=>{
 const name='A'.repeat(160);
 const doc=parse(h(ScheduleBoard,{response:{data:[{...fixture,team1:name,event:name,timeUntil:'LIVE'}],stale:false},now}));
 expect(doc.querySelector('h2')?.textContent).toBe(name);expect(doc.body.textContent).toContain('Source says LIVE');expect(doc.body.textContent).toContain('Date unavailable');
});
for(const kind of ['schedule','results'] as const) {
 it(`${kind}: distinguishes empty, failed and retained stale data`,()=>{
  const render=(data: boolean,stale:boolean,error?:string)=>kind==='schedule'
   ? parse(h(ScheduleBoard,{response:{data:data?[fixture]:[],stale,error},now}))
   : parse(h(ResultsBoard,{response:{data:data?[result]:[],stale,error},now}));
  expect(render(false,false).body.textContent).toContain(kind==='schedule'?'No upcoming matches scheduled.':'No recent results.');
  const failed=render(false,true,'HTTP 503');expect(failed.body.textContent).toContain("couldn't load");expect(failed.body.textContent).not.toContain('No recent');
  const retained=render(true,false,'HTTP 503');expect(retained.body.textContent).toContain('last available matches');expect(retained.body.textContent).not.toContain('Estimated date · UTC');expect(retained.querySelector('a')).not.toBeNull();
 });
 it(`${kind}: route preserves the API-backed page and failure heading`,async()=>{
  vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response('{}',{status:503}));
  const doc=parse(await (kind==='schedule'?SchedulePage():ResultsPage()));
  expect(doc.querySelectorAll('h1').length).toBe(1);expect(doc.body.textContent).toContain('unavailable');expect(doc.querySelector('a')?.getAttribute('href')).toBe(kind==='schedule'?'/results':'/schedule');
 });
}
