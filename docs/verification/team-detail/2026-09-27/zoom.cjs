const {chromium}=require('/tmp/vlr-browser-tools/node_modules/playwright');const assert=require('node:assert/strict');const fs=require('node:fs');
(async()=>{const results=[];for(const width of [1440,768]){
 const ctx=await chromium.launchPersistentContext(`/tmp/vlr-team-delivery/zoom-${width}`,{headless:true,channel:'chromium',viewport:null,args:[`--window-size=${width},1000`]});
 try{const page=ctx.pages()[0];await page.goto('chrome://settings/appearance');await page.evaluate(()=>new Promise(resolve=>chrome.settingsPrivate.setDefaultZoom(2,resolve)));const zoom=await page.evaluate(()=>new Promise(resolve=>chrome.settingsPrivate.getDefaultZoom(resolve)));assert.equal(zoom,2);
 await page.goto('http://10.0.0.21:3100/team/controlled-populated',{waitUntil:'networkidle'});await page.evaluate(()=>document.fonts.ready);await page.locator('.vlr-ticker').waitFor({timeout:20000});
 const layout=await page.evaluate(()=>({outerWidth,innerWidth,innerHeight,devicePixelRatio,documentWidth:document.documentElement.scrollWidth}));assert.equal(layout.innerWidth,width/2);assert.equal(layout.documentWidth,layout.innerWidth);
 await page.locator('.td-history summary').focus();await page.keyboard.press('Enter');assert(await page.locator('.td-history').evaluate(e=>e.open));
 const table=page.locator('.td-roster');await table.focus();await page.keyboard.press('ArrowRight');await page.waitForTimeout(250);const overflow=await table.evaluate(e=>({left:e.scrollLeft,client:e.clientWidth,scroll:e.scrollWidth}));if(overflow.scroll>overflow.client)assert(overflow.left>0);
 await page.locator('.td-results a').last().focus();const focusedClear=await page.locator('.td-results a').last().evaluate(e=>{const r=e.getBoundingClientRect();return r.top>=0&&r.bottom<=document.querySelector('.vlr-ticker').getBoundingClientRect().top});assert(focusedClear);
 await page.evaluate(()=>window.scrollTo(0,document.documentElement.scrollHeight));const bottomClear=await page.locator('.td-results').evaluate(e=>e.getBoundingClientRect().bottom<=document.querySelector('.vlr-ticker').getBoundingClientRect().top);assert(bottomClear);
 if(width===1440){await page.locator('.td-history summary').focus();const cdp=await ctx.newCDPSession(page);const shot=await cdp.send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync('/tmp/vlr-team-delivery/screenshots/controlled-zoom-200.png',Buffer.from(shot.data,'base64'));}
 results.push({browserZoom:zoom,...layout,overflow,focusedClear,bottomClear,keyboardDisclosure:true});
 }finally{await ctx.close();}}
 fs.writeFileSync('/tmp/vlr-team-delivery/zoom-results.json',JSON.stringify({checkedAt:new Date().toISOString(),method:'Actual Chromium default page zoom via chrome.settingsPrivate.setDefaultZoom(2)',results},null,2)+'\n');console.log(results);
})().catch(e=>{console.error(e);process.exitCode=1;});
