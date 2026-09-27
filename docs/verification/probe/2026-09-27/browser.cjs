const {chromium}=require('/tmp/vlr-browser-tools/node_modules/playwright');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:1000}});
 const page=await context.newPage();
 const rows=[]; let errors=0; page.on('pageerror',()=>errors++);
 try {
  for(const [listing,kind,id] of [['results','match','753445'],['rankings','team','8877'],['stats','player','3799']]){
   const row={listing,kind,id}; let started=Date.now();
   try {
    const response=await page.goto('http://10.0.0.21:3100/'+listing,{waitUntil:'domcontentloaded',timeout:95000});
    await page.locator('main h1').first().waitFor({timeout:95000});
    const link=page.locator(`main a[href="/${kind}/${id}"]`).first();
    row.listingStatus=response.status();row.linkPresent=await link.count()>0;
    row.listingMs=Date.now()-started;started=Date.now();
    if(row.linkPresent){await link.click({timeout:10000});await page.waitForURL(`**/${kind}/${id}`,{timeout:95000});}
    else {row.directFallback=true;await page.goto(`http://10.0.0.21:3100/${kind}/${id}`,{waitUntil:'domcontentloaded',timeout:95000});}
    await page.waitForFunction(()=>{const h=document.querySelector('main h1');return h&&!/^Loading/i.test(h.textContent)},null,{timeout:95000});
    row.detailMs=Date.now()-started;
    row.loaded=await page.locator('.'+kind+'-detail').count()>0;
    row.heading=await page.locator('main h1').first().textContent();
    const text=await page.locator('main').innerText();
    row.notices=text.split('\n').filter(x=>/unavailable|could not|no .*available|no .*history|not enough|not found/i.test(x)).slice(0,12);
    row.horizontalOverflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
    row.pageErrors=errors;
    await page.screenshot({path:`/tmp/vlr-probe-${kind}.png`,fullPage:true});
   }catch(e){row.failure=e.name;row.elapsedMs=Date.now()-started;}
   rows.push(row);console.log(JSON.stringify(row));
   await page.goto('about:blank');
   await new Promise(r=>setTimeout(r,2000));
  }
 }finally{fs.writeFileSync('/opt/vlr-api/docs/verification/probe/2026-09-27/browser.json',JSON.stringify(rows,null,2)+'\n');await browser.close();}
})().catch(e=>{console.error(e.name);process.exitCode=1});
