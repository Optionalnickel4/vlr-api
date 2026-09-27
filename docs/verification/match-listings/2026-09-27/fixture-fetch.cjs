const fs=require('node:fs');const original=globalThis.fetch;
globalThis.fetch=async function(input,options){
 const url=String(input?.url??input);if(/^http:\/\/127\.0\.0\.1:8101\/api\/v1\/matches\/(upcoming|results)$/.test(url)){
 const kind=fs.readFileSync('/tmp/vlr-listings-delivery/scenario','utf8').trim();
 if(kind==='error')return new Response('{}',{status:503});if(kind==='empty')return Response.json([]);
 const row={id:'controlled-1',teams:['CONTROLLED · International Championship Academy','CONTROLLED · '+ 'LongTeamName'.repeat(7)],scores:['2','0'],eta:'2h',time:'5:00 AM',event:'CONTROLLED · '+ 'LongEventName'.repeat(6),series:'Grand Final · Championship qualification'};
 return Response.json([row,{...row,id:'controlled-2',teams:[null,'CONTROLLED · Challenger'],scores:[null,'0'],eta:null,time:null,event:null,series:null},{...row,id:null,teams:[null,null],scores:['0','0'],eta:'LIVE',time:null,event:'CONTROLLED · Partial data',series:null}]);
 }return original(input,options);
};
