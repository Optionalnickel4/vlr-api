const fs=require('node:fs');const root='/opt/vlr-api/frontend/src/lib/__fixtures__/';const original=globalThis.fetch;
globalThis.fetch=async function(input,options){
 const url=String(input?.url??input);const match=url.match(/^http:\/\/127\.0\.0\.1:8101\/api\/v1\/(trends\/)?team\/controlled-([^?]+)/);
 if(match){const kind=match[2],history=!!match[1];
  if(kind==='error'||(history&&kind==='history-error'))return new Response('{}',{status:503});
  const d=JSON.parse(fs.readFileSync(root+(history?'trends.json':'team.json'),'utf8'));
  if(history){d.note='CONTROLLED ACCEPTANCE — fixture data, not live performance';d.rating_trend.forEach((p,i)=>{p.rating=[1700,1753,1725,1800,1770][i];p.captured_at=`2026-09-${String(1+i*5).padStart(2,'0')}T12:00:00Z`});d.rating_change=70;d.summary.current_rating=1770;d.summary.peak_rating=1800;
   if(kind==='empty'){d.rating_trend=[];d.results_in_window=[];d.summary=null;d.rating_change=null;}
   if(kind==='partial'){d.rating_trend=[{rating:1700,captured_at:null,rank:null}];d.summary=null;d.rating_change=null;d.results_in_window=[{opponent:null,result:null,score:null}];}
   if(kind==='flat'){d.rating_trend.forEach(p=>p.rating=1700);d.rating_change=0;d.summary.current_rating=1700;d.summary.peak_rating=1700;}
  }else{d.name='CONTROLLED · Sentinels';d.logo=kind==='imagery'?'https://example.test/supplied-crest.svg':kind==='broken'?'https://example.test/broken-crest.png':null;
   if(kind==='empty'){d.roster=[];d.results=[];}
   if(kind==='partial'){d.name='CONTROLLED · Partial';d.tag=null;d.country=null;d.roster=d.roster.slice(0,1);d.results=[{opponent:'Unknown opponent',result:null,score:null}];}
  }
  return Response.json(d);
 }
 return original(input,options);
};
