"""Two static GETs only: no detail page, API refresh, retry or VLR request."""
import pathlib,urllib.request,time,hashlib,json
F=pathlib.Path('/opt/vlr-api/frontend/.next');asset=next(p for p in sorted((F/'static').rglob('*.js')) if 1024<p.stat().st_size<100000)
path='/_next/'+str(asset.relative_to(F));expected=hashlib.sha256(asset.read_bytes()).hexdigest();out={'path':path,'expected_sha256':expected,'requests':[]}
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
opener=urllib.request.build_opener(NoRedirect)
for origin in ['http://10.0.0.21:3000','https://val.jushosting.dev']:
 start=time.monotonic();r={'origin':origin}
 try:
  with opener.open(origin+path+'?release-review=9301682',timeout=15) as response:
   data=response.read(2000001);assert len(data)<=2000000
   r.update(status=response.status,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),headers={h:response.headers.get(h) for h in ['content-type','server','cf-cache-status','age','content-length']})
  r['matches_disk']=r['sha256']==expected
 except Exception as e:r['error']=str(e)
 r['elapsed_ms']=round((time.monotonic()-start)*1000,1);out['requests'].append(r)
pathlib.Path('/opt/vlr-api/docs/verification/release-closure/2026-09-27/public-smoke.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
