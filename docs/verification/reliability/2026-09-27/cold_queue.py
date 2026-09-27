import asyncio,time,pathlib,json,httpx
B=pathlib.Path('/tmp/vlr-reliability')
async def main():
 (B/'scenario').write_text('fast')
 async with httpx.AsyncClient(timeout=90) as c:
  await c.post('http://127.0.0.1:8102/_audit/reset')
  async def run(i):
   start=time.monotonic();r=await c.get(f'http://127.0.0.1:8102/api/v1/match/{9100+i}')
   return {'id':9100+i,'status':r.status_code,'elapsedMs':round((time.monotonic()-start)*1000)}
  rows=await asyncio.gather(*(run(i) for i in range(9)))
 (B/'queue.json').write_text(json.dumps(rows,indent=2)+'\n');print(rows)
asyncio.run(main())
