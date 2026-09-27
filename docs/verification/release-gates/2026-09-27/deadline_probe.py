import asyncio,json,pathlib,sys,httpx
sys.path.insert(0,'/home/builder/vlr-release-review-9301682')
from scripts.probe_api import request
async def main():
 rows=[]
 # Disable httpx's default five-second idle timeout; request() bounds the
 # complete header/body operation at 95 seconds, including the real 80s route.
 async with httpx.AsyncClient(trust_env=False,timeout=None) as c:
  for path in ['/match/9905','/match/9900']:
   row,body=await request(c,'http://127.0.0.1:8111/api/v1'+path,95,2000000);rows.append(row);print(json.dumps({k:row.get(k) for k in ['path','status','elapsed_ms','failure']}),flush=True)
 pathlib.Path('docs/verification/release-gates/2026-09-27/deadline-api.json').write_text(json.dumps(rows,indent=2)+'\n')
asyncio.run(main())
