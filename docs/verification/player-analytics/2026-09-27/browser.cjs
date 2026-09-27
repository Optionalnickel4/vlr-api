const {chromium}=require('/tmp/vlr-browser-tools/node_modules/playwright');
const fs=require('node:fs');
const base=process.argv[2]||'http://10.0.0.21:3100';
const output=process.argv[3]||'docs/verification/player-analytics/2026-09-27/browser-before.json';
(async()=>{
 const browser=await chromium.launch({headless:true});const rows=[];
 try {
  for(const width of [1440,390]){
   const page=await browser.newPage({viewport:{width,height:1000}});let errors=0;page.on('pageerror',()=>errors++);
   const start=Date.now();const row={base,width,playerId:'3799'};
   try {
    const response=await page.goto(base+'/player/3799',{waitUntil:'domcontentloaded',timeout:95000});
    await page.locator('.player-detail').waitFor({timeout:95000});
    row.status=response.status();row.elapsedMs=Date.now()-start;
    row.headline=await page.locator('.pd-headline').innerText();
    row.agentRows=await page.locator('.pd-agents tbody tr').count();
    row.matchRows=await page.locator('section[aria-labelledby="player-matches"] tbody tr').count();
    row.historyRows=await page.locator('.pd-history tbody tr').count();
    row.radar=await page.locator('.pd-radar').count();
    row.notices=await page.locator('.pd-empty,.pd-notice').allTextContents();
    if(process.argv[4]==='inspect'){
     const summary=page.locator('.pd-history summary');
     if(await summary.count())await summary.click();
     row.visibleHistoryRows=await page.locator('.pd-history tbody tr:visible').count();
     row.dimensions=await page.locator('.pd-dimension').evaluateAll(es=>es.map(e=>e.getAttribute('aria-label')));
     const scroll=page.locator('.pd-agent-scroll');
     await scroll.focus();await page.keyboard.press('ArrowRight');
     await page.waitForFunction(()=>document.querySelector('.pd-agent-scroll').scrollLeft>0,null,{timeout:2000});
     row.tableScrolled=await scroll.evaluate(e=>e.scrollLeft>0);
     if(row.agentRows!==3||row.matchRows!==5||row.historyRows<1||row.radar!==1)process.exitCode=1;
    }
    row.horizontalOverflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
    row.pageErrors=errors;
    row.scrollRegions=await page.locator('.pd-table-scroll').evaluateAll(es=>es.map(e=>({label:e.getAttribute('aria-label'),scrollable:e.scrollWidth>e.clientWidth,keyboard:e.tabIndex===0})));
    await page.screenshot({path:'/tmp/vlr-analytics-'+(base.includes('3100')?'preview':'isolated')+'-'+width+'.png',fullPage:true});
   }catch(e){row.failure=e.name;row.elapsedMs=Date.now()-start;}
   rows.push(row);console.log(JSON.stringify(row));await page.close();await new Promise(r=>setTimeout(r,2000));
  }
 }finally{fs.writeFileSync(output,JSON.stringify(rows,null,2)+'\n');await browser.close();}
})().catch(e=>{console.error(e.name);process.exitCode=1});
