const {chromium}=require('/tmp/vlr-browser-tools/node_modules/playwright');const fs=require('fs');
(async()=>{
 const browser=await chromium.launch({headless:true});const rows=[];
 try{
  for(const [id,expected,budget] of [['9904','.match-detail',12000],['9901','.match-unavailable',90000]]){
   const page=await browser.newPage({viewport:{width:390,height:1000}});let pageErrors=0;page.on('pageerror',()=>pageErrors++);
   const start=Date.now();const response=await page.goto('http://127.0.0.1:3111/match/'+id,{waitUntil:'commit',timeout:10000});
   await page.getByRole('status').filter({hasText:/loading/i}).waitFor({timeout:5000});const loading_ms=Date.now()-start;
   await page.locator(expected).waitFor({timeout:100000});const elapsed_ms=Date.now()-start;
   rows.push({id,http_status:response.status(),loading_ms,elapsed_ms,expected,expected_budget_ms:budget,page_errors:pageErrors,pass:loading_ms<5000&&elapsed_ms>=budget-1500&&elapsed_ms<budget+10000});
   console.log(JSON.stringify(rows.at(-1)));await page.close();
  }
 }finally{await browser.close();fs.writeFileSync('/opt/vlr-api/docs/verification/release-gates/2026-09-27/deadline-browser.json',JSON.stringify(rows,null,2)+'\n')}
})().catch(e=>{console.error(e.name);process.exitCode=1});
