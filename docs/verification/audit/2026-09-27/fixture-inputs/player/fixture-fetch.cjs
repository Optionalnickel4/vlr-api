const fs=require('node:fs');const original=globalThis.fetch;
globalThis.fetch=async function(input,options){
 const url=String(input?.url??input);const match=url.match(/^http:\/\/127\.0\.0\.1:8101\/api\/v1\/(trends\/player|player|players)\/controlled-([^/?]+)(\/dimensions)?/);
 if(match){const kind=match[2],history=match[1]==='trends/player',dimensions=match[1]==='players';
  if(kind==='error'||(kind==='history-error'&&(history||dimensions)))return new Response('{}',{status:503});
  if(dimensions){if(kind==='empty')return new Response('{}',{status:404});return Response.json({player_id:'controlled-'+kind,region:kind==='partial'?null:'na',timespan:'all',firepower:kind==='partial'?null:92,entry:kind==='partial'?0:65,consistency:kind==='partial'?null:80,clutch:kind==='partial'?null:40,low_confidence:['clutch']});}
  if(history){const points=[1.05,1.08,1.06,1.15,1.12].map((rating,i)=>({captured_at:`2026-09-${String(1+i*5).padStart(2,'0')}T12:00:00Z`,rating:kind==='flat'?1.05:rating,acs:220+i*4,rounds:9000+i*100}));return Response.json({player_id:'controlled-'+kind,window_days:90,rating_trend:kind==='empty'?[]:kind==='partial'?[{rating:1.05,acs:null,rounds:null,captured_at:null}]:points,rating_change:kind==='empty'||kind==='partial'?null:kind==='flat'?0:.07,acs_change:kind==='empty'||kind==='partial'?null:16,summary:kind==='empty'||kind==='partial'?null:{current_rating:kind==='flat'?1.05:1.12,peak_rating:kind==='flat'?1.05:1.15,current_acs:236,peak_acs:236},note:'CONTROLLED ACCEPTANCE — fixture data, not live performance'});}
  const data=JSON.parse(fs.readFileSync('/opt/vlr-api/frontend/src/lib/__fixtures__/player.json','utf8'));data.alias='CONTROLLED · TenZ';data.real_name='Controlled acceptance data';
  if(kind==='empty'){data.agent_stats=[];data.matches=[];}
  if(kind==='partial'){data.alias='CONTROLLED · Partial';data.team=null;data.team_id=null;data.team_url=null;data.country=null;data.agent_stats=[{agent:'omen',stats:{R:'1.05',ACS:'—','K:D':'—',RND:'—'}}];data.matches=[{opponent:null,result:null,score:null}];}
  return Response.json(data);
 }
 return original(input,options);
};
