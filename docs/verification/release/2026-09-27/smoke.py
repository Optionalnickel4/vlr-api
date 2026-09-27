import asyncio,datetime,json,pathlib,sys,time
sys.path.insert(0,'/opt/vlr-api')
import httpx
from scripts.probe_api import request
out=pathlib.Path('/opt/vlr-api/docs/verification/release/2026-09-27')
async def main():
 targets=[('api',8000,'/api/v1/trends/player/3799?days=90'),('api',8000,'/api/v1/players/3799/dimensions?region=na&timespan=all'),('adapter',8101,'/api/v1/trends/player/3799?days=90'),('adapter',8101,'/api/v1/players/3799/dimensions?region=na&timespan=all'),('preview',3100,'/api/rankings'),('preview',3100,'/api/match/753445'),('preview',3100,'/api/team/8877'),('preview',3100,'/api/player/3799'),('preview',3100,'/api/trends/player/3799?days=90'),('preview',3100,'/'),('preview',3100,'/player/3799'),('production_frontend',3000,'/')]
 rows=[];end=time.monotonic()+300
 async with httpx.AsyncClient(trust_env=False,follow_redirects=False) as c:
  for layer,port,path in targets:
   if time.monotonic()>=end:break
   row,body=await request(c,f'http://127.0.0.1:{port}'+path,min(90,end-time.monotonic()),2_000_000)
   row.update(layer=layer,path=path)
   if path in ['/','/player/3799'] and row.get('failure')=='non_json' and 'text/html' in row['headers'].get('content-type',''):
    row.pop('failure');row['state']='html_received'
   d=body.get('data',body) if isinstance(body,dict) else body
   if isinstance(d,list) and len(d)==1:d=d[0]
   if isinstance(d,dict):
    row['feature_counts']={k:len(d[k]) for k in ['agent_stats','agentStats','matches','rating_trend','ratingTrend'] if isinstance(d.get(k),list)}
    row['numeric_dimensions']=[k for k in ['firepower','entry','consistency','clutch'] if isinstance(d.get(k),(int,float))]
   rows.append(row);print(json.dumps({k:row.get(k) for k in ['layer','path','status','state','elapsed_ms','stale','error_present','failure','feature_counts','numeric_dimensions']}),flush=True)
   if row.get('failure') in ['timeout','transport','body_limit'] or row.get('status')==429 or 'retry-after' in row['headers']:break
   await asyncio.sleep(2)
 (out/'preview-analytics-smoke.json').write_text(json.dumps({'limits':{'requests':12,'total_seconds':300,'request_seconds':90,'bytes':2000000,'interval_seconds':2},'observations':rows},indent=2)+'\n')
asyncio.run(main())
