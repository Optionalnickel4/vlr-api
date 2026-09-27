const fs=require('node:fs');
const root='/opt/vlr-api/frontend/src/lib/__fixtures__/';
const original=globalThis.fetch;
globalThis.fetch=async function(input,options){
 const url=String(input?.url??input);
 if(url.startsWith('http://127.0.0.1:8101/api/v1/match/controlled-')){
  const kind=url.split('controlled-')[1].split('?')[0];
  if(kind==='missing') return new Response('{}',{status:503});
  const data=JSON.parse(fs.readFileSync(root+(kind==='live'?'match_live_partial.json':'match.json'),'utf8'));
  data.id='controlled-'+kind;data.event='CONTROLLED ACCEPTANCE · '+data.event;
  if(kind==='upcoming'){data.status='upcoming';data.teams=data.teams.map(t=>({...t,score:null,won:false}));data.maps=[];data.all_maps=null;data.veto=null;}
  if(kind==='imagery'){data.teams[0].logo='https://example.test/supplied-crest.svg';data.teams[1].logo='https://example.test/broken-crest.png';}
  return Response.json(data);
 }
 return original(input,options);
};
