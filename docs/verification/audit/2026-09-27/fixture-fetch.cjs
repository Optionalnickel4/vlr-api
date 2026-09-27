const fs=require('node:fs');
for(const name of ['match','team','player','listings','ladders','news'])require(`/tmp/vlr-${name}-delivery/fixture-fetch.cjs`);
const original=globalThis.fetch;
globalThis.fetch=async(input,options)=>{
 const u=String(input?.url??input);const scenario=fs.readFileSync('/tmp/vlr-audit/scenario','utf8').trim();
 if(u.startsWith('http://127.0.0.1:8101/api/v1/')){
  if(scenario==='slow'&&u.includes('/rankings?'))return new Promise((resolve,reject)=>{const timer=setTimeout(()=>resolve(Response.json([])),12000);options.signal.addEventListener('abort',()=>{clearTimeout(timer);reject(new Error('Controlled slow upstream aborted'));});});
  if(u.endsWith('/matches/live'))return Response.json(scenario==='live'?[{id:'controlled-live',teams:['CONTROLLED Alpha','CONTROLLED Beta'],scores:['1','0'],event:'CONTROLLED LIVE',eta:'LIVE'}]:[]);
  if(u.includes('/rankings?')&&scenario==='stale'){const r=await original(input,options);return new Response(await r.text(),{headers:{'Content-Type':'application/json','X-VLR-Cache':'stale'}});}
  if(u.includes('/players?q='))return Response.json({data:[{id:'controlled-populated',alias:'CONTROLLED Search Player',team:'CONTROLLED Team',source:'db'}],stale:false});
 }
 return original(input,options);
};
