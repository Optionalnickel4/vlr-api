import asyncio,json,pathlib,sys,time
sys.path.insert(0,'/home/builder/vlr-release-review-9301682')
import httpx,redis.asyncio as redis
from scripts.probe_api import request
B=pathlib.Path('/tmp/vlr-gates-9301682');O=pathlib.Path('/opt/vlr-api/docs/verification/release-gates/2026-09-27')
async def main():
 r=redis.Redis(unix_socket_path=str(B/'redis/redis.sock'),db=0);initial=await r.dbsize();assert initial==0
 rows=[];end=time.monotonic()+300
 async with httpx.AsyncClient(trust_env=False,follow_redirects=False) as c:
  for path in ['/match/753445','/team/8877','/player/3799']:
   for phase in ['cold','warm']:
    row,body=await request(c,'http://127.0.0.1:8110/api/v1'+path,min(90,end-time.monotonic()),2_000_000)
    row.update(phase=phase,path=path);rows.append(row)
    print(json.dumps({k:row.get(k) for k in ['phase','path','status','state','elapsed_ms','failure']}),flush=True)
    if row.get('failure') or row['status']==429 or 'retry-after' in row['headers']:
     (B/'network-off').touch();break
    await asyncio.sleep(2)
   if (B/'network-off').exists():break
 (B/'network-off').touch();final=await r.dbsize();await r.aclose()
 (O/'cold-probe.json').write_text(json.dumps({'initial_staging_keys':initial,'final_staging_keys':final,'max_requests':6,'max_seconds':300,'request_seconds':90,'max_bytes':2000000,'interval_seconds':2,'observations':rows},indent=2)+'\n')
 if (B/'origin.jsonl').exists():(O/'origin.jsonl').write_text((B/'origin.jsonl').read_text())
asyncio.run(main())
