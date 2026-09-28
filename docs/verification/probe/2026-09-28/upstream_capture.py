import asyncio, json, time
from datetime import datetime, timezone
from pathlib import Path
from selectolax.parser import HTMLParser
from app.core.http import get_client, aclose_client
from app.scrapers.players import parse_player
from app.scrapers.match_detail import parse_match

async def main():
 c=get_client()
 report=[]
 try:
  for path,kind in [('/player/36245/?timespan=all','player'),('/753445','match')]:
   start=time.monotonic()
   row={'url':'https://www.vlr.gg'+path,'started':datetime.now(timezone.utc).isoformat()}
   async with asyncio.timeout(45):
    await c._throttle()
    async with c._client.stream('GET',path,follow_redirects=False) as r:
     row['status']=r.status_code
     raw=bytearray()
     async for chunk in r.aiter_bytes():
      raw.extend(chunk)
      if len(raw)>2000000: raise RuntimeError('body limit')
     row['bytes']=len(raw)
     if r.is_success:
      html=raw.decode(); tree=HTMLParser(html)
      data=parse_player(html) if kind=='player' else parse_match(html)
      print(kind, json.dumps({k:v for k,v in data.items() if k not in ('maps','all_maps','agent_stats','matches')}))
      selectors=['.player-header','h2.wf-label','.m-item'] if kind=='player' else ['.match-header-vs']
      for sel in selectors:
       for node in tree.css(sel)[:3]: print(sel,node.html[:14000])
      # Temporary in-memory source only; persist scoped excerpts after review.
      if kind=='player':
       nodes=tree.css('.player-header')+tree.css('.m-item')[:1]
       for h in tree.css('h2.wf-label'):
        if 'Current Teams' in h.text() or 'Past Teams' in h.text():
         nodes.append(h)
         sib=h.next
         while sib is not None and sib.tag != 'div': sib=sib.next
         if sib: nodes.append(sib)
      else: nodes=tree.css('.match-header-vs')
      Path('/tmp/vlr-'+kind+'-excerpt.html').write_text('\n'.join(n.html for n in nodes))
     row['retry_after_present']='retry-after' in r.headers
   row['elapsed_ms']=round((time.monotonic()-start)*1000,1); report.append(row)
   if row['status']!=200 or row['retry_after_present']: break
   await asyncio.sleep(3)
 finally:
  await aclose_client()
  Path('docs/verification/probe/2026-09-28/upstream.json').write_text(json.dumps(report,indent=2)+'\n')
asyncio.run(main())
