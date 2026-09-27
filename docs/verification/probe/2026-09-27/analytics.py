import asyncio,json
from pathlib import Path
import httpx
from scripts.probe_api import request
async def main():
 rows=[]
 async with httpx.AsyncClient(base_url='http://10.0.0.21:8000',trust_env=False,follow_redirects=False) as c:
  for path in ['/api/v1/trends/player/3799','/api/v1/players/3799/dimensions?region=na&timespan=all','/api/v1/trends/team/8877']:
   row,body=await request(c,path,90,2000000)
   rows.append(row)
   print(json.dumps({k:row.get(k) for k in ('path','status','state','elapsed_ms','failure')}),flush=True)
   if row.get('failure') in ('timeout','transport') or row['status']==429 or 'retry-after' in row['headers']:break
   await asyncio.sleep(2)
 Path('docs/verification/probe/2026-09-27/analytics.json').write_text(json.dumps(rows,indent=2)+'\n')
asyncio.run(main())
