// @vitest-environment happy-dom
import { createElement as h } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { afterEach, expect, it, vi } from 'vitest';
import { NewsBoard } from './NewsBoard';
import NewsPage from '@/app/news/page';
import { normalizeNews } from '@/lib/vlr';
import fixture from '@/lib/__fixtures__/news.json';
const parse=(node:React.ReactNode)=>new DOMParser().parseFromString(renderToStaticMarkup(node),'text/html');
afterEach(()=>vi.restoreAllMocks());
it('leads with the first supplied story and preserves every headline, byline, date and link in order',()=>{
 const data=normalizeNews(fixture);const doc=parse(h(NewsBoard,{news:{data,stale:false}}));
 expect(doc.querySelectorAll('article').length).toBe(data.length);expect(doc.querySelectorAll('.nw-lead').length).toBe(1);
 expect([...doc.querySelectorAll('article a')].map(a=>a.getAttribute('href'))).toEqual(data.map(a=>a.url));
 [...doc.querySelectorAll('article')].forEach((node,i)=>{expect(node.querySelector('h2')?.textContent).toContain(data[i].title);expect(node.querySelector('.nw-meta')?.textContent).toContain(data[i].date);expect(node.querySelector('.nw-meta')?.textContent).toContain(data[i].author);expect(node.querySelector('h2')?.textContent).not.toContain(data[i].author);});
 expect(doc.body.textContent).not.toContain(data[0].description);expect(doc.querySelector('img')).toBeNull();
});
it('uses supplied source destinations with safe new-tab attributes',()=>{
 const doc=parse(h(NewsBoard,{news:{data:normalizeNews(fixture),stale:false}}));for(const link of doc.querySelectorAll('a')) {expect(link.getAttribute('target')).toBe('_blank');expect(link.getAttribute('rel')).toBe('noopener noreferrer');expect(link.textContent).toContain('opens in a new tab');}
});
it('renders one story without a duplicate lead or empty article-list heading',()=>{
 const doc=parse(h(NewsBoard,{news:{data:normalizeNews(fixture.slice(0,1)),stale:false}}));expect(doc.querySelectorAll('article').length).toBe(1);expect(doc.querySelector('.nw-feed')).toBeNull();
});
it('handles missing title, metadata, imagery and source URL without invented content',()=>{
 const doc=parse(h(NewsBoard,{news:{data:normalizeNews([{}]),stale:false}}));for(const t of ['Untitled article','Date unavailable','Author unavailable','Source link unavailable'])expect(doc.body.textContent).toContain(t);expect(doc.querySelector('article a')).toBeNull();expect(doc.querySelector('img')).toBeNull();
});
it('distinguishes empty, failed and retained stale news',()=>{
 expect(parse(h(NewsBoard,{news:{data:[],stale:false}})).body.textContent).toContain('No news right now.');
 const error=parse(h(NewsBoard,{news:{data:[],stale:true,error:'timeout'}}));expect(error.body.textContent).toContain('News unavailable');expect(error.body.textContent).not.toContain('No news right now.');
 const stale=parse(h(NewsBoard,{news:{data:normalizeNews(fixture),stale:true}}));expect(stale.body.textContent).toContain('last available stories');expect(stale.querySelectorAll('article').length).toBe(fixture.length);
});
it('preserves long headlines and unknown date strings verbatim without parsing or sorting',()=>{
 const title='LongHeadline'.repeat(40);const data=normalizeNews([{title,meta:'Original date text',url:null},{title:'Earlier',meta:'January 1, 2000'}]);const doc=parse(h(NewsBoard,{news:{data,stale:false}}));expect(doc.querySelector('.nw-lead h2')?.textContent).toBe(title);expect(doc.querySelector('.nw-meta')?.textContent).toContain('Original date text');
});
it('keeps the route contract, page heading and graceful failure',async()=>{
 const fetcher=vi.spyOn(globalThis,'fetch').mockImplementation(async()=>Response.json(fixture));let doc=parse(await NewsPage());expect(doc.querySelectorAll('h1').length).toBe(1);expect(doc.querySelectorAll('article').length).toBe(fixture.length);expect(fetcher).toHaveBeenCalledWith(expect.stringMatching(/\/news$/),expect.anything());
 fetcher.mockResolvedValue(new Response('{}',{status:503}));doc=parse(await NewsPage());expect(doc.body.textContent).toContain('News unavailable');expect(doc.querySelector('a[href="https://www.vlr.gg/news"]')).not.toBeNull();
});
