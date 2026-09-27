import asyncio,httpx,time,json,pathlib
async def main():
 async with httpx.AsyncClient(timeout=95) as c:
  for _ in range(30):
   try:await c.get('http://127.0.0.1:8102/health');break
   except httpx.ConnectError:await asyncio.sleep(.2)
  started=time.monotonic();r=await c.get('http://127.0.0.1:8102/api/v1/match/9900');ms=round((time.monotonic()-started)*1000)
  assert r.status_code==504 and 79000<=ms<90000
  pathlib.Path('/tmp/vlr-reliability/hung.json').write_text(json.dumps({'elapsedMs':ms,'status':r.status_code,'body':r.json()},indent=2)+'\n')
asyncio.run(main())
