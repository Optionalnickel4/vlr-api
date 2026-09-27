// @vitest-environment happy-dom
import { act, createElement as h } from 'react';
import { createRoot } from 'react-dom/client';
import { renderToStaticMarkup } from 'react-dom/server';
import { afterEach, expect, it, vi } from 'vitest';
import { RankingsBoard, rankingGroups, RANKING_REGIONS } from './RankingsBoard';
import RankingsPage from '@/app/rankings/page';
import { StatsLeaderboard } from './StatsLeaderboard';
import { normalizeRankings, normalizeStats } from '@/lib/vlr';
import ranks from '@/lib/__fixtures__/rankings.json';
import stats from '@/lib/__fixtures__/stats.json';
const parse=(node:React.ReactNode)=>new DOMParser().parseFromString(renderToStaticMarkup(node),'text/html');
afterEach(()=>vi.restoreAllMocks());
it('preserves every ranked row and source label, splits only at rank resets',()=>{
 const rows=normalizeRankings([{rank:'1',team:'A',country:'Europe',team_id:'1'}, {rank:'2',team:'B',country:'Türkiye'}, {rank:'1',team:'C',country:'United States'}]);
 expect(rankingGroups(rows).map(g=>g.map(t=>t.team))).toEqual([['A','B'],['C']]);
 const doc=parse(h(RankingsBoard,{rankings:{data:rows,stale:false}}));
 expect(doc.querySelectorAll('tbody tr').length).toBe(3);expect(doc.body.textContent).toContain('not a global ranking');expect(doc.body.textContent).toContain('Türkiye');expect(doc.querySelector('a[href="/team/1"]')).not.toBeNull();
 expect(doc.querySelectorAll('nav a').length).toBe(Object.keys(RANKING_REGIONS).length);
});
it('renders partial and stale rankings without manufactured rating, crest or movement',()=>{
 const doc=parse(h(RankingsBoard,{rankings:{data:normalizeRankings([{}]),stale:true}}));
 expect(doc.body.textContent).toContain('last available rankings');expect(doc.body.textContent).toContain('Team unavailable');expect(doc.querySelector('tbody td:last-child')?.textContent).toBe('—');expect(doc.querySelector('img')).toBeNull();
});
it('distinguishes rankings empty and failed responses',()=>{
 expect(parse(h(RankingsBoard,{rankings:{data:[],stale:false}})).body.textContent).toContain('No rankings available.');
 const failed=parse(h(RankingsBoard,{rankings:{data:[],stale:true,error:'timeout'}}));expect(failed.body.textContent).toContain('Rankings unavailable');expect(failed.body.textContent).not.toContain('No rankings available.');
});
it('validates regional navigation and forwards only supported slugs',async()=>{
 const spy=vi.spyOn(globalThis,'fetch').mockImplementation(async()=>Response.json(ranks));
 let doc=parse(await RankingsPage({searchParams:Promise.resolve({region:'europe'})}));expect(spy).toHaveBeenLastCalledWith(expect.stringContaining('region=europe'),expect.anything());expect(doc.querySelector('[aria-current="page"]')?.textContent).toBe('Europe');
 doc=parse(await RankingsPage({searchParams:Promise.resolve({region:'__proto__'})}));expect(spy).toHaveBeenLastCalledWith(expect.stringContaining('region=all'),expect.anything());expect(doc.querySelector('[aria-current="page"]')?.textContent).toBe('All regional ladders');
});
it('shows supported sample counts and unavailable values with a keyboard-focusable table',()=>{
 const data=normalizeStats([{...stats[0],rnd:0},{...stats[1],rnd:null}]);const doc=parse(h(StatsLeaderboard,{initial:{data,stale:false}}));
 expect(doc.querySelector('th button[aria-label="Sort by ACS"]')).not.toBeNull();expect(doc.querySelector('.ld-stat-scroll')?.getAttribute('tabindex')).toBe('0');expect([...doc.querySelectorAll('tbody tr')].map(r=>r.children[2].textContent)).toEqual(['—','0']);expect(doc.body.textContent).not.toContain('Top Rated');expect(doc.body.textContent).toContain('Capture time');
});
it('does not label failed stats as a genuine empty leaderboard',()=>{
 const doc=parse(h(StatsLeaderboard,{initial:{data:[],stale:true,error:'timeout'}}));expect(doc.body.textContent).toContain('Leaderboard unavailable');expect(doc.body.textContent).not.toContain('No leaderboard data.');
});
it('sort buttons reverse direction, retain stable ties and keep preview cards tied to view order',async()=>{
 const host=document.createElement('div');const root=createRoot(host);const data=normalizeStats(stats);
 try{await act(async()=>root.render(h(StatsLeaderboard,{initial:{data,stale:false}})));
 const button=host.querySelector<HTMLButtonElement>('[aria-label="Sort by ACS"]')!;
 await act(async()=>button.click());expect(host.querySelector('th[aria-sort]')?.getAttribute('aria-sort')).toBe('descending');expect(host.querySelector('tbody tr')?.textContent).toContain('Charlie');
 await act(async()=>button.click());expect(host.querySelector('th[aria-sort]')?.getAttribute('aria-sort')).toBe('ascending');expect(host.querySelector('tbody tr')?.textContent).toContain('Alpha');expect(host.querySelector('[data-podium-rank="1"]')?.textContent).toContain('Alpha');
 }finally{await act(async()=>root.unmount());}
});
it('hides previous-filter data during loading and ignores late requests',async()=>{
 const pending:((r:Response)=>void)[]=[];vi.spyOn(globalThis,'fetch').mockImplementation(()=>new Promise(r=>pending.push(r)));
 const host=document.createElement('div');const root=createRoot(host);
 try{await act(async()=>root.render(h(StatsLeaderboard,{initial:{data:normalizeStats(stats),stale:false}})));
 const click=async(text:string)=>act(async()=>[...host.querySelectorAll('button')].find(b=>b.textContent===text)!.click());
 await click('EU');expect(host.querySelector('tbody')).toBeNull();expect(host.textContent).toContain('Loading selected filters');await click('30D');
 await act(async()=>pending[1](Response.json({data:normalizeStats([{player:'New',player_id:'8',r2:2}]),stale:true})));
 await act(async()=>pending[0](Response.json({data:normalizeStats([{player:'Old',r2:9}]),stale:false})));
 expect(host.querySelector('tbody')?.textContent).toContain('New');expect(host.querySelector('tbody')?.textContent).not.toContain('Old');expect(host.textContent).toContain('Updates unavailable');
 }finally{await act(async()=>root.unmount());}
});
it('rejects a failed or malformed client response instead of crashing',async()=>{
 vi.spyOn(globalThis,'fetch').mockResolvedValue(Response.json({unexpected:true}));const host=document.createElement('div');const root=createRoot(host);
 try{await act(async()=>root.render(h(StatsLeaderboard,{initial:{data:normalizeStats(stats),stale:false}})));await act(async()=>[...host.querySelectorAll('button')].find(b=>b.textContent==='EU')!.click());expect(host.textContent).toContain('Invalid leaderboard response');expect(host.querySelector('tbody')).toBeNull();}finally{await act(async()=>root.unmount());}
});
