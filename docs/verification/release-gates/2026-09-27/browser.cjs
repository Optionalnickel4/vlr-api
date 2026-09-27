const {chromium}=require('/tmp/vlr-browser-tools/node_modules/playwright');
const fs=require('fs');
(async()=>{
const browser=await chromium.launch({headless:true});const rows=[];
try{
 for(const [path,selector] of [['/match/753445','.match-detail'],['/team/8877','.team-detail'],['/player/3799','.player-detail']]){
  const page=await browser.newPage({viewport:{width:390,height:1000}});let errors=0;page.on('pageerror',()=>errors++);
  const start=Date.now();const row={path,cache:'warmed by preceding cold API probe; all subsequent origin traffic blocked'};
  try{
   const response=await page.goto('http://127.0.0.1:3110'+path,{waitUntil:'domcontentloaded',timeout:95000});row.http_status=response.status();
   await page.locator(selector).waitFor({timeout:95000});row.populated=true;row.elapsed_ms=Date.now()-start;
   row.page_errors=errors;row.overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
   row.table_rows=await page.locator('main tbody tr').count();
   await page.screenshot({path:'/tmp/vlr-gates-9301682/'+path.split('/')[1]+'.png',fullPage:true});
  }catch(e){row.failure=e.name;row.elapsed_ms=Date.now()-start;row.populated=false}
  rows.push(row);console.log(JSON.stringify(row));await page.close();await new Promise(r=>setTimeout(r,2000));
 }
}finally{await browser.close();fs.writeFileSync('/opt/vlr-api/docs/verification/release-gates/2026-09-27/browser.json',JSON.stringify(rows,null,2)+'\n')}
})().catch(e=>{console.error(e.name);process.exitCode=1});
