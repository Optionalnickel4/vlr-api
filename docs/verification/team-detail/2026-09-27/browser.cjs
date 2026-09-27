const {chromium}=require('/tmp/vlr-browser-tools/node_modules/playwright');const assert=require('node:assert/strict');const fs=require('node:fs');
const base='/tmp/vlr-team-delivery';fs.mkdirSync(`${base}/screenshots`,{recursive:true});
(async()=>{const browser=await chromium.launch({headless:true});const results=[];
try{for(const [width,height]of [[1440,1000],[768,1024],[390,844],[320,844]]){
 const page=await browser.newPage({viewport:{width,height}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://10.0.0.21:3100/team/controlled-populated',{waitUntil:'networkidle'});await page.evaluate(()=>document.fonts.ready);await page.locator('.vlr-ticker').waitFor({timeout:20000});
 const layout=await page.evaluate(()=>({width:innerWidth,documentWidth:document.documentElement.scrollWidth,tickers:document.querySelectorAll('.vlr-ticker').length,tickerPosition:getComputedStyle(document.querySelector('.vlr-ticker')).position}));assert.equal(layout.documentWidth,width);assert.equal(layout.tickers,1);assert.equal(layout.tickerPosition,'fixed');
 if(width===1440||width===390)await page.screenshot({path:`${base}/screenshots/controlled-overview-${width}.png`});
 await page.locator('.td-history summary').focus();const focus=await page.locator('.td-history summary').evaluate(e=>({outline:getComputedStyle(e).outlineStyle,width:getComputedStyle(e).outlineWidth}));assert.notEqual(focus.outline,'none');await page.keyboard.press('Enter');assert(await page.locator('.td-history').evaluate(e=>e.open));await page.keyboard.press('Tab');assert(await page.locator('.td-history [role="region"]').evaluate(e=>e===document.activeElement));
 const overflows=[];for(const region of await page.locator('.td-table-scroll').all()){
  await region.focus();const before=await region.evaluate(e=>({width:e.clientWidth,scroll:e.scrollWidth,left:e.scrollLeft}));await page.keyboard.press('ArrowRight');await page.waitForTimeout(250);const left=await region.evaluate(e=>e.scrollLeft);if(before.scroll>before.width)assert(left>before.left);
  await region.evaluate(e=>e.scrollLeft=e.scrollWidth);assert(await region.evaluate(e=>e.querySelector('tbody tr > :last-child').getBoundingClientRect().right<=e.getBoundingClientRect().right+1));overflows.push({...before,keyboardLeft:left});await region.evaluate(e=>e.scrollLeft=0);
 }
 if(width===1440){await page.locator('#team-rating').evaluate(e=>window.scrollTo(0,e.getBoundingClientRect().top+scrollY-44));await page.screenshot({path:`${base}/screenshots/controlled-history-1440.png`});}
 if(width===320){await page.locator('.td-roster').evaluate(e=>window.scrollTo(0,e.getBoundingClientRect().top+scrollY-65));await page.screenshot({path:`${base}/screenshots/controlled-roster-320.png`});}
 await page.locator('.td-results a').last().focus();const focusClear=await page.locator('.td-results a').last().evaluate(e=>{const r=e.getBoundingClientRect();return r.top>=0&&r.bottom<=document.querySelector('.vlr-ticker').getBoundingClientRect().top});assert(focusClear);
 await page.evaluate(()=>window.scrollTo(0,document.documentElement.scrollHeight));const bottomClear=await page.locator('.td-results').evaluate(e=>e.getBoundingClientRect().bottom<=document.querySelector('.vlr-ticker').getBoundingClientRect().top);assert(bottomClear);
 if(width===390)await page.screenshot({path:`${base}/screenshots/controlled-results-390.png`});
 assert.deepEqual(errors,[]);results.push({...layout,focus,overflows,focusClear,bottomClear,errors});await page.close();
}
const page=await browser.newPage({viewport:{width:390,height:844}});
await page.route('https://example.test/supplied-crest.svg',r=>r.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="88" height="88"><rect width="88" height="88" fill="#eeeae2"/><text x="9" y="48" fill="#17161b" font-size="24">TEST</text></svg>'}));await page.route('https://example.test/broken-crest.png',r=>r.fulfill({status:404,body:''}));
for(const kind of ['partial','empty','history-error','error','flat','imagery','broken']){
 await page.goto(`http://10.0.0.21:3100/team/controlled-${kind}`,{waitUntil:'networkidle'});const text=await page.locator('main').textContent();
 if(kind==='partial'){assert(text.includes('One rated snapshot'));assert(text.includes('Unknown'));assert.equal(await page.locator('.td-chart').count(),0);}
 if(kind==='empty'){assert(text.includes('No results matched'));assert(text.includes('No recent results listed'));}
 if(kind==='history-error'){assert(text.includes('Rating history unavailable'));assert(text.includes('Results unavailable'));assert(!text.includes('No results matched'));}
 if(kind==='error')assert(text.includes("Couldn't load this team"));
 if(kind==='flat'){assert(text.includes('Rating held flat'));assert.equal(await page.locator('.td-chart').count(),0);}
 if(kind==='imagery'){assert(await page.locator('.td-identity img').evaluate(e=>e.complete&&e.naturalWidth>0));}
 if(kind==='broken')assert.equal(await page.locator('.td-identity img').count(),0);
 if(kind==='partial'){await page.locator('#team-rating').evaluate(e=>window.scrollTo(0,e.getBoundingClientRect().top+scrollY-44));await page.screenshot({path:`${base}/screenshots/controlled-partial-390.png`});}
 results.push({controlledState:kind,result:'passed'});
}
await page.goto('http://10.0.0.21:3100/team/2',{waitUntil:'networkidle'});assert((await page.locator('main').textContent()).includes("Couldn't load this team"));results.push({realTeam:'2',state:'unavailable: no cached detail; no scrape attempted'});
fs.writeFileSync(`${base}/browser-results.json`,JSON.stringify({checkedAt:new Date().toISOString(),results},null,2)+'\n');console.log(results);
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
