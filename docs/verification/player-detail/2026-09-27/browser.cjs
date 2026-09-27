const {chromium}=require('/tmp/vlr-browser-tools/node_modules/playwright');const assert=require('node:assert/strict');const fs=require('node:fs');
async function label(page, width){await page.evaluate(width=>{let tag=document.getElementById('evidence-label');if(!tag){tag=document.createElement('div');tag.id='evidence-label';document.body.append(tag);}tag.textContent=`CONTROLLED DATA · 100% zoom · ${width}px`;tag.style.cssText='position:fixed;right:8px;top:8px;z-index:9999;background:#eeeae2;color:#17161b;padding:5px 8px;font:11px sans-serif;pointer-events:none';},width);}
const base='/tmp/vlr-player-delivery';fs.mkdirSync(`${base}/screenshots`,{recursive:true});
(async()=>{const browser=await chromium.launch({headless:true});const results=[];
try{for(const [width,height]of [[1440,1000],[768,1024],[390,844],[320,844]]){
 const page=await browser.newPage({viewport:{width,height}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://10.0.0.21:3100/player/controlled-populated',{waitUntil:'networkidle'});await page.evaluate(()=>document.fonts.ready);await page.locator('.vlr-ticker').waitFor({timeout:20000});
 const layout=await page.evaluate(()=>({width:innerWidth,devicePixelRatio,browserZoom:1,documentWidth:document.documentElement.scrollWidth,tickers:document.querySelectorAll('.vlr-ticker').length,tickerPosition:getComputedStyle(document.querySelector('.vlr-ticker')).position}));assert.equal(layout.documentWidth,width);assert.equal(layout.tickers,1);assert.equal(layout.tickerPosition,'fixed');
 if(width===390)await page.locator('.pd-identity').evaluate(e=>window.scrollTo(0,e.getBoundingClientRect().top+scrollY-16));
 if(width===1440)assert.equal(await page.evaluate(()=>devicePixelRatio),1);
 await label(page,width);
 if(width===1440||width===390)await page.screenshot({path:`${base}/screenshots/controlled-overview-${width}.png`});
 await page.locator('.pd-method summary').focus();await page.keyboard.press('Enter');assert(await page.locator('.pd-method').evaluate(e=>e.open));await page.keyboard.press('Enter');
 await page.locator('.pd-history summary').focus();const focus=await page.locator('.pd-history summary').evaluate(e=>({outline:getComputedStyle(e).outlineStyle,width:getComputedStyle(e).outlineWidth}));assert.notEqual(focus.outline,'none');await page.keyboard.press('Enter');assert(await page.locator('.pd-history').evaluate(e=>e.open));await page.keyboard.press('Tab');assert(await page.locator('.pd-history [role="region"]').evaluate(e=>e===document.activeElement));
 assert.equal(await page.locator('.pd-agents tbody td').nth(1).evaluate(e=>getComputedStyle(e).textAlign),'right');
 const overflows=[];for(const region of await page.locator('.pd-table-scroll').all()){
  await region.focus();const before=await region.evaluate(e=>({width:e.clientWidth,scroll:e.scrollWidth,left:e.scrollLeft}));await page.keyboard.press('ArrowRight');await page.waitForTimeout(250);const left=await region.evaluate(e=>e.scrollLeft);if(before.scroll>before.width)assert(left>before.left);
  await region.evaluate(e=>e.scrollLeft=e.scrollWidth);assert(await region.evaluate(e=>e.querySelector('tbody tr > :last-child').getBoundingClientRect().right<=e.getBoundingClientRect().right+1));const sticky=await region.evaluate(e=>{const t=e.querySelector('table');if(!t.matches('.pd-agents,.pd-matches'))return null;return Math.abs(t.querySelector('tbody tr > :first-child').getBoundingClientRect().left-e.getBoundingClientRect().left)<3});if(sticky!==null)assert(sticky);overflows.push({...before,keyboardLeft:left,sticky});await region.evaluate(e=>e.scrollLeft=0);
 }
 if(width===1440){await page.locator('#player-rating').evaluate(e=>window.scrollTo(0,e.getBoundingClientRect().top+scrollY-44));await page.screenshot({path:`${base}/screenshots/controlled-history-1440.png`});}
 if(width===1440){await page.locator('#player-dimensions').evaluate(e=>window.scrollTo(0,e.getBoundingClientRect().top+scrollY-44));await page.screenshot({path:`${base}/screenshots/controlled-dimensions-1440.png`});}
 if(width===320){await page.locator('#player-agents').evaluate(e=>window.scrollTo(0,e.getBoundingClientRect().top+scrollY-44));await page.screenshot({path:`${base}/screenshots/controlled-agents-320.png`});}
 await page.locator('.pd-matches a').last().focus();const focusClear=await page.locator('.pd-matches a').last().evaluate(e=>{const r=e.getBoundingClientRect();return r.top>=0&&r.bottom<=document.querySelector('.vlr-ticker').getBoundingClientRect().top});assert(focusClear);
 await page.evaluate(()=>window.scrollTo(0,document.documentElement.scrollHeight));const bottomClear=await page.locator('.pd-matches').evaluate(e=>e.getBoundingClientRect().bottom<=document.querySelector('.vlr-ticker').getBoundingClientRect().top);assert(bottomClear);
 if(width===390)await page.screenshot({path:`${base}/screenshots/controlled-matches-390.png`});
 assert.deepEqual(errors,[]);results.push({...layout,focus,overflows,focusClear,bottomClear,errors});await page.close();
}
const page=await browser.newPage({viewport:{width:390,height:844}});
for(const kind of ['partial','empty','history-error','error','flat']){
 await page.goto(`http://10.0.0.21:3100/player/controlled-${kind}`,{waitUntil:'networkidle'});const text=await page.locator('main').textContent();
 if(kind==='partial'){assert(text.includes('History is still young'));assert(text.includes('Unknown'));assert.equal(await page.locator('.pd-chart').count(),0);}
 if(kind==='empty'){assert(text.includes('No agent stats available'));assert(text.includes('No recent matches listed'));}
 if(kind==='history-error'){assert(text.includes('Rating history unavailable'));assert(text.includes('leaderboard lookup failed'));assert(!text.includes('No rated snapshots'));}
 if(kind==='error')assert(text.includes("Couldn't load this player"));
 if(kind==='flat'){assert(text.includes('Rating held flat'));assert.equal(await page.locator('.pd-chart').count(),0);}
 if(kind==='partial'){await label(page,390);await page.locator('#player-rating').evaluate(e=>window.scrollTo(0,e.getBoundingClientRect().top+scrollY-44));await page.screenshot({path:`${base}/screenshots/controlled-partial-390.png`});}
 results.push({controlledState:kind,result:'passed'});
}
await page.goto('http://10.0.0.21:3100/player/9',{waitUntil:'networkidle'});assert((await page.locator('main').textContent()).includes("Couldn't load this player"));results.push({realPlayer:'9',state:'unavailable: no cached detail; no scrape attempted'});
fs.writeFileSync(`${base}/browser-results.json`,JSON.stringify({checkedAt:new Date().toISOString(),results},null,2)+'\n');console.log(results);
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
