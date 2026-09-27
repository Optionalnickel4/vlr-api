import httpx,pathlib,json,hashlib,sys,asyncio
B=pathlib.Path('/tmp/vlr-reliability')
async def main():
 (B/'scenario').write_text('fast');out={}
 async with httpx.AsyncClient(timeout=90) as c:
  await c.post('http://127.0.0.1:8102/_audit/reset')
  for k in ['match','team','player']:
   r=await c.get(f'http://127.0.0.1:8102/api/v1/{k}/9001');assert r.status_code==200
   out[k]=hashlib.sha256(json.dumps(r.json(),sort_keys=True).encode()).hexdigest()
 (B/f'{sys.argv[1]}-body-hashes.json').write_text(json.dumps(out,indent=2)+'\n')
asyncio.run(main())
