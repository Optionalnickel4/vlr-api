import asyncio,json,pathlib,time,sys,httpx
B=pathlib.Path('/tmp/vlr-reliability');label=sys.argv[1];rows=[]
if len(sys.argv)>2 and (B/f"{label}-requests.json").exists(): rows=json.loads((B/f"{label}-requests.json").read_text())
async def main():
 async with httpx.AsyncClient(timeout=100, headers={"Connection":"close"}) as c:
  for mode in (sys.argv[2:] or ['fast','slow','failed','missing','dbfailed','dbslow']):
   (B/'scenario').write_text(mode)
   for kind in ['match','team','player']:
    if mode.startswith('db') and kind=='match':continue
    await c.post('http://127.0.0.1:8102/_audit/reset')
    for state in ['cold','warm']:
     start=time.monotonic();r=await c.get(f'http://127.0.0.1:8102/api/v1/{kind}/9001');elapsed=round((time.monotonic()-start)*1000)
     try:body=r.json()
     except ValueError:body=r.text
     record=dict(mode=mode,kind=kind,state=state,status=r.status_code,elapsedMs=elapsed,bodyKeys=list(body) if isinstance(body,dict) else None,name=body.get('name',body.get('alias')) if isinstance(body,dict) else None)
     rows.append(record);(B/f"{label}-requests.json").write_text(json.dumps(rows,indent=2)+"\n");print(json.dumps(record),flush=True)
  (B/f'{label}-requests.json').write_text(json.dumps(rows,indent=2)+'\n');(B/'scenario').write_text('fast')
asyncio.run(main())
