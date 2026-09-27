const fs=require('node:fs');const original=globalThis.fetch;
globalThis.fetch=async function(input,options){const url=String(input?.url??input);if(/^http:\/\/127\.0\.0\.1:8101\/api\/v1\/(rankings|stats)\?/.test(url)){
 const kind=fs.readFileSync('/tmp/vlr-ladders-delivery/scenario','utf8').trim();const isStats=url.includes('/stats?');
 if(kind==='error')return new Response('{}',{status:503});
 if(isStats){let data=JSON.parse(fs.readFileSync('/opt/vlr-api/frontend/src/lib/__fixtures__/stats.json','utf8'));data[0].player='CONTROLLED · '+ 'LongPlayerName'.repeat(5);data[0].team='CONTROLLEDLONGTEAM';data[1].player='CONTROLLED · Bravo';data[2].player='CONTROLLED · Partial';data[2].rnd=null;data[2].player_id=null;return Response.json({data:kind==='empty'?[]:data,stale:kind==='stale',...(kind==='stale'?{error:'Controlled stale cache'}:{})});}
 return Response.json(kind==='empty'?[]:[{rank:'1',team:'CONTROLLED · '+ 'LongTeamName'.repeat(6),team_id:'controlled-1',country:'Source label',rating:'2000'},{rank:'2',team:null,team_id:null,country:null,rating:null},{rank:'1',team:'CONTROLLED · Another ladder',team_id:'controlled-2',country:'Other source label',rating:'0'}]);
}return original(input,options);};
