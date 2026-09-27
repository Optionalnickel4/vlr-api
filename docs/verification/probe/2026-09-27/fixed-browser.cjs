const {chromium}=require('/tmp/vlr-browser-tools/node_modules/playwright');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try {
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  let errors=0;page.on('pageerror',()=>errors++);
  const start=Date.now();
  const response=await page.goto('http://127.0.0.1:3101/player/3799',{waitUntil:'domcontentloaded',timeout:95000});
  await page.locator('.player-detail').waitFor({timeout:95000});
  const card=page.locator('.pd-identity');
  const text=await card.innerText();
  const row={route:'/player/3799',preview:3101,status:response.status(),elapsedMs:Date.now()-start,
   hasKnownRounds:text.includes('504 known rounds across 3 rows'),
   hasRating:text.includes('1.98'),hasWeightedACS:await page.locator('.pd-headline > div').nth(2).locator('strong').innerText()==='228',
   signature:await page.locator('.pd-signature strong').innerText(),
   noRoundSampleUnavailable:!text.includes('Round sample unavailable'),
   pageErrors:errors,horizontalOverflow:await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)};
  await page.screenshot({path:'/tmp/vlr-probe-player-fixed.png',fullPage:true});
  fs.writeFileSync('/opt/vlr-api/docs/verification/probe/2026-09-27/fixed-browser.json',JSON.stringify(row,null,2)+'\n');
  console.log(JSON.stringify(row));
  if(!row.hasKnownRounds||!row.hasRating||!row.hasWeightedACS||row.signature.toLowerCase()!=='sova'||!row.noRoundSampleUnavailable||errors||row.horizontalOverflow)process.exitCode=1;
 }finally{await browser.close();}
})().catch(e=>{console.error(e.name);process.exitCode=1});
