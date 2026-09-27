"""Review-only staging harness; never install as production entry point."""
import asyncio,json,os,pathlib,time
B=pathlib.Path('/tmp/vlr-gates-9301682'); MODE=os.environ.get('GATE_MODE','cold')
os.environ.update(VLR_REDIS_URL='unix:///tmp/vlr-gates-9301682/redis/redis.sock?db='+('0' if MODE=='cold' else '1'),VLR_DATABASE_URL='postgresql+asyncpg://builder@/cold?host=/tmp/vlr-gates-9301682/pg/socket&port=55439',VLR_ENABLE_SCHEDULER='false',VLR_MAX_RETRIES='1',VLR_MIN_REQUEST_INTERVAL='2')
import httpx,uvicorn
from app.main import app
from app.core import http as H,db
class BoundedOrigin(httpx.AsyncBaseTransport):
 def __init__(self):self.inner=httpx.AsyncHTTPTransport();self.count=0;self.last=0;self.stopped=False
 async def handle_async_request(self,request):
  path=request.url.path
  allowed=request.url.host in ['www.vlr.gg','vlr.gg'] and any(path==p or path.startswith(p+'/') for p in ['/753445','/team/8877','/player/3799'])
  if self.stopped or not allowed or self.count>=6 or (B/'network-off').exists():raise httpx.ConnectError('Staging source budget closed',request=request)
  await asyncio.sleep(max(0,2-(time.monotonic()-self.last)));self.count+=1;self.last=time.monotonic();start=time.monotonic();row={'sequence':self.count,'path':path,'failure':'cancelled','stop':True}
  try:
   response=await self.inner.handle_async_request(request)
   await response.aread()
   if response.status_code==429 or 'retry-after' in response.headers or response.status_code>=400:self.stopped=True
   row={'sequence':self.count,'path':path,'status':response.status_code,'elapsed_ms':round((time.monotonic()-start)*1000,1),'stop':self.stopped}
  except Exception as e:
   self.stopped=True;row={'sequence':self.count,'path':path,'failure':type(e).__name__,'stop':True};raise
  finally:
   with (B/'origin.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
  return response
 async def aclose(self):await self.inner.aclose()
async def fixture(request):
 if request.url.path=='/9900':await asyncio.sleep(120)
 else:await asyncio.sleep(12)
 return httpx.Response(200,text=pathlib.Path('/home/builder/vlr-release-review-9301682/tests/fixtures/match_detail_completed.html').read_text())
if MODE=='fixture':
 @app.middleware('http')
 async def beyond_backend(request,call_next):
  if request.url.path=='/api/v1/match/9901':
   # Deliberately bypass the backend route only in this isolated harness:
   # verify Next's independent 90-second deadline against a hung HTTP service.
   await asyncio.sleep(120)
  return await call_next(request)
async def main():
 await db.init_db();client=H.get_client();await client._client.aclose()
 transport=BoundedOrigin() if MODE=='cold' else httpx.MockTransport(fixture)
 client._client=httpx.AsyncClient(base_url=client._settings.base_url,headers={'User-Agent':client._settings.user_agent},timeout=20,follow_redirects=True,max_redirects=1,transport=transport)
 await uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8110 if MODE=='cold' else 8111,lifespan='off',log_level='warning')).serve()
asyncio.run(main())
